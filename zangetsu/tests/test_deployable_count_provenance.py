"""Tests for derive_deployable_count_with_provenance (0-9K §8.3)."""

from __future__ import annotations

import pytest

from zangetsu.services.candidate_trace import (
    CandidateLifecycle,
    PROVENANCE_FULL,
    PROVENANCE_PARTIAL,
    PROVENANCE_UNAVAILABLE,
    STATUS_NOT_RUN,
    STATUS_PASS,
    STATUS_REJECT,
    STATUS_SKIPPED,
    assess_provenance_quality,
    derive_deployable_count_with_provenance,
    is_valid_provenance_quality,
    valid_provenance_qualities,
)


def _full_deployable(cid: str = "FULL-1") -> CandidateLifecycle:
    lc = CandidateLifecycle(
        candidate_id=cid,
        arena_0_status=STATUS_PASS,  # required by is_deployable_through("A3")
        arena_1_status=STATUS_PASS,
        arena_2_status=STATUS_PASS,
        arena_3_status=STATUS_PASS,
        arena_1_entry="2026-04-16T00:00:00",
        arena_1_exit="2026-04-16T00:00:01",
        arena_2_entry="2026-04-16T00:00:02",
        arena_2_exit="2026-04-16T00:00:03",
        arena_3_entry="2026-04-16T00:00:04",
        arena_3_exit="2026-04-16T00:00:05",
        final_stage="A3",
        final_status="DEPLOYABLE",
    )
    return lc


def _partial_a2_reject(cid: str = "PARTIAL-1") -> CandidateLifecycle:
    return CandidateLifecycle(
        candidate_id=cid,
        arena_1_status=STATUS_PASS,
        arena_2_status=STATUS_REJECT,
        reject_stage="A2",
        reject_reason="SIGNAL_TOO_SPARSE",
        reject_category="SIGNAL_DENSITY",
        reject_severity="BLOCKING",
    )


# ---------------------------------------------------------------------------
# Provenance quality assessment
# ---------------------------------------------------------------------------


def test_provenance_unavailable_when_candidate_id_empty():
    lc = CandidateLifecycle(candidate_id="")
    prov, missing = assess_provenance_quality(lc)
    assert prov == PROVENANCE_UNAVAILABLE
    assert "candidate_id" in missing


def test_provenance_unavailable_when_no_stage_resolved():
    lc = CandidateLifecycle(candidate_id="X")
    prov, missing = assess_provenance_quality(lc)
    assert prov == PROVENANCE_UNAVAILABLE
    assert "no_stage_resolved" in missing


def test_provenance_full_for_complete_deployable():
    lc = _full_deployable()
    prov, missing = assess_provenance_quality(lc)
    assert prov == PROVENANCE_FULL
    assert missing == []


def test_provenance_partial_when_a2_entry_missing():
    lc = _full_deployable()
    lc.arena_2_entry = None
    prov, missing = assess_provenance_quality(lc)
    assert prov == PROVENANCE_PARTIAL
    assert "arena_2_entry" in missing


def test_provenance_partial_for_a2_reject_without_entry_exit_timestamps():
    lc = _partial_a2_reject()
    prov, missing = assess_provenance_quality(lc)
    assert prov == PROVENANCE_PARTIAL
    # Both arena_1_entry/exit expected (A1 PASS) and arena_2_entry/exit expected (A2 REJECT)
    assert "arena_1_entry" in missing
    assert "arena_2_exit" in missing


def test_provenance_partial_for_rejected_without_reject_reason():
    lc = CandidateLifecycle(
        candidate_id="NOREJ-1",
        arena_2_status=STATUS_REJECT,
        # reject_reason and governance_blocker both None
    )
    prov, missing = assess_provenance_quality(lc)
    assert prov == PROVENANCE_PARTIAL
    assert "reject_reason_or_governance_blocker" in missing


# ---------------------------------------------------------------------------
# derive_deployable_count_with_provenance
# ---------------------------------------------------------------------------


def test_derive_empty_lifecycles_returns_unavailable():
    r = derive_deployable_count_with_provenance([])
    assert r["deployable_count"] == 0
    assert r["total_candidates"] == 0
    assert r["confidence"] == PROVENANCE_UNAVAILABLE


def test_derive_full_confidence_when_all_lifecycles_full():
    lcs = [_full_deployable(cid=f"F-{i}") for i in range(3)]
    r = derive_deployable_count_with_provenance(lcs)
    assert r["deployable_count"] == 3
    assert r["confidence"] == PROVENANCE_FULL
    assert r["breakdown_by_provenance_quality"][PROVENANCE_FULL] == 3
    assert r["breakdown_by_provenance_quality"][PROVENANCE_PARTIAL] == 0
    assert r["breakdown_by_provenance_quality"][PROVENANCE_UNAVAILABLE] == 0
    assert set(r["deployable_candidate_ids"]) == {"F-0", "F-1", "F-2"}
    assert r["missing_field_register"] == {}


def test_derive_partial_confidence_when_some_missing_fields():
    lcs = [_full_deployable(), _partial_a2_reject()]
    r = derive_deployable_count_with_provenance(lcs)
    assert r["deployable_count"] == 1
    assert r["confidence"] == PROVENANCE_PARTIAL
    assert r["breakdown_by_provenance_quality"][PROVENANCE_FULL] == 1
    assert r["breakdown_by_provenance_quality"][PROVENANCE_PARTIAL] == 1
    assert r["breakdown_by_reject_reason"]["SIGNAL_TOO_SPARSE"] == 1


def test_derive_unavailable_confidence_when_all_lifecycles_empty_identity():
    lcs = [CandidateLifecycle(candidate_id="") for _ in range(3)]
    r = derive_deployable_count_with_provenance(lcs)
    assert r["deployable_count"] == 0
    assert r["confidence"] == PROVENANCE_UNAVAILABLE
    assert r["breakdown_by_provenance_quality"][PROVENANCE_UNAVAILABLE] == 3


def test_derive_never_fabricates_deployable_when_provenance_unavailable():
    """A lifecycle with empty candidate_id must NOT count as deployable even
    if all statuses claim PASS — the identity is missing, so we cannot claim
    the lifecycle is real."""
    lc = CandidateLifecycle(
        candidate_id="",
        arena_1_status=STATUS_PASS,
        arena_2_status=STATUS_PASS,
        arena_3_status=STATUS_PASS,
    )
    r = derive_deployable_count_with_provenance([lc])
    assert r["deployable_count"] == 0


def test_derive_governance_blocker_blocks_deployable():
    lc = _full_deployable()
    lc.governance_blocker = "a13_weight_sanity_rejected"
    r = derive_deployable_count_with_provenance([lc])
    assert r["deployable_count"] == 0
    assert r["breakdown_by_reject_reason"]["a13_weight_sanity_rejected"] == 1


def test_derive_missing_field_register_aggregates_across_lifecycles():
    lc1 = _partial_a2_reject("P-1")
    lc2 = _partial_a2_reject("P-2")
    r = derive_deployable_count_with_provenance([lc1, lc2])
    # Each partial contributes the same set of missing fields -> each count=2
    assert r["missing_field_register"].get("arena_1_entry", 0) == 2
    assert r["missing_field_register"].get("arena_2_exit", 0) == 2


def test_derive_breakdown_by_final_stage_correct():
    lcs = [
        _full_deployable("D-1"),
        _partial_a2_reject("R-1"),
        _partial_a2_reject("R-2"),
    ]
    # Set explicit final_stage for partials
    lcs[1].final_stage = "A2"
    lcs[2].final_stage = "A2"
    lcs[0].final_stage = "A3"
    r = derive_deployable_count_with_provenance(lcs)
    assert r["breakdown_by_final_stage"].get("A3") == 1
    assert r["breakdown_by_final_stage"].get("A2") == 2


def test_valid_provenance_qualities_enum():
    assert is_valid_provenance_quality("FULL")
    assert is_valid_provenance_quality("PARTIAL")
    assert is_valid_provenance_quality("UNAVAILABLE")
    assert not is_valid_provenance_quality("SORT_OF")
    assert set(valid_provenance_qualities()) == {"FULL", "PARTIAL", "UNAVAILABLE"}
