"""Candidate Lifecycle Trace + deployable_count source tracing (P7-PR1).

Two capabilities:

  1. ``CandidateLifecycle`` — records a single candidate's journey through
     Arena stages A0..A3 (and optional A4/A5 for forward-compat). Designed
     to be populated incrementally as each stage resolves.

  2. ``derive_deployable_count`` — given a collection of lifecycles,
     returns the deployable candidate count **together with its provenance**:
     which candidates count, at which stage they were last evaluated, and
     whether the count is authoritative or estimated. Answers 0-9E §5 q8
     ("Why is deployable_count zero?") by surfacing per-stage breakdown.

INSTRUMENTATION-ONLY guarantee (0-9E §8 / §9):
    No Arena runtime is imported or modified. This module provides the
    DATA MODEL only; population remains caller responsibility. SHADOW
    wrappers and future P7-PR2 integration bridge runtime to this API.

Status values:
    "PASS"    — candidate passed this Arena stage gate.
    "REJECT"  — candidate failed this Arena stage gate.
    "SKIPPED" — stage bypassed (e.g., earlier-stage reject makes it moot).
    "NOT_RUN" — stage has not yet executed or is not applicable.

A candidate is "deployable" iff every applicable Arena stage resolved to
PASS and no governance blocker intervened. This matches the
``deployable_candidate`` field on ``RejectionTrace``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple


# Canonical per-stage status string vocabulary.
STATUS_PASS = "PASS"
STATUS_REJECT = "REJECT"
STATUS_SKIPPED = "SKIPPED"
STATUS_NOT_RUN = "NOT_RUN"

_VALID_STATUS = (STATUS_PASS, STATUS_REJECT, STATUS_SKIPPED, STATUS_NOT_RUN)


@dataclass
class CandidateLifecycle:
    """A candidate's journey through Arena stages.

    Attributes mirror the per-stage fields on RejectionTrace so a lifecycle
    can be projected to a trace record (or vice versa) without data loss.
    """

    candidate_id: str
    alpha_id: Optional[str] = None
    formula_hash: Optional[str] = None
    source_pool: Optional[str] = None

    arena_0_status: str = STATUS_NOT_RUN
    arena_1_status: str = STATUS_NOT_RUN
    arena_2_status: str = STATUS_NOT_RUN
    arena_3_status: str = STATUS_NOT_RUN
    arena_4_status: str = STATUS_NOT_RUN  # forward-compat; A4 exists in arena_gates.py

    # If rejected, which stage rejected it?
    reject_stage: Optional[str] = None
    # Canonical rejection reason (e.g. "OOS_FAIL"). None if deployable or in-progress.
    reject_reason: Optional[str] = None

    # Governance blocker — any weight-sanity / controlled-diff / audit block.
    governance_blocker: Optional[str] = None

    def is_deployable(self) -> bool:
        """True iff every A0..A3 stage resolved PASS and no governance blocker.

        A4 is intentionally NOT required for the base deployable count (MOD-7
        legacy contract). Callers that want A4-gated deployable can call
        ``is_deployable_through(stage="A4")``.
        """
        return self.is_deployable_through(stage="A3")

    def is_deployable_through(self, stage: str = "A3") -> bool:
        """Return True iff all stages up to and including ``stage`` are PASS.

        Governance blocker short-circuits to False.
        """
        if self.governance_blocker:
            return False
        stage = stage.upper()
        order = ["A0", "A1", "A2", "A3", "A4"]
        if stage not in order:
            return False
        required = order[: order.index(stage) + 1]
        statuses = {
            "A0": self.arena_0_status,
            "A1": self.arena_1_status,
            "A2": self.arena_2_status,
            "A3": self.arena_3_status,
            "A4": self.arena_4_status,
        }
        return all(statuses[s] == STATUS_PASS for s in required)

    def current_stage(self) -> str:
        """Return the last stage that ran (or "NONE" if nothing ran yet)."""
        order: List[Tuple[str, str]] = [
            ("A4", self.arena_4_status),
            ("A3", self.arena_3_status),
            ("A2", self.arena_2_status),
            ("A1", self.arena_1_status),
            ("A0", self.arena_0_status),
        ]
        for label, status in order:
            if status != STATUS_NOT_RUN:
                return label
        return "NONE"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "alpha_id": self.alpha_id,
            "formula_hash": self.formula_hash,
            "source_pool": self.source_pool,
            "arena_0_status": self.arena_0_status,
            "arena_1_status": self.arena_1_status,
            "arena_2_status": self.arena_2_status,
            "arena_3_status": self.arena_3_status,
            "arena_4_status": self.arena_4_status,
            "reject_stage": self.reject_stage,
            "reject_reason": self.reject_reason,
            "governance_blocker": self.governance_blocker,
            "deployable": self.is_deployable(),
            "current_stage": self.current_stage(),
        }


def derive_deployable_count(
    lifecycles: Iterable[CandidateLifecycle],
    through_stage: str = "A3",
) -> Dict[str, Any]:
    """Compute deployable_count with full provenance.

    Returns a structured dict answering 0-9E §5 questions 7, 8, 10:
        - Q7: "How many candidates were rejected per reason?"
        - Q8: "Why is deployable_count zero?"
        - Q10: "How much rejection remains UNKNOWN_REJECT?"

    Structure:
        {
            "deployable_count": int,
            "total_candidates": int,
            "through_stage": "A3",
            "definition": "candidates with PASS at every stage up to A3 "
                          "AND no governance_blocker",
            "breakdown_by_current_stage": {"A0":..., "A1":..., ...},
            "breakdown_by_reject_reason": {"OOS_FAIL": N, ...},
            "deployable_ids": [...],       # truncated to 100 for report safety
            "rejected_ids_by_stage": {"A2": [...], ...},
            "non_deployable_reasons": {
                "A0": {"INVALID_FORMULA": N, ...},
                "A1": {"LOW_BACKTEST_SCORE": N, ...},
                "A2": {"OOS_FAIL": N, ...},
                "A3": {"PROMOTION_BLOCKED": N, ...},
                "GOVERNANCE": {...}
            }
        }
    """
    lifecycles = list(lifecycles)
    total = len(lifecycles)
    deployable = [lc for lc in lifecycles if lc.is_deployable_through(through_stage)]
    deployable_count = len(deployable)

    breakdown_by_stage: Dict[str, int] = {}
    breakdown_by_reason: Dict[str, int] = {}
    rejected_ids_by_stage: Dict[str, List[str]] = {}
    non_deployable_reasons: Dict[str, Dict[str, int]] = {}

    for lc in lifecycles:
        cur = lc.current_stage()
        breakdown_by_stage[cur] = breakdown_by_stage.get(cur, 0) + 1

        if lc.is_deployable_through(through_stage):
            continue

        # Not deployable — categorize.
        stage_key = lc.reject_stage if lc.reject_stage else (
            "GOVERNANCE" if lc.governance_blocker else cur
        )
        rejected_ids_by_stage.setdefault(stage_key, []).append(lc.candidate_id)

        reason_key = lc.reject_reason or (
            lc.governance_blocker or "UNKNOWN_REJECT"
        )
        breakdown_by_reason[reason_key] = breakdown_by_reason.get(reason_key, 0) + 1

        non_deployable_reasons.setdefault(stage_key, {})
        non_deployable_reasons[stage_key][reason_key] = (
            non_deployable_reasons[stage_key].get(reason_key, 0) + 1
        )

    # Truncate deployable_ids for report safety (never print unbounded lists).
    deployable_ids = [lc.candidate_id for lc in deployable][:100]

    return {
        "deployable_count": deployable_count,
        "total_candidates": total,
        "through_stage": through_stage.upper(),
        "definition": (
            f"count of candidates with PASS at every Arena stage up to "
            f"{through_stage.upper()} AND no governance_blocker set"
        ),
        "breakdown_by_current_stage": breakdown_by_stage,
        "breakdown_by_reject_reason": breakdown_by_reason,
        "deployable_ids": deployable_ids,
        "rejected_ids_by_stage": {k: v[:100] for k, v in rejected_ids_by_stage.items()},
        "non_deployable_reasons": non_deployable_reasons,
    }


def is_valid_status(status: str) -> bool:
    """Return True if ``status`` is a canonical per-stage status string."""
    return status in _VALID_STATUS


def valid_statuses() -> Tuple[str, ...]:
    """Return the canonical per-stage status vocabulary."""
    return _VALID_STATUS
