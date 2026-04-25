"""Dry-run feedback budget allocator (TEAM ORDER 0-9O-B).

Consumes ``generation_profile_metrics``-shaped inputs and produces a
``dry_run_budget_allocation`` event plus a matching
``feedback_decision_record``. The output is **never applied** to
generation runtime.

Invariants
----------

  * ``mode = "DRY_RUN"``
  * ``applied = False``
  * No ``apply()`` method exists.
  * No runtime generator imports this module.

Allocator logic
---------------

  * Confidence gate: actionable only when
    ``confidence == "CONFIDENCE_A1_A2_A3_METRICS_AVAILABLE"`` AND
    ``sample_size_rounds >= MIN_SAMPLE_SIZE_ROUNDS``.
  * Sample-size gate: low sample size → non-actionable per profile.
  * Missing A2/A3 metrics → non-actionable per profile.
  * Counter inconsistency (``UNKNOWN_REJECT`` rate >= ``UNKNOWN_REJECT_VETO``)
    → non-actionable per profile (taxonomy / visibility problem).
  * Missing required fields → non-actionable per profile (safe fallback).
  * Weight transform: ``raw_weight = max(profile_score + 1.0, 0.0)``.
  * UNKNOWN_PROFILE may not dominate: capped at ``EXPLORATION_FLOOR``
    before normalization.
  * Each actionable profile gets at least ``EXPLORATION_FLOOR``; the
    remainder is distributed proportionally to raw_weight.
  * Final weights sum to 1.0, deterministic, never negative.
  * Bottleneck explanation derived from aggregate reject-reason
    distribution.

The allocator is computation-only — it does not read or write Arena
runtime state, the database, or the filesystem (other than via callers
that may serialize the output).
"""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

# Re-use canonical constants from upstream contracts so allocator and
# producer stay in lock-step. Importing for read-only constants only —
# the allocator does not mutate any of these modules.
from zangetsu.services.generation_profile_metrics import (
    CONFIDENCE_A1_A2_A3_AVAILABLE,
    CONFIDENCE_LOW_SAMPLE_SIZE,
    CONFIDENCE_LOW_UNTIL_A2_A3,
    EXPLORATION_FLOOR,
    MIN_SAMPLE_SIZE_ROUNDS,
)
from zangetsu.services.generation_profile_identity import (
    UNAVAILABLE_FINGERPRINT,
    UNKNOWN_PROFILE_ID,
)
from zangetsu.services.feedback_decision_record import (
    DEFAULT_SAFETY_CONSTRAINTS,
    build_feedback_decision_record,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOCATOR_VERSION = "0-9O-B"
TELEMETRY_VERSION = "1"
EVENT_TYPE_DRY_RUN_BUDGET_ALLOCATION = "dry_run_budget_allocation"

MODE_DRY_RUN = "DRY_RUN"
APPLIED_FALSE = False

# Allocator-only confidence outcome (not from generation_profile_metrics).
CONFIDENCE_NO_ACTIONABLE_PROFILE = "NO_ACTIONABLE_PROFILE"

# Bottleneck classification.
BOTTLENECK_SIGNAL_TOO_SPARSE = "SIGNAL_TOO_SPARSE_DOMINANT"
BOTTLENECK_OOS_FAIL = "OOS_FAIL_DOMINANT"
BOTTLENECK_UNKNOWN_REJECT = "UNKNOWN_REJECT_DOMINANT"
BOTTLENECK_LOW_SAMPLE = "LOW_SAMPLE_SIZE"
BOTTLENECK_MISSING_A2_A3 = "MISSING_A2_A3_METRICS"
BOTTLENECK_NO_ACTIONABLE = "NO_ACTIONABLE_PROFILE"
BOTTLENECK_UNKNOWN = "UNKNOWN"

# Per-profile non-actionable reasons.
REASON_LOW_CONFIDENCE = "LOW_CONFIDENCE"
REASON_LOW_SAMPLE_SIZE = "LOW_SAMPLE_SIZE"
REASON_MISSING_A2_A3 = "MISSING_A2_A3_METRICS"
REASON_COUNTER_INCONSISTENCY = "COUNTER_INCONSISTENCY"
REASON_MISSING_FIELDS = "MISSING_REQUIRED_FIELDS"
REASON_UNKNOWN_PROFILE = "UNKNOWN_PROFILE_NOT_DOMINANT"

# Threshold above which a profile's UNKNOWN_REJECT rate is treated as a
# taxonomy / visibility breakdown (counter inconsistency proxy).
UNKNOWN_REJECT_VETO = 0.20

# Bottleneck dominance threshold — a reason must contribute at least this
# fraction of total rejects to be considered dominant.
BOTTLENECK_DOMINANCE_THRESHOLD = 0.40


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_decision_id() -> str:
    return "alloc-" + uuid.uuid4().hex[:16]


@dataclass
class DryRunBudgetAllocation:
    """One run of the allocator. Fields mirror TEAM ORDER 0-9O-B §6.2.

    The dataclass enforces ``mode = "DRY_RUN"``, ``applied = False``, and
    ``allocator_version = "0-9O-B"`` at construction and at every
    serialization. Caller-supplied overrides via kwargs are silently
    discarded — the post-init resets the invariants unconditionally.
    """

    run_id: str
    confidence: str
    input_profile_count: int
    actionable_profile_count: int
    non_actionable_profile_count: int
    previous_profile_weights: Dict[str, float] = field(default_factory=dict)
    proposed_profile_weights_dry_run: Dict[str, float] = field(default_factory=dict)
    profile_scores: Dict[str, float] = field(default_factory=dict)
    profile_ranks: Dict[str, int] = field(default_factory=dict)
    non_actionable_reasons: Dict[str, List[str]] = field(default_factory=dict)
    observed_bottleneck: str = BOTTLENECK_UNKNOWN
    top_reject_reasons: List[str] = field(default_factory=list)
    expected_effect: str = "DRY_RUN_ONLY_NO_EFFECT_APPLIED"
    safety_constraints: List[str] = field(
        default_factory=lambda: list(DEFAULT_SAFETY_CONSTRAINTS)
    )
    reason: str = ""
    decision_id: str = field(default_factory=_new_decision_id)
    created_at: str = field(default_factory=_utc_now_iso)
    telemetry_version: str = TELEMETRY_VERSION
    exploration_floor: float = EXPLORATION_FLOOR
    min_sample_size_rounds: int = MIN_SAMPLE_SIZE_ROUNDS
    mode: str = MODE_DRY_RUN
    applied: bool = APPLIED_FALSE
    allocator_version: str = ALLOCATOR_VERSION
    source: str = "feedback_budget_allocator"

    def __post_init__(self) -> None:
        # Invariants — bug-proof against caller overrides.
        self.mode = MODE_DRY_RUN
        self.applied = APPLIED_FALSE
        self.allocator_version = ALLOCATOR_VERSION
        if not isinstance(self.safety_constraints, list) or not self.safety_constraints:
            self.safety_constraints = list(DEFAULT_SAFETY_CONSTRAINTS)
        if not isinstance(self.top_reject_reasons, list):
            self.top_reject_reasons = []
        for attr in (
            "previous_profile_weights",
            "proposed_profile_weights_dry_run",
            "profile_scores",
            "profile_ranks",
            "non_actionable_reasons",
        ):
            if not isinstance(getattr(self, attr), dict):
                setattr(self, attr, {})

    def to_event(self) -> dict:
        payload = asdict(self)
        payload["event_type"] = EVENT_TYPE_DRY_RUN_BUDGET_ALLOCATION
        # Re-assert at serialization time so a post-construction mutation
        # cannot ship an applied=true record.
        payload["mode"] = MODE_DRY_RUN
        payload["applied"] = APPLIED_FALSE
        payload["allocator_version"] = ALLOCATOR_VERSION
        return payload


def required_allocation_fields() -> Tuple[str, ...]:
    """Stable list of required fields for ``DryRunBudgetAllocation``."""
    return (
        "telemetry_version", "decision_id", "run_id", "created_at",
        "mode", "applied", "confidence", "allocator_version",
        "input_profile_count", "actionable_profile_count",
        "non_actionable_profile_count",
        "exploration_floor", "min_sample_size_rounds",
        "previous_profile_weights", "proposed_profile_weights_dry_run",
        "profile_scores", "profile_ranks", "non_actionable_reasons",
        "observed_bottleneck", "top_reject_reasons",
        "expected_effect", "safety_constraints",
        "reason", "source",
    )


# ---------------------------------------------------------------------------
# Input adaptation
# ---------------------------------------------------------------------------


_REQUIRED_INPUT_FIELDS = (
    "generation_profile_id",
    "profile_score",
    "avg_a2_pass_rate",
    "avg_a3_pass_rate",
    "sample_size_rounds",
    "min_sample_size_met",
    "confidence",
)


def _coerce_metric(metric: Any) -> Optional[Mapping[str, Any]]:
    """Return a read-only view of a profile-metric input.

    Accepts either ``GenerationProfileMetrics`` instances (or any dataclass)
    or plain mappings. Returns ``None`` if the input cannot be coerced.
    """
    if metric is None:
        return None
    if isinstance(metric, Mapping):
        return metric
    # Dataclass-like — fall back to ``__dict__``.
    raw = getattr(metric, "__dict__", None)
    if isinstance(raw, dict):
        return raw
    try:
        return asdict(metric)
    except Exception:
        return None


def _has_required_fields(metric: Mapping[str, Any]) -> bool:
    for f in _REQUIRED_INPUT_FIELDS:
        if f not in metric:
            return False
    return True


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        v = float(value)
        if math.isnan(v) or math.isinf(v):
            return default
        return v
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Per-profile actionability
# ---------------------------------------------------------------------------


def evaluate_profile_actionability(
    metric: Mapping[str, Any],
) -> Tuple[bool, List[str]]:
    """Return ``(actionable, reasons)`` for a single profile metric.

    Reasons are appended in the order they were detected. Empty reasons
    means actionable. Never raises.
    """
    reasons: List[str] = []
    if not _has_required_fields(metric):
        reasons.append(REASON_MISSING_FIELDS)
        return False, reasons

    confidence = str(metric.get("confidence") or "")
    if confidence != CONFIDENCE_A1_A2_A3_AVAILABLE:
        if confidence == CONFIDENCE_LOW_UNTIL_A2_A3:
            reasons.append(REASON_MISSING_A2_A3)
        elif confidence == CONFIDENCE_LOW_SAMPLE_SIZE:
            reasons.append(REASON_LOW_SAMPLE_SIZE)
        else:
            reasons.append(REASON_LOW_CONFIDENCE)

    if not bool(metric.get("min_sample_size_met")):
        if REASON_LOW_SAMPLE_SIZE not in reasons:
            reasons.append(REASON_LOW_SAMPLE_SIZE)
    if _safe_int(metric.get("sample_size_rounds"), 0) < MIN_SAMPLE_SIZE_ROUNDS:
        if REASON_LOW_SAMPLE_SIZE not in reasons:
            reasons.append(REASON_LOW_SAMPLE_SIZE)

    a2 = _safe_float(metric.get("avg_a2_pass_rate"), 0.0)
    a3 = _safe_float(metric.get("avg_a3_pass_rate"), 0.0)
    a2_entered = _safe_int(metric.get("total_entered_a2"), 0)
    a3_entered = _safe_int(metric.get("total_entered_a3"), 0)
    if (a2 == 0.0 and a2_entered == 0) or (a3 == 0.0 and a3_entered == 0):
        # Either A2 or A3 metric is structurally absent.
        if REASON_MISSING_A2_A3 not in reasons:
            reasons.append(REASON_MISSING_A2_A3)

    unknown_rate = _safe_float(metric.get("unknown_reject_rate"), 0.0)
    if unknown_rate >= UNKNOWN_REJECT_VETO:
        reasons.append(REASON_COUNTER_INCONSISTENCY)

    return (len(reasons) == 0), reasons


# ---------------------------------------------------------------------------
# Bottleneck explanation
# ---------------------------------------------------------------------------


def classify_bottleneck(
    metrics: Sequence[Mapping[str, Any]],
    *,
    actionable_count: int,
) -> Tuple[str, List[str]]:
    """Return ``(observed_bottleneck, top_reject_reasons)`` aggregated
    across all input metrics. Never raises.
    """
    if not metrics:
        return BOTTLENECK_NO_ACTIONABLE, []
    if actionable_count == 0:
        # When nothing is actionable, the bottleneck is structural rather
        # than reason-distribution based — pick the most common blocker.
        any_missing_a2_a3 = False
        any_low_sample = False
        for m in metrics:
            conf = str(m.get("confidence") or "")
            if conf == CONFIDENCE_LOW_UNTIL_A2_A3:
                any_missing_a2_a3 = True
            elif conf == CONFIDENCE_LOW_SAMPLE_SIZE:
                any_low_sample = True
            elif not bool(m.get("min_sample_size_met")):
                any_low_sample = True
        if any_missing_a2_a3:
            return BOTTLENECK_MISSING_A2_A3, []
        if any_low_sample:
            return BOTTLENECK_LOW_SAMPLE, []
        return BOTTLENECK_NO_ACTIONABLE, []

    sparse = oos = unknown = 0.0
    for m in metrics:
        sparse += _safe_float(m.get("signal_too_sparse_count"), 0.0)
        oos += _safe_float(m.get("oos_fail_count"), 0.0)
        unknown += _safe_float(m.get("unknown_reject_count"), 0.0)

    total = sparse + oos + unknown
    top: List[str] = []
    bottleneck = BOTTLENECK_UNKNOWN
    if total <= 0:
        return BOTTLENECK_UNKNOWN, []

    contributions = [
        ("SIGNAL_TOO_SPARSE", sparse, BOTTLENECK_SIGNAL_TOO_SPARSE),
        ("OOS_FAIL", oos, BOTTLENECK_OOS_FAIL),
        ("UNKNOWN_REJECT", unknown, BOTTLENECK_UNKNOWN_REJECT),
    ]
    contributions.sort(key=lambda kv: -kv[1])
    top = [name for name, val, _ in contributions if val > 0]

    leader_name, leader_val, leader_label = contributions[0]
    if leader_val / total >= BOTTLENECK_DOMINANCE_THRESHOLD:
        bottleneck = leader_label
    return bottleneck, top


# ---------------------------------------------------------------------------
# Weight normalization
# ---------------------------------------------------------------------------


def _raw_weight_from_score(score: float) -> float:
    """``raw_weight = max(score + 1.0, 0.0)``. Score is clamped to
    ``[-1.0, 1.0]`` upstream; the floor keeps the transform stable for
    legacy / out-of-range inputs."""
    return max(_safe_float(score, 0.0) + 1.0, 0.0)


def _normalize_with_floor(
    raw_weights: Dict[str, float],
    *,
    floor: float,
    cap_overrides: Optional[Mapping[str, float]] = None,
) -> Dict[str, float]:
    """Convert raw weights into a normalized distribution where every
    profile receives at least ``floor`` and the total sums to 1.0.

    Cap overrides are applied AFTER raw-weight transformation but BEFORE
    floor allocation — used to prevent UNKNOWN_PROFILE from dominating.

    Deterministic: keys are sorted before the proportional split so the
    final dict iteration order is reproducible.
    """
    if not raw_weights:
        return {}

    cap_overrides = dict(cap_overrides or {})
    capped: Dict[str, float] = {}
    for key in sorted(raw_weights):
        w = max(0.0, _safe_float(raw_weights[key], 0.0))
        if key in cap_overrides:
            w = min(w, max(0.0, cap_overrides[key]))
        capped[key] = w

    n = len(capped)
    if n == 0:
        return {}

    floor = max(0.0, _safe_float(floor, 0.0))
    if n * floor >= 1.0:
        # Floor already saturates the budget — split evenly so every
        # profile is at least at the floor.
        even = 1.0 / n
        return {k: even for k in capped}

    floor_total = floor * n
    remainder = 1.0 - floor_total

    raw_sum = sum(capped.values())
    if raw_sum <= 0:
        even_remainder = remainder / n
        return {k: floor + even_remainder for k in capped}

    weights: Dict[str, float] = {}
    for key, raw in capped.items():
        weights[key] = floor + remainder * (raw / raw_sum)

    # Numerical safety: rebalance so the final sum is exactly 1.0.
    total = sum(weights.values())
    if total <= 0:
        even = 1.0 / n
        return {k: even for k in capped}
    scale = 1.0 / total
    rebalanced = {k: w * scale for k, w in weights.items()}
    # Ensure non-negativity (floor already guarantees this in the math
    # above; this is defense-in-depth).
    for k in rebalanced:
        if rebalanced[k] < 0:
            rebalanced[k] = 0.0
    return rebalanced


def compute_proposed_weights(
    actionable: Sequence[Mapping[str, Any]],
    *,
    floor: float = EXPLORATION_FLOOR,
    unknown_profile_cap: float = EXPLORATION_FLOOR,
) -> Dict[str, float]:
    """Compute proposed dry-run weights for the supplied actionable
    profiles. UNKNOWN_PROFILE is capped at ``unknown_profile_cap`` so it
    cannot dominate the allocation. Deterministic. Does not mutate inputs.
    """
    raw: Dict[str, float] = {}
    cap_overrides: Dict[str, float] = {}
    for m in actionable:
        pid = str(m.get("generation_profile_id") or UNKNOWN_PROFILE_ID)
        score = _safe_float(m.get("profile_score"), 0.0)
        raw[pid] = _raw_weight_from_score(score)
        if pid == UNKNOWN_PROFILE_ID:
            cap_overrides[pid] = unknown_profile_cap
    return _normalize_with_floor(
        raw, floor=floor, cap_overrides=cap_overrides
    )


def equal_weight_fallback(profiles: Sequence[str]) -> Dict[str, float]:
    """Equal-weight distribution for the supplied profile ids.
    Deterministic; sorts keys."""
    keys = sorted({str(p) for p in profiles if p is not None})
    if not keys:
        return {}
    even = 1.0 / len(keys)
    return {k: even for k in keys}


# ---------------------------------------------------------------------------
# Top-level allocator
# ---------------------------------------------------------------------------


def allocate_dry_run_budget(
    profile_metrics: Iterable[Any],
    *,
    run_id: str,
    previous_profile_weights: Optional[Mapping[str, float]] = None,
) -> DryRunBudgetAllocation:
    """Compute a dry-run budget allocation from the supplied profile
    metrics. Returns a fully populated ``DryRunBudgetAllocation`` event.

    Inputs may be ``GenerationProfileMetrics`` instances or plain dicts
    with the equivalent fields. Inputs are never mutated.

    Output is **never applied** to runtime: ``mode = "DRY_RUN"``,
    ``applied = False``. The allocator emits a non-actionable record when
    no profile clears the confidence + sample-size gates.
    """
    coerced_inputs: List[Mapping[str, Any]] = []
    coercion_failed_count = 0
    for raw in profile_metrics or ():
        m = _coerce_metric(raw)
        if m is None:
            coercion_failed_count += 1
            continue
        coerced_inputs.append(dict(m))  # local copy — never mutate caller's input

    actionable_metrics: List[Mapping[str, Any]] = []
    non_actionable_reasons: Dict[str, List[str]] = {}
    profile_scores: Dict[str, float] = {}

    for m in coerced_inputs:
        pid = str(m.get("generation_profile_id") or UNKNOWN_PROFILE_ID)
        profile_scores[pid] = _safe_float(m.get("profile_score"), 0.0)
        ok, reasons = evaluate_profile_actionability(m)
        if ok:
            actionable_metrics.append(m)
        else:
            non_actionable_reasons[pid] = list(reasons)

    # Add coercion failures as a synthetic non-actionable bucket so the
    # caller can see they were skipped.
    if coercion_failed_count > 0:
        non_actionable_reasons.setdefault("__coercion_failed__", []).append(
            REASON_MISSING_FIELDS
        )

    actionable_count = len(actionable_metrics)
    non_actionable_count = (
        len(non_actionable_reasons)
        - (1 if "__coercion_failed__" in non_actionable_reasons else 0)
    )
    input_profile_count = len(coerced_inputs)

    bottleneck, top_reject_reasons = classify_bottleneck(
        coerced_inputs, actionable_count=actionable_count
    )

    if actionable_count == 0:
        confidence_label = CONFIDENCE_NO_ACTIONABLE_PROFILE
        previous = dict(previous_profile_weights or {})
        if previous:
            proposed = dict(previous)
            # Renormalize previous weights so the dry-run output remains a
            # valid distribution even if the caller-provided dict does not
            # sum exactly to 1.0.
            total = sum(max(0.0, _safe_float(v, 0.0)) for v in proposed.values())
            if total > 0:
                proposed = {k: max(0.0, _safe_float(v, 0.0)) / total for k, v in proposed.items()}
            else:
                proposed = equal_weight_fallback(list(proposed.keys()))
        else:
            # Fallback: equal weight across all observed profiles.
            ids = [
                str(m.get("generation_profile_id") or UNKNOWN_PROFILE_ID)
                for m in coerced_inputs
            ]
            proposed = equal_weight_fallback(ids)
        ranks: Dict[str, int] = {}
        return DryRunBudgetAllocation(
            run_id=str(run_id or ""),
            confidence=confidence_label,
            input_profile_count=input_profile_count,
            actionable_profile_count=0,
            non_actionable_profile_count=non_actionable_count,
            previous_profile_weights=dict(previous_profile_weights or {}),
            proposed_profile_weights_dry_run=proposed,
            profile_scores=profile_scores,
            profile_ranks=ranks,
            non_actionable_reasons=non_actionable_reasons,
            observed_bottleneck=bottleneck,
            top_reject_reasons=top_reject_reasons,
            expected_effect="DRY_RUN_NON_ACTIONABLE_NO_RECOMMENDATION_APPLIED",
            reason=(
                "no actionable profile passed confidence + sample-size + "
                "A2/A3 metrics gates"
            ),
        )

    proposed = compute_proposed_weights(actionable_metrics)

    # Profile ranks (1-based, by profile_score desc; deterministic ties via id).
    ranking_pairs: List[Tuple[float, str]] = sorted(
        (
            (-_safe_float(m.get("profile_score"), 0.0),
             str(m.get("generation_profile_id") or UNKNOWN_PROFILE_ID))
            for m in actionable_metrics
        ),
    )
    ranks = {pid: i + 1 for i, (_, pid) in enumerate(ranking_pairs)}

    return DryRunBudgetAllocation(
        run_id=str(run_id or ""),
        confidence=CONFIDENCE_A1_A2_A3_AVAILABLE,
        input_profile_count=input_profile_count,
        actionable_profile_count=actionable_count,
        non_actionable_profile_count=non_actionable_count,
        previous_profile_weights=dict(previous_profile_weights or {}),
        proposed_profile_weights_dry_run=proposed,
        profile_scores=profile_scores,
        profile_ranks=ranks,
        non_actionable_reasons=non_actionable_reasons,
        observed_bottleneck=bottleneck,
        top_reject_reasons=top_reject_reasons,
        expected_effect="DRY_RUN_ALLOCATION_RECOMMENDED_NOT_APPLIED",
        reason=(
            f"{actionable_count} of {input_profile_count} profile(s) cleared "
            "all gates; weights are dry-run only"
        ),
    )


def to_feedback_decision_record(allocation: DryRunBudgetAllocation):
    """Convert a ``DryRunBudgetAllocation`` into a
    ``FeedbackDecisionRecord``. Reuses the existing 0-9O-A append-only
    builder so that ``mode=DRY_RUN`` / ``applied=False`` invariants are
    enforced by two independent layers.
    """
    return build_feedback_decision_record(
        run_id=allocation.run_id,
        previous_profile_weights=allocation.previous_profile_weights,
        proposed_profile_weights_dry_run=allocation.proposed_profile_weights_dry_run,
        profile_scores=allocation.profile_scores,
        observed_bottleneck=allocation.observed_bottleneck,
        top_reject_reasons=allocation.top_reject_reasons,
        expected_effect=allocation.expected_effect,
        confidence=allocation.confidence,
        min_sample_size_met=(
            allocation.confidence == CONFIDENCE_A1_A2_A3_AVAILABLE
        ),
        safety_constraints=allocation.safety_constraints,
        reason=allocation.reason,
        source="feedback_budget_allocator",
    )


def serialize_allocation(allocation: DryRunBudgetAllocation) -> str:
    """JSON-serialize a ``DryRunBudgetAllocation``. Never raises."""
    try:
        return json.dumps(allocation.to_event(), sort_keys=True)
    except Exception:
        return ""


def safe_allocate_dry_run_budget(
    profile_metrics: Iterable[Any],
    *,
    run_id: str,
    previous_profile_weights: Optional[Mapping[str, float]] = None,
) -> Optional[DryRunBudgetAllocation]:
    """Exception-safe wrapper. Returns ``None`` on any failure so a bug
    in the allocator cannot propagate into a caller. The allocator is
    pure — there is no runtime caller, but offline reports / tests may
    prefer a None-on-failure contract."""
    try:
        return allocate_dry_run_budget(
            profile_metrics,
            run_id=run_id,
            previous_profile_weights=previous_profile_weights,
        )
    except Exception:
        return None
