"""Verify NO-FAKE-ZERO and NOT_EVALUATED-≠-REJECTED rules."""
import json
import pathlib

from zangetsu.dashboard.data_sources.batch_artifacts import load_batch_from_folder
from zangetsu.dashboard.view_models.overview import build_overview
from zangetsu.dashboard.view_models.arenas import build_a2
from zangetsu.dashboard.view_models.survivors import build_survivors


def test_no_data_distinct_from_zero(tmp_path):
    # No fixture written → folder empty → state must be NO_DATA, not zero
    bv = load_batch_from_folder(tmp_path)
    ov = build_overview(bv)
    assert ov.state == 'NO_DATA'
    assert ov.passed is None  # explicit None, not 0
    assert ov.rejected is None


def test_not_evaluated_separate_from_rejected_in_a2(tmp_path):
    folder = tmp_path / 'b'
    out = folder / 'shadow_outputs'; out.mkdir(parents=True)
    (out / 'shadow_batch_results.jsonl').write_text(
        '\n'.join([
            json.dumps({'candidate_id': 'a', 'axis_id': 'C', 'symbol': 'BTC',
                        'timeframe': '15m', 'intended_side_mode': 'LONG',
                        'alpha_hash': 'h', 'status': 'NOT_EVALUATED',
                        'reject_reason': None, 'blocker_reason': 'INVALID_CANDIDATE',
                        'gross_bps': 0.0, 'cost_bps': 0.0, 'net_bps': 0.0,
                        'trade_count': 0, 'long_trade_count': 0,
                        'short_trade_count': 0, 'a1_pass': None, 'a2_pass': None}),
            json.dumps({'candidate_id': 'b', 'axis_id': 'C', 'symbol': 'BTC',
                        'timeframe': '15m', 'intended_side_mode': 'LONG',
                        'alpha_hash': 'h', 'status': 'REJECTED',
                        'reject_reason': 'too_few_trades', 'blocker_reason': None,
                        'gross_bps': 5.0, 'cost_bps': 14.5, 'net_bps': -9.5,
                        'trade_count': 5, 'long_trade_count': 5,
                        'short_trade_count': 0, 'a1_pass': True, 'a2_pass': False}),
        ]) + '\n'
    )
    (out / 'survivor_report.csv').write_text('candidate_id\n')
    (out / 'near_survivor_report.csv').write_text('candidate_id,net_bps\n')
    bv = load_batch_from_folder(folder)
    a2 = build_a2(bv)
    # Assert NOT_EVALUATED and REJECTED are tracked in separate fields with
    # independent counts derived from the status column. This proves the
    # view-model never collapses one into the other regardless of equal counts.
    assert a2.n_not_evaluated == 1
    assert a2.n_rejected == 1
    assert a2.n_passed == 0
    assert a2.n_received == 2  # not_eval + rejected sum


def test_not_evaluated_not_in_survivors(tmp_path):
    folder = tmp_path / 'c'
    out = folder / 'shadow_outputs'; out.mkdir(parents=True)
    (out / 'shadow_batch_results.jsonl').write_text(
        json.dumps({'candidate_id': 'x', 'axis_id': 'C', 'symbol': 'BTC',
                    'timeframe': '15m', 'intended_side_mode': 'LONG',
                    'alpha_hash': 'h', 'status': 'NOT_EVALUATED',
                    'reject_reason': None, 'blocker_reason': 'INVALID_CANDIDATE',
                    'gross_bps': 0.0, 'cost_bps': 0.0, 'net_bps': 0.0,
                    'trade_count': 0, 'long_trade_count': 0,
                    'short_trade_count': 0, 'a1_pass': None, 'a2_pass': None}) + '\n'
    )
    (out / 'survivor_report.csv').write_text('candidate_id\n')
    (out / 'near_survivor_report.csv').write_text('candidate_id,net_bps\n')
    bv = load_batch_from_folder(folder)
    view = build_survivors(bv)
    surv_ids = set(view.survivors['candidate_id'].tolist()) if view.survivors is not None and not view.survivors.empty else set()
    near_ids = set(view.near_survivors['candidate_id'].tolist()) if view.near_survivors is not None and not view.near_survivors.empty else set()
    assert 'x' not in surv_ids
    assert 'x' not in near_ids
