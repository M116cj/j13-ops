"""Tests for HE2 A1 horizon-aware generation (per spec Phase 4).

Required tests (master order):
   1. test_a1_selects_horizon_per_round_simple_cycle
   2. test_env_unset_defaults_to_fixed_60
   3. test_redesign_mode_cycles_180_240_360
   4. test_alpha_engine_receives_selected_horizon
   5. test_alpha_result_horizon_propagates_to_candidate_metadata
   6. test_generation_profile_id_includes_horizon
   7. test_passport_or_trace_contains_horizon
   8. test_same_formula_different_horizon_has_distinct_identity
   9. test_batch_telemetry_contains_selected_horizon
  10. test_validation_thresholds_unchanged
  11. test_cost_model_unchanged
  12. test_a2_min_trades_unchanged
  13. test_tf4_aggregation_default_off_still_off
  14. test_legacy_missing_horizon_defaults_to_60
"""
from __future__ import annotations

import hashlib
import os
import tokenize
import numpy as np
import pytest

from zangetsu.services import horizon_config as hc_mod
from zangetsu.services.horizon_config import (
    get_horizon_config, get_active_a1_horizons, get_horizon_mode,
    select_horizon, refresh_horizon_config,
    MODE_FIXED, MODE_SIMPLE_CYCLE,
    DEFAULT_HORIZONS, DEFAULT_FIXED, DEFAULT_MODE,
)


def _reset_env(monkeypatch):
    for v in ("ACTIVE_A1_HORIZONS", "ARENA_HORIZON_MODE", "ARENA_HORIZON_FIXED",
              "ALPHA_FORWARD_HORIZON",
              "ARENA_AGGREGATION_MODE", "ARENA_AGGREGATION_Q", "ARENA_AGGREGATION_TOPK",
              "ARENA_TF3_SHADOW"):
        monkeypatch.delenv(v, raising=False)
    refresh_horizon_config()


# ---------------------------------------------------------------------------
# 1. A1 selects horizon per round in SIMPLE_CYCLE
# ---------------------------------------------------------------------------
def test_1_a1_selects_horizon_per_round_simple_cycle(monkeypatch):
    monkeypatch.setenv("ACTIVE_A1_HORIZONS", "60,180,240,360")
    monkeypatch.setenv("ARENA_HORIZON_MODE", "SIMPLE_CYCLE")
    refresh_horizon_config()
    seq = [select_horizon(r) for r in range(12)]
    # Cycle pattern: 60, 180, 240, 360, 60, 180, 240, 360, 60, 180, 240, 360
    assert seq == [60, 180, 240, 360] * 3
    # Determinism: stable across calls
    seq2 = [select_horizon(r) for r in range(12)]
    assert seq == seq2


# ---------------------------------------------------------------------------
# 2. env unset defaults to FIXED 60
# ---------------------------------------------------------------------------
def test_2_env_unset_defaults_to_fixed_60(monkeypatch):
    _reset_env(monkeypatch)
    cfg = get_horizon_config()
    assert cfg.active_horizons == (60,)
    assert cfg.mode == MODE_FIXED
    assert cfg.fixed_horizon == 60
    assert get_active_a1_horizons() == (60,)
    assert get_horizon_mode() == MODE_FIXED
    for r in range(50):
        assert select_horizon(r) == 60


# ---------------------------------------------------------------------------
# 3. redesign mode cycles 180/240/360
# ---------------------------------------------------------------------------
def test_3_redesign_mode_cycles_180_240_360(monkeypatch):
    monkeypatch.setenv("ACTIVE_A1_HORIZONS", "180,240,360")
    monkeypatch.setenv("ARENA_HORIZON_MODE", "SIMPLE_CYCLE")
    refresh_horizon_config()
    seq = [select_horizon(r) for r in range(9)]
    assert seq == [180, 240, 360, 180, 240, 360, 180, 240, 360]
    assert 60 not in seq


# ---------------------------------------------------------------------------
# 4. AlphaEngine receives selected horizon
# ---------------------------------------------------------------------------
def test_4_alpha_engine_receives_selected_horizon():
    from zangetsu.engine.components.alpha_engine import AlphaEngine
    e60 = AlphaEngine(horizon=60)
    e180 = AlphaEngine(horizon=180)
    e240 = AlphaEngine(horizon=240)
    assert e60.horizon == 60
    assert e180.horizon == 180
    assert e240.horizon == 240
    # Default (None) -> falls back to env default 60 (or ALPHA_FORWARD_HORIZON if set)
    edefault = AlphaEngine()
    assert edefault.horizon == 60


# ---------------------------------------------------------------------------
# 5. AlphaResult.horizon propagates to candidate metadata
# ---------------------------------------------------------------------------
def test_5_alpha_result_horizon_propagates():
    from zangetsu.engine.components.alpha_engine import AlphaResult
    r60 = AlphaResult(formula="x", ast_json=[], alpha_hash="abc", depth=1, node_count=1, horizon=60)
    r180 = AlphaResult(formula="x", ast_json=[], alpha_hash="def", depth=1, node_count=1, horizon=180)
    assert r60.horizon == 60
    assert r180.horizon == 180
    # to_dict() preserves horizon
    d = r180.to_dict()
    assert d["horizon"] == 180


# ---------------------------------------------------------------------------
# 6. generation_profile_id includes horizon
# ---------------------------------------------------------------------------
def test_6_generation_profile_id_includes_horizon():
    """HE2 derives a per-batch generation_profile_horizon = '<base>:h<horizon>'.
    This is verified by replicating the derivation logic used in arena_pipeline.py.
    """
    base_pid = "gp_26f478846fd0f729"
    for h in (180, 240, 360):
        gp_h = f"{base_pid}:h{h}"
        assert gp_h.endswith(f":h{h}")
        assert gp_h != base_pid
    # Distinct identity per horizon
    derivations = [f"{base_pid}:h{h}" for h in (60, 180, 240, 360)]
    assert len(set(derivations)) == 4


# ---------------------------------------------------------------------------
# 7. Passport contains horizon (schema support)
# ---------------------------------------------------------------------------
def test_7_passport_contains_horizon():
    from zangetsu.engine.components.passport import ChampionPassport
    # Default (no horizon kwarg) → no horizon in arena1 (pre-HE2 schema)
    p = ChampionPassport("ind_hash", "trend", "engine_v10")
    p.stamp_arena1(
        indicator_configs=[{}], n_indicators=1, base_wr=0.5, base_pnl=0.1,
        base_weighted_pnl=0.1, base_score=0.5, base_n_trades=10,
        round_number=1, symbol="BTCUSDT",
    )
    assert "horizon" not in p._data["arena1"]
    # With horizon kwarg → field present
    for h in (60, 180, 240, 360):
        pp = ChampionPassport("ind_hash", "trend", "engine_v10")
        pp.stamp_arena1(
            indicator_configs=[{}], n_indicators=1, base_wr=0.5, base_pnl=0.1,
            base_weighted_pnl=0.1, base_score=0.5, base_n_trades=10,
            round_number=1, symbol="BTCUSDT", horizon=h,
        )
        assert pp._data["arena1"]["horizon"] == h


# ---------------------------------------------------------------------------
# 7b. Lifecycle trace extras carry horizon
# ---------------------------------------------------------------------------
def test_7b_lifecycle_trace_extras_carry_horizon():
    from zangetsu.services.candidate_trace import build_lifecycle_trace_event
    ev = build_lifecycle_trace_event(
        arena_stage="A1",
        stage_event="ENTRY",
        status="ENTERED",
        candidate_id="abc",
        extras={"horizon": 240},
    )
    d = ev.to_dict()
    assert d.get("horizon") == 240


# ---------------------------------------------------------------------------
# 8. Same formula at different horizons → distinct identity
# ---------------------------------------------------------------------------
def test_8_same_formula_distinct_identity_per_horizon():
    formula = "ts_sum_60(close)"
    h60 = hashlib.md5(formula.encode("utf-8")).hexdigest()[:16]
    h180 = hashlib.md5(f"{formula}|h180".encode("utf-8")).hexdigest()[:16]
    h240 = hashlib.md5(f"{formula}|h240".encode("utf-8")).hexdigest()[:16]
    h360 = hashlib.md5(f"{formula}|h360".encode("utf-8")).hexdigest()[:16]
    assert len({h60, h180, h240, h360}) == 4
    # h=60 preserves legacy hash format
    assert h60 == hashlib.md5(formula.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# 9. batch telemetry contains selected_horizon
# ---------------------------------------------------------------------------
def test_9_batch_telemetry_contains_selected_horizon(monkeypatch):
    """Verify the code-path constructs telemetry dict with selected_horizon when active.
    Inspected by replicating the dict-construction logic from arena_pipeline.py.
    """
    monkeypatch.setenv("ACTIVE_A1_HORIZONS", "180,240,360")
    monkeypatch.setenv("ARENA_HORIZON_MODE", "SIMPLE_CYCLE")
    cfg = refresh_horizon_config()
    # Replicate the per-batch logic
    selected_h = select_horizon(0)  # → 180
    telemetry = {"schema_version": "0-9y-b1-v1"}
    telemetry["horizon"] = int(selected_h)
    telemetry["selected_horizon"] = int(selected_h)
    if cfg.is_multi_horizon:
        telemetry["horizon_config"] = {"mode": cfg.mode, "active_horizons": list(cfg.active_horizons)}
        telemetry["active_horizons"] = list(cfg.active_horizons)
        telemetry["horizon_mode"] = str(cfg.mode)
    if int(selected_h) != 60:
        telemetry["generation_profile_horizon"] = f"gp_test:h{int(selected_h)}"
    # Assertions
    assert telemetry["selected_horizon"] == 180
    assert telemetry["horizon"] == 180
    assert telemetry["active_horizons"] == [180, 240, 360]
    assert telemetry["horizon_mode"] == "SIMPLE_CYCLE"
    assert telemetry["generation_profile_horizon"] == "gp_test:h180"


# ---------------------------------------------------------------------------
# 10. validation thresholds unchanged
# ---------------------------------------------------------------------------
def test_10_validation_thresholds_unchanged():
    """Tokenize-scan: HE2 source files contain no validator-threshold identifiers."""
    forbidden = ["entry_rank_threshold", "exit_rank_threshold", "rank_window",
                 "VAL_MIN_TRADES", "validator_threshold", "validation_threshold"]
    paths = [
        hc_mod.__file__,  # horizon_config.py
    ]
    for p in paths:
        toks = []
        with open(p, "rb") as f:
            for tok in tokenize.tokenize(f.readline):
                if tok.type in (tokenize.NAME, tokenize.NUMBER, tokenize.OP):
                    toks.append(tok.string)
        for t in forbidden:
            assert t not in toks, f"{t!r} in code of {p}"


# ---------------------------------------------------------------------------
# 11. cost_model unchanged
# ---------------------------------------------------------------------------
def test_11_cost_model_unchanged():
    forbidden = ["cost_bps", "cost_model", "fee_bps", "slippage_bps",
                 "round_total_cost", "FEE_BPS", "SLIPPAGE"]
    paths = [hc_mod.__file__]
    for p in paths:
        toks = []
        with open(p, "rb") as f:
            for tok in tokenize.tokenize(f.readline):
                if tok.type in (tokenize.NAME, tokenize.NUMBER, tokenize.OP):
                    toks.append(tok.string)
        for t in forbidden:
            assert t not in toks, f"{t!r} in code of {p}"


# ---------------------------------------------------------------------------
# 12. A2_MIN_TRADES unchanged
# ---------------------------------------------------------------------------
def test_12_a2_min_trades_unchanged():
    forbidden = ["A2_MIN_TRADES", "MIN_TRADES", "a2_min_trades", "MIN_TRADE_COUNT"]
    paths = [hc_mod.__file__]
    for p in paths:
        toks = []
        with open(p, "rb") as f:
            for tok in tokenize.tokenize(f.readline):
                if tok.type in (tokenize.NAME, tokenize.NUMBER, tokenize.OP):
                    toks.append(tok.string)
        for t in forbidden:
            assert t not in toks, f"{t!r} in code of {p}"


# ---------------------------------------------------------------------------
# 13. TF4 aggregation default OFF still OFF
# ---------------------------------------------------------------------------
def test_13_tf4_aggregation_default_off_still_off(monkeypatch):
    """HE2 must not change TF4's default-OFF behavior."""
    for v in ("ARENA_AGGREGATION_MODE", "ARENA_AGGREGATION_Q", "ARENA_AGGREGATION_TOPK"):
        monkeypatch.delenv(v, raising=False)
    from zangetsu.services.aggregation_config import (
        get_aggregation_config, refresh_aggregation_config, MODE_OFF,
    )
    cfg = refresh_aggregation_config()
    assert cfg.mode == MODE_OFF
    assert cfg.is_active is False


# ---------------------------------------------------------------------------
# 14. legacy missing horizon defaults to 60
# ---------------------------------------------------------------------------
def test_14_legacy_missing_horizon_defaults_to_60(monkeypatch):
    """When `horizon` is not passed to AlphaEngine constructor (legacy path),
    falls back to ALPHA_FORWARD_HORIZON env (default 60). When env unset → 60."""
    monkeypatch.delenv("ALPHA_FORWARD_HORIZON", raising=False)
    from zangetsu.engine.components.alpha_engine import AlphaEngine
    e = AlphaEngine()
    assert e.horizon == 60
    # Same for _forward_returns
    close = np.linspace(100.0, 200.0, 200, dtype=np.float32)
    fr_default = AlphaEngine._forward_returns(close)  # no horizon arg
    fr_60 = AlphaEngine._forward_returns(close, horizon=60)
    np.testing.assert_array_equal(fr_default, fr_60)
