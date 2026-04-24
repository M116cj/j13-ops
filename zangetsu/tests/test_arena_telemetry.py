"""Tests for zangetsu.services.arena_telemetry (P7-PR1).

Covers:
- RejectionTrace construction + required field presence.
- JSON round-trip (to_json / from_dict).
- TelemetryCollector aggregation: counts_by_reason, counts_by_stage,
  arena2_breakdown, unknown_reject_ratio.
- make_rejection_trace convenience helper invokes taxonomy correctly.
- CandidateLifecycle + derive_deployable_count provenance.
"""

from __future__ import annotations

import json

import pytest

from zangetsu.services.arena_rejection_taxonomy import (
    ArenaStage,
    RejectionReason,
)
from zangetsu.services.arena_telemetry import (
    RejectionTrace,
    TelemetryCollector,
    arena2_extra_fields,
    make_rejection_trace,
    required_fields,
)
from zangetsu.services.candidate_trace import (
    CandidateLifecycle,
    STATUS_NOT_RUN,
    STATUS_PASS,
    STATUS_REJECT,
    STATUS_SKIPPED,
    derive_deployable_count,
    is_valid_status,
    valid_statuses,
)


# ---------------------------------------------------------------------------
# RejectionTrace
# ---------------------------------------------------------------------------


def test_required_fields_declared():
    fields = required_fields()
    assert "candidate_id" in fields
    assert "reject_reason" in fields
    assert "timestamp_utc" in fields
    # 0-9E §7 requires 20 mandatory fields.
    assert len(fields) == 20


def test_arena2_extras_declared():
    extras = arena2_extra_fields()
    assert "oos_score" in extras
    assert "promotion_blocker" in extras
    assert len(extras) == 11


def test_trace_minimum_construction():
    t = RejectionTrace(candidate_id="c1")
    d = t.to_dict()
    assert d["candidate_id"] == "c1"
    assert d["reject_reason"] == "UNKNOWN_REJECT"
    assert d["arena_stage"] == "UNKNOWN"
    assert d["deployable_candidate"] is False
    assert d["timestamp_utc"]  # default-filled RFC3339


def test_trace_json_round_trip():
    t1 = RejectionTrace(
        candidate_id="c1",
        alpha_id="a1",
        formula_hash="deadbeef",
        arena_stage="A2",
        reject_reason="OOS_FAIL",
        reject_category="OOS_VALIDATION",
        reject_severity="BLOCKING",
        run_id="test-run",
        oos_score=0.1,
    )
    s = t1.to_json()
    parsed = json.loads(s)
    t2 = RejectionTrace.from_dict(parsed)
    assert t2.candidate_id == "c1"
    assert t2.arena_stage == "A2"
    assert t2.reject_reason == "OOS_FAIL"
    assert t2.oos_score == pytest.approx(0.1)


def test_trace_missing_required_fields_detection():
    t = RejectionTrace(
        candidate_id="c1",
        alpha_id=None,  # explicitly None
        formula_hash=None,
    )
    missing = t.missing_required_fields()
    assert "alpha_id" in missing
    assert "formula_hash" in missing
    # candidate_id is set
    assert "candidate_id" not in missing


def test_make_rejection_trace_via_taxonomy_classify():
    t = make_rejection_trace(
        candidate_id="c42",
        raw_reason="validation split fail",
        arena_stage="A2",
        extras={"oos_score": 0.3, "turnover": 0.8},
    )
    assert t.candidate_id == "c42"
    assert t.reject_reason == RejectionReason.OOS_FAIL.value
    assert t.arena_stage == ArenaStage.A2.value
    assert t.oos_score == pytest.approx(0.3)
    assert t.turnover == pytest.approx(0.8)


def test_make_rejection_trace_unknown_fallback():
    t = make_rejection_trace(
        candidate_id="c1",
        raw_reason="totally_unknown_reason_abc",
    )
    assert t.reject_reason == RejectionReason.UNKNOWN_REJECT.value


# ---------------------------------------------------------------------------
# TelemetryCollector
# ---------------------------------------------------------------------------


def test_collector_empty():
    c = TelemetryCollector(run_id="r1")
    assert c.total_rejections() == 0
    assert c.unknown_reject_ratio() == 0.0
    assert c.counts_by_reason() == {}
    assert c.counts_by_stage() == {}
    assert c.arena2_breakdown() == {}


def test_collector_aggregates_counts():
    c = TelemetryCollector(run_id="r1")
    c.record(make_rejection_trace("c1", raw_reason="too_few_trades", arena_stage="A2"))
    c.record(make_rejection_trace("c2", raw_reason="too_few_trades", arena_stage="A2"))
    c.record(make_rejection_trace("c3", raw_reason="validation split fail", arena_stage="A2"))
    c.record(make_rejection_trace("c4", raw_reason="reject_val_low_sharpe", arena_stage="A1"))
    c.record(make_rejection_trace("c5", raw_reason="unmappable_xyz"))  # -> UNKNOWN

    assert c.total_rejections() == 5
    counts = c.counts_by_reason()
    assert counts["SIGNAL_TOO_SPARSE"] == 2
    assert counts["OOS_FAIL"] == 1
    assert counts["LOW_BACKTEST_SCORE"] == 1
    assert counts["UNKNOWN_REJECT"] == 1

    stage = c.counts_by_stage()
    assert stage["A2"] == 3
    assert stage["A1"] == 1
    assert stage["UNKNOWN"] == 1

    a2 = c.arena2_breakdown()
    assert a2["SIGNAL_TOO_SPARSE"] == 2
    assert a2["OOS_FAIL"] == 1
    assert "LOW_BACKTEST_SCORE" not in a2  # A1, not A2


def test_collector_unknown_reject_ratio():
    c = TelemetryCollector(run_id="r1")
    for i in range(8):
        c.record(make_rejection_trace(f"c{i}", raw_reason="too_few_trades", arena_stage="A2"))
    for i in range(2):
        c.record(make_rejection_trace(f"u{i}", raw_reason="unmappable_blob"))
    assert c.unknown_reject_ratio() == pytest.approx(0.2)  # 2 / 10


def test_collector_summary_serializable_json():
    c = TelemetryCollector(run_id="r1")
    c.record(make_rejection_trace("c1", raw_reason="too_few_trades", arena_stage="A2"))
    s = c.to_json()
    parsed = json.loads(s)
    assert parsed["run_id"] == "r1"
    assert parsed["total_rejections"] == 1
    assert parsed["unknown_reject_ratio"] == 0.0
    assert "generated_at_utc" in parsed


# ---------------------------------------------------------------------------
# CandidateLifecycle + derive_deployable_count
# ---------------------------------------------------------------------------


def test_lifecycle_default_is_not_deployable():
    lc = CandidateLifecycle(candidate_id="c1")
    assert lc.is_deployable() is False
    assert lc.current_stage() == "NONE"


def test_lifecycle_full_pass_through_a3_is_deployable():
    lc = CandidateLifecycle(
        candidate_id="c1",
        arena_0_status=STATUS_PASS,
        arena_1_status=STATUS_PASS,
        arena_2_status=STATUS_PASS,
        arena_3_status=STATUS_PASS,
    )
    assert lc.is_deployable() is True
    assert lc.current_stage() == "A3"


def test_lifecycle_reject_anywhere_blocks_deployment():
    lc = CandidateLifecycle(
        candidate_id="c1",
        arena_0_status=STATUS_PASS,
        arena_1_status=STATUS_REJECT,
        arena_2_status=STATUS_SKIPPED,
        arena_3_status=STATUS_SKIPPED,
    )
    assert lc.is_deployable() is False
    assert lc.current_stage() == "A3"  # stage status != NOT_RUN


def test_lifecycle_governance_blocker_blocks_deployment_even_with_all_pass():
    lc = CandidateLifecycle(
        candidate_id="c1",
        arena_0_status=STATUS_PASS,
        arena_1_status=STATUS_PASS,
        arena_2_status=STATUS_PASS,
        arena_3_status=STATUS_PASS,
        governance_blocker="a13_weight_sanity_rejected",
    )
    assert lc.is_deployable() is False


def test_derive_deployable_count_basic():
    lifecycles = [
        CandidateLifecycle(
            candidate_id=f"c{i}",
            arena_0_status=STATUS_PASS,
            arena_1_status=STATUS_PASS,
            arena_2_status=STATUS_PASS,
            arena_3_status=STATUS_PASS,
        )
        for i in range(3)
    ] + [
        CandidateLifecycle(
            candidate_id=f"r{i}",
            arena_0_status=STATUS_PASS,
            arena_1_status=STATUS_PASS,
            arena_2_status=STATUS_REJECT,
            reject_stage="A2",
            reject_reason="OOS_FAIL",
        )
        for i in range(7)
    ]
    out = derive_deployable_count(lifecycles)
    assert out["deployable_count"] == 3
    assert out["total_candidates"] == 10
    assert out["breakdown_by_reject_reason"]["OOS_FAIL"] == 7
    assert "A2" in out["rejected_ids_by_stage"]
    assert len(out["rejected_ids_by_stage"]["A2"]) == 7
    assert out["non_deployable_reasons"]["A2"]["OOS_FAIL"] == 7


def test_derive_deployable_count_answers_q8_zero_case():
    # All rejected at A2 — deployable_count = 0 with clear provenance.
    lifecycles = [
        CandidateLifecycle(
            candidate_id=f"r{i}",
            arena_0_status=STATUS_PASS,
            arena_1_status=STATUS_PASS,
            arena_2_status=STATUS_REJECT,
            reject_stage="A2",
            reject_reason="OOS_FAIL",
        )
        for i in range(5)
    ]
    out = derive_deployable_count(lifecycles)
    assert out["deployable_count"] == 0
    # Must explain WHY it's zero
    assert "A2" in out["non_deployable_reasons"]
    assert out["non_deployable_reasons"]["A2"]["OOS_FAIL"] == 5


def test_derive_deployable_count_governance_blocker_surfaces():
    lifecycles = [
        CandidateLifecycle(
            candidate_id="g1",
            arena_0_status=STATUS_PASS,
            arena_1_status=STATUS_PASS,
            arena_2_status=STATUS_PASS,
            arena_3_status=STATUS_PASS,
            governance_blocker="a13_weight_sanity_rejected",
        )
    ]
    out = derive_deployable_count(lifecycles)
    assert out["deployable_count"] == 0
    # Governance blocker surfaces under its own key
    assert "GOVERNANCE" in out["non_deployable_reasons"]


def test_valid_statuses():
    assert is_valid_status("PASS")
    assert is_valid_status("REJECT")
    assert is_valid_status("SKIPPED")
    assert is_valid_status("NOT_RUN")
    assert not is_valid_status("MAYBE")
    assert set(valid_statuses()) == {"PASS", "REJECT", "SKIPPED", "NOT_RUN"}
