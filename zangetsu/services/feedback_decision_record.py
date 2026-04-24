"""Dry-run feedback decision record (TEAM ORDER 0-9O-A).

This module builds an append-only ``feedback_decision_record`` event that
captures a dry-run budget recommendation. The record is **never applied**
to generation runtime in 0-9O-A — the builder enforces::

    mode = "DRY_RUN"
    applied = False

The builder rejects any attempt to set ``applied=True`` by overwriting it
back to ``False`` at construction time, so a caller bug cannot produce a
record that claims to have been applied.

Telemetry version: "1".
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, List, Mapping, Optional

TELEMETRY_VERSION = "1"
EVENT_TYPE_FEEDBACK_DECISION_RECORD = "feedback_decision_record"

MODE_DRY_RUN = "DRY_RUN"
MODE_MUST_EQUAL = "DRY_RUN"
APPLIED_MUST_EQUAL_FALSE = False

CONFIDENCE_LOW = "LOW"
CONFIDENCE_MEDIUM = "MEDIUM"
CONFIDENCE_HIGH = "HIGH"

# Safety constraints embedded in every record.
DEFAULT_SAFETY_CONSTRAINTS = (
    "A2_MIN_TRADES_UNCHANGED",
    "ARENA_PASS_FAIL_LOGIC_UNCHANGED",
    "CHAMPION_PROMOTION_UNCHANGED",
    "DEPLOYABLE_COUNT_SEMANTICS_UNCHANGED",
    "EXECUTION_CAPITAL_RISK_UNCHANGED",
    "EXPLORATION_FLOOR_GE_0_05",
    "NOT_APPLIED_TO_RUNTIME",
    "DRY_RUN_MODE_ENFORCED",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_decision_id() -> str:
    return "dec-" + uuid.uuid4().hex[:16]


@dataclass
class FeedbackDecisionRecord:
    """Append-only dry-run record. The mode / applied fields are enforced
    post-init so a caller cannot construct an applied record via kwargs.
    """

    run_id: str
    observed_bottleneck: str = "UNKNOWN"
    top_reject_reasons: List[str] = field(default_factory=list)
    previous_profile_weights: dict = field(default_factory=dict)
    proposed_profile_weights_dry_run: dict = field(default_factory=dict)
    profile_scores: dict = field(default_factory=dict)
    expected_effect: str = "DRY_RUN_ONLY_NO_EFFECT_APPLIED"
    confidence: str = CONFIDENCE_LOW
    min_sample_size_met: bool = False
    safety_constraints: List[str] = field(
        default_factory=lambda: list(DEFAULT_SAFETY_CONSTRAINTS)
    )
    reason: str = ""
    source: str = "feedback_decision_record"
    telemetry_version: str = TELEMETRY_VERSION
    decision_id: str = field(default_factory=_new_decision_id)
    created_at: str = field(default_factory=_utc_now_iso)
    mode: str = MODE_DRY_RUN
    mode_must_equal: str = MODE_MUST_EQUAL
    applied: bool = False
    applied_must_equal_false: bool = True

    def __post_init__(self) -> None:
        # Invariant enforcement — bug-proof against caller attempts to
        # construct an applied record.
        self.mode = MODE_DRY_RUN
        self.mode_must_equal = MODE_MUST_EQUAL
        self.applied = APPLIED_MUST_EQUAL_FALSE
        self.applied_must_equal_false = True
        if not isinstance(self.safety_constraints, list):
            self.safety_constraints = list(DEFAULT_SAFETY_CONSTRAINTS)
        if not self.safety_constraints:
            self.safety_constraints = list(DEFAULT_SAFETY_CONSTRAINTS)
        if not isinstance(self.top_reject_reasons, list):
            self.top_reject_reasons = []
        if not isinstance(self.previous_profile_weights, Mapping):
            self.previous_profile_weights = {}
        if not isinstance(self.proposed_profile_weights_dry_run, Mapping):
            self.proposed_profile_weights_dry_run = {}
        if not isinstance(self.profile_scores, Mapping):
            self.profile_scores = {}

    def to_event(self) -> dict:
        payload = asdict(self)
        payload["event_type"] = EVENT_TYPE_FEEDBACK_DECISION_RECORD
        # Re-enforce invariants at serialization time as a second line of
        # defense (e.g. if a caller mutated the dataclass field directly).
        payload["mode"] = MODE_DRY_RUN
        payload["mode_must_equal"] = MODE_MUST_EQUAL
        payload["applied"] = APPLIED_MUST_EQUAL_FALSE
        payload["applied_must_equal_false"] = True
        return payload


def build_feedback_decision_record(
    *,
    run_id: str,
    previous_profile_weights: Optional[Mapping[str, float]] = None,
    proposed_profile_weights_dry_run: Optional[Mapping[str, float]] = None,
    profile_scores: Optional[Mapping[str, float]] = None,
    observed_bottleneck: str = "UNKNOWN",
    top_reject_reasons: Optional[List[str]] = None,
    expected_effect: str = "DRY_RUN_ONLY_NO_EFFECT_APPLIED",
    confidence: str = CONFIDENCE_LOW,
    min_sample_size_met: bool = False,
    safety_constraints: Optional[List[str]] = None,
    reason: str = "",
    source: str = "feedback_decision_record",
    **ignored: Any,
) -> FeedbackDecisionRecord:
    """Construct an append-only dry-run ``feedback_decision_record``.

    Any attempt to pass ``applied=True`` or ``mode="APPLIED"`` via
    ``**ignored`` is dropped — the dataclass post-init resets those fields
    unconditionally.
    """
    return FeedbackDecisionRecord(
        run_id=run_id,
        previous_profile_weights=dict(previous_profile_weights or {}),
        proposed_profile_weights_dry_run=dict(
            proposed_profile_weights_dry_run or {}
        ),
        profile_scores=dict(profile_scores or {}),
        observed_bottleneck=observed_bottleneck,
        top_reject_reasons=list(top_reject_reasons or []),
        expected_effect=expected_effect,
        confidence=confidence,
        min_sample_size_met=min_sample_size_met,
        safety_constraints=(
            list(safety_constraints)
            if safety_constraints
            else list(DEFAULT_SAFETY_CONSTRAINTS)
        ),
        reason=reason,
        source=source,
    )


def safe_build_feedback_decision_record(
    **kwargs: Any,
) -> Optional[FeedbackDecisionRecord]:
    """Exception-safe wrapper. Returns None on failure."""
    try:
        return build_feedback_decision_record(**kwargs)
    except Exception:
        return None


def serialize_feedback_decision_record(
    record: FeedbackDecisionRecord,
) -> str:
    """JSON-serialize a record. Never raises (returns empty string on error)."""
    try:
        return json.dumps(record.to_event(), sort_keys=True)
    except Exception:
        return ""
