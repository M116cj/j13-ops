"""Sparse-Candidate Dry-Run Feedback Consumer (TEAM ORDER 0-9R-IMPL-DRY).

Consumes a ``DryRunBudgetAllocation`` (produced by 0-9O-B's
:mod:`feedback_budget_allocator`) plus a 0-9P-AUDIT attribution
verdict, and produces a :class:`SparseCandidateDryRunPlan` whose
output **never** reaches generation runtime.

Three-layer dry-run invariant
-----------------------------

  1. ``mode = "DRY_RUN"`` and ``applied = False`` are reset in
     ``__post_init__`` regardless of caller-supplied kwargs.
  2. ``to_event()`` re-asserts the same fields at serialization time.
  3. No ``apply`` / ``commit`` / ``execute`` symbol is exported.
  4. The consumer module is **not** imported by any runtime
     module (``arena_pipeline`` / ``arena23_orchestrator`` /
     ``arena45_orchestrator`` / ``alpha_engine`` / ``live/``) —
     verified by source-text tests in the suite.

Allowed intervention classes
----------------------------

Only these three from 0-9R taxonomy:

  - ``PB-FLOOR``: enforce ``EXPLORATION_FLOOR`` per profile.
  - ``PB-DIV``: preserve ≥ ``DIVERSITY_CAP_MIN`` profiles at floor.
  - ``PB-SHIFT``: produce dry-run shift recommendation only.

Forbidden classes (PB-SUPPRESS / PB-QUARANTINE / PB-RESURRECT /
PB-MUT / PB-DENSITY / PRE-A2-SCREEN / threshold change / Arena
relaxation / candidate prefilter / operator pool change / mutation
probability change / crossover probability change / real sampling
weight change / real budget change) are not implemented; future
orders may add them under explicit j13 authorization.

Gating chain
------------

A plan is ``ACTIONABLE_DRY_RUN`` only when **all** of:

  - allocation ``mode == "DRY_RUN"`` and ``applied is False``
  - allocation ``confidence == "CONFIDENCE_A1_A2_A3_METRICS_AVAILABLE"``
  - allocation ``actionable_profile_count >= 2``
  - allocation has no ``COUNTER_INCONSISTENCY`` reason
  - aggregate UNKNOWN_REJECT rate < ``UNKNOWN_REJECT_VETO``
  - attribution verdict is not ``"RED"``

When any check fails the plan is ``NON_ACTIONABLE`` (or ``BLOCKED``
for governance-grade failures like applied=True input). The plan is
still emitted with ``applied=False`` so downstream observers can
record the attempt.

Smoothing pipeline
------------------

  1. ``smoothed_proposed_weights = ema(allocator_weights, history,
     alpha=ema_alpha)`` — α ≤ 0.2, window ≥ 5.
  2. ``max_step_limited_weights`` — per-profile delta clipped to
     ±``max_step_abs`` against ``previous_profile_weights``.
  3. ``final_dry_run_weights`` — re-applies floor + diversity cap +
     renormalization so the result sums to 1.0 and respects all
     PB-FLOOR / PB-DIV invariants.

The consumer never performs DB writes, network IO, or filesystem
writes. Plans are serialized via ``to_event()`` for callers that
choose to log them; that's it.
"""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
)

from zangetsu.services.feedback_budget_allocator import (
    BOTTLENECK_NO_ACTIONABLE,
    CONFIDENCE_NO_ACTIONABLE_PROFILE,
    DryRunBudgetAllocation,
    REASON_COUNTER_INCONSISTENCY,
)
from zangetsu.services.feedback_decision_record import (
    DEFAULT_SAFETY_CONSTRAINTS,
)
from zangetsu.services.generation_profile_identity import (
    UNKNOWN_PROFILE_ID,
)
from zangetsu.services.generation_profile_metrics import (
    CONFIDENCE_A1_A2_A3_AVAILABLE,
    EXPLORATION_FLOOR,
    MIN_SAMPLE_SIZE_ROUNDS,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONSUMER_VERSION = "0-9R-IMPL-DRY"
TELEMETRY_VERSION = "1"
EVENT_TYPE_SPARSE_CANDIDATE_DRY_RUN_PLAN = "sparse_candidate_dry_run_plan"

MODE_DRY_RUN = "DRY_RUN"
APPLIED_FALSE = False

# Smoothing limits (per TEAM ORDER 0-9R-IMPL-DRY §6).
EMA_ALPHA_MAX = 0.20
DEFAULT_EMA_ALPHA = 0.20
SMOOTHING_WINDOW_MIN = 5
DEFAULT_SMOOTHING_WINDOW = 5

# Step-size limit: max per-profile change per round (10 percentage points).
DEFAULT_MAX_STEP_ABS = 0.10

# Diversity cap: at least N profiles must be at >= EXPLORATION_FLOOR.
DEFAULT_DIVERSITY_CAP_MIN = 2

# UNKNOWN_REJECT veto — consumer-level (stricter than allocator's 0.20).
# At consumer time we want true visibility, not just enough to refuse the
# offending profile.
UNKNOWN_REJECT_VETO = 0.05

# Allowed intervention class codes (per 0-9R taxonomy).
INTERVENTION_PB_FLOOR = "PB-FLOOR"
INTERVENTION_PB_DIV = "PB-DIV"
INTERVENTION_PB_SHIFT = "PB-SHIFT"
ALLOWED_INTERVENTIONS = (
    INTERVENTION_PB_FLOOR,
    INTERVENTION_PB_DIV,
    INTERVENTION_PB_SHIFT,
)

# Plan status enumeration.
PLAN_STATUS_ACTIONABLE = "ACTIONABLE_DRY_RUN"
PLAN_STATUS_NON_ACTIONABLE = "NON_ACTIONABLE"
PLAN_STATUS_BLOCKED = "BLOCKED"

# Block reason enumeration (governance-grade gating).
BLOCK_INPUT_NOT_DRY_RUN = "INPUT_MODE_NOT_DRY_RUN"
BLOCK_INPUT_APPLIED_TRUE = "INPUT_APPLIED_TRUE"
BLOCK_INPUT_BAD_VERSION = "INPUT_BAD_ALLOCATOR_VERSION"
BLOCK_RED_ATTRIBUTION = "ATTRIBUTION_VERDICT_RED"
BLOCK_LOW_CONFIDENCE = "LOW_CONFIDENCE"
BLOCK_LOW_SAMPLE_SIZE = "LOW_SAMPLE_SIZE"
BLOCK_FEW_ACTIONABLE = "FEWER_THAN_TWO_ACTIONABLE_PROFILES"
BLOCK_UNKNOWN_REJECT_HIGH = "UNKNOWN_REJECT_TOO_HIGH"
BLOCK_COUNTER_INCONSISTENCY = "COUNTER_INCONSISTENCY"

# Attribution verdict labels (mirror tools.profile_attribution_audit).
VERDICT_GREEN = "GREEN"
VERDICT_YELLOW = "YELLOW"
VERDICT_RED = "RED"
VERDICT_UNAVAILABLE = "UNAVAILABLE"

# Default consumer-side rollback expectations.
DEFAULT_ROLLBACK_REQUIREMENTS = (
    "previous_profile_weights_must_be_recoverable",
    "no_runtime_apply_attempted",
    "no_change_to_actual_generation_budget",
    "no_change_to_actual_sampling_weights",
    "no_change_to_thresholds",
    "no_change_to_arena_pass_fail",
    "no_change_to_champion_promotion",
    "no_change_to_deployable_count_semantics",
    "consumer_state_purgeable_without_side_effects",
)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_plan_id() -> str:
    return "plan-" + uuid.uuid4().hex[:16]


@dataclass
class SparseCandidateDryRunPlan:
    """Per-cycle plan produced by the consumer. Append-only.

    The dataclass enforces ``mode = "DRY_RUN"``, ``applied = False``,
    and ``consumer_version = "0-9R-IMPL-DRY"`` at construction and at
    serialization. Caller-supplied overrides are silently discarded.
    """

    run_id: str
    plan_id: str = field(default_factory=_new_plan_id)
    created_at: str = field(default_factory=_utc_now_iso)
    mode: str = MODE_DRY_RUN
    applied: bool = APPLIED_FALSE
    consumer_version: str = CONSUMER_VERSION
    source_allocation_id: str = ""
    attribution_verdict: str = VERDICT_UNAVAILABLE
    confidence: str = ""
    plan_status: str = PLAN_STATUS_NON_ACTIONABLE
    actionable_profile_count: int = 0
    observed_bottleneck: str = BOTTLENECK_NO_ACTIONABLE
    selected_interventions: List[str] = field(default_factory=list)
    previous_profile_weights: Dict[str, float] = field(default_factory=dict)
    allocator_proposed_weights: Dict[str, float] = field(default_factory=dict)
    smoothed_proposed_weights: Dict[str, float] = field(default_factory=dict)
    max_step_limited_weights: Dict[str, float] = field(default_factory=dict)
    final_dry_run_weights: Dict[str, float] = field(default_factory=dict)
    exploration_floor: float = EXPLORATION_FLOOR
    diversity_cap: int = DEFAULT_DIVERSITY_CAP_MIN
    ema_alpha: float = DEFAULT_EMA_ALPHA
    smoothing_window: int = DEFAULT_SMOOTHING_WINDOW
    max_step_abs: float = DEFAULT_MAX_STEP_ABS
    safety_constraints: List[str] = field(
        default_factory=lambda: list(DEFAULT_SAFETY_CONSTRAINTS)
    )
    non_actionable_reasons: Dict[str, List[str]] = field(default_factory=dict)
    block_reasons: List[str] = field(default_factory=list)
    expected_effect: str = "DRY_RUN_ONLY_NO_EFFECT_APPLIED"
    rollback_requirements: List[str] = field(
        default_factory=lambda: list(DEFAULT_ROLLBACK_REQUIREMENTS)
    )
    reason: str = ""
    source: str = "feedback_budget_consumer"
    telemetry_version: str = TELEMETRY_VERSION

    def __post_init__(self) -> None:
        # Invariants — bug-proof against caller overrides.
        self.mode = MODE_DRY_RUN
        self.applied = APPLIED_FALSE
        self.consumer_version = CONSUMER_VERSION
        if not isinstance(self.safety_constraints, list) or not self.safety_constraints:
            self.safety_constraints = list(DEFAULT_SAFETY_CONSTRAINTS)
        if not isinstance(self.rollback_requirements, list) or not self.rollback_requirements:
            self.rollback_requirements = list(DEFAULT_ROLLBACK_REQUIREMENTS)
        if not isinstance(self.selected_interventions, list):
            self.selected_interventions = []
        if not isinstance(self.block_reasons, list):
            self.block_reasons = []
        for attr in (
            "previous_profile_weights",
            "allocator_proposed_weights",
            "smoothed_proposed_weights",
            "max_step_limited_weights",
            "final_dry_run_weights",
            "non_actionable_reasons",
        ):
            if not isinstance(getattr(self, attr), dict):
                setattr(self, attr, {})
        # Range-clamp smoothing knobs in case a caller supplies bad values.
        if self.ema_alpha > EMA_ALPHA_MAX or self.ema_alpha <= 0:
            self.ema_alpha = DEFAULT_EMA_ALPHA
        if self.smoothing_window < SMOOTHING_WINDOW_MIN:
            self.smoothing_window = DEFAULT_SMOOTHING_WINDOW
        if self.max_step_abs <= 0 or self.max_step_abs > 1.0:
            self.max_step_abs = DEFAULT_MAX_STEP_ABS
        if self.exploration_floor < EXPLORATION_FLOOR or self.exploration_floor >= 1.0:
            self.exploration_floor = EXPLORATION_FLOOR
        if self.diversity_cap < 1:
            self.diversity_cap = DEFAULT_DIVERSITY_CAP_MIN

    def to_event(self) -> dict:
        payload = asdict(self)
        payload["event_type"] = EVENT_TYPE_SPARSE_CANDIDATE_DRY_RUN_PLAN
        # Re-assert at serialization time so post-construction mutation
        # cannot ship an applied=true / wrong-version / wrong-mode plan.
        payload["mode"] = MODE_DRY_RUN
        payload["applied"] = APPLIED_FALSE
        payload["consumer_version"] = CONSUMER_VERSION
        return payload


def required_plan_fields() -> Tuple[str, ...]:
    """Stable list of required fields on
    :class:`SparseCandidateDryRunPlan`. Tests use this to lock the schema."""
    return (
        "telemetry_version",
        "plan_id",
        "run_id",
        "created_at",
        "mode",
        "applied",
        "consumer_version",
        "source_allocation_id",
        "attribution_verdict",
        "confidence",
        "actionable_profile_count",
        "observed_bottleneck",
        "selected_interventions",
        "previous_profile_weights",
        "allocator_proposed_weights",
        "smoothed_proposed_weights",
        "max_step_limited_weights",
        "final_dry_run_weights",
        "exploration_floor",
        "diversity_cap",
        "ema_alpha",
        "smoothing_window",
        "max_step_abs",
        "safety_constraints",
        "non_actionable_reasons",
        "expected_effect",
        "rollback_requirements",
        "source",
    )


# ---------------------------------------------------------------------------
# Smoothing pipeline
# ---------------------------------------------------------------------------


def ema_smooth(
    new_weights: Mapping[str, float],
    history: Optional[Sequence[Mapping[str, float]]] = None,
    *,
    alpha: float = DEFAULT_EMA_ALPHA,
) -> Dict[str, float]:
    """Apply EMA smoothing across a window of prior weight snapshots
    plus the new allocator output. Returns a new dict; never mutates
    inputs.

    History is interpreted oldest-first. ``alpha`` controls the
    new-vs-old weighting; clamped to ``(0, EMA_ALPHA_MAX]``.
    """
    if alpha <= 0 or alpha > EMA_ALPHA_MAX:
        alpha = DEFAULT_EMA_ALPHA

    if not history:
        return {str(k): float(v) for k, v in new_weights.items()}

    keys = set(new_weights.keys())
    for snap in history:
        if isinstance(snap, Mapping):
            keys.update(snap.keys())

    smoothed: Dict[str, float] = {}
    for key in sorted(keys):
        # Initialize with the oldest history value (or 0.0 if missing).
        current: Optional[float] = None
        for snap in history:
            if not isinstance(snap, Mapping):
                continue
            v = snap.get(key)
            if v is None:
                continue
            try:
                vf = float(v)
            except Exception:
                continue
            if math.isnan(vf) or math.isinf(vf):
                continue
            if current is None:
                current = vf
            else:
                current = alpha * vf + (1.0 - alpha) * current
        new_v = new_weights.get(key)
        try:
            new_vf = float(new_v) if new_v is not None else 0.0
        except Exception:
            new_vf = 0.0
        if math.isnan(new_vf) or math.isinf(new_vf):
            new_vf = 0.0
        if current is None:
            smoothed[key] = new_vf
        else:
            smoothed[key] = alpha * new_vf + (1.0 - alpha) * current
    return smoothed


def limit_step(
    proposed: Mapping[str, float],
    previous: Optional[Mapping[str, float]] = None,
    *,
    max_step_abs: float = DEFAULT_MAX_STEP_ABS,
) -> Dict[str, float]:
    """Clip per-profile delta against ``previous`` to ±``max_step_abs``.

    If ``previous`` is empty / None, returns ``proposed`` unchanged.
    Never mutates inputs. Negative weights are floored to 0.0.
    """
    if not previous:
        return {str(k): max(0.0, float(v)) for k, v in proposed.items()}

    if max_step_abs <= 0 or max_step_abs > 1.0:
        max_step_abs = DEFAULT_MAX_STEP_ABS

    out: Dict[str, float] = {}
    for key in sorted(proposed.keys()):
        try:
            target = float(proposed[key])
        except Exception:
            target = 0.0
        try:
            prev = float(previous.get(key, target))
        except Exception:
            prev = target
        delta = target - prev
        if delta > max_step_abs:
            target = prev + max_step_abs
        elif delta < -max_step_abs:
            target = prev - max_step_abs
        out[key] = max(0.0, target)
    return out


def enforce_floor_and_diversity(
    weights: Mapping[str, float],
    *,
    floor: float = EXPLORATION_FLOOR,
    diversity_cap_min: int = DEFAULT_DIVERSITY_CAP_MIN,
) -> Dict[str, float]:
    """Apply PB-FLOOR + PB-DIV invariants and renormalize to sum 1.0.

    Rules:
      - Every key gets at least ``floor``.
      - At least ``diversity_cap_min`` profiles end up >= floor.
      - UNKNOWN_PROFILE is capped at ``floor`` (cannot dominate).
      - Final weights sum to 1.0 (within numerical precision).
      - Never mutates inputs.
    """
    if not weights:
        return {}

    floor = max(0.0, min(floor, 1.0))
    if diversity_cap_min < 1:
        diversity_cap_min = 1

    keys = sorted(weights.keys())
    n = len(keys)

    # Cap UNKNOWN_PROFILE before normalization.
    raw: Dict[str, float] = {}
    for k in keys:
        try:
            v = max(0.0, float(weights[k]))
        except Exception:
            v = 0.0
        if k == UNKNOWN_PROFILE_ID:
            v = min(v, floor)
        raw[k] = v

    # If the floor saturates the budget (rare), split evenly.
    if n * floor >= 1.0:
        even = 1.0 / n
        return {k: even for k in keys}

    floor_total = floor * n
    remainder = 1.0 - floor_total
    raw_sum = sum(raw.values())

    if raw_sum <= 0:
        # No signal; equal split above floor.
        return {k: floor + remainder / n for k in keys}

    out: Dict[str, float] = {}
    for k in keys:
        out[k] = floor + remainder * (raw[k] / raw_sum)

    # Final sum-to-1.0 sanity rebalance.
    total = sum(out.values())
    if total <= 0:
        return {k: 1.0 / n for k in keys}
    scale = 1.0 / total
    for k in out:
        out[k] = max(0.0, out[k] * scale)

    # Diversity cap: ensure at least diversity_cap_min entries >= floor.
    above_floor = sum(1 for v in out.values() if v >= floor - 1e-12)
    if above_floor < diversity_cap_min:
        # Rare path: floor enforcement above guarantees this for
        # well-formed input. Keep the safety net for paranoid cases.
        even = 1.0 / n
        return {k: even for k in keys}

    return out


# ---------------------------------------------------------------------------
# Gating
# ---------------------------------------------------------------------------


def _has_counter_inconsistency(
    non_actionable_reasons: Mapping[str, Sequence[str]],
) -> bool:
    try:
        for reasons in non_actionable_reasons.values():
            if REASON_COUNTER_INCONSISTENCY in (reasons or ()):
                return True
    except Exception:
        return False
    return False


def _aggregate_unknown_reject_rate(
    profile_metrics: Optional[Sequence[Mapping[str, Any]]],
) -> float:
    """Sum unknown_reject_count across actionable + non-actionable
    profiles relative to the total reject count. Returns 0.0 if no
    metrics are supplied (caller is expected to pass them when
    actionability is being computed)."""
    if not profile_metrics:
        return 0.0
    unknown_total = 0
    rejects_total = 0
    for m in profile_metrics:
        if not isinstance(m, Mapping):
            continue
        try:
            sparse = int(m.get("signal_too_sparse_count") or 0)
            oos = int(m.get("oos_fail_count") or 0)
            unk = int(m.get("unknown_reject_count") or 0)
            unknown_total += max(0, unk)
            rejects_total += max(0, sparse + oos + unk)
        except Exception:
            continue
    if rejects_total <= 0:
        return 0.0
    return unknown_total / rejects_total


def _validate_allocation_input(
    allocation: Any,
) -> Tuple[bool, List[str]]:
    """Return (is_safe, block_reasons). Hard-rejects governance-grade
    failures (mode != DRY_RUN, applied=True, wrong consumer_version)."""
    reasons: List[str] = []
    if not isinstance(allocation, DryRunBudgetAllocation):
        reasons.append(BLOCK_INPUT_BAD_VERSION)
        return False, reasons
    if getattr(allocation, "mode", None) != MODE_DRY_RUN:
        reasons.append(BLOCK_INPUT_NOT_DRY_RUN)
    if getattr(allocation, "applied", False) is True:
        reasons.append(BLOCK_INPUT_APPLIED_TRUE)
    return (len(reasons) == 0), reasons


def _evaluate_actionability(
    allocation: DryRunBudgetAllocation,
    *,
    attribution_verdict: str,
    profile_metrics: Optional[Sequence[Mapping[str, Any]]],
) -> Tuple[str, List[str], List[str]]:
    """Return ``(plan_status, block_reasons, selected_interventions)``."""

    safe, gov_reasons = _validate_allocation_input(allocation)
    if not safe:
        return PLAN_STATUS_BLOCKED, gov_reasons, []

    block: List[str] = []

    if str(attribution_verdict).upper() == VERDICT_RED:
        block.append(BLOCK_RED_ATTRIBUTION)

    confidence = str(getattr(allocation, "confidence", "") or "")
    if confidence != CONFIDENCE_A1_A2_A3_AVAILABLE:
        block.append(BLOCK_LOW_CONFIDENCE)

    actionable_count = int(getattr(allocation, "actionable_profile_count", 0) or 0)
    if actionable_count < 2:
        block.append(BLOCK_FEW_ACTIONABLE)

    non_actionable_reasons = (
        getattr(allocation, "non_actionable_reasons", None) or {}
    )
    if _has_counter_inconsistency(non_actionable_reasons):
        block.append(BLOCK_COUNTER_INCONSISTENCY)

    unknown_rate = _aggregate_unknown_reject_rate(profile_metrics)
    if unknown_rate >= UNKNOWN_REJECT_VETO:
        block.append(BLOCK_UNKNOWN_REJECT_HIGH)

    # Sample-size: rely on allocator's gate (allocation only flips to
    # CONFIDENCE_A1_A2_A3_AVAILABLE when sample-size is met). If the
    # caller provided profile_metrics, double-check.
    if profile_metrics:
        for m in profile_metrics:
            if not isinstance(m, Mapping):
                continue
            try:
                if int(m.get("sample_size_rounds") or 0) < MIN_SAMPLE_SIZE_ROUNDS:
                    block.append(BLOCK_LOW_SAMPLE_SIZE)
                    break
            except Exception:
                continue

    if block:
        return PLAN_STATUS_NON_ACTIONABLE, block, []

    interventions = list(ALLOWED_INTERVENTIONS)
    return PLAN_STATUS_ACTIONABLE, [], interventions


# ---------------------------------------------------------------------------
# Top-level consumer
# ---------------------------------------------------------------------------


def consume(
    allocation: DryRunBudgetAllocation,
    *,
    run_id: str,
    attribution_verdict: str = VERDICT_UNAVAILABLE,
    previous_profile_weights: Optional[Mapping[str, float]] = None,
    smoothing_history: Optional[Sequence[Mapping[str, float]]] = None,
    profile_metrics: Optional[Sequence[Mapping[str, Any]]] = None,
    ema_alpha: float = DEFAULT_EMA_ALPHA,
    smoothing_window: int = DEFAULT_SMOOTHING_WINDOW,
    max_step_abs: float = DEFAULT_MAX_STEP_ABS,
    diversity_cap_min: int = DEFAULT_DIVERSITY_CAP_MIN,
    exploration_floor: float = EXPLORATION_FLOOR,
) -> SparseCandidateDryRunPlan:
    """Consume one ``DryRunBudgetAllocation`` and produce a
    ``SparseCandidateDryRunPlan``. Never raises.

    The plan is **always** dry-run (``mode=DRY_RUN``,
    ``applied=False``). The plan's ``plan_status`` indicates whether
    the recommendation is actionable; even non-actionable / blocked
    plans are emitted so observers can record the attempt.
    """

    _resolved_diversity_cap = (
        diversity_cap_min if diversity_cap_min >= 1 else DEFAULT_DIVERSITY_CAP_MIN
    )
    plan = SparseCandidateDryRunPlan(
        run_id=str(run_id or ""),
        attribution_verdict=str(attribution_verdict or VERDICT_UNAVAILABLE),
        ema_alpha=ema_alpha,
        smoothing_window=smoothing_window,
        max_step_abs=max_step_abs,
        diversity_cap=_resolved_diversity_cap,
        exploration_floor=exploration_floor,
    )

    if not isinstance(allocation, DryRunBudgetAllocation):
        plan.plan_status = PLAN_STATUS_BLOCKED
        plan.block_reasons = [BLOCK_INPUT_BAD_VERSION]
        plan.reason = "input is not a DryRunBudgetAllocation"
        return plan

    # Snapshot allocation fields onto the plan (read-only).
    plan.source_allocation_id = str(getattr(allocation, "decision_id", "") or "")
    plan.confidence = str(getattr(allocation, "confidence", "") or "")
    plan.actionable_profile_count = int(
        getattr(allocation, "actionable_profile_count", 0) or 0
    )
    plan.observed_bottleneck = str(
        getattr(allocation, "observed_bottleneck", BOTTLENECK_NO_ACTIONABLE)
        or BOTTLENECK_NO_ACTIONABLE
    )
    plan.previous_profile_weights = dict(
        previous_profile_weights or getattr(allocation, "previous_profile_weights", {}) or {}
    )
    plan.allocator_proposed_weights = dict(
        getattr(allocation, "proposed_profile_weights_dry_run", {}) or {}
    )
    plan.non_actionable_reasons = {
        str(k): list(v or [])
        for k, v in (getattr(allocation, "non_actionable_reasons", {}) or {}).items()
    }

    # Gate.
    status, block_reasons, interventions = _evaluate_actionability(
        allocation,
        attribution_verdict=attribution_verdict,
        profile_metrics=profile_metrics,
    )
    plan.plan_status = status
    plan.block_reasons = list(block_reasons)
    plan.selected_interventions = list(interventions)

    # Add a YELLOW-attribution safety_constraint marker so downstream
    # readers can tell the plan was made under documented limitation.
    if str(attribution_verdict).upper() == VERDICT_YELLOW:
        plan.safety_constraints = list(plan.safety_constraints) + [
            "ATTRIBUTION_VERDICT_YELLOW_DOCUMENTED",
        ]

    # Run the smoothing pipeline only when actionable. Non-actionable
    # plans expose the allocator output passthrough so observers can
    # see what would have been recommended.
    if status == PLAN_STATUS_ACTIONABLE:
        plan.smoothed_proposed_weights = ema_smooth(
            plan.allocator_proposed_weights,
            history=smoothing_history,
            alpha=plan.ema_alpha,
        )
        plan.max_step_limited_weights = limit_step(
            plan.smoothed_proposed_weights,
            previous=plan.previous_profile_weights,
            max_step_abs=plan.max_step_abs,
        )
        plan.final_dry_run_weights = enforce_floor_and_diversity(
            plan.max_step_limited_weights,
            floor=plan.exploration_floor,
            diversity_cap_min=plan.diversity_cap,
        )
        plan.expected_effect = "DRY_RUN_PLAN_RECOMMENDED_NOT_APPLIED"
        plan.reason = (
            f"actionable dry-run plan: {plan.actionable_profile_count} profile(s) "
            f"cleared all gates; {len(plan.selected_interventions)} intervention(s) "
            f"selected; weights are dry-run only"
        )
    else:
        plan.smoothed_proposed_weights = dict(plan.allocator_proposed_weights)
        plan.max_step_limited_weights = dict(plan.allocator_proposed_weights)
        plan.final_dry_run_weights = dict(plan.allocator_proposed_weights)
        plan.expected_effect = "DRY_RUN_NON_ACTIONABLE_NO_RECOMMENDATION_APPLIED"
        plan.reason = (
            "non-actionable: " + ", ".join(plan.block_reasons)
            if plan.block_reasons
            else "non-actionable"
        )

    return plan


def safe_consume(
    allocation: Any,
    *,
    run_id: str,
    **kwargs: Any,
) -> SparseCandidateDryRunPlan:
    """Exception-safe wrapper. On internal failure returns a BLOCKED
    plan whose ``reason`` records the exception class name. Never
    raises."""
    try:
        return consume(allocation, run_id=run_id, **kwargs)
    except Exception as exc:  # noqa: BLE001
        plan = SparseCandidateDryRunPlan(run_id=str(run_id or ""))
        plan.plan_status = PLAN_STATUS_BLOCKED
        plan.block_reasons = [BLOCK_INPUT_BAD_VERSION]
        plan.reason = (
            f"consume() raised {type(exc).__name__} — caller should investigate"
        )
        return plan


def serialize_plan(plan: SparseCandidateDryRunPlan) -> str:
    """JSON-serialize a plan. Never raises."""
    try:
        return json.dumps(plan.to_event(), sort_keys=True)
    except Exception:
        return ""
