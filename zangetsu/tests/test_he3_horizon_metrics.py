"""Tests for HE3 horizon economic telemetry (per spec Phase 3).

Required tests (master order):
  1. test_horizon_metrics_present_in_batch
  2. test_selected_horizon_matches_metrics_key
  3. test_baseline_60_metrics_identical_to_pre_he3
  4. test_cost_model_unchanged
  5. test_validation_unchanged
  6. test_conservation_per_horizon
  7. test_no_unknown_reject_regression
  8. test_counter_inconsistency_zero
"""
from __future__ import annotations

import os
import math
import statistics
import tokenize
import pytest

from zangetsu.services import horizon_metrics as hm_mod
from zangetsu.services.horizon_metrics import (
    build_horizon_metrics,
    aggregate_horizon_metrics_across_batches,
)


# ---------------------------------------------------------------------------
# 1. horizon_metrics present in batch (helper builds dict)
# ---------------------------------------------------------------------------
def test_1_horizon_metrics_present_in_batch():
    out = build_horizon_metrics(
        selected_horizon=60,
        train_gross_pnl=[2.4, 2.5, 1.8, 3.0, 2.0],
        train_net_pnl=[-1.2, -1.0, -1.5, -0.5, -1.4],
        train_total_trades=[980, 1000, 950, 1050, 990],
        train_win_rate=[0.31, 0.32, 0.30, 0.33, 0.31],
        round_total_cost_bps=14.5,
        signal_density_per_bar=0.0070,
    )
    assert 60 in out
    metrics = out[60]
    assert metrics["alpha_count"] == 5
    assert metrics["trade_count_median"] == 990
    assert metrics["gross_pnl_median"] == 2.4
    assert metrics["net_pnl_median"] == -1.2
    assert metrics["win_rate_median"] == 0.31
    assert metrics["signal_density_per_bar"] == pytest.approx(0.0070)
    assert metrics["total_cost"] == pytest.approx(14.5 * 5)
    # cost_per_trade derivable
    assert metrics["cost_per_trade"] is not None and metrics["cost_per_trade"] > 0


# ---------------------------------------------------------------------------
# 2. selected_horizon matches metrics key
# ---------------------------------------------------------------------------
def test_2_selected_horizon_matches_metrics_key():
    for h in (60, 180, 240, 360):
        out = build_horizon_metrics(
            selected_horizon=h,
            train_gross_pnl=[1.0, 1.5],
            train_net_pnl=[0.5, 0.8],
            train_total_trades=[100, 150],
            train_win_rate=[0.4, 0.5],
            round_total_cost_bps=10.0,
            signal_density_per_bar=0.005,
        )
        assert list(out.keys()) == [h]
        assert out[h]["alpha_count"] == 2


# ---------------------------------------------------------------------------
# 3. baseline 60 metrics identical to pre-HE3 (numeric values match expectations)
# ---------------------------------------------------------------------------
def test_3_baseline_60_metrics_match_existing_aggregate_keys():
    """The HE3 helper builds horizon_metrics[60] from the same per-alpha lists
    that arena_pipeline.py uses for `train_gross_pnl_median` etc.
    Values must match exactly (no off-by-one, no transformation)."""
    gross = [2.0, 2.5, 1.5, 3.0]
    net = [-1.0, -0.5, -1.5, 0.0]
    trades = [900, 1000, 950, 1100]
    wr = [0.30, 0.35, 0.28, 0.32]
    out = build_horizon_metrics(
        selected_horizon=60,
        train_gross_pnl=gross, train_net_pnl=net,
        train_total_trades=trades, train_win_rate=wr,
        round_total_cost_bps=14.5,
        signal_density_per_bar=0.007,
    )
    m = out[60]
    # Values must match what arena_pipeline.py computes via _b1_median()
    assert m["gross_pnl_median"] == pytest.approx(statistics.median(gross))
    assert m["net_pnl_median"] == pytest.approx(statistics.median(net))
    assert m["trade_count_median"] == statistics.median(trades)
    assert m["win_rate_median"] == pytest.approx(statistics.median(wr))


# ---------------------------------------------------------------------------
# 4. cost model unchanged (tokenize-scan)
# ---------------------------------------------------------------------------
def test_4_cost_model_unchanged():
    forbidden = ["cost_bps", "cost_model", "fee_bps", "slippage_bps",
                 "round_total_cost_bps_modify", "FEE_BPS", "SLIPPAGE"]
    src_path = hm_mod.__file__
    toks = []
    with open(src_path, "rb") as f:
        for tok in tokenize.tokenize(f.readline):
            if tok.type in (tokenize.NAME, tokenize.NUMBER, tokenize.OP):
                toks.append(tok.string)
    for t in forbidden:
        assert t not in toks, f"{t!r} in code of {src_path}"


# ---------------------------------------------------------------------------
# 5. validation unchanged (tokenize-scan)
# ---------------------------------------------------------------------------
def test_5_validation_unchanged():
    forbidden = ["entry_rank_threshold", "exit_rank_threshold", "rank_window",
                 "VAL_MIN_TRADES", "validator_threshold", "validation_threshold"]
    src_path = hm_mod.__file__
    toks = []
    with open(src_path, "rb") as f:
        for tok in tokenize.tokenize(f.readline):
            if tok.type in (tokenize.NAME, tokenize.NUMBER, tokenize.OP):
                toks.append(tok.string)
    for t in forbidden:
        assert t not in toks, f"{t!r} in code of {src_path}"


# ---------------------------------------------------------------------------
# 6. conservation per horizon (entered = kept + skipped)
# ---------------------------------------------------------------------------
def test_6_conservation_per_horizon():
    # Baseline: skipped=0, kept=entered
    out = build_horizon_metrics(
        selected_horizon=60,
        train_gross_pnl=[1.0], train_net_pnl=[0.5], train_total_trades=[100],
        train_win_rate=[0.5], round_total_cost_bps=10.0,
        skipped_count_total=0, kept_count_total=100, entered_count_total=100,
    )
    m = out[60]
    assert m["entered_count_total"] == m["kept_count_total"] + m["skipped_count_total"]
    # TF4 active: skipped > 0
    out2 = build_horizon_metrics(
        selected_horizon=180,
        train_gross_pnl=[1.0], train_net_pnl=[0.5], train_total_trades=[60],
        train_win_rate=[0.5], round_total_cost_bps=10.0,
        skipped_count_total=900, kept_count_total=60, entered_count_total=960,
    )
    m2 = out2[180]
    assert m2["entered_count_total"] == m2["kept_count_total"] + m2["skipped_count_total"]


# ---------------------------------------------------------------------------
# 7. no unknown reject regression (helper does not touch reject paths)
# ---------------------------------------------------------------------------
def test_7_no_unknown_reject_regression():
    """horizon_metrics helper has no reject-path code; tokenize-scan confirms."""
    forbidden = ["UNKNOWN_REJECT", "unknown_reject", "reject_reason_distribution",
                 "increment_unknown", "unknown_count"]
    src_path = hm_mod.__file__
    toks = []
    with open(src_path, "rb") as f:
        for tok in tokenize.tokenize(f.readline):
            if tok.type in (tokenize.NAME, tokenize.NUMBER, tokenize.OP):
                toks.append(tok.string)
    for t in forbidden:
        assert t not in toks


# ---------------------------------------------------------------------------
# 8. counter inconsistency zero
# ---------------------------------------------------------------------------
def test_8_counter_inconsistency_zero():
    """Helper does not introduce any counter-mutation API."""
    forbidden = ["COUNTER_INCONSISTENCY", "counter_inconsistency",
                 "increment_passed_count", "set_pass_count", "modify_rejected_count"]
    src_path = hm_mod.__file__
    toks = []
    with open(src_path, "rb") as f:
        for tok in tokenize.tokenize(f.readline):
            if tok.type in (tokenize.NAME, tokenize.NUMBER, tokenize.OP):
                toks.append(tok.string)
    for t in forbidden:
        assert t not in toks


# ---------------------------------------------------------------------------
# Bonus tests: edge cases, aggregation, robustness
# ---------------------------------------------------------------------------
def test_9_empty_lists_safe():
    """Helper handles empty input lists gracefully."""
    out = build_horizon_metrics(
        selected_horizon=60,
        train_gross_pnl=[], train_net_pnl=[], train_total_trades=[],
        train_win_rate=[], round_total_cost_bps=14.5,
    )
    m = out[60]
    assert m["alpha_count"] == 0
    assert m["gross_pnl_median"] is None
    assert m["net_pnl_median"] is None
    assert m["trade_count_median"] is None


def test_10_invalid_horizon_returns_empty():
    """Garbage selected_horizon → empty dict (never raises)."""
    out = build_horizon_metrics(
        selected_horizon=None,  # type: ignore
        train_gross_pnl=[1.0], train_net_pnl=[0.5], train_total_trades=[100],
        train_win_rate=[0.5],
    )
    assert out == {}


def test_11_aggregate_across_batches():
    """Cross-batch aggregator groups correctly by horizon."""
    batches = [
        {"horizon_metrics": {180: {"net_pnl_median": -0.5, "win_rate_median": 0.40}}},
        {"horizon_metrics": {180: {"net_pnl_median": -0.3, "win_rate_median": 0.42}}},
        {"horizon_metrics": {240: {"net_pnl_median": -0.2, "win_rate_median": 0.45}}},
    ]
    agg = aggregate_horizon_metrics_across_batches(batches)
    assert 180 in agg and 240 in agg
    assert agg[180]["batch_count"] == 2
    assert agg[240]["batch_count"] == 1
    # Median across [(-0.5, -0.3)] = -0.4
    assert agg[180]["net_pnl_median"] == pytest.approx(-0.4)


def test_12_per_trade_derivations():
    """gross_per_trade / net_per_trade computed correctly."""
    out = build_horizon_metrics(
        selected_horizon=180,
        train_gross_pnl=[2.0, 4.0],
        train_net_pnl=[1.0, 2.0],
        train_total_trades=[100, 200],
        train_win_rate=[0.5, 0.6],
        round_total_cost_bps=10.0,
    )
    m = out[180]
    # gross_per_trade per alpha: [2.0/100, 4.0/200] = [0.02, 0.02] → median 0.02
    assert m["gross_per_trade_median"] == pytest.approx(0.02)
    # net_per_trade per alpha: [1.0/100, 2.0/200] = [0.01, 0.01] → median 0.01
    assert m["net_per_trade_median"] == pytest.approx(0.01)
    # cost_over_gross per alpha: [(2.0-1.0)/2.0, (4.0-2.0)/4.0] = [0.5, 0.5] → 0.5
    assert m["cost_over_gross_ratio"] == pytest.approx(0.5)
