import pathlib
import json
import pandas as pd
import pytest

from zangetsu.dashboard.data_sources.batch_artifacts import (
    BatchView, load_batch_from_folder,
)
from zangetsu.dashboard.view_models.overview import build_overview
from zangetsu.dashboard.view_models.arenas import build_a1, build_a2, build_a3
from zangetsu.dashboard.view_models.candidates import (
    apply_filters, candidates_dataframe,
)
from zangetsu.dashboard.view_models.survivors import build_survivors
from zangetsu.dashboard.view_models.feedback import build_feedback
from zangetsu.dashboard.view_models.health import build_health


def _make_fixture(tmp_path: pathlib.Path) -> pathlib.Path:
    folder = tmp_path / '20260430-test'
    out = folder / 'shadow_outputs'
    out.mkdir(parents=True)
    # manifest
    (out / 'candidate_manifest.jsonl').write_text(
        '\n'.join([
            json.dumps({'candidate_id': 'c1', 'axis_id': 'C', 'symbol': 'BTCUSDT',
                        'timeframe': '15m', 'intended_side_mode': 'LONG',
                        'alpha_hash': 'h1', 'grammar_family': 'axis_C',
                        'primitive_family': 'add', 'formula': 'add(close,open)'}),
            json.dumps({'candidate_id': 'c2', 'axis_id': 'C', 'symbol': 'BTCUSDT',
                        'timeframe': '15m', 'intended_side_mode': 'SHORT',
                        'alpha_hash': 'h2', 'grammar_family': 'axis_C',
                        'primitive_family': 'sub', 'formula': 'sub(close,open)'}),
        ]) + '\n'
    )
    # results
    (out / 'shadow_batch_results.jsonl').write_text(
        '\n'.join([
            json.dumps({'candidate_id': 'c1', 'axis_id': 'C', 'symbol': 'BTCUSDT',
                        'timeframe': '15m', 'intended_side_mode': 'LONG',
                        'alpha_hash': 'h1', 'status': 'PASSED', 'reject_reason': None,
                        'blocker_reason': None, 'gross_bps': 30.0, 'cost_bps': 14.5,
                        'net_bps': 15.5, 'trade_count': 30, 'long_trade_count': 30,
                        'short_trade_count': 0, 'a1_pass': True, 'a2_pass': True}),
            json.dumps({'candidate_id': 'c2', 'axis_id': 'C', 'symbol': 'BTCUSDT',
                        'timeframe': '15m', 'intended_side_mode': 'SHORT',
                        'alpha_hash': 'h2', 'status': 'REJECTED',
                        'reject_reason': 'no_trades_generated', 'blocker_reason': None,
                        'gross_bps': 0.0, 'cost_bps': 0.0, 'net_bps': 0.0,
                        'trade_count': 0, 'long_trade_count': 0,
                        'short_trade_count': 0, 'a1_pass': False, 'a2_pass': False}),
        ]) + '\n'
    )
    (out / 'survivor_report.csv').write_text('candidate_id,axis_id\nc1,C\n')
    (out / 'near_survivor_report.csv').write_text('candidate_id,axis_id,net_bps\nc2,C,-0.5\n')
    (out / 'reject_reason_summary.json').write_text(json.dumps({
        'overall': {'rejected_total': 1,
                    'rejected_by_reason': {'no_trades_generated': 1},
                    'unknown_reject_count': 0, 'not_evaluated_total': 0,
                    'error_total': 0, 'passed_total': 1},
    }))
    (out / 'feedback_weights.json').write_text(json.dumps({
        'overall': {'status': 'OK',
                    'weights': {'no_trades_generated': 1.0},
                    'reason': None}
    }))
    (out / 'next_batch_weights.json').write_text(json.dumps({
        'overall': {'status': 'OK', 'rejected_total': 1,
                    'recommended_actions': [{'reason': 'no_trades_generated',
                                             'failure_mode': 'NO_TRADES_GENERATED',
                                             'action': 'increase_density',
                                             'grammar_weight_delta': -0.1,
                                             'share': 1.0}]}
    }))
    (out / 'long_short_summary.csv').write_text('axis_id,intended_side_mode,n_candidates\nC,LONG,1\nC,SHORT,1\n')
    (out / 'formula_collision_report.csv').write_text(
        'axis_id,collisions_dropped,unsupported_operator_count,unique_formulas_kept\nC,0,0,2\n')
    (out / 'axis_scoreboard.csv').write_text('axis_id,total\nC,98.0\n')
    (out / 'run_summary.json').write_text(json.dumps({
        'a2_min_trades': 25, 'axes': ['C'],
        'candidates_per_axis': {'C': 2}, 'candidates_total': 2,
        'evaluation_seconds': 1.0, 'generation_id': 'test',
        'overall_feedback_status': 'OK',
        'overall_reject_summary': {'passed_total': 1, 'rejected_total': 1,
                                   'rejected_by_reason': {'no_trades_generated': 1},
                                   'unknown_reject_count': 0,
                                   'not_evaluated_total': 0, 'error_total': 0},
        'symbols': ['BTCUSDT'], 'timeframe': '15m',
        'unique_formulas_per_axis': {'C': 2},
    }))
    return folder


def test_build_overview(tmp_path):
    bv = load_batch_from_folder(_make_fixture(tmp_path))
    ov = build_overview(bv)
    assert ov.state == 'OK'
    assert ov.passed == 1
    assert ov.rejected == 1
    assert ov.unknown_reject == 0
    assert ov.a2_min_trades == 25


def test_build_a1_a2_a3(tmp_path):
    bv = load_batch_from_folder(_make_fixture(tmp_path))
    a1 = build_a1(bv)
    a2 = build_a2(bv)
    a3 = build_a3(bv)
    assert a1.state == 'OK'
    assert a2.state == 'OK'
    assert a2.n_passed == 1
    assert a2.n_rejected == 1
    assert a2.n_not_evaluated == 0
    # NOT_EVALUATED is distinct from REJECTED
    assert a2.n_not_evaluated != a2.n_rejected or a2.n_not_evaluated == 0
    assert a3.state == 'NOT_AVAILABLE'


def test_candidate_filter(tmp_path):
    bv = load_batch_from_folder(_make_fixture(tmp_path))
    df = candidates_dataframe(bv)
    out = apply_filters(df, status='PASSED')
    assert len(out) == 1
    assert out.iloc[0]['candidate_id'] == 'c1'


def test_survivors_distinct_from_near(tmp_path):
    bv = load_batch_from_folder(_make_fixture(tmp_path))
    view = build_survivors(bv)
    assert view.state == 'OK'
    surv_ids = set(view.survivors['candidate_id'].tolist()) if view.survivors is not None else set()
    near_ids = set(view.near_survivors['candidate_id'].tolist()) if view.near_survivors is not None else set()
    assert not (surv_ids & near_ids), 'survivors and near-survivors must not overlap'


def test_feedback_loaded(tmp_path):
    bv = load_batch_from_folder(_make_fixture(tmp_path))
    fv = build_feedback(bv)
    assert fv.state == 'OK'
    assert fv.feedback_weights['overall']['status'] == 'OK'
    assert fv.next_batch_weights['overall']['recommended_actions']


def test_health_per_source(tmp_path):
    bv = load_batch_from_folder(_make_fixture(tmp_path))
    rows = build_health(bv)
    assert rows
    keys = {r.source_key for r in rows}
    for required in ('candidate_manifest', 'shadow_batch_results',
                     'feedback_weights', 'next_batch_weights'):
        assert required in keys
