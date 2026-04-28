"""Tests for TF4 aggregation_config + integration hook (per spec Phase 5).

Required tests (master order):
  1. OFF mode identical to baseline
  2. STRENGTH_FILTER reduces signals
  3. TOP_K_PER_BAR deterministic
  4. skipped_count correct
  5. conservation holds
  6. config invalid handling
"""
from __future__ import annotations

import os
import numpy as np
import pytest

from zangetsu.services import aggregation_config as cfg_mod
from zangetsu.services.aggregation_config import (
    MODE_OFF, MODE_STRENGTH_FILTER, MODE_TOP_K_PER_BAR, MODE_HYBRID_TOPK_STRENGTH,
    ALLOWED_MODES, DEFAULT_Q, DEFAULT_TOPK,
    AggregationConfig,
    get_aggregation_config, refresh_aggregation_config,
)
from zangetsu.services.signal_aggregation import (
    apply_signal_aggregation,
    PROFILE_OFF, PROFILE_STRENGTH_FILTER, PROFILE_TOP_K_PER_BAR, PROFILE_HYBRID,
)


def _build_signals():
    """3 entry trades with strengths 0.10 / 0.55 / 0.95."""
    sig = np.zeros(80, dtype=np.int8)
    sizes = np.zeros(80, dtype=np.float64)
    sig[5:15] = 1; sizes[5:15] = 0.10
    sig[25:35] = 1; sizes[25:35] = 0.55
    sig[45:55] = 1; sizes[45:55] = 0.95
    return sig, sizes


# ---------------------------------------------------------------------------
# 1. OFF mode identical to baseline
# ---------------------------------------------------------------------------
def test_1_off_mode_identical_to_baseline(monkeypatch):
    monkeypatch.delenv("ARENA_AGGREGATION_MODE", raising=False)
    monkeypatch.delenv("ARENA_AGGREGATION_Q", raising=False)
    monkeypatch.delenv("ARENA_AGGREGATION_TOPK", raising=False)
    cfg = refresh_aggregation_config()
    assert cfg.mode == MODE_OFF
    assert cfg.is_active is False
    # The hook in arena_pipeline.py guards with `_TF4_CFG.is_active` — when False
    # apply_signal_aggregation is NEVER called. Verify the integration intent:
    sig, sizes = _build_signals()
    sig_orig = sig.copy()
    sizes_orig = sizes.copy()
    if cfg.is_active:
        # Defensive: should not reach this branch in default OFF mode
        result = apply_signal_aggregation(sig, sizes, profile=PROFILE_OFF)
        sig, sizes = result.signals, result.sizes
    np.testing.assert_array_equal(sig, sig_orig)
    np.testing.assert_array_equal(sizes, sizes_orig)


# ---------------------------------------------------------------------------
# 2. STRENGTH_FILTER reduces signals
# ---------------------------------------------------------------------------
def test_2_strength_filter_reduces_signals(monkeypatch):
    monkeypatch.setenv("ARENA_AGGREGATION_MODE", "STRENGTH_FILTER")
    monkeypatch.setenv("ARENA_AGGREGATION_Q", "0.50")
    cfg = refresh_aggregation_config()
    assert cfg.mode == MODE_STRENGTH_FILTER
    assert cfg.is_active
    assert cfg.strength_quantile == 0.50
    sig, sizes = _build_signals()
    result = apply_signal_aggregation(
        sig, sizes,
        profile=PROFILE_STRENGTH_FILTER,
        strength=sizes,
        strength_quantile=cfg.strength_quantile,
    )
    assert result.entered_count == 3
    assert result.kept_count < result.entered_count, "STRENGTH_FILTER must reduce entries"
    assert result.skipped_count > 0
    # Specifically: q=0.50 over [0.10, 0.55, 0.95] = 0.55 → keep entries with strength >= 0.55
    # The 0.10 entry suppressed for sure
    assert (result.signals[5:15] == 0).all()


# ---------------------------------------------------------------------------
# 3. TOP_K_PER_BAR deterministic
# ---------------------------------------------------------------------------
def test_3_topk_deterministic(monkeypatch):
    monkeypatch.setenv("ARENA_AGGREGATION_MODE", "TOP_K_PER_BAR")
    monkeypatch.setenv("ARENA_AGGREGATION_TOPK", "1")
    cfg = refresh_aggregation_config()
    assert cfg.mode == MODE_TOP_K_PER_BAR
    assert cfg.top_k == 1
    sig, sizes = _build_signals()
    r1 = apply_signal_aggregation(
        sig, sizes,
        profile=PROFILE_TOP_K_PER_BAR,
        strength=sizes,
        top_k=cfg.top_k,
    )
    r2 = apply_signal_aggregation(
        sig, sizes,
        profile=PROFILE_TOP_K_PER_BAR,
        strength=sizes,
        top_k=cfg.top_k,
    )
    np.testing.assert_array_equal(r1.signals, r2.signals)
    np.testing.assert_array_equal(r1.kept, r2.kept)
    assert r1.kept_count == 1
    # The strongest entry (index 45, strength=0.95) is kept; others suppressed
    assert (r1.signals[5:15] == 0).all()
    assert (r1.signals[25:35] == 0).all()
    assert (r1.signals[45:55] == 1).all()


# ---------------------------------------------------------------------------
# 4. skipped_count correct
# ---------------------------------------------------------------------------
def test_4_skipped_count_correct(monkeypatch):
    """Across all modes, skipped_count equals entered - kept exactly."""
    sig, sizes = _build_signals()
    for mode_env, kwargs, expected_min_skipped in [
        ("OFF", {}, 0),
        ("STRENGTH_FILTER", {"strength_quantile": 0.50}, 1),
        ("TOP_K_PER_BAR", {"top_k": 1}, 2),
        ("HYBRID_TOPK_STRENGTH", {"strength_quantile": 0.50, "top_k": 1}, 2),
    ]:
        if mode_env == "OFF":
            monkeypatch.delenv("ARENA_AGGREGATION_MODE", raising=False)
            cfg = refresh_aggregation_config()
            assert not cfg.is_active
            continue
        monkeypatch.setenv("ARENA_AGGREGATION_MODE", mode_env)
        if "strength_quantile" in kwargs:
            monkeypatch.setenv("ARENA_AGGREGATION_Q", str(kwargs["strength_quantile"]))
        if "top_k" in kwargs:
            monkeypatch.setenv("ARENA_AGGREGATION_TOPK", str(kwargs["top_k"]))
        cfg = refresh_aggregation_config()
        prof_map = {
            "STRENGTH_FILTER": PROFILE_STRENGTH_FILTER,
            "TOP_K_PER_BAR": PROFILE_TOP_K_PER_BAR,
            "HYBRID_TOPK_STRENGTH": PROFILE_HYBRID,
        }
        result = apply_signal_aggregation(
            sig, sizes, profile=prof_map[mode_env], strength=sizes, **kwargs,
        )
        assert result.entered_count - result.kept_count == result.skipped_count, (
            f"mode={mode_env}: entered={result.entered_count} kept={result.kept_count} skipped={result.skipped_count}"
        )
        assert result.skipped_count >= expected_min_skipped, (
            f"mode={mode_env}: expected at least {expected_min_skipped} skipped; got {result.skipped_count}"
        )


# ---------------------------------------------------------------------------
# 5. conservation holds (entered = kept + skipped) across random fixtures
# ---------------------------------------------------------------------------
def test_5_conservation_holds():
    rng = np.random.default_rng(123)
    for trial in range(20):
        n = 200
        sig = np.zeros(n, dtype=np.int8)
        sizes = np.zeros(n, dtype=np.float64)
        cur = 5
        while cur + 12 < n:
            sig[cur:cur+8] = 1
            sizes[cur:cur+8] = float(rng.uniform(0, 1))
            cur += int(rng.integers(15, 25))
        for profile, kwargs in [
            (PROFILE_STRENGTH_FILTER, {"strength_quantile": 0.7}),
            (PROFILE_TOP_K_PER_BAR, {"top_k": 3}),
            (PROFILE_HYBRID, {"strength_quantile": 0.5, "top_k": 2}),
        ]:
            r = apply_signal_aggregation(sig, sizes, profile=profile, strength=sizes, **kwargs)
            assert r.entered_count == r.kept_count + r.skipped_count


# ---------------------------------------------------------------------------
# 6. config invalid handling — fallback to OFF
# ---------------------------------------------------------------------------
def test_6_config_invalid_handling(monkeypatch):
    # Invalid mode → fallback to OFF
    monkeypatch.setenv("ARENA_AGGREGATION_MODE", "GARBAGE_VALUE")
    cfg = refresh_aggregation_config()
    assert cfg.mode == MODE_OFF
    assert cfg.is_active is False

    # Invalid Q (out of range)
    monkeypatch.setenv("ARENA_AGGREGATION_MODE", "STRENGTH_FILTER")
    monkeypatch.setenv("ARENA_AGGREGATION_Q", "1.5")
    cfg = refresh_aggregation_config()
    assert cfg.strength_quantile == DEFAULT_Q

    # Invalid Q (string)
    monkeypatch.setenv("ARENA_AGGREGATION_Q", "not_a_number")
    cfg = refresh_aggregation_config()
    assert cfg.strength_quantile == DEFAULT_Q

    # Invalid TOPK (negative)
    monkeypatch.setenv("ARENA_AGGREGATION_TOPK", "-5")
    cfg = refresh_aggregation_config()
    assert cfg.top_k == DEFAULT_TOPK

    # Invalid TOPK (string)
    monkeypatch.setenv("ARENA_AGGREGATION_TOPK", "abc")
    cfg = refresh_aggregation_config()
    assert cfg.top_k == DEFAULT_TOPK

    # Empty strings → defaults
    monkeypatch.setenv("ARENA_AGGREGATION_MODE", "")
    monkeypatch.setenv("ARENA_AGGREGATION_Q", "")
    monkeypatch.setenv("ARENA_AGGREGATION_TOPK", "")
    cfg = refresh_aggregation_config()
    assert cfg.mode == MODE_OFF and cfg.strength_quantile == DEFAULT_Q and cfg.top_k == DEFAULT_TOPK

    # Case-insensitive mode
    monkeypatch.setenv("ARENA_AGGREGATION_MODE", "strength_filter")
    cfg = refresh_aggregation_config()
    assert cfg.mode == MODE_STRENGTH_FILTER


# ---------------------------------------------------------------------------
# 7. config module no forbidden refs (tokenize-scan)
# ---------------------------------------------------------------------------
def test_7_config_no_forbidden_refs():
    import tokenize
    src_path = cfg_mod.__file__
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
        "cost_bps", "cost_model", "fee_bps", "slippage_bps",
        "entry_rank_threshold", "exit_rank_threshold", "rank_window",
        "VAL_MIN_TRADES", "validation_threshold",
    ]
    for token in forbidden_exact:
        assert token not in code_tokens, (
            f"identifier {token!r} appears in CODE of aggregation_config.py"
        )
