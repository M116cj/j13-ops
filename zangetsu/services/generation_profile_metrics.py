"""Read-only generation profile metrics + scoring (TEAM ORDER 0-9O-A).

This module aggregates Arena pass-rate telemetry (emitted by
``arena_pass_rate_telemetry``) by ``generation_profile_id`` and computes a
read-only ``profile_score`` + ``next_budget_weight_dry_run``.

Core invariants
---------------

1. No score produced here is consumed by generation runtime.
2. No score produced here is consumed by Arena runtime.
3. ``profile_score`` is a diagnostic observation only.
4. ``next_budget_weight_dry_run`` is a recommendation only.
5. Scoring marks ``LOW_CONFIDENCE_UNTIL_A2_A3_METRICS_AVAILABLE`` whenever
   A2 / A3 metrics are unavailable (which is the case for the whole of
   0-9O-A, since P7-PR4-LITE only wired A1).
6. Scoring marks ``min_sample_size_met = False`` until
   ``sample_size_rounds >= MIN_SAMPLE_SIZE_ROUNDS``.
7. All computation is exception-safe.

Telemetry version: "1".
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Iterable, List, Mapping, Optional

from zangetsu.services.generation_profile_identity import (
    UNAVAILABLE_FINGERPRINT,
    UNKNOWN_PROFILE_ID,
)

TELEMETRY_VERSION = "1"
EVENT_TYPE_GENERATION_PROFILE_METRICS = "generation_profile_metrics"

# Scoring mode markers.
MODE_READ_ONLY = "READ_ONLY"
MODE_DRY_RUN = "DRY_RUN"
CONFIDENCE_LOW_UNTIL_A2_A3 = "LOW_CONFIDENCE_UNTIL_A2_A3_METRICS_AVAILABLE"
CONFIDENCE_A1_A2_A3_AVAILABLE = "CONFIDENCE_A1_A2_A3_METRICS_AVAILABLE"
CONFIDENCE_LOW_SAMPLE_SIZE = "LOW_SAMPLE_SIZE_UNTIL_20_ROUNDS"
# Backwards-compatible alias for prior consumers (0-9O-A introduced
# ``CONFIDENCE_FULL`` as the upgraded marker; P7-PR4B prefers the
# canonical ``CONFIDENCE_A1_A2_A3_AVAILABLE`` name from order §8 but keeps
# ``CONFIDENCE_FULL`` resolvable so existing tests / dashboards do not
# regress).
CONFIDENCE_FULL = CONFIDENCE_A1_A2_A3_AVAILABLE

# Guardrails.
MIN_SAMPLE_SIZE_ROUNDS = 20
EXPLORATION_FLOOR = 0.05
PROFILE_SCORE_MIN = -1.0
PROFILE_SCORE_MAX = 1.0

# Default weights per 0-9N §04 scoring model + 2-3 §9 defaults.
DEFAULT_WEIGHTS: dict = {
    "w1_avg_a1_pass_rate": 0.10,
    "w2_avg_a2_pass_rate": 0.30,
    "w3_avg_a3_pass_rate": 0.30,
    "w4_deployable_score": 0.20,
    "w5_signal_too_sparse_penalty": 0.25,
    "w6_oos_fail_penalty": 0.20,
    "w7_unknown_reject_penalty": 0.50,
    "w8_instability_penalty": 0.15,
}


def _clip(value: float, lo: float, hi: float) -> float:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def _safe_rate(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return _clip(float(numerator) / float(denominator), 0.0, 1.0)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class GenerationProfileMetrics:
    """Aggregate metrics for a single generation_profile_id.

    Any field whose underlying metric is unavailable (e.g. A2 / A3) holds
    ``0`` or ``0.0`` per repository convention while ``min_sample_size_met``
    and ``confidence`` stay conservative.
    """

    run_id: str
    generation_profile_id: str = UNKNOWN_PROFILE_ID
    generation_profile_fingerprint: str = UNAVAILABLE_FINGERPRINT
    profile_name: str = UNKNOWN_PROFILE_ID
    profile_config_hash: str = UNAVAILABLE_FINGERPRINT
    total_batches: int = 0
    total_candidates_generated: int = 0
    total_entered_a1: int = 0
    total_passed_a1: int = 0
    total_rejected_a1: int = 0
    avg_a1_pass_rate: float = 0.0
    total_entered_a2: int = 0
    total_passed_a2: int = 0
    total_rejected_a2: int = 0
    avg_a2_pass_rate: float = 0.0
    total_entered_a3: int = 0
    total_passed_a3: int = 0
    total_rejected_a3: int = 0
    avg_a3_pass_rate: float = 0.0
    total_deployable_count: int = 0
    avg_deployable_count: float = 0.0
    signal_too_sparse_count: int = 0
    signal_too_sparse_rate: float = 0.0
    oos_fail_count: int = 0
    oos_fail_rate: float = 0.0
    unknown_reject_count: int = 0
    unknown_reject_rate: float = 0.0
    instability_penalty: float = 0.0
    profile_score: float = 0.0
    next_budget_weight_dry_run: float = EXPLORATION_FLOOR
    sample_size_rounds: int = 0
    min_sample_size_met: bool = False
    confidence: str = CONFIDENCE_LOW_UNTIL_A2_A3
    mode: str = MODE_READ_ONLY
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)
    telemetry_version: str = TELEMETRY_VERSION
    source: str = "generation_profile_metrics"

    def to_event(self) -> dict:
        payload = asdict(self)
        payload["event_type"] = EVENT_TYPE_GENERATION_PROFILE_METRICS
        return payload


def compute_profile_score(
    *,
    avg_a1_pass_rate: float,
    avg_a2_pass_rate: float,
    avg_a3_pass_rate: float,
    avg_deployable_count: float,
    signal_too_sparse_rate: float,
    oos_fail_rate: float,
    unknown_reject_rate: float,
    instability_penalty: float,
    deployable_ceiling: float = 10.0,
    weights: Optional[Mapping[str, float]] = None,
) -> float:
    """Compute the read-only composite profile_score.

    The score is capped to ``[PROFILE_SCORE_MIN, PROFILE_SCORE_MAX]``.
    Never raises — invalid inputs are coerced to safe defaults.
    """
    try:
        w = dict(DEFAULT_WEIGHTS)
        if weights:
            w.update({k: float(v) for k, v in weights.items()})
        deploy_norm = 0.0
        if deployable_ceiling > 0:
            deploy_norm = _clip(
                float(avg_deployable_count) / float(deployable_ceiling),
                0.0,
                1.0,
            )
        score = (
            w["w1_avg_a1_pass_rate"] * _clip(avg_a1_pass_rate, 0.0, 1.0)
            + w["w2_avg_a2_pass_rate"] * _clip(avg_a2_pass_rate, 0.0, 1.0)
            + w["w3_avg_a3_pass_rate"] * _clip(avg_a3_pass_rate, 0.0, 1.0)
            + w["w4_deployable_score"] * deploy_norm
            - w["w5_signal_too_sparse_penalty"]
            * _clip(signal_too_sparse_rate, 0.0, 1.0)
            - w["w6_oos_fail_penalty"] * _clip(oos_fail_rate, 0.0, 1.0)
            - w["w7_unknown_reject_penalty"]
            * _clip(unknown_reject_rate, 0.0, 1.0)
            - w["w8_instability_penalty"]
            * _clip(instability_penalty, 0.0, 1.0)
        )
        return _clip(score, PROFILE_SCORE_MIN, PROFILE_SCORE_MAX)
    except Exception:
        return 0.0


def compute_dry_run_budget_weight(
    profile_score: float,
    *,
    exploration_floor: float = EXPLORATION_FLOOR,
    min_sample_size_met: bool = False,
) -> float:
    """Recommendation-only weight in [exploration_floor, 1.0].

    Not min_sample_size_met → return exactly ``exploration_floor``.
    """
    try:
        if not min_sample_size_met:
            return float(exploration_floor)
        base = 0.5 + 0.5 * float(profile_score)
        return _clip(base, float(exploration_floor), 1.0)
    except Exception:
        return float(exploration_floor)


def aggregate_batches_for_profile(
    batch_events: Iterable[Mapping[str, Any]],
    *,
    run_id: str,
    generation_profile_id: str = UNKNOWN_PROFILE_ID,
    generation_profile_fingerprint: str = UNAVAILABLE_FINGERPRINT,
    profile_name: Optional[str] = None,
    profile_config_hash: Optional[str] = None,
    weights: Optional[Mapping[str, float]] = None,
    deployable_ceiling: float = 10.0,
) -> GenerationProfileMetrics:
    """Aggregate a list of ``arena_batch_metrics`` events into one
    ``GenerationProfileMetrics`` record. Never raises.

    A2 / A3 aggregates default to 0 because P7-PR4-LITE only wired A1.
    """
    metrics = GenerationProfileMetrics(
        run_id=run_id,
        generation_profile_id=generation_profile_id,
        generation_profile_fingerprint=generation_profile_fingerprint,
        profile_name=profile_name or generation_profile_id,
        profile_config_hash=(
            profile_config_hash or generation_profile_fingerprint
        ),
    )
    try:
        batches: List[Mapping[str, Any]] = [
            b for b in batch_events if isinstance(b, Mapping)
        ]
        if not batches:
            metrics.confidence = CONFIDENCE_LOW_UNTIL_A2_A3
            return metrics

        a1_pass_rates: List[float] = []
        a2_pass_rates: List[float] = []
        a3_pass_rates: List[float] = []
        deployable_values: List[int] = []

        for b in batches:
            stage = str(b.get("arena_stage", "")).upper()
            entered = int(b.get("entered_count", 0) or 0)
            passed = int(b.get("passed_count", 0) or 0)
            rejected = int(b.get("rejected_count", 0) or 0)
            dist = b.get("reject_reason_distribution") or {}
            if stage == "A1":
                metrics.total_entered_a1 += entered
                metrics.total_passed_a1 += passed
                metrics.total_rejected_a1 += rejected
                a1_pass_rates.append(_safe_rate(passed, entered))
            elif stage == "A2":
                metrics.total_entered_a2 += entered
                metrics.total_passed_a2 += passed
                metrics.total_rejected_a2 += rejected
                a2_pass_rates.append(_safe_rate(passed, entered))
            elif stage == "A3":
                metrics.total_entered_a3 += entered
                metrics.total_passed_a3 += passed
                metrics.total_rejected_a3 += rejected
                a3_pass_rates.append(_safe_rate(passed, entered))
            deployable = b.get("deployable_count")
            if isinstance(deployable, int):
                deployable_values.append(deployable)
            for reason_name, count in dict(dist).items():
                cnum = int(count or 0)
                if reason_name == "SIGNAL_TOO_SPARSE":
                    metrics.signal_too_sparse_count += cnum
                elif reason_name in ("OOS_FAIL", "OOS_OVERFIT"):
                    metrics.oos_fail_count += cnum
                elif reason_name == "UNKNOWN_REJECT":
                    metrics.unknown_reject_count += cnum

        metrics.total_batches = len(batches)
        metrics.total_candidates_generated = metrics.total_entered_a1
        metrics.sample_size_rounds = metrics.total_batches
        metrics.min_sample_size_met = (
            metrics.sample_size_rounds >= MIN_SAMPLE_SIZE_ROUNDS
        )
        metrics.avg_a1_pass_rate = (
            sum(a1_pass_rates) / len(a1_pass_rates) if a1_pass_rates else 0.0
        )
        metrics.avg_a2_pass_rate = (
            sum(a2_pass_rates) / len(a2_pass_rates) if a2_pass_rates else 0.0
        )
        metrics.avg_a3_pass_rate = (
            sum(a3_pass_rates) / len(a3_pass_rates) if a3_pass_rates else 0.0
        )
        if deployable_values:
            metrics.total_deployable_count = sum(deployable_values)
            metrics.avg_deployable_count = metrics.total_deployable_count / len(
                deployable_values
            )

        total_rejects = (
            metrics.total_rejected_a1
            + metrics.total_rejected_a2
            + metrics.total_rejected_a3
        )
        metrics.signal_too_sparse_rate = _safe_rate(
            metrics.signal_too_sparse_count, total_rejects
        )
        metrics.oos_fail_rate = _safe_rate(
            metrics.oos_fail_count, total_rejects
        )
        metrics.unknown_reject_rate = _safe_rate(
            metrics.unknown_reject_count, total_rejects
        )

        if len(a1_pass_rates) >= 2:
            mean_rate = sum(a1_pass_rates) / len(a1_pass_rates)
            variance = sum((r - mean_rate) ** 2 for r in a1_pass_rates) / len(
                a1_pass_rates
            )
            stddev = variance ** 0.5
            denominator = mean_rate if mean_rate > 0 else 1.0
            metrics.instability_penalty = _clip(stddev / denominator, 0.0, 1.0)

        metrics.profile_score = compute_profile_score(
            avg_a1_pass_rate=metrics.avg_a1_pass_rate,
            avg_a2_pass_rate=metrics.avg_a2_pass_rate,
            avg_a3_pass_rate=metrics.avg_a3_pass_rate,
            avg_deployable_count=metrics.avg_deployable_count,
            signal_too_sparse_rate=metrics.signal_too_sparse_rate,
            oos_fail_rate=metrics.oos_fail_rate,
            unknown_reject_rate=metrics.unknown_reject_rate,
            instability_penalty=metrics.instability_penalty,
            deployable_ceiling=deployable_ceiling,
            weights=weights,
        )
        metrics.next_budget_weight_dry_run = compute_dry_run_budget_weight(
            metrics.profile_score,
            min_sample_size_met=metrics.min_sample_size_met,
        )
        a2_a3_available = metrics.total_entered_a2 > 0 and metrics.total_entered_a3 > 0
        # P7-PR4B confidence resolution (per order §8):
        #   A2/A3 unavailable               → LOW_CONFIDENCE_UNTIL_A2_A3_METRICS_AVAILABLE
        #   A2/A3 available + samples < 20  → LOW_SAMPLE_SIZE_UNTIL_20_ROUNDS
        #   A2/A3 available + samples >= 20 → CONFIDENCE_A1_A2_A3_METRICS_AVAILABLE
        if not a2_a3_available:
            metrics.confidence = CONFIDENCE_LOW_UNTIL_A2_A3
        elif not metrics.min_sample_size_met:
            metrics.confidence = CONFIDENCE_LOW_SAMPLE_SIZE
        else:
            metrics.confidence = CONFIDENCE_A1_A2_A3_AVAILABLE
        metrics.updated_at = _utc_now_iso()
        return metrics
    except Exception:
        metrics.confidence = CONFIDENCE_LOW_UNTIL_A2_A3
        return metrics


def rank_profiles(
    profile_metrics: Iterable[GenerationProfileMetrics],
) -> List[GenerationProfileMetrics]:
    """Return profile metrics sorted by profile_score (descending). Read-only."""
    try:
        return sorted(
            list(profile_metrics),
            key=lambda m: m.profile_score,
            reverse=True,
        )
    except Exception:
        return list(profile_metrics)


def safe_build_generation_profile_metrics(
    batch_events: Iterable[Mapping[str, Any]],
    *,
    run_id: str,
    generation_profile_id: str = UNKNOWN_PROFILE_ID,
    generation_profile_fingerprint: str = UNAVAILABLE_FINGERPRINT,
    profile_name: Optional[str] = None,
    profile_config_hash: Optional[str] = None,
) -> Optional[GenerationProfileMetrics]:
    """Exception-safe builder. Returns None on failure."""
    try:
        return aggregate_batches_for_profile(
            batch_events,
            run_id=run_id,
            generation_profile_id=generation_profile_id,
            generation_profile_fingerprint=generation_profile_fingerprint,
            profile_name=profile_name,
            profile_config_hash=profile_config_hash,
        )
    except Exception:
        return None
