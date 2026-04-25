"""Sparse-Candidate Dry-Run CANARY Observer (TEAM ORDER 0-9S-CANARY).

Read-only observer that consumes existing dry-run telemetry and
produces ``sparse_canary_observation`` evidence records. The observer
**never** applies recommendations, never connects to generation
runtime, and never touches Arena pass/fail logic.

Inputs (all read-only):

  - ``generation_profile_metrics`` aggregate (per-profile)
  - ``DryRunBudgetAllocation`` events (from 0-9O-B allocator)
  - ``SparseCandidateDryRunPlan`` events (from 0-9R-IMPL-DRY consumer)
  - attribution audit verdict (from 0-9P-AUDIT)
  - aggregate ``arena_batch_metrics`` (from P7-PR4B)
  - aggregate ``arena_stage_summary``

Outputs:

  ``SparseCanaryObservation`` event (28 fields, ``mode=DRY_RUN_CANARY``,
  ``applied=False``, ``canary_version="0-9S-CANARY"``).

Three-layer dry-run invariant
-----------------------------

  1. ``__post_init__`` resets ``mode`` / ``applied`` / ``canary_version``
     regardless of caller-supplied kwargs.
  2. ``to_event()`` re-asserts the same fields at serialization time.
  3. No public ``apply`` / ``commit`` / ``execute`` symbol.

Composite score
---------------

The CANARY default scoring weights are 0.4 / 0.4 / 0.2 per
TEAM ORDER 0-9S-CANARY §4 (matching 0-9R / 0-9S-READY proposal):

    composite_score = 0.4 * a2_pass_rate
                    + 0.4 * a3_pass_rate
                    + 0.2 * deployable_density

Where ``deployable_density = deployable_count / passed_a3`` (clamped
to ``[0, 1]`` for scoring stability).

Success / failure criteria S1-S14 / F1-F9 are evaluated against
caller-supplied baseline metrics. When history is insufficient,
criteria are marked ``INSUFFICIENT_HISTORY`` rather than faked.
"""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from zangetsu.services.feedback_budget_consumer import (
    PLAN_STATUS_ACTIONABLE,
    PLAN_STATUS_BLOCKED,
    PLAN_STATUS_NON_ACTIONABLE,
    SparseCandidateDryRunPlan,
)
from zangetsu.services.feedback_budget_allocator import (
    DryRunBudgetAllocation,
)
from zangetsu.services.feedback_decision_record import (
    DEFAULT_SAFETY_CONSTRAINTS,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CANARY_VERSION = "0-9S-CANARY"
TELEMETRY_VERSION = "1"
EVENT_TYPE_SPARSE_CANARY_OBSERVATION = "sparse_canary_observation"

MODE_DRY_RUN_CANARY = "DRY_RUN_CANARY"
APPLIED_FALSE = False

# Composite scoring weights (CANARY default per §4).
DEFAULT_COMPOSITE_W_A2 = 0.4
DEFAULT_COMPOSITE_W_A3 = 0.4
DEFAULT_COMPOSITE_W_DEPLOY = 0.2

# Success / failure thresholds (per §9 / §10).
S1_SPARSE_REDUCTION_MIN_REL = 0.20    # >= 20% relative drop
S2_A2_PASS_RATE_INCREASE_MIN_PP = 0.03  # >= 3 pp absolute
S3_A3_PASS_RATE_TOLERANCE_PP = 0.02    # tolerance 2 pp
S4_OOS_FAIL_TOLERANCE_PP = 0.03        # tolerance 3 pp
S6_UNKNOWN_REJECT_VETO = 0.05          # < 0.05 required
S14_COMPOSITE_DELTA_MIN_SIGMA = 1.0    # >= 1σ

F4_UNKNOWN_REJECT_TRIGGER = 0.05       # > 0.05 triggers F4

# Profile diversity floor (carried from 0-9R-IMPL-DRY consumer).
EXPLORATION_FLOOR = 0.05
DIVERSITY_CAP_MIN = 2

# Status enums.
STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
STATUS_NOT_EVALUATED = "NOT_EVALUATED"

# Readiness verdicts (mirror 0-9P-AUDIT but we keep our own enum so
# this module does not import the audit tool — keeping the
# observer fully isolated.)
VERDICT_GREEN = "GREEN"
VERDICT_YELLOW = "YELLOW"
VERDICT_RED = "RED"
VERDICT_UNAVAILABLE = "UNAVAILABLE"

# Default plan-stability threshold: at least 70% of consumed plans
# must be ACTIONABLE_DRY_RUN for the consumer to be considered
# stable. This is a soft observability metric, not a gate.
PLAN_STABILITY_MIN = 0.70


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_canary_id() -> str:
    return "canary-" + uuid.uuid4().hex[:16]


@dataclass
class SparseCanaryObservation:
    """One CANARY observation record. Enforces dry-run invariants at
    construction and at serialization."""

    run_id: str
    canary_id: str = field(default_factory=_new_canary_id)
    created_at: str = field(default_factory=_utc_now_iso)
    mode: str = MODE_DRY_RUN_CANARY
    applied: bool = APPLIED_FALSE
    canary_version: str = CANARY_VERSION
    readiness_verdict: str = STATUS_NOT_EVALUATED
    attribution_verdict: str = VERDICT_UNAVAILABLE
    observation_window_start: str = ""
    observation_window_end: str = ""
    observation_window_complete: bool = False
    rounds_observed: int = 0
    profiles_observed: int = 0
    unknown_reject_rate: float = 0.0
    signal_too_sparse_rate: float = 0.0
    a1_pass_rate: float = 0.0
    a2_pass_rate: float = 0.0
    a3_pass_rate: float = 0.0
    oos_fail_rate: float = 0.0
    deployable_count: int = 0
    deployable_density: float = 0.0
    composite_score: float = 0.0
    baseline_composite_score: float = 0.0
    composite_delta: float = 0.0
    profile_diversity_score: float = 0.0
    profile_collapse_detected: bool = False
    consumer_plan_stability: float = 0.0
    success_criteria_status: Dict[str, str] = field(default_factory=dict)
    failure_criteria_status: Dict[str, str] = field(default_factory=dict)
    rollback_required: bool = False
    alerts_triggered: List[str] = field(default_factory=list)
    evidence_paths: List[str] = field(default_factory=list)
    safety_constraints: List[str] = field(
        default_factory=lambda: list(DEFAULT_SAFETY_CONSTRAINTS)
    )
    telemetry_version: str = TELEMETRY_VERSION
    source: str = "sparse_canary_observer"

    def __post_init__(self) -> None:
        # Invariants — bug-proof against caller overrides.
        self.mode = MODE_DRY_RUN_CANARY
        self.applied = APPLIED_FALSE
        self.canary_version = CANARY_VERSION
        if not isinstance(self.success_criteria_status, dict):
            self.success_criteria_status = {}
        if not isinstance(self.failure_criteria_status, dict):
            self.failure_criteria_status = {}
        if not isinstance(self.alerts_triggered, list):
            self.alerts_triggered = []
        if not isinstance(self.evidence_paths, list):
            self.evidence_paths = []
        if not isinstance(self.safety_constraints, list) or not self.safety_constraints:
            self.safety_constraints = list(DEFAULT_SAFETY_CONSTRAINTS)

    def to_event(self) -> dict:
        payload = asdict(self)
        payload["event_type"] = EVENT_TYPE_SPARSE_CANARY_OBSERVATION
        # Re-assert at serialization time.
        payload["mode"] = MODE_DRY_RUN_CANARY
        payload["applied"] = APPLIED_FALSE
        payload["canary_version"] = CANARY_VERSION
        return payload


def required_observation_fields() -> Tuple[str, ...]:
    """Stable list of required fields on :class:`SparseCanaryObservation`.

    Used by tests to lock the schema."""
    return (
        "telemetry_version",
        "canary_id",
        "run_id",
        "created_at",
        "mode",
        "applied",
        "canary_version",
        "readiness_verdict",
        "attribution_verdict",
        "observation_window_start",
        "observation_window_end",
        "observation_window_complete",
        "rounds_observed",
        "profiles_observed",
        "unknown_reject_rate",
        "signal_too_sparse_rate",
        "a1_pass_rate",
        "a2_pass_rate",
        "a3_pass_rate",
        "oos_fail_rate",
        "deployable_count",
        "deployable_density",
        "composite_score",
        "baseline_composite_score",
        "composite_delta",
        "profile_diversity_score",
        "profile_collapse_detected",
        "consumer_plan_stability",
        "success_criteria_status",
        "failure_criteria_status",
        "rollback_required",
        "alerts_triggered",
        "evidence_paths",
        "source",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _clip(value: float, lo: float, hi: float) -> float:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def compute_composite_score(
    a2_pass_rate: float,
    a3_pass_rate: float,
    deployable_density: float,
    *,
    w_a2: float = DEFAULT_COMPOSITE_W_A2,
    w_a3: float = DEFAULT_COMPOSITE_W_A3,
    w_deploy: float = DEFAULT_COMPOSITE_W_DEPLOY,
) -> float:
    """Composite score per §4. Caller may override weights when an
    explicitly committed contract exists; otherwise defaults apply.

    Returns a value in ``[0, 1]``. Never raises.
    """
    try:
        a2 = _clip(_safe_float(a2_pass_rate), 0.0, 1.0)
        a3 = _clip(_safe_float(a3_pass_rate), 0.0, 1.0)
        d = _clip(_safe_float(deployable_density), 0.0, 1.0)
        score = w_a2 * a2 + w_a3 * a3 + w_deploy * d
        return _clip(score, 0.0, 1.0)
    except Exception:
        return 0.0


def compute_deployable_density(
    deployable_count: int, passed_a3: int
) -> float:
    """``deployable_count / passed_a3``, clamped to ``[0, 1]``. Returns
    0.0 when ``passed_a3 <= 0``."""
    try:
        passed = max(0, _safe_int(passed_a3, 0))
        deploy = max(0, _safe_int(deployable_count, 0))
        if passed <= 0:
            return 0.0
        return _clip(deploy / passed, 0.0, 1.0)
    except Exception:
        return 0.0


def compute_profile_diversity(weights: Mapping[str, float]) -> float:
    """Return the share of profiles whose weight is >=
    ``EXPLORATION_FLOOR``. Returns 0.0 when no profiles supplied."""
    try:
        if not weights:
            return 0.0
        total = len(weights)
        above = sum(
            1
            for v in weights.values()
            if _safe_float(v, 0.0) >= EXPLORATION_FLOOR - 1e-12
        )
        return _clip(above / total, 0.0, 1.0)
    except Exception:
        return 0.0


def detect_profile_collapse(
    weights: Mapping[str, float],
    *,
    diversity_cap_min: int = DIVERSITY_CAP_MIN,
) -> bool:
    """Return True when fewer than ``diversity_cap_min`` profiles are at
    or above the exploration floor."""
    try:
        if not weights:
            return False
        above = sum(
            1
            for v in weights.values()
            if _safe_float(v, 0.0) >= EXPLORATION_FLOOR - 1e-12
        )
        return above < diversity_cap_min
    except Exception:
        return False


def compute_consumer_plan_stability(
    plans: Optional[Sequence[Any]],
) -> float:
    """Fraction of supplied plans whose ``plan_status`` is
    ``ACTIONABLE_DRY_RUN``. Returns 0.0 when no plans supplied."""
    if not plans:
        return 0.0
    try:
        total = 0
        actionable = 0
        for p in plans:
            total += 1
            status = getattr(p, "plan_status", None)
            if status is None and isinstance(p, Mapping):
                status = p.get("plan_status")
            if status == PLAN_STATUS_ACTIONABLE:
                actionable += 1
        if total <= 0:
            return 0.0
        return actionable / total
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Success / failure evaluation
# ---------------------------------------------------------------------------


@dataclass
class CanaryBaseline:
    """Baseline metric snapshot used for delta-style criteria."""

    a2_pass_rate: float = 0.0
    a3_pass_rate: float = 0.0
    signal_too_sparse_rate: float = 0.0
    oos_fail_rate: float = 0.0
    unknown_reject_rate: float = 0.0
    deployable_count: int = 0
    composite_score: float = 0.0
    composite_score_stddev: Optional[float] = None
    sample_size_rounds: int = 0


def _has_enough_history(baseline: CanaryBaseline, *, min_rounds: int = 20) -> bool:
    return _safe_int(baseline.sample_size_rounds, 0) >= min_rounds


def evaluate_success_criteria(
    treatment: Mapping[str, Any],
    baseline: CanaryBaseline,
    *,
    no_threshold_change: bool = True,
    no_arena_change: bool = True,
    no_promotion_change: bool = True,
    no_execution_change: bool = True,
    per_regime_stable: Optional[bool] = None,
) -> Dict[str, str]:
    """Return ``{S1..S14: PASS|FAIL|INSUFFICIENT_HISTORY}``.

    Never raises. ``treatment`` is a dict-like with the same fields
    `SparseCanaryObservation` exposes (a2_pass_rate, ..., deployable_density,
    composite_score). ``baseline`` is the prior period's snapshot.
    """
    out: Dict[str, str] = {}
    try:
        t_a2 = _safe_float(treatment.get("a2_pass_rate"))
        t_a3 = _safe_float(treatment.get("a3_pass_rate"))
        t_sparse = _safe_float(treatment.get("signal_too_sparse_rate"))
        t_oos = _safe_float(treatment.get("oos_fail_rate"))
        t_unknown = _safe_float(treatment.get("unknown_reject_rate"))
        t_deploy = _safe_int(treatment.get("deployable_count"))
        t_collapse = bool(treatment.get("profile_collapse_detected"))
        t_diversity = _safe_float(treatment.get("profile_diversity_score"))
        t_composite = _safe_float(treatment.get("composite_score"))

        history_ok = _has_enough_history(baseline)

        # S1 — sparse rate decreases >= 20% relative
        if not history_ok or baseline.signal_too_sparse_rate <= 0:
            out["S1"] = STATUS_INSUFFICIENT_HISTORY
        else:
            rel = (
                baseline.signal_too_sparse_rate - t_sparse
            ) / baseline.signal_too_sparse_rate
            out["S1"] = STATUS_PASS if rel >= S1_SPARSE_REDUCTION_MIN_REL else STATUS_FAIL

        # S2 — A2 pass_rate +>= 3pp absolute
        if not history_ok:
            out["S2"] = STATUS_INSUFFICIENT_HISTORY
        else:
            out["S2"] = (
                STATUS_PASS
                if (t_a2 - baseline.a2_pass_rate) >= S2_A2_PASS_RATE_INCREASE_MIN_PP
                else STATUS_FAIL
            )

        # S3 — A3 pass_rate not degrading > 2pp
        if not history_ok:
            out["S3"] = STATUS_INSUFFICIENT_HISTORY
        else:
            out["S3"] = (
                STATUS_PASS
                if (baseline.a3_pass_rate - t_a3) <= S3_A3_PASS_RATE_TOLERANCE_PP
                else STATUS_FAIL
            )

        # S4 — OOS_FAIL not increasing > 3pp
        if not history_ok:
            out["S4"] = STATUS_INSUFFICIENT_HISTORY
        else:
            out["S4"] = (
                STATUS_PASS
                if (t_oos - baseline.oos_fail_rate) <= S4_OOS_FAIL_TOLERANCE_PP
                else STATUS_FAIL
            )

        # S5 — deployable_count maintained or improved
        if not history_ok:
            out["S5"] = STATUS_INSUFFICIENT_HISTORY
        else:
            out["S5"] = STATUS_PASS if t_deploy >= baseline.deployable_count else STATUS_FAIL

        # S6 — UNKNOWN_REJECT < 0.05
        out["S6"] = STATUS_PASS if t_unknown < S6_UNKNOWN_REJECT_VETO else STATUS_FAIL

        # S7 — profile collapse must NOT occur
        out["S7"] = STATUS_FAIL if t_collapse else STATUS_PASS

        # S8 — exploration floor active (proxy: diversity > 0)
        out["S8"] = STATUS_PASS if t_diversity > 0 else STATUS_FAIL

        # S9 — no threshold changes (caller-supplied flag)
        out["S9"] = STATUS_PASS if no_threshold_change else STATUS_FAIL

        # S10 — no Arena pass/fail changes (caller-supplied flag)
        out["S10"] = STATUS_PASS if no_arena_change else STATUS_FAIL

        # S11 — no champion promotion changes
        out["S11"] = STATUS_PASS if no_promotion_change else STATUS_FAIL

        # S12 — no execution / capital / risk changes
        out["S12"] = STATUS_PASS if no_execution_change else STATUS_FAIL

        # S13 — per-regime stability (caller-supplied)
        if per_regime_stable is None:
            out["S13"] = STATUS_INSUFFICIENT_HISTORY
        else:
            out["S13"] = STATUS_PASS if per_regime_stable else STATUS_FAIL

        # S14 — composite score improves >= 1σ
        if (
            not history_ok
            or baseline.composite_score_stddev is None
            or baseline.composite_score_stddev <= 0
        ):
            out["S14"] = STATUS_INSUFFICIENT_HISTORY
        else:
            delta = t_composite - baseline.composite_score
            sigma = baseline.composite_score_stddev
            out["S14"] = (
                STATUS_PASS
                if delta >= S14_COMPOSITE_DELTA_MIN_SIGMA * sigma
                else STATUS_FAIL
            )

    except Exception:
        # Never propagate. Mark anything missing as NOT_EVALUATED.
        for s in ("S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8",
                  "S9", "S10", "S11", "S12", "S13", "S14"):
            out.setdefault(s, STATUS_NOT_EVALUATED)
    return out


def evaluate_failure_criteria(
    treatment: Mapping[str, Any],
    baseline: CanaryBaseline,
    *,
    rollback_executable: bool = True,
    execution_path_touched: bool = False,
    attribution_verdict: str = VERDICT_UNAVAILABLE,
) -> Dict[str, str]:
    """Return ``{F1..F9: PASS|FAIL}`` where ``PASS`` means "no
    failure" and ``FAIL`` means "failure criterion triggered".

    Never raises.
    """
    out: Dict[str, str] = {}
    try:
        t_a2 = _safe_float(treatment.get("a2_pass_rate"))
        t_a3 = _safe_float(treatment.get("a3_pass_rate"))
        t_oos = _safe_float(treatment.get("oos_fail_rate"))
        t_unknown = _safe_float(treatment.get("unknown_reject_rate"))
        t_deploy = _safe_int(treatment.get("deployable_count"))
        t_collapse = bool(treatment.get("profile_collapse_detected"))
        t_diversity = _safe_float(treatment.get("profile_diversity_score"))

        # Use epsilon-tolerant comparison for ≥ 5pp thresholds to avoid
        # float-precision false negatives (e.g. 0.30 - 0.25 = 0.04999...).
        _eps = 1e-9

        a2_improves = t_a2 > baseline.a2_pass_rate
        # F1: A2 improves but A3 collapses (≥ 5pp drop is "collapse").
        a3_collapse = (baseline.a3_pass_rate - t_a3) >= 0.05 - _eps
        out["F1"] = STATUS_FAIL if (a2_improves and a3_collapse) else STATUS_PASS

        # F2: A2 improves but deployable_count falls.
        deploy_falls = t_deploy < baseline.deployable_count
        out["F2"] = STATUS_FAIL if (a2_improves and deploy_falls) else STATUS_PASS

        # F3: OOS_FAIL increases materially (≥ 5pp).
        oos_material = (t_oos - baseline.oos_fail_rate) >= 0.05 - _eps
        out["F3"] = STATUS_FAIL if oos_material else STATUS_PASS

        # F4: UNKNOWN_REJECT > 0.05
        out["F4"] = STATUS_FAIL if t_unknown > F4_UNKNOWN_REJECT_TRIGGER else STATUS_PASS

        # F5: profile collapse occurs
        out["F5"] = STATUS_FAIL if t_collapse else STATUS_PASS

        # F6: exploration floor violated (diversity == 0 means no profile at floor)
        out["F6"] = STATUS_FAIL if t_diversity <= 0.0 else STATUS_PASS

        # F7: attribution verdict regresses to RED
        out["F7"] = (
            STATUS_FAIL
            if str(attribution_verdict).upper() == VERDICT_RED
            else STATUS_PASS
        )

        # F8: rollback cannot execute
        out["F8"] = STATUS_PASS if rollback_executable else STATUS_FAIL

        # F9: unexpected execution / capital / risk path touched
        out["F9"] = STATUS_FAIL if execution_path_touched else STATUS_PASS

    except Exception:
        for f in ("F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9"):
            out.setdefault(f, STATUS_NOT_EVALUATED)
    return out


# ---------------------------------------------------------------------------
# Top-level observer
# ---------------------------------------------------------------------------


def observe(
    *,
    run_id: str,
    treatment_metrics: Mapping[str, Any],
    baseline: CanaryBaseline,
    profile_weights: Optional[Mapping[str, float]] = None,
    consumer_plans: Optional[Sequence[Any]] = None,
    readiness_verdict: str = STATUS_NOT_EVALUATED,
    attribution_verdict: str = VERDICT_UNAVAILABLE,
    observation_window_start: str = "",
    observation_window_end: str = "",
    observation_window_complete: bool = False,
    rounds_observed: int = 0,
    profiles_observed: int = 0,
    rollback_executable: bool = True,
    execution_path_touched: bool = False,
    no_threshold_change: bool = True,
    no_arena_change: bool = True,
    no_promotion_change: bool = True,
    no_execution_change: bool = True,
    per_regime_stable: Optional[bool] = None,
    composite_weights: Optional[Mapping[str, float]] = None,
    evidence_paths: Optional[Sequence[str]] = None,
    alerts_triggered: Optional[Sequence[str]] = None,
) -> SparseCanaryObservation:
    """Build a :class:`SparseCanaryObservation` from telemetry inputs.

    Never raises. Pathological inputs produce a record with all
    metrics set to safe defaults; success / failure criteria default
    to ``INSUFFICIENT_HISTORY`` / ``NOT_EVALUATED``.
    """

    obs = SparseCanaryObservation(
        run_id=str(run_id or ""),
        readiness_verdict=str(readiness_verdict or STATUS_NOT_EVALUATED),
        attribution_verdict=str(attribution_verdict or VERDICT_UNAVAILABLE),
        observation_window_start=str(observation_window_start or ""),
        observation_window_end=str(observation_window_end or ""),
        observation_window_complete=bool(observation_window_complete),
        rounds_observed=_safe_int(rounds_observed, 0),
        profiles_observed=_safe_int(profiles_observed, 0),
    )

    try:
        obs.unknown_reject_rate = _safe_float(treatment_metrics.get("unknown_reject_rate"))
        obs.signal_too_sparse_rate = _safe_float(treatment_metrics.get("signal_too_sparse_rate"))
        obs.a1_pass_rate = _safe_float(treatment_metrics.get("a1_pass_rate"))
        obs.a2_pass_rate = _safe_float(treatment_metrics.get("a2_pass_rate"))
        obs.a3_pass_rate = _safe_float(treatment_metrics.get("a3_pass_rate"))
        obs.oos_fail_rate = _safe_float(treatment_metrics.get("oos_fail_rate"))
        obs.deployable_count = _safe_int(treatment_metrics.get("deployable_count"))
        passed_a3 = _safe_int(treatment_metrics.get("passed_a3"))
        obs.deployable_density = compute_deployable_density(
            obs.deployable_count, passed_a3
        )

        w = composite_weights or {}
        obs.composite_score = compute_composite_score(
            obs.a2_pass_rate,
            obs.a3_pass_rate,
            obs.deployable_density,
            w_a2=_safe_float(w.get("a2"), DEFAULT_COMPOSITE_W_A2),
            w_a3=_safe_float(w.get("a3"), DEFAULT_COMPOSITE_W_A3),
            w_deploy=_safe_float(w.get("deploy"), DEFAULT_COMPOSITE_W_DEPLOY),
        )
        obs.baseline_composite_score = _safe_float(baseline.composite_score)
        obs.composite_delta = obs.composite_score - obs.baseline_composite_score

        if profile_weights:
            obs.profile_diversity_score = compute_profile_diversity(profile_weights)
            obs.profile_collapse_detected = detect_profile_collapse(profile_weights)
        else:
            obs.profile_diversity_score = 0.0
            obs.profile_collapse_detected = False

        obs.consumer_plan_stability = compute_consumer_plan_stability(consumer_plans)

        obs.success_criteria_status = evaluate_success_criteria(
            {
                "a2_pass_rate": obs.a2_pass_rate,
                "a3_pass_rate": obs.a3_pass_rate,
                "signal_too_sparse_rate": obs.signal_too_sparse_rate,
                "oos_fail_rate": obs.oos_fail_rate,
                "unknown_reject_rate": obs.unknown_reject_rate,
                "deployable_count": obs.deployable_count,
                "profile_collapse_detected": obs.profile_collapse_detected,
                "profile_diversity_score": obs.profile_diversity_score,
                "composite_score": obs.composite_score,
            },
            baseline,
            no_threshold_change=no_threshold_change,
            no_arena_change=no_arena_change,
            no_promotion_change=no_promotion_change,
            no_execution_change=no_execution_change,
            per_regime_stable=per_regime_stable,
        )

        obs.failure_criteria_status = evaluate_failure_criteria(
            {
                "a2_pass_rate": obs.a2_pass_rate,
                "a3_pass_rate": obs.a3_pass_rate,
                "oos_fail_rate": obs.oos_fail_rate,
                "unknown_reject_rate": obs.unknown_reject_rate,
                "deployable_count": obs.deployable_count,
                "profile_collapse_detected": obs.profile_collapse_detected,
                "profile_diversity_score": obs.profile_diversity_score,
            },
            baseline,
            rollback_executable=rollback_executable,
            execution_path_touched=execution_path_touched,
            attribution_verdict=obs.attribution_verdict,
        )

        # rollback_required: any F triggered → True
        obs.rollback_required = any(
            v == STATUS_FAIL for v in obs.failure_criteria_status.values()
        )

        if alerts_triggered:
            obs.alerts_triggered = [str(x) for x in alerts_triggered]
        if evidence_paths:
            obs.evidence_paths = [str(x) for x in evidence_paths]

    except Exception:
        # Never propagate. Mark anything missing.
        if not obs.success_criteria_status:
            obs.success_criteria_status = {
                f"S{i}": STATUS_NOT_EVALUATED for i in range(1, 15)
            }
        if not obs.failure_criteria_status:
            obs.failure_criteria_status = {
                f"F{i}": STATUS_NOT_EVALUATED for i in range(1, 10)
            }

    return obs


def safe_observe(**kwargs: Any) -> SparseCanaryObservation:
    """Exception-safe wrapper. On internal failure returns an
    observation with rollback_required=True and an alerts entry
    recording the exception class name."""
    try:
        return observe(**kwargs)
    except Exception as exc:  # noqa: BLE001
        obs = SparseCanaryObservation(
            run_id=str(kwargs.get("run_id") or ""),
        )
        obs.rollback_required = True
        obs.alerts_triggered = [
            f"observe_raised_{type(exc).__name__}",
        ]
        return obs


def serialize_observation(obs: SparseCanaryObservation) -> str:
    """JSON-serialize an observation. Never raises."""
    try:
        return json.dumps(obs.to_event(), sort_keys=True)
    except Exception:
        return ""
