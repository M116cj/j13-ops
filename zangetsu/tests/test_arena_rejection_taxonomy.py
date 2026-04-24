"""Tests for zangetsu.services.arena_rejection_taxonomy (P7-PR1).

Covers:
- Taxonomy completeness (all 18 reasons, 14 categories, 4 severities present).
- Metadata consistency (each reason maps to category / severity / stage).
- UNKNOWN_REJECT existence and non-abuse.
- classify() deterministic mapping for exact + substring matches.
- classify() never raises; UNKNOWN_REJECT fallback only when warranted.
"""

from __future__ import annotations

import pytest

from zangetsu.services.arena_rejection_taxonomy import (
    ArenaStage,
    REJECTION_METADATA,
    RAW_TO_REASON,
    RejectionCategory,
    RejectionReason,
    RejectionSeverity,
    all_reasons,
    classify,
    metadata_for,
)


# Expected canonical vocabulary per 0-9E §6.
_EXPECTED_REASONS = {
    "INVALID_FORMULA",
    "UNSUPPORTED_OPERATOR",
    "WINDOW_INSUFFICIENT",
    "NON_CAUSAL_RISK",
    "NAN_INF_OUTPUT",
    "LOW_BACKTEST_SCORE",
    "HIGH_DRAWDOWN",
    "HIGH_TURNOVER",
    "COST_NEGATIVE",
    "FRESH_FAIL",
    "OOS_FAIL",
    "REGIME_FAIL",
    "SIGNAL_TOO_SPARSE",
    "SIGNAL_TOO_DENSE",
    "CORRELATION_DUPLICATE",
    "PROMOTION_BLOCKED",
    "GOVERNANCE_BLOCKED",
    "UNKNOWN_REJECT",
}

_EXPECTED_CATEGORIES = {
    "FORMULA_QUALITY",
    "DATA_QUALITY",
    "CAUSALITY",
    "BACKTEST_SCORE",
    "RISK",
    "COST",
    "FRESH_VALIDATION",
    "OOS_VALIDATION",
    "REGIME",
    "SIGNAL_DENSITY",
    "CORRELATION",
    "PROMOTION",
    "GOVERNANCE",
    "UNKNOWN",
}

_EXPECTED_SEVERITIES = {"INFO", "WARN", "BLOCKING", "FATAL"}


def test_all_18_mandatory_reasons_present():
    actual = {r.value for r in RejectionReason}
    assert actual == _EXPECTED_REASONS, (
        f"Taxonomy missing / extra reasons: "
        f"missing={_EXPECTED_REASONS - actual}, extra={actual - _EXPECTED_REASONS}"
    )


def test_all_14_mandatory_categories_present():
    actual = {c.value for c in RejectionCategory}
    assert actual == _EXPECTED_CATEGORIES


def test_all_4_severity_levels_present():
    actual = {s.value for s in RejectionSeverity}
    assert actual == _EXPECTED_SEVERITIES


def test_unknown_reject_exists():
    assert RejectionReason.UNKNOWN_REJECT.value == "UNKNOWN_REJECT"
    assert RejectionReason.UNKNOWN_REJECT in REJECTION_METADATA


def test_every_reason_has_complete_metadata():
    """Each of the 18 reasons must have metadata with all 5 required fields."""
    for reason in RejectionReason:
        assert reason in REJECTION_METADATA, f"Missing metadata: {reason}"
        meta = metadata_for(reason)
        assert meta.reason == reason
        assert isinstance(meta.category, RejectionCategory)
        assert isinstance(meta.severity, RejectionSeverity)
        assert isinstance(meta.default_arena_stage, ArenaStage)
        assert meta.description and isinstance(meta.description, str)
        assert len(meta.description) > 10, (
            f"Description for {reason.value} is too terse: {meta.description!r}"
        )


def test_every_category_reachable_from_at_least_one_reason():
    """Every canonical category should be used by at least one reason."""
    used = {meta.category for meta in REJECTION_METADATA.values()}
    # UNKNOWN is only used by UNKNOWN_REJECT — that's allowed.
    assert used == {c for c in RejectionCategory}


def test_classify_exact_match_returns_canonical_reason():
    # arena_gates.py emits GateResult(reason="too_few_trades") for A2 under-volume rejects.
    reason, cat, stage = classify(raw_reason="too_few_trades", arena_stage="A2")
    assert reason == RejectionReason.SIGNAL_TOO_SPARSE
    assert cat == RejectionCategory.SIGNAL_DENSITY
    assert stage == ArenaStage.A2


def test_classify_stage_hint_overrides_default_when_unknown():
    # If metadata default is UNKNOWN (e.g. GOVERNANCE_BLOCKED), stage hint wins.
    reason, cat, stage = classify(raw_reason="a13_weight_sanity_rejected", arena_stage="A1")
    assert reason == RejectionReason.GOVERNANCE_BLOCKED
    assert stage == ArenaStage.A1  # overridden from default UNKNOWN


def test_classify_substring_match():
    # Matches substring within a log line.
    raw = "A2 REJECTED id=42 BTCUSDT: validation split fail details=..."
    reason, cat, stage = classify(raw_reason=raw, arena_stage="A2")
    assert reason == RejectionReason.OOS_FAIL
    assert cat == RejectionCategory.OOS_VALIDATION


def test_classify_unmappable_returns_unknown_reject():
    reason, cat, stage = classify(raw_reason="completely_novel_rejection_reason_xyz")
    assert reason == RejectionReason.UNKNOWN_REJECT
    assert cat == RejectionCategory.UNKNOWN


def test_classify_none_raw_returns_unknown_reject():
    reason, cat, stage = classify(raw_reason=None)
    assert reason == RejectionReason.UNKNOWN_REJECT


def test_classify_empty_raw_returns_unknown_reject():
    reason, cat, stage = classify(raw_reason="   ")
    assert reason == RejectionReason.UNKNOWN_REJECT


def test_classify_does_not_return_unknown_when_deterministic_mapping_available():
    """UNKNOWN_REJECT must not be used when a deterministic mapping exists."""
    for raw, expected_reason in RAW_TO_REASON.items():
        got_reason, _, _ = classify(raw_reason=raw)
        assert got_reason == expected_reason, (
            f"Deterministic mapping broken: raw={raw!r} expected={expected_reason} got={got_reason}"
        )
        assert got_reason != RejectionReason.UNKNOWN_REJECT, (
            f"UNKNOWN_REJECT returned for deterministic-mapped raw={raw!r}"
        )


def test_classify_never_raises_on_weird_inputs():
    # Numbers, control chars, giant strings — never raise.
    for weird in [
        "\x00\x01\x02",
        "\n\n\n",
        "x" * 10000,
        "reject",
        "",
        None,
        "null",
    ]:
        classify(raw_reason=weird, arena_stage="A2")
        classify(raw_reason=weird, arena_stage=None)


def test_arena_stages_complete():
    expected = {"A0", "A1", "A2", "A3", "A4", "UNKNOWN"}
    actual = {s.value for s in ArenaStage}
    assert actual == expected


def test_all_reasons_iterable_in_declaration_order():
    reasons = all_reasons()
    assert len(reasons) == 18
    assert reasons[0] == RejectionReason.INVALID_FORMULA
    assert reasons[-1] == RejectionReason.UNKNOWN_REJECT


def test_raw_to_reason_coverage_includes_arena_gates_strings():
    """Sanity: classifier knows about arena_gates.py-emitted reason strings."""
    # These are the exact reason strings emitted by arena_gates.GateResult:
    for s in ("too_few_trades", "non_positive_pnl", "wrong_segment_count"):
        assert s in RAW_TO_REASON, f"Missing mapping for arena_gates.py reason: {s!r}"


def test_raw_to_reason_coverage_includes_arena_pipeline_counters():
    """Sanity: A1 reject-counter keys from arena_pipeline.py stats are mapped."""
    for s in (
        "reject_few_trades",
        "reject_neg_pnl",
        "reject_val_constant",
        "reject_val_error",
        "reject_val_few_trades",
        "reject_val_neg_pnl",
        "reject_val_low_sharpe",
        "reject_val_low_wr",
    ):
        assert s in RAW_TO_REASON, f"Missing mapping for A1 counter: {s!r}"
