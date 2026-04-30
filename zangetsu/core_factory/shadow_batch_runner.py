"""0-9AB shadow batch runner.

Generates candidates for axes H/C/D, evaluates them through the shadow
Economic Arena adapter, writes all required machine outputs to the
evidence-folder shadow_outputs/ directory.

CLI:
  python -m zangetsu.core_factory.shadow_batch_runner \\
    --mode shadow \\
    --generation-id 0-9ab-shadow-v1 \\
    --candidate-count-per-axis 128 \\
    --axes H,C,D \\
    --symbols BTCUSDT,ETHUSDT,SOLUSDT \\
    --timeframe 15m \\
    --output docs/recovery/20260430-0-9ab-core-factory-multi-axis-shadow-tournament/shadow_outputs/
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
from typing import Iterable

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
from .economic_arena_adapter import EvaluationResult, evaluate_candidate
from .io import write_csv, write_json, write_jsonl
from .long_short_summary import aggregate_long_short
from .rejection_feedback import (
    feedback_weights_from_summary,
    summarize_reject_reasons,
)
from .axis_scoreboard import rank_axes
from .survivor_bank import is_near_survivor, is_survivor


def _ast_for_formula(formula_text: str, manifest_lookup: dict[str, dict]) -> tuple | None:
    """Re-parse not needed; pass AST through manifest in-memory cache instead."""
    return None


def run(
    *,
    generation_id: str,
    candidate_count_per_axis: int,
    axes: tuple[str, ...],
    symbols: tuple[str, ...],
    timeframe: str,
    output_dir: pathlib.Path,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)

    # Plan unique formulas per axis: candidate_count / (n_symbols * 2 side modes)
    side_modes = ('LONG', 'SHORT')
    formulas_per_axis = max(
        UNIQUE_FORMULA_TARGET_PER_AXIS,
        (candidate_count_per_axis + len(symbols) * len(side_modes) - 1)
        // (len(symbols) * len(side_modes)),
    )

    all_candidates: list[CandidateRecord] = []
    formula_to_ast: dict[str, tuple] = {}
    formula_collisions: Counter[str] = Counter()
    unsupported_op_counter: Counter[str] = Counter()

    for axis_id in axes:
        get_axis(axis_id)  # raises if unknown
        seen_hashes: set[str] = set()
        formulas = []
        for spec in generate_formulas(axis_id, formulas_per_axis, seed=hash(axis_id) & 0xFFFFFFFF):
            if spec.primitive_family == 'UNSUPPORTED':
                unsupported_op_counter[axis_id] += 1
                continue
            if spec.alpha_hash in seen_hashes:
                formula_collisions[axis_id] += 1
                continue
            seen_hashes.add(spec.alpha_hash)
            formulas.append(spec)
            formula_to_ast[spec.alpha_hash] = spec.ast
        cands = list(expand_formulas_to_candidates(
            formulas,
            generation_id=generation_id,
            symbols=symbols,
            timeframe=timeframe,
            side_modes=side_modes,
        ))
        all_candidates.extend(cands)

    # Manifest
    manifest_path = output_dir / 'candidate_manifest.jsonl'
    n_manifest = write_manifest_jsonl(all_candidates, manifest_path)

    # Evaluate each candidate
    result_rows: list[dict] = []
    t0 = time.time()
    for i, c in enumerate(all_candidates):
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
            }
        else:
            r = evaluate_candidate(
                candidate_id=c.candidate_id,
                formula_ast=ast,
                symbol=c.symbol,
                timeframe=c.timeframe,
                axis_id=c.axis_id,
                intended_side_mode=c.intended_side_mode,
            )
            row = {
                'candidate_id': c.candidate_id, 'axis_id': c.axis_id,
                'alpha_hash': c.alpha_hash, 'symbol': c.symbol,
                'timeframe': c.timeframe, 'intended_side_mode': c.intended_side_mode,
                'status': r.status, 'reject_reason': r.reject_reason,
                'blocker_reason': r.blocker_reason,
                'gross_bps': r.gross_bps, 'cost_bps': r.cost_bps,
                'net_bps': r.net_bps,
                'trade_count': r.trade_count,
                'long_trade_count': r.long_trade_count,
                'short_trade_count': r.short_trade_count,
                'a1_pass': r.a1_pass, 'a2_pass': r.a2_pass,
            }
        result_rows.append(row)
    t_eval = time.time() - t0

    # Per-axis aggregates for scoreboard
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
        # Per-axis feedback summary
        sub_summary = summarize_reject_reasons(axis_rows)
        sub_feedback = feedback_weights_from_summary(sub_summary)
        per_axis[axis_id] = {
            'axis_id': axis_id,
            'n_candidates': n, 'n_passed': n_passed, 'n_rejected': n_rejected,
            'n_not_evaluated': n_not_eval, 'n_error': n_error, 'n_evaluated': n_eval,
            'n_unknown_reject': n_unknown, 'n_near_survivors': n_near,
            'realized_long_trade_count': n_long_realized,
            'realized_short_trade_count': n_short_realized,
            'avg_net_bps': avg_net,
            'unique_formulas': unique_formulas,
            'target_candidates': candidate_count_per_axis,
            'target_unique_formulas': UNIQUE_FORMULA_TARGET_PER_AXIS,
            'feedback_status': sub_feedback['status'],
            'formula_collisions': int(formula_collisions.get(axis_id, 0)),
            'unsupported_operator_count': int(unsupported_op_counter.get(axis_id, 0)),
        }

    # Write shadow_batch_results.jsonl
    write_jsonl(result_rows, output_dir / 'shadow_batch_results.jsonl')

    # Write reject_reason_summary.json (overall + per-axis)
    overall_summary = summarize_reject_reasons(result_rows)
    overall_feedback = feedback_weights_from_summary(overall_summary)
    write_json({
        'overall': overall_summary,
        'per_axis': {a: summarize_reject_reasons([r for r in result_rows if r['axis_id'] == a])
                     for a in axes},
    }, output_dir / 'reject_reason_summary.json')

    # Write feedback_weights.json
    write_json({
        'overall': overall_feedback,
        'per_axis': {a: feedback_weights_from_summary(
            summarize_reject_reasons([r for r in result_rows if r['axis_id'] == a]))
                     for a in axes},
    }, output_dir / 'feedback_weights.json')

    # Long/short summary CSV
    ls_rows = aggregate_long_short(result_rows)
    write_csv(ls_rows, output_dir / 'long_short_summary.csv', list(ls_rows[0].keys()) if ls_rows else
              ['axis_id','intended_side_mode','n_candidates','n_passed','n_rejected',
               'n_not_evaluated','n_error','realized_long_trade_count','realized_short_trade_count',
               'trade_count_sum','avg_gross_bps','avg_net_bps'])

    # Near-survivor CSV (status==REJECTED and within net-bps band)
    near_rows = [r for r in result_rows if is_near_survivor(r)]
    near_fields = ['candidate_id','axis_id','alpha_hash','symbol','timeframe',
                   'intended_side_mode','net_bps','gross_bps','trade_count','reject_reason']
    write_csv(near_rows, output_dir / 'near_survivor_report.csv',
              near_fields if not near_rows else list(near_rows[0].keys()))

    # Formula-collision CSV
    coll_rows = [
        {'axis_id': a, 'collisions_dropped': int(formula_collisions.get(a, 0)),
         'unsupported_operator_count': int(unsupported_op_counter.get(a, 0)),
         'unique_formulas_kept': per_axis.get(a, {}).get('unique_formulas', 0)}
        for a in axes
    ]
    write_csv(coll_rows, output_dir / 'formula_collision_report.csv',
              ['axis_id','collisions_dropped','unsupported_operator_count','unique_formulas_kept'])

    # Axis scoreboard CSV
    scored = rank_axes(per_axis.values())
    sb_fields = list(scored[0].keys()) if scored else \
        ['axis_id','rank','total','candidate_generation','formula_diversity',
         'long_short_balance','economic_result_quality','cost_robustness',
         'reject_reason_quality','feedback_usability']
    write_csv(scored, output_dir / 'axis_scoreboard.csv', sb_fields)

    summary = {
        'generation_id': generation_id,
        'axes': list(axes),
        'symbols': list(symbols),
        'timeframe': timeframe,
        'a2_min_trades': A2_MIN_TRADES,
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
    p.add_argument('--output', required=True)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.mode != 'shadow':
        print(f'ERROR: only --mode shadow is supported (got {args.mode!r})', file=sys.stderr)
        return 2
    axes = tuple(a.strip() for a in args.axes.split(',') if a.strip())
    symbols = tuple(s.strip() for s in args.symbols.split(',') if s.strip())
    output_dir = pathlib.Path(args.output)
    summary = run(
        generation_id=args.generation_id,
        candidate_count_per_axis=args.candidate_count_per_axis,
        axes=axes,
        symbols=symbols,
        timeframe=args.timeframe,
        output_dir=output_dir,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
