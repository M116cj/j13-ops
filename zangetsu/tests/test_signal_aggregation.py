"""Tests for TF2 signal aggregation prototype.

Covers the 13 required tests from TEAM ORDER 0-9Y-TF2-SIGNAL-AGGREGATION-PROTOTYPE
Phase 3:

  1. baseline_profile_returns_all_signals
  2. strength_filter_keeps_strongest_only
  3. top_k_per_bar_keeps_k_deterministically
  4. skipped_count_conservation
  5. nan_strength_handled_safely
  6. unknown_profile_fails_closed
  7. no_mutation_or_documented_mutation
  8. telemetry_fields_present
  9. validation_thresholds_unchanged
 10. cost_model_unchanged
 11. A2_MIN_TRADES_unchanged
 12. no_alpha_zoo_write_path
 13. no_canary_or_production_flags_enabled
"""
from __future__ import annotations

import numpy as np
import pytest

from zangetsu.services.signal_aggregation import (
    AggregationResult,
    ALLOWED_PROFILES,
    PASS_THROUGH_PROFILES,
    PROFILE_OFF,
    PROFILE_BASELINE,
    PROFILE_STRENGTH_FILTER,
    PROFILE_TOP_K_PER_BAR,
    PROFILE_HYBRID,
    PROFILE_CONSENSUS,
    SKIP_REASON_STRENGTH_BELOW_Q,
    SKIP_REASON_BELOW_TOPK_RANK,
    SKIP_REASON_NAN_STRENGTH,
    SKIP_REASON_HYBRID_STRENGTH,
    SKIP_REASON_HYBRID_TOPK,
    apply_signal_aggregation,
)


def _build_signals(entry_bars, exit_bars, n=200):
    """Build a signals array with explicit entry/exit edges. Direction = +1 (long)."""
    sig = np.zeros(n, dtype=np.int8)
    sizes = np.zeros(n, dtype=np.float64)
    for e, x in zip(entry_bars, exit_bars):
        sig[e:x] = 1
        sizes[e:x] = 0.5  # default size
    return sig, sizes


def _strength_at_entries(entries, values):
    """Convenience: build a strength array of length max(entries)+10 with values
    set at the entry indices (rest zero)."""
    n = max(entries) + 10
    s = np.zeros(n, dtype=np.float64)
    for i, v in zip(entries, values):
        s[i] = v
    return s


# ---------------------------------------------------------------------------
# 1. baseline_profile_returns_all_signals
# ---------------------------------------------------------------------------
def test_1_baseline_profile_returns_all_signals():
    entries = [10, 50, 90]
    exits = [25, 70, 110]
    sig, sizes = _build_signals(entries, exits, n=200)
    for profile in (PROFILE_OFF, PROFILE_BASELINE):
        result = apply_signal_aggregation(sig, sizes, profile=profile)
        assert result.entered_count == 3
        assert result.kept_count == 3
        assert result.skipped_count == 0
        np.testing.assert_array_equal(result.signals, sig)
        np.testing.assert_array_equal(result.sizes, sizes)
        assert result.metadata["skip_reason_distribution"] == {}


# ---------------------------------------------------------------------------
# 2. strength_filter_keeps_strongest_only
# ---------------------------------------------------------------------------
def test_2_strength_filter_keeps_strongest_only():
    entries = [10, 50, 90, 130]
    exits = [25, 70, 110, 150]
    sig, sizes = _build_signals(entries, exits, n=200)
    # Strength at entries: 0.10, 0.50, 0.80, 0.95
    # quantile=0.50 over [0.10, 0.50, 0.80, 0.95] = 0.65 → keep entries with strength >= 0.65
    # Expected kept: [90 (0.80), 130 (0.95)]; skipped: [10, 50]
    strength = sig.astype(np.float64).copy()  # placeholder length
    strength = np.zeros(200, dtype=np.float64)
    strength[10] = 0.10
    strength[50] = 0.50
    strength[90] = 0.80
    strength[130] = 0.95
    result = apply_signal_aggregation(
        sig, sizes, profile=PROFILE_STRENGTH_FILTER, strength=strength,
        strength_quantile=0.50,
    )
    assert result.entered_count == 4
    # quantile(0.5) of [0.10, 0.50, 0.80, 0.95] = 0.65 → 0.10, 0.50 BELOW; 0.80, 0.95 KEEP
    assert result.kept_count == 2
    assert result.skipped_count == 2
    # The first two entries (indices 10 and 50) were suppressed
    assert (result.signals[10:25] == 0).all()
    assert (result.signals[50:70] == 0).all()
    # The strong entries (90 and 130) were preserved
    assert (result.signals[90:110] == 1).all()
    assert (result.signals[130:150] == 1).all()
    assert result.metadata["skip_reason_distribution"][SKIP_REASON_STRENGTH_BELOW_Q] == 2
    assert result.metadata["strength_threshold"] == pytest.approx(0.65)


# ---------------------------------------------------------------------------
# 3. top_k_per_bar_keeps_k_deterministically
# ---------------------------------------------------------------------------
def test_3_top_k_per_bar_keeps_k_deterministically():
    entries = [10, 50, 90, 130, 170]
    exits = [25, 70, 110, 150, 190]
    sig, sizes = _build_signals(entries, exits, n=200)
    # Strength at entries: 0.10, 0.40, 0.70, 0.90, 0.55
    # top_k=2 → keep [130 (0.90), 90 (0.70)]
    strength = np.zeros(200, dtype=np.float64)
    strength[10] = 0.10
    strength[50] = 0.40
    strength[90] = 0.70
    strength[130] = 0.90
    strength[170] = 0.55
    result = apply_signal_aggregation(
        sig, sizes, profile=PROFILE_TOP_K_PER_BAR, strength=strength, top_k=2,
    )
    assert result.entered_count == 5
    assert result.kept_count == 2
    assert result.skipped_count == 3
    # Determinism: re-run produces identical output
    result2 = apply_signal_aggregation(
        sig, sizes, profile=PROFILE_TOP_K_PER_BAR, strength=strength, top_k=2,
    )
    np.testing.assert_array_equal(result.signals, result2.signals)
    np.testing.assert_array_equal(result.kept, result2.kept)
    # Tiebreak (equal strength) test: smaller index first
    sig_t, sizes_t = _build_signals([10, 50, 90, 130], [25, 70, 110, 150], n=200)
    strength_t = np.zeros(200, dtype=np.float64)
    strength_t[10] = 0.50
    strength_t[50] = 0.50
    strength_t[90] = 0.50
    strength_t[130] = 0.50
    res_tie = apply_signal_aggregation(
        sig_t, sizes_t, profile=PROFILE_TOP_K_PER_BAR,
        strength=strength_t, top_k=2,
    )
    # All strengths equal → top-2 should be the FIRST two entry edges (10 and 50)
    assert res_tie.kept_count == 2
    assert (res_tie.signals[10:25] == 1).all()
    assert (res_tie.signals[50:70] == 1).all()
    assert (res_tie.signals[90:110] == 0).all()
    assert (res_tie.signals[130:150] == 0).all()


# ---------------------------------------------------------------------------
# 4. skipped_count_conservation
# ---------------------------------------------------------------------------
def test_4_skipped_count_conservation():
    """Conservation: entered_count == kept_count + skipped_count, always."""
    rng = np.random.RandomState(42)
    n = 500
    sig = np.zeros(n, dtype=np.int8)
    sizes = np.zeros(n, dtype=np.float64)
    # Random non-overlapping entries
    cur = 5
    entries = []
    while cur + 10 < n:
        entries.append(cur)
        sig[cur:cur + 8] = 1
        sizes[cur:cur + 8] = rng.uniform(0.0, 1.0)
        cur += int(rng.randint(10, 30))
    strength = sizes.copy()
    for profile_kwargs in [
        {"profile": PROFILE_OFF},
        {"profile": PROFILE_BASELINE},
        {"profile": PROFILE_STRENGTH_FILTER, "strength_quantile": 0.7,
         "strength": strength},
        {"profile": PROFILE_TOP_K_PER_BAR, "top_k": 3, "strength": strength},
        {"profile": PROFILE_HYBRID, "strength_quantile": 0.5,
         "top_k": 2, "strength": strength},
        {"profile": PROFILE_CONSENSUS},
    ]:
        result = apply_signal_aggregation(sig, sizes, **profile_kwargs)
        assert result.entered_count == result.kept_count + result.skipped_count, (
            f"conservation failed for {profile_kwargs['profile']}: "
            f"entered={result.entered_count} kept={result.kept_count} skip={result.skipped_count}"
        )
        # kept mask length matches entered_count
        assert result.kept.size == result.entered_count
        assert int(result.kept.sum()) == result.kept_count


# ---------------------------------------------------------------------------
# 5. nan_strength_handled_safely
# ---------------------------------------------------------------------------
def test_5_nan_strength_handled_safely():
    entries = [10, 50, 90]
    exits = [25, 70, 110]
    sig, sizes = _build_signals(entries, exits, n=200)
    strength = np.zeros(200, dtype=np.float64)
    strength[10] = 0.80
    strength[50] = float("nan")  # NaN at the second entry
    strength[90] = 0.40
    # STRENGTH_FILTER with quantile 0.5: NaN → -inf → always skipped.
    result = apply_signal_aggregation(
        sig, sizes, profile=PROFILE_STRENGTH_FILTER, strength=strength,
        strength_quantile=0.5,
    )
    assert result.skipped_count >= 1  # At least the NaN-strength entry was suppressed
    assert SKIP_REASON_NAN_STRENGTH in result.metadata["skip_reason_distribution"]
    # No exception was raised → safe handling confirmed.
    # TOP_K case
    result_topk = apply_signal_aggregation(
        sig, sizes, profile=PROFILE_TOP_K_PER_BAR, strength=strength, top_k=2,
    )
    # NaN entry should never be in kept set
    nan_entry_idx = entries.index(50)
    assert not result_topk.kept[nan_entry_idx]


# ---------------------------------------------------------------------------
# 6. unknown_profile_fails_closed
# ---------------------------------------------------------------------------
def test_6_unknown_profile_fails_closed():
    sig, sizes = _build_signals([10, 50], [25, 70], n=100)
    with pytest.raises(ValueError, match="unknown profile"):
        apply_signal_aggregation(sig, sizes, profile="GARBAGE_PROFILE")
    with pytest.raises(ValueError, match="unknown profile"):
        apply_signal_aggregation(sig, sizes, profile="")
    # Required params missing for known profile → ValueError
    with pytest.raises(ValueError, match="STRENGTH_FILTER requires strength_quantile"):
        apply_signal_aggregation(sig, sizes, profile=PROFILE_STRENGTH_FILTER)
    with pytest.raises(ValueError, match="TOP_K_PER_BAR requires top_k"):
        apply_signal_aggregation(sig, sizes, profile=PROFILE_TOP_K_PER_BAR)
    with pytest.raises(ValueError, match="HYBRID_TOPK_STRENGTH requires"):
        apply_signal_aggregation(sig, sizes, profile=PROFILE_HYBRID,
                                 strength_quantile=0.9)
    # Out-of-range quantile
    with pytest.raises(ValueError, match="strength_quantile must be in"):
        apply_signal_aggregation(sig, sizes, profile=PROFILE_STRENGTH_FILTER,
                                 strength_quantile=1.5)
    # Negative top_k
    with pytest.raises(ValueError, match="top_k must be"):
        apply_signal_aggregation(sig, sizes, profile=PROFILE_TOP_K_PER_BAR, top_k=-1)


# ---------------------------------------------------------------------------
# 7. no_mutation_or_documented_mutation
# ---------------------------------------------------------------------------
def test_7_no_mutation_or_documented_mutation():
    """Helper must not mutate input arrays; outputs must be distinct objects."""
    sig, sizes = _build_signals([10, 50, 90], [25, 70, 110], n=200)
    sig_orig = sig.copy()
    sizes_orig = sizes.copy()
    strength = np.zeros(200, dtype=np.float64)
    strength[[10, 50, 90]] = [0.10, 0.50, 0.90]

    result = apply_signal_aggregation(
        sig, sizes, profile=PROFILE_STRENGTH_FILTER, strength=strength,
        strength_quantile=0.5,
    )
    # Inputs unchanged
    np.testing.assert_array_equal(sig, sig_orig)
    np.testing.assert_array_equal(sizes, sizes_orig)
    # Output distinct objects
    assert result.signals is not sig
    assert result.sizes is not sizes
    # Output buffers may share dtype but must not share memory
    assert result.signals.ctypes.data != sig.ctypes.data
    assert result.sizes.ctypes.data != sizes.ctypes.data


# ---------------------------------------------------------------------------
# 8. telemetry_fields_present
# ---------------------------------------------------------------------------
def test_8_telemetry_fields_present():
    """AggregationResult must expose all required telemetry fields."""
    sig, sizes = _build_signals([10, 50, 90, 130], [25, 70, 110, 150], n=200)
    strength = np.zeros(200, dtype=np.float64)
    strength[[10, 50, 90, 130]] = [0.20, 0.50, 0.80, 0.95]
    result = apply_signal_aggregation(
        sig, sizes, profile=PROFILE_HYBRID, strength=strength,
        strength_quantile=0.50, top_k=1,
    )
    # Top-level fields
    for f in ("signals", "sizes", "kept", "profile",
              "entered_count", "kept_count", "skipped_count", "metadata"):
        assert hasattr(result, f), f"missing field {f}"
    # Metadata fields
    md = result.metadata
    for k in ("strength_threshold", "top_k", "skip_reason_distribution",
              "mean_strength_kept", "mean_strength_skipped"):
        assert k in md, f"missing metadata key {k}"
    # Profile recorded literally
    assert result.profile == PROFILE_HYBRID
    # top_k and threshold recorded
    assert md["top_k"] == 1
    assert md["strength_threshold"] is not None
    # Skip distribution non-empty
    assert sum(md["skip_reason_distribution"].values()) == result.skipped_count


# ---------------------------------------------------------------------------
# Helper for source-token scans (tests 9-13)
# ---------------------------------------------------------------------------
def _code_tokens(path):
    """Yield (lineno, token_string) for NAME/NUMBER/OP tokens, skipping
    comments and string literals (including docstrings)."""
    import tokenize
    out = []
    with open(path, "rb") as f:
        for tok in tokenize.tokenize(f.readline):
            if tok.type in (tokenize.NAME, tokenize.NUMBER, tokenize.OP):
                out.append((tok.start[0], tok.string))
    return out


def _has_code_token(path, name):
    """Exact identifier match against NAME/NUMBER tokens (skips strings)."""
    return any(t == name for _, t in _code_tokens(path))


def _has_code_substring(path, fragment):
    """Substring match inside NAME tokens (e.g. 'alpha_zoo' matches identifier
    'alpha_zoo_write')."""
    return any(fragment in t for _, t in _code_tokens(path))


# ---------------------------------------------------------------------------
# 9. validation_thresholds_unchanged
# ---------------------------------------------------------------------------
def test_9_validation_thresholds_unchanged():
    """The aggregation module must not import or modify any validator
    threshold in CODE (docstring prose is allowed)."""
    import zangetsu.services.signal_aggregation as agg_mod
    forbidden = [
        "entry_rank_threshold",
        "exit_rank_threshold",
        "rank_window",
        "validator_threshold",
        "VAL_MIN_TRADES",
        "validation_threshold",
    ]
    for token in forbidden:
        assert not _has_code_substring(agg_mod.__file__, token), (
            f"{token!r} appears in CODE of signal_aggregation.py "
            f"— validation invariant violated"
        )


# ---------------------------------------------------------------------------
# 10. cost_model_unchanged
# ---------------------------------------------------------------------------
def test_10_cost_model_unchanged():
    """Aggregation must not reference cost-model knobs in code."""
    import zangetsu.services.signal_aggregation as agg_mod
    forbidden = [
        "cost_bps",
        "cost_model",
        "fee_bps",
        "slippage_bps",
        "round_total_cost",
        "FEE_BPS",
        "SLIPPAGE",
    ]
    for token in forbidden:
        assert not _has_code_substring(agg_mod.__file__, token), (
            f"{token!r} appears in CODE of signal_aggregation.py "
            f"— cost invariant violated"
        )


# ---------------------------------------------------------------------------
# 11. A2_MIN_TRADES_unchanged
# ---------------------------------------------------------------------------
def test_11_a2_min_trades_unchanged():
    """A2_MIN_TRADES is locked at 25; aggregation must not touch it in code."""
    import zangetsu.services.signal_aggregation as agg_mod
    forbidden_exact = [
        "A2_MIN_TRADES",
        "MIN_TRADES",
        "a2_min_trades",
        "MIN_TRADE_COUNT",
    ]
    for token in forbidden_exact:
        assert not _has_code_token(agg_mod.__file__, token), (
            f"identifier {token!r} appears in CODE of signal_aggregation.py "
            f"— A2 invariant violated"
        )


# ---------------------------------------------------------------------------
# 12. no_alpha_zoo_write_path
# ---------------------------------------------------------------------------
def test_12_no_alpha_zoo_write_path():
    """Aggregation must not import / invoke alpha_zoo write helpers in code."""
    import zangetsu.services.signal_aggregation as agg_mod
    forbidden_exact = [
        "alpha_zoo",
        "ALPHA_ZOO",
        "alpha_zoo_injection",
        "champion_pipeline_staging",
        "champion_pipeline_fresh",
        "execute_insert",
        "DB_WRITE",
    ]
    for token in forbidden_exact:
        assert not _has_code_token(agg_mod.__file__, token), (
            f"identifier {token!r} appears in CODE of signal_aggregation.py "
            f"— alpha_zoo write path violated"
        )


# ---------------------------------------------------------------------------
# 13. no_canary_or_production_flags_enabled
# ---------------------------------------------------------------------------
def test_13_no_canary_or_production_flags_enabled():
    """Aggregation must not enable / set CANARY or production flags in code."""
    import zangetsu.services.signal_aggregation as agg_mod
    forbidden_exact = [
        "canary_active",
        "CANARY_ENABLED",
        "production_rollout",
        "real_capital",
        "ORDER_ROUTER",
        "order_router",
        "execute_order",
        "live_trading",
    ]
    for token in forbidden_exact:
        assert not _has_code_token(agg_mod.__file__, token), (
            f"identifier {token!r} appears in CODE of signal_aggregation.py "
            f"— CANARY/prod invariant violated"
        )
