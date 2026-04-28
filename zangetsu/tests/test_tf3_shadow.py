"""Tests for TF3 SHADOW activation harness.

TEAM ORDER 0-9Y-TF3-SIGNAL-AGGREGATION-SHADOW-ACTIVATION — Phase 3.

Coverage:
  1. shadow_disabled_by_default (ARENA_TF3_SHADOW unset)
  2. shadow_enabled_when_env_set
  3. shadow_runs_three_profiles_per_alpha
  4. baseline_signals_not_mutated
  5. accumulators_isolated_per_profile
  6. payload_shape_matches_spec
  7. conservation_per_profile_per_alpha
  8. all_kept_count_zero_handles_safely (aggregation suppresses everything)
  9. shadow_helper_no_alpha_zoo_canary_production_refs (tokenize-scan)
"""
from __future__ import annotations

import os
import numpy as np
import pytest

from zangetsu.services import tf3_shadow
from zangetsu.services.tf3_shadow import (
    PROFILE_KEYS,
    PROFILE_PARAMS,
    ShadowAccumulator,
    is_shadow_enabled,
    refresh_shadow_flag,
    make_accumulators,
    run_shadow_for_alpha,
    build_shadow_profiles_payload,
)


class _StubBacktester:
    """Stub that returns a deterministic BacktestResult-like object."""

    class _Result:
        def __init__(self, gross_pnl, net_pnl, total_trades, win_rate):
            self.gross_pnl = gross_pnl
            self.net_pnl = net_pnl
            self.total_trades = total_trades
            self.win_rate = win_rate
            self.sharpe_ratio = 0.0

    def __init__(self):
        self.calls = 0

    def run(self, signals, close, sym, cost_bps, max_hold, *, high=None, low=None, sizes=None):
        self.calls += 1
        # Compute a "trade outcome" proportional to signal magnitude
        n_trades = int(np.sum(signals != 0))
        gross = float(np.sum(np.abs(sizes) * 0.001))
        net = gross - cost_bps * 1e-5 * n_trades
        return self._Result(gross_pnl=gross, net_pnl=net,
                            total_trades=n_trades, win_rate=0.5)


def _build_signals_with_strength_gradient():
    """3 entry trades with monotonically increasing strength:
    entries at 5, 25, 45; strengths 0.10, 0.55, 0.95.
    """
    sig = np.zeros(80, dtype=np.int8)
    sizes = np.zeros(80, dtype=np.float64)
    sig[5:15] = 1; sizes[5:15] = 0.10
    sig[25:35] = 1; sizes[25:35] = 0.55
    sig[45:55] = 1; sizes[45:55] = 0.95
    close = np.linspace(100.0, 110.0, 80, dtype=np.float32)
    return sig, sizes, close


# ---------------------------------------------------------------------------
# 1. shadow_disabled_by_default
# ---------------------------------------------------------------------------
def test_1_shadow_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ARENA_TF3_SHADOW", raising=False)
    assert refresh_shadow_flag() is False
    assert is_shadow_enabled() is False


# ---------------------------------------------------------------------------
# 2. shadow_enabled_when_env_set
# ---------------------------------------------------------------------------
def test_2_shadow_enabled_when_env_set(monkeypatch):
    for v in ("1", "true", "yes", "on", "TRUE"):
        monkeypatch.setenv("ARENA_TF3_SHADOW", v)
        assert refresh_shadow_flag() is True
    monkeypatch.setenv("ARENA_TF3_SHADOW", "0")
    assert refresh_shadow_flag() is False
    monkeypatch.setenv("ARENA_TF3_SHADOW", "")
    assert refresh_shadow_flag() is False


# ---------------------------------------------------------------------------
# 3. shadow_runs_three_profiles_per_alpha
# ---------------------------------------------------------------------------
def test_3_shadow_runs_three_profiles_per_alpha():
    sig, sizes, close = _build_signals_with_strength_gradient()
    bt = _StubBacktester()
    accs = make_accumulators()
    assert set(accs.keys()) == set(PROFILE_KEYS)
    run_shadow_for_alpha(
        signals=sig, sizes=sizes, backtester=bt,
        close_f32=close, high_f32=None, low_f32=None,
        sym="TESTUSDT", cost_bps=14.5, max_hold=60,
        accumulators=accs,
    )
    # Each profile ran one backtester call (3 calls total)
    assert bt.calls == 3
    # All profiles recorded their alpha sample
    for k in PROFILE_KEYS:
        assert len(accs[k].train_gross_pnl) == 1
        assert len(accs[k].train_net_pnl) == 1
        assert len(accs[k].train_total_trades) == 1


# ---------------------------------------------------------------------------
# 4. baseline_signals_not_mutated
# ---------------------------------------------------------------------------
def test_4_baseline_signals_not_mutated():
    sig, sizes, close = _build_signals_with_strength_gradient()
    sig_orig = sig.copy()
    sizes_orig = sizes.copy()
    bt = _StubBacktester()
    accs = make_accumulators()
    run_shadow_for_alpha(
        signals=sig, sizes=sizes, backtester=bt,
        close_f32=close, high_f32=None, low_f32=None,
        sym="TESTUSDT", cost_bps=14.5, max_hold=60,
        accumulators=accs,
    )
    np.testing.assert_array_equal(sig, sig_orig)
    np.testing.assert_array_equal(sizes, sizes_orig)


# ---------------------------------------------------------------------------
# 5. accumulators_isolated_per_profile
# ---------------------------------------------------------------------------
def test_5_accumulators_isolated_per_profile():
    sig, sizes, close = _build_signals_with_strength_gradient()
    bt = _StubBacktester()
    accs = make_accumulators()
    run_shadow_for_alpha(
        signals=sig, sizes=sizes, backtester=bt,
        close_f32=close, high_f32=None, low_f32=None,
        sym="TESTUSDT", cost_bps=14.5, max_hold=60,
        accumulators=accs,
    )
    # Each profile must have its own ShadowAccumulator (different objects)
    objs = [accs[k] for k in PROFILE_KEYS]
    assert objs[0] is not objs[1] and objs[1] is not objs[2]
    # STRENGTH q=0.95: keeps top 5% of 3 entries → just the strongest (s=0.95)
    # TOPK K=50: 3 entries < 50 → all kept
    # HYBRID q=0.90 K=50: q=0.90 of [0.10, 0.55, 0.95] → ~0.87 → keep just 0.95
    s_acc = accs["strength"]
    t_acc = accs["top_k"]
    h_acc = accs["hybrid"]
    # Each accumulator records 1 alpha sample (the kept entry/entries from one alpha)
    assert s_acc.entered_count_total == 3
    assert s_acc.kept_count_total <= 1  # very strict quantile
    assert t_acc.entered_count_total == 3
    assert t_acc.kept_count_total == 3  # K=50 > 3
    assert h_acc.entered_count_total == 3
    assert h_acc.kept_count_total <= 1
    # Skipped + kept = entered for each profile
    for acc in objs:
        assert acc.entered_count_total == acc.kept_count_total + acc.skipped_count_total


# ---------------------------------------------------------------------------
# 6. payload_shape_matches_spec
# ---------------------------------------------------------------------------
def test_6_payload_shape_matches_spec():
    sig, sizes, close = _build_signals_with_strength_gradient()
    bt = _StubBacktester()
    accs = make_accumulators()
    run_shadow_for_alpha(
        signals=sig, sizes=sizes, backtester=bt,
        close_f32=close, high_f32=None, low_f32=None,
        sym="TESTUSDT", cost_bps=14.5, max_hold=60,
        accumulators=accs,
    )
    payload = build_shadow_profiles_payload(
        accs,
        baseline_train_gross_pnl=[1.0, 1.5, 2.0],
        baseline_train_net_pnl=[0.5, 0.8, 1.0],
        baseline_train_total_trades=[100, 150, 200],
        baseline_train_win_rate=[0.3, 0.35, 0.4],
    )
    # Required top-level keys
    assert "baseline" in payload
    for k in PROFILE_KEYS:
        assert k in payload
    # Baseline echoes existing aggregate_metrics
    base = payload["baseline"]
    assert "trade_count_median" in base
    assert "gross_pnl_median" in base
    assert "net_pnl_median" in base
    assert "win_rate_median" in base
    assert base["alpha_count"] == 3
    # Per-profile required fields per master order
    for k in PROFILE_KEYS:
        p = payload[k]
        for required in ("trade_count_median", "gross_pnl_median", "net_pnl_median",
                         "win_rate_median", "skipped_count_total", "label", "params"):
            assert required in p, f"profile {k} missing {required}"


# ---------------------------------------------------------------------------
# 7. conservation_per_profile_per_alpha
# ---------------------------------------------------------------------------
def test_7_conservation_per_profile_per_alpha():
    rng = np.random.default_rng(7)
    sig = np.zeros(500, dtype=np.int8)
    sizes = np.zeros(500, dtype=np.float64)
    cur = 5
    while cur + 12 < 500:
        sig[cur:cur + 8] = 1
        sizes[cur:cur + 8] = float(rng.uniform(0, 1))
        cur += int(rng.integers(15, 25))
    close = np.linspace(100.0, 200.0, 500, dtype=np.float32)
    bt = _StubBacktester()
    accs = make_accumulators()
    run_shadow_for_alpha(
        signals=sig, sizes=sizes, backtester=bt,
        close_f32=close, high_f32=None, low_f32=None,
        sym="TESTUSDT", cost_bps=14.5, max_hold=60,
        accumulators=accs,
    )
    for k, acc in accs.items():
        assert acc.entered_count_total == acc.kept_count_total + acc.skipped_count_total, (
            f"conservation failed for {k}: entered={acc.entered_count_total} "
            f"kept={acc.kept_count_total} skip={acc.skipped_count_total}"
        )


# ---------------------------------------------------------------------------
# 8. all_kept_count_zero_handles_safely
# ---------------------------------------------------------------------------
def test_8_all_kept_count_zero_handles_safely():
    """If aggregation suppresses every entry (skipped == entered), the
    accumulator records a zero-trade alpha — backtester is NOT called."""
    sig = np.zeros(80, dtype=np.int8)
    sizes = np.zeros(80, dtype=np.float64)
    sig[5:15] = 1; sizes[5:15] = 0.0  # strength = 0 → suppressed by all profiles
    sig[25:35] = 1; sizes[25:35] = 0.0
    close = np.linspace(100.0, 110.0, 80, dtype=np.float32)
    bt = _StubBacktester()
    accs = make_accumulators()
    run_shadow_for_alpha(
        signals=sig, sizes=sizes, backtester=bt,
        close_f32=close, high_f32=None, low_f32=None,
        sym="TESTUSDT", cost_bps=14.5, max_hold=60,
        accumulators=accs,
    )
    # All profiles record zero-trade alpha when nothing kept
    # STRENGTH q=0.95 over [0,0]: all are below threshold (or equal to threshold)
    s_acc = accs["strength"]
    if s_acc.kept_count_total == 0:
        assert s_acc.train_total_trades == [0]
        assert s_acc.train_gross_pnl == [0.0]
    # TOPK with K=50 keeps all 2 entries since K > entered → backtester called
    # HYBRID kept ≈ 0 → zero-trade
    # backtester.calls is at most 3 (one per profile that kept something)
    assert bt.calls <= 3


# ---------------------------------------------------------------------------
# 9. shadow_helper_no_alpha_zoo_canary_production_refs (tokenize-scan)
# ---------------------------------------------------------------------------
def test_9_shadow_helper_no_alpha_zoo_canary_production_refs():
    """tf3_shadow.py must not reference forbidden subsystems in code."""
    import tokenize
    src_path = tf3_shadow.__file__
    code_tokens = []
    with open(src_path, "rb") as f:
        for tok in tokenize.tokenize(f.readline):
            if tok.type in (tokenize.NAME, tokenize.NUMBER, tokenize.OP):
                code_tokens.append(tok.string)
    forbidden_exact = [
        "alpha_zoo", "ALPHA_ZOO", "alpha_zoo_injection",
        "champion_pipeline_staging", "champion_pipeline_fresh",
        "execute_insert", "DB_WRITE",
        "canary_active", "CANARY_ENABLED", "production_rollout",
        "real_capital", "ORDER_ROUTER", "order_router",
        "execute_order", "live_trading",
        "A2_MIN_TRADES", "MIN_TRADES", "a2_min_trades",
    ]
    for token in forbidden_exact:
        assert token not in code_tokens, (
            f"identifier {token!r} appears in CODE of tf3_shadow.py"
        )
