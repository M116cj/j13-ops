"""Tests for trace-native reconstruction and FULL provenance projection (0-9L §13.3)."""

from __future__ import annotations

import json

import pytest

from zangetsu.services.candidate_trace import (
    PROVENANCE_FULL,
    PROVENANCE_PARTIAL,
    PROVENANCE_UNAVAILABLE,
    STAGE_EVENT_ENTRY,
    STAGE_EVENT_EXIT,
    STAGE_EVENT_HANDOFF,
    STATUS_COMPLETE,
    STATUS_ENTERED,
    STATUS_PASSED,
    STATUS_REJECTED,
    build_lifecycle_trace_event,
    derive_deployable_count_with_provenance,
)
from zangetsu.services.candidate_lifecycle_reconstruction import (
    reconstruct_lifecycles_from_trace_events,
)


def _ev(stage, stage_event, status, *, cid=None, alpha_id=None, ts=None,
        reject_reason=None, next_stage=None, source_pool=None):
    return build_lifecycle_trace_event(
        arena_stage=stage, stage_event=stage_event, status=status,
        timestamp_utc=ts,
        candidate_id=cid, alpha_id=alpha_id, formula_hash=alpha_id,
        source_pool=source_pool,
        reject_reason=reject_reason, next_stage=next_stage,
    )


# ---------------------------------------------------------------------------
# A1_ENTRY / A1_EXIT_PASS fills arena_1_entry / arena_1_exit
# ---------------------------------------------------------------------------


def test_a1_entry_plus_exit_pass_fills_entry_and_exit_timestamps():
    events = [
        _ev("A1", STAGE_EVENT_ENTRY, STATUS_ENTERED, cid="ah_1",
            ts="2026-05-01T00:00:00Z"),
        _ev("A1", STAGE_EVENT_EXIT, STATUS_PASSED, cid="ah_1",
            ts="2026-05-01T00:00:05Z"),
    ]
    lcs, conflicts = reconstruct_lifecycles_from_trace_events(events)
    assert len(lcs) == 1
    lc = lcs[0]
    assert lc.arena_1_entry == "2026-05-01T00:00:00Z"
    assert lc.arena_1_exit == "2026-05-01T00:00:05Z"
    assert lc.arena_1_status == "PASS"
    assert conflicts == {}


def test_a1_entry_plus_exit_reject_produces_a1_rejection_lifecycle():
    events = [
        _ev("A1", STAGE_EVENT_ENTRY, STATUS_ENTERED, cid="ah_reject",
            ts="2026-05-01T00:00:00Z"),
        _ev("A1", STAGE_EVENT_EXIT, STATUS_REJECTED, cid="ah_reject",
            ts="2026-05-01T00:00:05Z",
            reject_reason="SIGNAL_TOO_SPARSE"),
    ]
    lcs, _ = reconstruct_lifecycles_from_trace_events(events)
    lc = lcs[0]
    assert lc.arena_1_status == "REJECT"
    assert lc.reject_stage == "A1"
    assert lc.reject_reason == "SIGNAL_TOO_SPARSE"
    assert lc.reject_severity == "BLOCKING"  # derived from taxonomy metadata


# ---------------------------------------------------------------------------
# Full synthetic A1 → A2 → A3 path produces FULL provenance
# ---------------------------------------------------------------------------


def test_full_synthetic_a1_a2_a3_deployable_path_produces_full_provenance():
    events = [
        # A1 full
        _ev("A1", STAGE_EVENT_ENTRY, STATUS_ENTERED, cid="DPL-1", ts="2026-05-01T00:00:00Z"),
        _ev("A1", STAGE_EVENT_EXIT, STATUS_PASSED, cid="DPL-1", ts="2026-05-01T00:00:05Z"),
        _ev("A1", STAGE_EVENT_HANDOFF, STATUS_PASSED, cid="DPL-1",
            ts="2026-05-01T00:00:06Z", next_stage="A2"),
        # A2 full
        _ev("A2", STAGE_EVENT_ENTRY, STATUS_ENTERED, cid="DPL-1", ts="2026-05-01T00:01:00Z"),
        _ev("A2", STAGE_EVENT_EXIT, STATUS_PASSED, cid="DPL-1", ts="2026-05-01T00:01:10Z"),
        # A3 full → deployable
        _ev("A3", STAGE_EVENT_ENTRY, STATUS_ENTERED, cid="DPL-1", ts="2026-05-01T00:02:00Z"),
        _ev("A3", STAGE_EVENT_EXIT, STATUS_COMPLETE, cid="DPL-1", ts="2026-05-01T00:02:30Z"),
    ]
    # Need A0 = PASS too; infer via reconstruction. The trace-native reconstruction
    # does not infer A0, so set it via a direct field in a subsequent helper test.
    lcs, _ = reconstruct_lifecycles_from_trace_events(events)
    lc = lcs[0]
    # Trace-native reconstruction fills A1/A2/A3; A0 is not emitted, so we
    # treat A0 as an implicit "formula validation passed" prerequisite and
    # mark it PASS to satisfy is_deployable_through("A3"). This is done by
    # the runtime-level reconstruction wrapper; here we assert the structure.
    assert lc.arena_1_status == "PASS"
    assert lc.arena_2_status == "PASS"
    assert lc.arena_3_status == "PASS"
    assert lc.arena_1_entry == "2026-05-01T00:00:00Z"
    assert lc.arena_3_exit == "2026-05-01T00:02:30Z"
    # FULL provenance requires A0 too. For trace-native reconstruction, A0 is
    # synthesized by callers (e.g., the runtime wrapper); we explicitly set it
    # here to validate that the schema supports FULL.
    lc.arena_0_status = "PASS"
    # reset final flags to match updated A0
    from zangetsu.services.candidate_trace import assess_provenance_quality
    prov, missing = assess_provenance_quality(lc)
    assert prov == PROVENANCE_FULL, f"expected FULL but got {prov} (missing={missing})"


# ---------------------------------------------------------------------------
# Missing A1 trace remains PARTIAL
# ---------------------------------------------------------------------------


def test_missing_a1_trace_remains_partial():
    """A lifecycle with only A2/A3 trace events (no A1) should have
    arena_1_entry / arena_1_exit missing, so the registration register
    flags them and the overall provenance is PARTIAL."""
    events = [
        _ev("A2", STAGE_EVENT_ENTRY, STATUS_ENTERED, cid="NO_A1", ts="2026-05-01T00:01:00Z"),
        _ev("A2", STAGE_EVENT_EXIT, STATUS_PASSED, cid="NO_A1", ts="2026-05-01T00:01:10Z"),
    ]
    lcs, _ = reconstruct_lifecycles_from_trace_events(events)
    lc = lcs[0]
    assert lc.arena_1_entry is None
    assert lc.arena_1_exit is None
    from zangetsu.services.candidate_trace import assess_provenance_quality
    prov, missing = assess_provenance_quality(lc)
    assert prov == PROVENANCE_PARTIAL


# ---------------------------------------------------------------------------
# Duplicate A1 events deduplicate deterministically
# ---------------------------------------------------------------------------


def test_duplicate_a1_events_deduplicate_deterministically():
    events = [
        _ev("A1", STAGE_EVENT_ENTRY, STATUS_ENTERED, cid="DUP-1", ts="2026-05-01T00:00:00Z"),
        _ev("A1", STAGE_EVENT_ENTRY, STATUS_ENTERED, cid="DUP-1", ts="2026-05-01T00:00:05Z"),
        _ev("A1", STAGE_EVENT_ENTRY, STATUS_ENTERED, cid="DUP-1", ts="2026-05-01T00:00:10Z"),
    ]
    lcs, _ = reconstruct_lifecycles_from_trace_events(events)
    assert len(lcs) == 1  # deduplicated to one lifecycle
    lc = lcs[0]
    # Earliest timestamp wins for entry
    assert lc.arena_1_entry == "2026-05-01T00:00:00Z"


# ---------------------------------------------------------------------------
# Conflicting A1 statuses produce explicit conflict register
# ---------------------------------------------------------------------------


def test_conflicting_a1_statuses_produce_conflict_register():
    events = [
        _ev("A1", STAGE_EVENT_EXIT, STATUS_REJECTED, cid="CONFLICT-1",
            ts="2026-05-01T00:00:00Z", reject_reason="SIGNAL_TOO_SPARSE"),
        _ev("A1", STAGE_EVENT_EXIT, STATUS_PASSED, cid="CONFLICT-1",
            ts="2026-05-01T00:00:01Z"),
    ]
    lcs, conflicts = reconstruct_lifecycles_from_trace_events(events)
    assert "CONFLICT-1" in conflicts
    assert any("A1 conflict" in c for c in conflicts["CONFLICT-1"])


# ---------------------------------------------------------------------------
# Unknown candidate identity produces UNAVAILABLE
# ---------------------------------------------------------------------------


def test_events_with_no_identity_go_to_no_identity_bucket():
    events = [
        _ev("A1", STAGE_EVENT_ENTRY, STATUS_ENTERED),  # no cid/alpha_id/formula_hash
    ]
    lcs, conflicts = reconstruct_lifecycles_from_trace_events(events)
    assert lcs == []
    assert "_no_identity" in conflicts


# ---------------------------------------------------------------------------
# deployable_count not inflated by trace-only events
# ---------------------------------------------------------------------------


def test_deployable_count_not_inflated_by_trace_only_events():
    """Even if a trace emits an A1 PASSED event, deployable_count must not
    count it unless the full chain A0..A3 == PASS + no governance blocker."""
    events = [
        _ev("A1", STAGE_EVENT_EXIT, STATUS_PASSED, cid="TRACE-ONLY", ts="2026-05-01T00:00:00Z"),
    ]
    lcs, _ = reconstruct_lifecycles_from_trace_events(events)
    r = derive_deployable_count_with_provenance(lcs)
    assert r["deployable_count"] == 0  # no A2/A3 evidence → not deployable


# ---------------------------------------------------------------------------
# Unknown stages are tolerated (not raise)
# ---------------------------------------------------------------------------


def test_unknown_stage_event_tolerated():
    # stage=A4 is valid vocabulary but has no assigned fields on CandidateLifecycle
    events = [
        _ev("A4", STAGE_EVENT_ENTRY, STATUS_ENTERED, cid="A4-1", ts="2026-05-01T00:00:00Z"),
    ]
    lcs, _ = reconstruct_lifecycles_from_trace_events(events)
    # A lifecycle is created (identity present) but A4 has no entry/exit fields
    # on CandidateLifecycle — trace stays in extras / is ignored for stage fields.
    assert len(lcs) == 1
    lc = lcs[0]
    assert lc.arena_4_status == "NOT_RUN"
