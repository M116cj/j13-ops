"""Tests for zangetsu.services.arena_pass_rate_telemetry (P7-PR4-LITE).

Schema, counter conservation, rate calculation, rejection distribution,
generation-profile fallback, deployable_count linkage, failure safety,
and behavior invariance.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys

import pytest

from zangetsu.services.arena_pass_rate_telemetry import (
    ArenaBatchMetrics,
    ArenaStageMetrics,
    ArenaStageSummary,
    EVENT_TYPE_ARENA_BATCH_METRICS,
    EVENT_TYPE_ARENA_STAGE_SUMMARY,
    RejectReasonCounter,
    TELEMETRY_VERSION,
    UNAVAILABLE_FINGERPRINT,
    UNKNOWN_PROFILE_ID,
    build_arena_batch_metrics,
    build_arena_stage_summary,
    compute_pass_rate,
    compute_reject_rate,
    required_batch_fields,
    required_summary_fields,
    safe_emit_arena_metrics,
    valid_stages,
    validate_counter_conservation,
)


# ---------------------------------------------------------------------------
# 12.1 Schema tests
# ---------------------------------------------------------------------------


def test_arena_batch_metrics_schema_contains_required_fields():
    fields = required_batch_fields()
    for must_have in (
        "telemetry_version", "run_id", "batch_id",
        "generation_profile_id", "generation_profile_fingerprint",
        "arena_stage",
        "entered_count", "passed_count", "rejected_count",
        "skipped_count", "error_count", "in_flight_count",
        "pass_rate", "reject_rate",
        "top_reject_reason", "reject_reason_distribution",
        "deployable_count",
        "timestamp_start", "timestamp_end",
        "source",
    ):
        assert must_have in fields, f"required field {must_have!r} missing"


def test_arena_stage_summary_schema_contains_required_fields():
    fields = required_summary_fields()
    for must_have in (
        "telemetry_version", "run_id", "batch_id", "arena_stage",
        "entered_count", "passed_count", "rejected_count",
        "skipped_count", "error_count", "in_flight_count",
        "pass_rate", "reject_rate",
        "top_3_reject_reasons", "bottleneck_score",
        "timestamp", "source",
    ):
        assert must_have in fields, f"required field {must_have!r} missing"


def test_arena_batch_metrics_serializes_to_json():
    b = ArenaBatchMetrics(run_id="r1", batch_id="b1", arena_stage="A2",
                          entered_count=100, passed_count=6, rejected_count=90,
                          skipped_count=4)
    d = b.to_dict()
    assert d["event_type"] == EVENT_TYPE_ARENA_BATCH_METRICS
    assert d["telemetry_version"] == TELEMETRY_VERSION
    s = b.to_json()
    parsed = json.loads(s)
    assert parsed["arena_stage"] == "A2"


def test_arena_stage_summary_serializes_to_json():
    s = ArenaStageSummary(run_id="r1", batch_id="ALL", arena_stage="A2",
                          entered_count=100, passed_count=6, rejected_count=94,
                          bottleneck_score=0.94)
    d = s.to_dict()
    assert d["event_type"] == EVENT_TYPE_ARENA_STAGE_SUMMARY
    json.dumps(d)  # must round-trip


def test_valid_stages_includes_a0_through_a5():
    stages = set(valid_stages())
    for s in ("A0", "A1", "A2", "A3", "A4", "A5", "UNKNOWN"):
        assert s in stages


# ---------------------------------------------------------------------------
# 12.2 Counter conservation tests
# ---------------------------------------------------------------------------


def test_closed_stage_counter_conservation():
    ok, reason = validate_counter_conservation(
        entered_count=100, passed_count=10, rejected_count=85,
        skipped_count=3, error_count=2, in_flight_count=0,
        open_stage=False,
    )
    assert ok, reason


def test_closed_stage_rejects_nonzero_in_flight():
    ok, reason = validate_counter_conservation(
        entered_count=100, passed_count=10, rejected_count=85,
        skipped_count=3, error_count=0, in_flight_count=2,
        open_stage=False,
    )
    assert not ok
    assert "in_flight_count" in reason


def test_open_stage_counter_conservation_with_in_flight():
    ok, reason = validate_counter_conservation(
        entered_count=100, passed_count=10, rejected_count=85,
        skipped_count=3, error_count=0, in_flight_count=2,
        open_stage=True,
    )
    assert ok, reason


def test_counter_conservation_rejects_invalid_counts():
    ok, reason = validate_counter_conservation(
        entered_count=100, passed_count=50, rejected_count=20,  # 50+20 != 100
        skipped_count=0, error_count=0,
        open_stage=False,
    )
    assert not ok
    assert "conservation" in reason


def test_counter_conservation_rejects_negative_counter():
    ok, reason = validate_counter_conservation(
        entered_count=10, passed_count=-1, rejected_count=11,
    )
    assert not ok
    assert "negative" in reason


def test_arena_stage_metrics_accumulator_preserves_conservation():
    m = ArenaStageMetrics(arena_stage="A2", run_id="r", batch_id="b")
    for _ in range(10):
        m.on_entered()
    m.on_passed()
    for _ in range(8):
        m.on_rejected("SIGNAL_TOO_SPARSE")
    m.on_skipped("CORRELATION_DUPLICATE")
    m.mark_closed()
    ok, _ = validate_counter_conservation(
        m.entered_count, m.passed_count, m.rejected_count,
        m.skipped_count, m.error_count, m.in_flight_count, open_stage=False,
    )
    assert ok
    assert m.entered_count == 10
    assert m.passed_count == 1
    assert m.rejected_count == 8
    assert m.skipped_count == 1


def test_arena_stage_metrics_drains_in_flight_on_close():
    m = ArenaStageMetrics(arena_stage="A2", run_id="r", batch_id="b")
    for _ in range(5):
        m.on_entered()
    m.on_passed()
    # 4 still in_flight
    m.mark_closed()
    # Drained into skipped_count
    assert m.skipped_count == 4
    assert m.in_flight_count == 0
    ok, _ = validate_counter_conservation(
        m.entered_count, m.passed_count, m.rejected_count,
        m.skipped_count, m.error_count, m.in_flight_count, open_stage=False,
    )
    assert ok


# ---------------------------------------------------------------------------
# 12.3 Rate calculation tests
# ---------------------------------------------------------------------------


def test_pass_rate_calculation():
    assert compute_pass_rate(10, 100) == 0.1
    assert compute_pass_rate(50, 100) == 0.5


def test_reject_rate_calculation():
    assert compute_reject_rate(90, 100) == 0.9


def test_zero_entered_count_rate_handling():
    assert compute_pass_rate(0, 0) == 0.0
    assert compute_reject_rate(0, 0) == 0.0
    # Also handles negative entered defensively
    assert compute_pass_rate(5, -1) == 0.0


def test_rate_caps_at_1_0_defensively():
    # If passed_count somehow exceeds entered_count (telemetry bug),
    # rate caps at 1.0 rather than amplifying the bug
    assert compute_pass_rate(200, 100) == 1.0
    assert compute_reject_rate(200, 100) == 1.0


# ---------------------------------------------------------------------------
# 12.4 Rejection distribution tests
# ---------------------------------------------------------------------------


def test_reject_reason_distribution_counts():
    c = RejectReasonCounter()
    c.add("SIGNAL_TOO_SPARSE")
    c.add("SIGNAL_TOO_SPARSE")
    c.add("SIGNAL_TOO_SPARSE", 3)
    c.add("OOS_FAIL")
    d = c.as_dict()
    assert d["SIGNAL_TOO_SPARSE"] == 5
    assert d["OOS_FAIL"] == 1
    assert c.total() == 6


def test_top_reject_reason_selection():
    c = RejectReasonCounter()
    c.add("OOS_FAIL", 2)
    c.add("SIGNAL_TOO_SPARSE", 10)
    c.add("UNKNOWN_REJECT", 1)
    assert c.top_reason() == "SIGNAL_TOO_SPARSE"
    top3 = c.top_n(3)
    assert top3[0] == "SIGNAL_TOO_SPARSE"
    assert "OOS_FAIL" in top3
    assert "UNKNOWN_REJECT" in top3


def test_unknown_reject_remains_visible():
    c = RejectReasonCounter()
    c.add("SIGNAL_TOO_SPARSE")
    c.add("UNKNOWN_REJECT", 5)
    d = c.as_dict()
    assert "UNKNOWN_REJECT" in d
    assert d["UNKNOWN_REJECT"] == 5


def test_empty_counter_returns_unknown_reject_as_top():
    c = RejectReasonCounter()
    assert c.top_reason() == "UNKNOWN_REJECT"


def test_counter_merge():
    c1 = RejectReasonCounter()
    c1.add("A", 3)
    c2 = RejectReasonCounter()
    c2.add("A", 2)
    c2.add("B", 1)
    c1.merge(c2)
    assert c1.as_dict() == {"A": 5, "B": 1}


# ---------------------------------------------------------------------------
# 12.5 Generation profile fallback tests
# ---------------------------------------------------------------------------


def test_generation_profile_id_used_when_available():
    m = ArenaStageMetrics(
        arena_stage="A2", run_id="r", batch_id="b",
        generation_profile_id="gp_v10_volume_l9",
        generation_profile_fingerprint="sha256:abc123",
    )
    b = build_arena_batch_metrics(m)
    assert b.generation_profile_id == "gp_v10_volume_l9"
    assert b.generation_profile_fingerprint == "sha256:abc123"


def test_unknown_profile_fallback_when_missing():
    m = ArenaStageMetrics(arena_stage="A2", run_id="r", batch_id="b")
    # Default values populate UNKNOWN / UNAVAILABLE
    assert m.generation_profile_id == UNKNOWN_PROFILE_ID
    assert m.generation_profile_fingerprint == UNAVAILABLE_FINGERPRINT
    b = build_arena_batch_metrics(m)
    assert b.generation_profile_id == UNKNOWN_PROFILE_ID
    assert b.generation_profile_fingerprint == UNAVAILABLE_FINGERPRINT


def test_missing_profile_does_not_block_telemetry():
    m = ArenaStageMetrics(arena_stage="A2", run_id="r", batch_id="b")
    m.on_entered()
    m.on_passed()
    m.mark_closed()
    b = build_arena_batch_metrics(m)
    # Event is produced successfully
    assert b.entered_count == 1
    assert b.passed_count == 1
    assert b.generation_profile_id == UNKNOWN_PROFILE_ID


# ---------------------------------------------------------------------------
# 12.6 Deployable count tests
# ---------------------------------------------------------------------------


def test_deployable_count_uses_authoritative_source():
    m = ArenaStageMetrics(arena_stage="A3", run_id="r", batch_id="b")
    for _ in range(10):
        m.on_entered()
    for _ in range(3):
        m.on_passed()  # A3 pass = in principle eligible
    for _ in range(7):
        m.on_rejected("OOS_FAIL")
    m.mark_closed()
    # Caller supplies authoritative deployable_count (lower than passed_count —
    # e.g., because some passed at A3 but failed downstream admission_validator)
    b = build_arena_batch_metrics(m, deployable_count=2)
    assert b.deployable_count == 2
    # Not inflated by passed_count


def test_trace_only_pass_events_do_not_inflate_deployable_count():
    """Critical: if no authoritative deployable_count is supplied, the event
    reports None (UNAVAILABLE) — NOT the passed_count."""
    m = ArenaStageMetrics(arena_stage="A3", run_id="r", batch_id="b")
    for _ in range(10):
        m.on_entered()
    for _ in range(3):
        m.on_passed()
    for _ in range(7):
        m.on_rejected("OOS_FAIL")
    m.mark_closed()
    b = build_arena_batch_metrics(m, deployable_count=None)
    assert b.deployable_count is None  # UNAVAILABLE, not 3
    assert b.passed_count == 3


def test_deployable_count_unavailable_by_default():
    m = ArenaStageMetrics(arena_stage="A2", run_id="r", batch_id="b")
    b = build_arena_batch_metrics(m)
    assert b.deployable_count is None


# ---------------------------------------------------------------------------
# 12.7 Failure safety tests
# ---------------------------------------------------------------------------


def test_metrics_emitter_failure_is_swallowed():
    def bad_writer(_s):
        raise RuntimeError("disk full")
    b = ArenaBatchMetrics(run_id="r", arena_stage="A2", entered_count=10,
                          passed_count=1, rejected_count=9)
    assert safe_emit_arena_metrics(b, writer=bad_writer) is False
    # Critically — did NOT raise


def test_metrics_emitter_returns_true_on_clean_write():
    captured = []
    b = ArenaBatchMetrics(run_id="r", arena_stage="A2", entered_count=10)
    assert safe_emit_arena_metrics(b, writer=captured.append) is True
    assert len(captured) == 1
    parsed = json.loads(captured[0])
    assert parsed["arena_stage"] == "A2"


def test_metrics_builder_failure_is_swallowed_via_emitter_wrap():
    # If someone passes a non-serializable object, emitter swallows
    class Unserialize:
        pass
    assert safe_emit_arena_metrics(Unserialize(), writer=lambda s: None) is False


def test_runtime_behavior_invariant_when_telemetry_fails():
    """Simulates an emission path that raises. The caller's control flow is
    unaffected. This mirrors the invariant the arena_pipeline.py helper
    (_emit_a1_batch_metrics_from_stats_safe) relies on."""
    control_flow_marker = []

    def bad_writer(_s):
        raise RuntimeError("logger died")

    b = ArenaBatchMetrics(run_id="r", arena_stage="A1", entered_count=5,
                          passed_count=1, rejected_count=4)
    result = safe_emit_arena_metrics(b, writer=bad_writer)
    # Caller's flow continues — emission returned False, no raise
    control_flow_marker.append("continued")
    assert result is False
    assert control_flow_marker == ["continued"]


# ---------------------------------------------------------------------------
# 12.8 Behavior-invariance tests (Phase 7)
# ---------------------------------------------------------------------------


def test_telemetry_import_does_not_pull_arena_runtime():
    # Purge arena-runtime modules to test fresh import of the telemetry
    # module does not trigger them as side effects.
    for m in list(sys.modules):
        if m.startswith("zangetsu.services.arena_") and m not in {
            "zangetsu.services.arena_rejection_taxonomy",
            "zangetsu.services.arena_telemetry",
            "zangetsu.services.arena_pass_rate_telemetry",
        }:
            sys.modules.pop(m, None)
    sys.modules.pop("zangetsu.services.arena_pass_rate_telemetry", None)
    importlib.import_module("zangetsu.services.arena_pass_rate_telemetry")
    assert "zangetsu.services.arena_pipeline" not in sys.modules
    assert "zangetsu.services.arena23_orchestrator" not in sys.modules
    assert "zangetsu.services.arena45_orchestrator" not in sys.modules


PINNED_THRESHOLDS = {
    "A2_MIN_TRADES": 25,
    "A3_SEGMENTS": 5,
    "A3_MIN_TRADES_PER_SEGMENT": 15,
    "A3_MIN_WR_PASSES": 4,
    "A3_MIN_PNL_PASSES": 4,
    "A3_WR_FLOOR": 0.45,
}


def test_no_threshold_constants_changed_under_p7_pr4_lite():
    ag = importlib.import_module("zangetsu.services.arena_gates")
    for name, expected in PINNED_THRESHOLDS.items():
        actual = getattr(ag, name, None)
        assert actual == expected, (
            f"{name} changed from {expected!r} to {actual!r} under P7-PR4-LITE"
        )


def _mk_trade(pnl, i):
    from zangetsu.services.arena_gates import Trade
    return Trade(pnl=pnl, entry_idx=i, exit_idx=i + 1)


def test_arena_pass_fail_behavior_unchanged_too_few_trades_p7_pr4_lite():
    from zangetsu.services.arena_gates import arena2_pass, A2_MIN_TRADES
    r = arena2_pass([_mk_trade(1.0, i) for i in range(A2_MIN_TRADES - 1)])
    assert r.passed is False
    assert r.reason == "too_few_trades"


def test_arena_pass_fail_behavior_unchanged_non_positive_pnl_p7_pr4_lite():
    from zangetsu.services.arena_gates import arena2_pass, A2_MIN_TRADES
    r = arena2_pass([_mk_trade(0.0, i) for i in range(A2_MIN_TRADES)])
    assert r.passed is False
    assert r.reason == "non_positive_pnl"


def test_arena_pass_fail_behavior_unchanged_edge_accept_p7_pr4_lite():
    from zangetsu.services.arena_gates import arena2_pass, A2_MIN_TRADES
    r = arena2_pass([_mk_trade(0.01, i) for i in range(A2_MIN_TRADES)])
    assert r.passed is True
    assert r.reason == "ok"


def test_champion_promotion_not_affected_by_telemetry():
    """Ensure aggregate Arena metrics do NOT expose or alter any champion
    promotion semantics. Metrics are informational only; the deployable_count
    field accepts an authoritative value from the caller (the Arena pipeline)
    and does not re-derive it."""
    m = ArenaStageMetrics(arena_stage="A3", run_id="r", batch_id="b")
    # Simulate 10 candidates with 4 passing A3
    for _ in range(10):
        m.on_entered()
    for _ in range(4):
        m.on_passed()
    for _ in range(6):
        m.on_rejected("OOS_FAIL")
    m.mark_closed()
    # Deployable != passed; only authoritative caller knows
    b = build_arena_batch_metrics(m, deployable_count=1)
    assert b.deployable_count == 1  # authoritative
    assert b.passed_count == 4      # observational
    # Telemetry does not infer promotion; it reports.


# ---------------------------------------------------------------------------
# Integration tests — build + summary
# ---------------------------------------------------------------------------


def test_build_arena_stage_summary_aggregates_batches():
    batches = [
        ArenaBatchMetrics(run_id="r", arena_stage="A2", entered_count=100,
                          passed_count=5, rejected_count=92, skipped_count=3,
                          reject_reason_distribution={"SIGNAL_TOO_SPARSE": 80,
                                                       "OOS_FAIL": 12}),
        ArenaBatchMetrics(run_id="r", arena_stage="A2", entered_count=120,
                          passed_count=8, rejected_count=110, skipped_count=2,
                          reject_reason_distribution={"SIGNAL_TOO_SPARSE": 100,
                                                       "COST_NEGATIVE": 10}),
        ArenaBatchMetrics(run_id="r", arena_stage="A1", entered_count=1000,
                          passed_count=200, rejected_count=800),
    ]
    summary = build_arena_stage_summary("A2", "r", batches)
    assert summary.arena_stage == "A2"
    assert summary.entered_count == 220
    assert summary.passed_count == 13
    assert summary.rejected_count == 202
    assert summary.skipped_count == 5
    assert "SIGNAL_TOO_SPARSE" in summary.top_3_reject_reasons


def test_build_arena_stage_summary_empty_batches_yields_zero_metrics():
    summary = build_arena_stage_summary("A2", "r", [])
    assert summary.entered_count == 0
    assert summary.pass_rate == 0.0
    assert summary.reject_rate == 0.0


# ---------------------------------------------------------------------------
# Runtime helper import check
# ---------------------------------------------------------------------------


def test_arena_pipeline_exposes_p7_pr4_lite_helper():
    ap = importlib.import_module("zangetsu.services.arena_pipeline")
    assert hasattr(ap, "_emit_a1_batch_metrics_from_stats_safe")
    assert getattr(ap, "_ARENA_PASS_RATE_TELEMETRY_AVAILABLE", False) is True


def test_arena_pipeline_helper_is_exception_safe_under_bad_stats():
    ap = importlib.import_module("zangetsu.services.arena_pipeline")
    # Pass garbage stats — helper must not raise.
    ap._emit_a1_batch_metrics_from_stats_safe(
        run_id="r", batch_id="b", entered_count=10, passed_count=1,
        stats={"reject_few_trades": "not-an-int"},  # deliberately wrong type
        log=None,
    )


def test_arena_pipeline_helper_is_exception_safe_when_log_raises():
    ap = importlib.import_module("zangetsu.services.arena_pipeline")

    class BadLog:
        def info(self, _s):
            raise RuntimeError("logger dead")

    ap._emit_a1_batch_metrics_from_stats_safe(
        run_id="r", batch_id="b", entered_count=10, passed_count=1,
        stats={"reject_few_trades": 5, "reject_val_low_sharpe": 4},
        log=BadLog(),
    )
