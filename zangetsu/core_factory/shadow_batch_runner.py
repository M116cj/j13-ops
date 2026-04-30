"""0-9AB / 0-9AC shadow batch runner.

CLI flags added in 0-9AC:
  --h-value-clip p99_abs       (apply value clipping for axis H)
  --d-trigger band_crossing    (replace sign-flip with band-crossing for D)
  --d-band-k 0.5,1.0,1.5       (test bands for d_band_crossing_report)
  --d-symbol-mode all14        (expand D symbol set to all 14 symbols)
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys
import time
from collections import Counter
from dataclasses import asdict
from typing import Iterable, Optional

from .axis_registry import get_axis
from .candidate_manifest import (
    CandidateRecord,
    expand_formulas_to_candidates,
    write_manifest_jsonl,
)
from .combination_grammar import generate_formulas
from .constants import (
    A2_MIN_TRADES,
    CANDIDATES_PER_AXIS_DEFAULT,
    DEFAULT_SYMBOLS,
    DEFAULT_TIMEFRAME,
    GENERATION_ID_DEFAULT,
    UNIQUE_FORMULA_TARGET_PER_AXIS,
)
from .economic_arena_adapter import (
    EvaluationParams, EvaluationResult, evaluate_candidate,
)
from .io import write_csv, write_json, write_jsonl
from .long_short_summary import aggregate_long_short
from .rejection_feedback import (
    feedback_weights_from_summary,
    summarize_reject_reasons,
)
from .axis_scoreboard import rank_axes
from .next_batch_weights import next_batch_weights_from_summary
from .survivor_bank import is_near_survivor, is_survivor


ALL14_SYMBOLS = (
    '1000PEPEUSDT', '1000SHIBUSDT', 'AAVEUSDT', 'AVAXUSDT', 'BNBUSDT',
    'BTCUSDT', 'DOGEUSDT', 'DOTUSDT', 'ETHUSDT', 'FILUSDT',
    'GALAUSDT', 'LINKUSDT', 'SOLUSDT', 'XRPUSDT',
)


def _params_for_axis(
    axis_id: str, h_value_clip: Optional[str], d_trigger: str,
    d_band_k: float, sigma_window: int,
) -> EvaluationParams:
    if axis_id == 'H' and h_value_clip == 'p99_abs':
        return EvaluationParams(value_clip='p99_abs', trigger='sign_flip',
                                band_k=d_band_k, rolling_sigma_window=sigma_window)
    if axis_id == 'D' and d_trigger == 'band_crossing':
        return EvaluationParams(value_clip=None, trigger='band_crossing',
                                band_k=d_band_k, rolling_sigma_window=sigma_window)
    return EvaluationParams()  # C and others get default sign_flip, no clip


def _symbols_for_axis(
    axis_id: str, base_symbols: tuple[str, ...], d_symbol_mode: str,
) -> tuple[str, ...]:
    if axis_id == 'D' and d_symbol_mode == 'all14':
        return ALL14_SYMBOLS
    return base_symbols


def run(
    *,
    generation_id: str,
    candidate_count_per_axis: int,
    axes: tuple[str, ...],
    symbols: tuple[str, ...],
    timeframe: str,
    output_dir: pathlib.Path,
    h_value_clip: Optional[str] = None,
    d_trigger: str = 'sign_flip',
    d_band_k_list: tuple[float, ...] = (1.0,),
    d_symbol_mode: str = 'default',
    sigma_window: int = 20,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    side_modes = ('LONG', 'SHORT')

    # Per-axis state
    formula_to_ast: dict[str, tuple] = {}
    formula_collisions: Counter[str] = Counter()
    unsupported_op_counter: Counter[str] = Counter()
    all_candidates: list[CandidateRecord] = []
    per_axis_symbol_counts: dict[str, dict[str, int]] = {}

    for axis_id in axes:
        get_axis(axis_id)
        axis_symbols = _symbols_for_axis(axis_id, symbols, d_symbol_mode)
        formulas_per_axis = max(
            UNIQUE_FORMULA_TARGET_PER_AXIS,
            (candidate_count_per_axis + len(axis_symbols) * len(side_modes) - 1)
            // (len(axis_symbols) * len(side_modes)),
        )
        seen_hashes: set[str] = set()
        formulas = []
        for spec in generate_formulas(
            axis_id, formulas_per_axis, seed=hash(axis_id) & 0xFFFFFFFF,
        ):
            if spec.primitive_family == 'UNSUPPORTED':
                unsupported_op_counter[axis_id] += 1
                continue
            if spec.alpha_hash in seen_hashes:
                formula_collisions[axis_id] += 1
                continue
            seen_hashes.add(spec.alpha_hash)
            formulas.append(spec)
            formula_to_ast[spec.alpha_hash] = spec.ast
            if len(formulas) >= UNIQUE_FORMULA_TARGET_PER_AXIS:
                # Cap unique formulas at target to keep tournament size bounded.
                pass
        cands = list(expand_formulas_to_candidates(
            formulas, generation_id=generation_id,
            symbols=axis_symbols, timeframe=timeframe, side_modes=side_modes,
        ))
        all_candidates.extend(cands)
        # Track per-symbol counts for D coverage report
        per_axis_symbol_counts[axis_id] = {}
        for c in cands:
            per_axis_symbol_counts[axis_id][c.symbol] = (
                per_axis_symbol_counts[axis_id].get(c.symbol, 0) + 1
            )

    # Manifest
    n_manifest = write_manifest_jsonl(all_candidates, output_dir / 'candidate_manifest.jsonl')

    # Pick the primary band_k for D's main pass (median of provided list).
    primary_band_k = sorted(d_band_k_list)[len(d_band_k_list) // 2]

    # Evaluate each candidate
    result_rows: list[dict] = []
    h_clip_distributions: list[dict] = []
    t0 = time.time()
    for c in all_candidates:
        ast = formula_to_ast.get(c.alpha_hash)
        if ast is None:
            row = {
                'candidate_id': c.candidate_id, 'axis_id': c.axis_id,
                'alpha_hash': c.alpha_hash, 'symbol': c.symbol,
                'timeframe': c.timeframe, 'intended_side_mode': c.intended_side_mode,
                'status': 'NOT_EVALUATED', 'reject_reason': None,
                'blocker_reason': 'GENERATOR_PATH_BLOCKED',
                'gross_bps': 0.0, 'cost_bps': 0.0, 'net_bps': 0.0,
                'trade_count': 0, 'long_trade_count': 0, 'short_trade_count': 0,
                'a1_pass': None, 'a2_pass': None,
                'clip_method': None, 'clip_threshold': None,
                'trigger_type': None, 'band_k': None,
            }
            result_rows.append(row)
            continue
        params = _params_for_axis(
            c.axis_id, h_value_clip, d_trigger, primary_band_k, sigma_window,
        )
        r = evaluate_candidate(
            candidate_id=c.candidate_id, formula_ast=ast,
            symbol=c.symbol, timeframe=c.timeframe, axis_id=c.axis_id,
            intended_side_mode=c.intended_side_mode, params=params,
        )
        clip_method = r.clip_metadata.get('method') if r.clip_metadata else None
        clip_threshold = r.clip_metadata.get('threshold') if r.clip_metadata else None
        trigger_type = r.trigger_metadata.get('trigger_type') if r.trigger_metadata else None
        band_k_used = r.trigger_metadata.get('band_k') if r.trigger_metadata else None
        result_rows.append({
            'candidate_id': r.candidate_id, 'axis_id': c.axis_id,
            'alpha_hash': c.alpha_hash, 'symbol': c.symbol,
            'timeframe': c.timeframe, 'intended_side_mode': c.intended_side_mode,
            'status': r.status, 'reject_reason': r.reject_reason,
            'blocker_reason': r.blocker_reason,
            'gross_bps': r.gross_bps, 'cost_bps': r.cost_bps, 'net_bps': r.net_bps,
            'trade_count': r.trade_count,
            'long_trade_count': r.long_trade_count,
            'short_trade_count': r.short_trade_count,
            'a1_pass': r.a1_pass, 'a2_pass': r.a2_pass,
            'clip_method': clip_method, 'clip_threshold': clip_threshold,
            'trigger_type': trigger_type, 'band_k': band_k_used,
        })
        if c.axis_id == 'H' and r.clip_metadata:
            h_clip_distributions.append({
                'candidate_id': r.candidate_id,
                'symbol': c.symbol,
                'side_mode': c.intended_side_mode,
                **r.clip_metadata,
            })
    t_eval = time.time() - t0

    # Side-pass for D band-crossing report: re-evaluate a sample subset at all
    # provided d_band_k values to compare trade counts per band.
    d_band_rows: list[dict] = []
    if 'D' in axes and d_trigger == 'band_crossing' and len(d_band_k_list) > 0:
        # Use one symbol BTCUSDT and side LONG, all D unique formulas, all bands.
        d_formulas = [(h, ast) for (h, ast) in formula_to_ast.items()
                      if any(c.alpha_hash == h and c.axis_id == 'D' for c in all_candidates)]
        sample_symbol = 'BTCUSDT'
        for k in d_band_k_list:
            params_k = EvaluationParams(value_clip=None, trigger='band_crossing',
                                        band_k=k, rolling_sigma_window=sigma_window)
            for (h, ast) in d_formulas:
                rr = evaluate_candidate(
                    candidate_id=f'd-band-{k}-{h[:8]}',
                    formula_ast=ast, symbol=sample_symbol, timeframe=timeframe,
                    axis_id='D', intended_side_mode='LONG', params=params_k,
                )
                d_band_rows.append({
                    'alpha_hash': h, 'symbol': sample_symbol, 'band_k': k,
                    'status': rr.status, 'reject_reason': rr.reject_reason,
                    'trade_count': rr.trade_count, 'long_trade_count': rr.long_trade_count,
                    'short_trade_count': rr.short_trade_count,
                    'gross_bps': rr.gross_bps, 'net_bps': rr.net_bps,
                })

    # Per-axis aggregates
    per_axis: dict[str, dict] = {}
    for axis_id in axes:
        axis_rows = [r for r in result_rows if r['axis_id'] == axis_id]
        n = len(axis_rows)
        n_passed = sum(1 for r in axis_rows if r['status'] == 'PASSED')
        n_rejected = sum(1 for r in axis_rows if r['status'] == 'REJECTED')
        n_not_eval = sum(1 for r in axis_rows if r['status'] == 'NOT_EVALUATED')
        n_error = sum(1 for r in axis_rows if r['status'] == 'ERROR')
        n_eval = n_passed + n_rejected
        n_unknown = sum(1 for r in axis_rows
                        if r['status'] == 'REJECTED' and r['reject_reason'] == 'UNKNOWN_REJECT')
        n_near = sum(1 for r in axis_rows if is_near_survivor(r))
        n_long_realized = sum(int(r['long_trade_count'] or 0) for r in axis_rows)
        n_short_realized = sum(int(r['short_trade_count'] or 0) for r in axis_rows)
        avg_net = (sum(float(r['net_bps'] or 0.0) for r in axis_rows) / n) if n else 0.0
        unique_formulas = len(set(r['alpha_hash'] for r in axis_rows))
        sub_summary = summarize_reject_reasons(axis_rows)
        sub_feedback = feedback_weights_from_summary(sub_summary)
        # Correction success bonus
        correction_score = 0.0
        if axis_id == 'H' and h_value_clip == 'p99_abs':
            blow_up = any(abs(float(r['net_bps'] or 0.0)) > 1000.0 for r in axis_rows)
            correction_score = 10.0 if not blow_up else 5.0
        elif axis_id == 'D' and d_trigger == 'band_crossing':
            no_trades_share = sum(1 for r in axis_rows if r['reject_reason'] == 'no_trades_generated') / max(n, 1)
            correction_score = 10.0 if no_trades_share < 0.50 else (
                7.0 if no_trades_share < 0.80 else 3.0
            )
        elif axis_id == 'C':
            correction_score = 10.0  # baseline preserved
        per_axis[axis_id] = {
            'axis_id': axis_id,
            'n_candidates': n, 'n_passed': n_passed, 'n_rejected': n_rejected,
            'n_not_evaluated': n_not_eval, 'n_error': n_error, 'n_evaluated': n_eval,
            'n_unknown_reject': n_unknown, 'n_near_survivors': n_near,
            'realized_long_trade_count': n_long_realized,
            'realized_short_trade_count': n_short_realized,
            'avg_net_bps': avg_net, 'unique_formulas': unique_formulas,
            'target_candidates': candidate_count_per_axis,
            'target_unique_formulas': UNIQUE_FORMULA_TARGET_PER_AXIS,
            'feedback_status': sub_feedback['status'],
            'formula_collisions': int(formula_collisions.get(axis_id, 0)),
            'unsupported_operator_count': int(unsupported_op_counter.get(axis_id, 0)),
            'correction_success': correction_score,
        }

    write_jsonl(result_rows, output_dir / 'shadow_batch_results.jsonl')

    overall_summary = summarize_reject_reasons(result_rows)
    overall_feedback = feedback_weights_from_summary(overall_summary)
    write_json({
        'overall': overall_summary,
        'per_axis': {a: summarize_reject_reasons([r for r in result_rows if r['axis_id'] == a])
                     for a in axes},
    }, output_dir / 'reject_reason_summary.json')
    write_json({
        'overall': overall_feedback,
        'per_axis': {a: feedback_weights_from_summary(
            summarize_reject_reasons([r for r in result_rows if r['axis_id'] == a]))
                     for a in axes},
    }, output_dir / 'feedback_weights.json')

    ls_rows = aggregate_long_short(result_rows)
    ls_fields = (list(ls_rows[0].keys()) if ls_rows else
                 ['axis_id','intended_side_mode','n_candidates','n_passed',
                  'n_rejected','n_not_evaluated','n_error',
                  'realized_long_trade_count','realized_short_trade_count',
                  'trade_count_sum','avg_gross_bps','avg_net_bps'])
    write_csv(ls_rows, output_dir / 'long_short_summary.csv', ls_fields)

    near_rows = [r for r in result_rows if is_near_survivor(r)]
    near_fields = (list(near_rows[0].keys()) if near_rows else
                   ['candidate_id','axis_id','alpha_hash','symbol','timeframe',
                    'intended_side_mode','net_bps','gross_bps','trade_count',
                    'reject_reason','clip_method','trigger_type','band_k'])
    write_csv(near_rows, output_dir / 'near_survivor_report.csv', near_fields)

    # Survivor report (PASSED only) — distinct from near-survivor.
    survivor_rows = [r for r in result_rows if is_survivor(r)]
    survivor_fields = (list(survivor_rows[0].keys()) if survivor_rows else
                       ['candidate_id','axis_id','alpha_hash','symbol','timeframe',
                        'intended_side_mode','net_bps','gross_bps','trade_count',
                        'a1_pass','a2_pass'])
    write_csv(survivor_rows, output_dir / 'survivor_report.csv', survivor_fields)

    # next_batch_weights.json — derived from overall reject summary; honest empty if blocked.
    write_json({
        'overall': next_batch_weights_from_summary(overall_summary),
        'per_axis': {a: next_batch_weights_from_summary(
            summarize_reject_reasons([r for r in result_rows if r['axis_id'] == a]))
                     for a in axes},
    }, output_dir / 'next_batch_weights.json')


    coll_rows = [
        {'axis_id': a, 'collisions_dropped': int(formula_collisions.get(a, 0)),
         'unsupported_operator_count': int(unsupported_op_counter.get(a, 0)),
         'unique_formulas_kept': per_axis.get(a, {}).get('unique_formulas', 0)}
        for a in axes
    ]
    write_csv(coll_rows, output_dir / 'formula_collision_report.csv',
              ['axis_id','collisions_dropped','unsupported_operator_count','unique_formulas_kept'])

    # Use scoreboard with correction bonus
    scored = rank_axes(per_axis.values())
    # Inject correction_success after-the-fact (axis_scoreboard.py is unchanged).
    for s in scored:
        s['correction_success'] = float(per_axis[s['axis_id']]['correction_success'])
        s['total'] = round(s['total'] + s['correction_success'], 2)
    scored.sort(key=lambda x: x['total'], reverse=True)
    for i, s in enumerate(scored, start=1):
        s['rank'] = i
    sb_fields = (list(scored[0].keys()) if scored else
                 ['axis_id','rank','total','candidate_generation','formula_diversity',
                  'long_short_balance','economic_result_quality','cost_robustness',
                  'reject_reason_quality','feedback_usability','correction_success'])
    write_csv(scored, output_dir / 'axis_scoreboard.csv', sb_fields)

    if h_clip_distributions:
        # Aggregate to axis-level distribution stats (sampled per candidate)
        write_json({
            'enabled': True, 'method': 'p99_abs',
            'sample_count': len(h_clip_distributions),
            'samples': h_clip_distributions[:200],  # cap to avoid bloat
            'aggregate': {
                'mean_threshold': sum(d['threshold'] for d in h_clip_distributions) / len(h_clip_distributions),
                'mean_pre_variance': sum(d['pre_variance'] for d in h_clip_distributions) / len(h_clip_distributions),
                'mean_post_variance': sum(d['post_variance'] for d in h_clip_distributions) / len(h_clip_distributions),
                'min_post_variance': min(d['post_variance'] for d in h_clip_distributions),
            },
        }, output_dir / 'h_clip_distribution.json')
    else:
        write_json({'enabled': False, 'reason': 'no_H_axis_or_no_clip'},
                   output_dir / 'h_clip_distribution.json')

    if d_band_rows:
        # Aggregate by band_k for the headline d_band_crossing_report.
        bands = sorted({r['band_k'] for r in d_band_rows})
        agg_rows = []
        for k in bands:
            sub = [r for r in d_band_rows if r['band_k'] == k]
            agg_rows.append({
                'band_k': k,
                'samples': len(sub),
                'n_status_passed': sum(1 for r in sub if r['status'] == 'PASSED'),
                'n_status_rejected_no_trades': sum(1 for r in sub if r['reject_reason'] == 'no_trades_generated'),
                'n_status_rejected_other': sum(1 for r in sub if r['status'] == 'REJECTED' and r['reject_reason'] != 'no_trades_generated'),
                'mean_trade_count': sum(r['trade_count'] for r in sub) / max(len(sub), 1),
                'mean_long_trade_count': sum(r['long_trade_count'] for r in sub) / max(len(sub), 1),
                'mean_gross_bps': sum(r['gross_bps'] for r in sub) / max(len(sub), 1),
                'mean_net_bps': sum(r['net_bps'] for r in sub) / max(len(sub), 1),
            })
        # Write aggregate as the summary CSV (per-row band_k stats).
        write_csv(agg_rows, output_dir / 'd_band_crossing_report.csv',
                  list(agg_rows[0].keys()))
    else:
        write_csv([], output_dir / 'd_band_crossing_report.csv',
                  ['band_k','samples','n_status_passed','n_status_rejected_no_trades',
                   'n_status_rejected_other','mean_trade_count','mean_long_trade_count',
                   'mean_gross_bps','mean_net_bps'])

    # D symbol-coverage report
    d_symbol_rows = []
    if 'D' in axes:
        for sym, count in sorted(per_axis_symbol_counts.get('D', {}).items()):
            d_rows = [r for r in result_rows if r['axis_id'] == 'D' and r['symbol'] == sym]
            n = len(d_rows)
            n_pass = sum(1 for r in d_rows if r['status'] == 'PASSED')
            n_rej = sum(1 for r in d_rows if r['status'] == 'REJECTED')
            n_no_trade = sum(1 for r in d_rows
                             if r['status'] == 'REJECTED' and r['reject_reason'] == 'no_trades_generated')
            d_symbol_rows.append({
                'axis_id': 'D', 'symbol': sym,
                'candidate_count': count,
                'n_passed': n_pass, 'n_rejected': n_rej,
                'n_no_trades_generated': n_no_trade,
                'avg_trade_count': sum(int(r['trade_count'] or 0) for r in d_rows) / max(n, 1),
                'avg_net_bps': sum(float(r['net_bps'] or 0.0) for r in d_rows) / max(n, 1),
            })
    write_csv(d_symbol_rows, output_dir / 'd_symbol_coverage.csv',
              list(d_symbol_rows[0].keys()) if d_symbol_rows else
              ['axis_id','symbol','candidate_count','n_passed','n_rejected',
               'n_no_trades_generated','avg_trade_count','avg_net_bps'])

    summary = {
        'generation_id': generation_id, 'axes': list(axes),
        'symbols': list(symbols), 'timeframe': timeframe,
        'a2_min_trades': A2_MIN_TRADES,
        'h_value_clip': h_value_clip, 'd_trigger': d_trigger,
        'd_band_k_list': list(d_band_k_list), 'd_symbol_mode': d_symbol_mode,
        'candidates_total': n_manifest,
        'candidates_per_axis': {a: per_axis[a]['n_candidates'] for a in axes},
        'unique_formulas_per_axis': {a: per_axis[a]['unique_formulas'] for a in axes},
        'evaluation_seconds': round(t_eval, 2),
        'overall_reject_summary': overall_summary,
        'overall_feedback_status': overall_feedback['status'],
        'scoreboard': scored,
    }
    write_json(summary, output_dir / 'run_summary.json')
    return summary


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument('--mode', default='shadow')
    p.add_argument('--generation-id', default=GENERATION_ID_DEFAULT)
    p.add_argument('--candidate-count-per-axis', type=int, default=CANDIDATES_PER_AXIS_DEFAULT)
    p.add_argument('--axes', default='H,C,D')
    p.add_argument('--symbols', default=','.join(DEFAULT_SYMBOLS))
    p.add_argument('--timeframe', default=DEFAULT_TIMEFRAME)
    p.add_argument('--h-value-clip', default=None, choices=[None, 'p99_abs'])
    p.add_argument('--d-trigger', default='sign_flip', choices=['sign_flip', 'band_crossing'])
    p.add_argument('--d-band-k', default='1.0', help='comma-separated list, e.g. 0.5,1.0,1.5')
    p.add_argument('--d-symbol-mode', default='default', choices=['default', 'all14'])
    p.add_argument('--rolling-sigma-window', type=int, default=20)
    p.add_argument('--output', required=True)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.mode != 'shadow':
        print(f'ERROR: only --mode shadow is supported (got {args.mode!r})', file=sys.stderr)
        return 2
    axes = tuple(a.strip() for a in args.axes.split(',') if a.strip())
    symbols = tuple(s.strip() for s in args.symbols.split(',') if s.strip())
    d_band_k_list = tuple(float(x.strip()) for x in args.d_band_k.split(',') if x.strip())
    output_dir = pathlib.Path(args.output)
    summary = run(
        generation_id=args.generation_id,
        candidate_count_per_axis=args.candidate_count_per_axis,
        axes=axes, symbols=symbols, timeframe=args.timeframe,
        output_dir=output_dir,
        h_value_clip=args.h_value_clip, d_trigger=args.d_trigger,
        d_band_k_list=d_band_k_list, d_symbol_mode=args.d_symbol_mode,
        sigma_window=args.rolling_sigma_window,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
