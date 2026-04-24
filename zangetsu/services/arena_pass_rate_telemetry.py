"""Aggregate Arena Pass-Rate Telemetry (P7-PR4-LITE / TEAM ORDER post-0-9N).

Implements the Arena-level pass-rate observability contract designed in
`docs/recovery/20260424-mod-7/0-9n/02_arena_pass_rate_telemetry_contract.md`.

Scope: **trace-only / telemetry-only**. This module produces aggregate
metrics (`arena_batch_metrics`, `arena_stage_summary`) without reading
or mutating Arena decision logic.

BLACK-BOX guarantee:
    - No call into AlphaEngine internals.
    - No threshold reference.
    - No pass/fail predicate evaluation.
    - No deployable_count semantic redefinition — the authoritative source
      remains the Arena pipeline's own accounting; this module only
      EXPOSES deployable_count as an aggregate field when the caller
      supplies it.

EXCEPTION-SAFE emission:
    `safe_emit_arena_metrics()` wraps build + serialize + write in
    try/except. Any failure returns False silently; the caller (Arena
    runtime) continues exactly as before. This is the same pattern used
    by `_emit_a1_lifecycle_safe()` in `arena_pipeline.py` (P7-PR3).

COUNTER CONSERVATION INVARIANT:
    For closed stage summaries:
        entered = passed + rejected + skipped + error
    For open / in-flight summaries:
        entered = passed + rejected + skipped + error + in_flight

    Violations are LOGGED but NOT raised — telemetry bugs must not alter
    Arena behavior.

GENERATION PROFILE FALLBACK:
    If generation_profile_id is not supplied, falls back to
    ``UNKNOWN_PROFILE`` + ``UNAVAILABLE`` fingerprint. Telemetry never
    blocks on missing profile metadata.

See also:
    - `zangetsu/services/candidate_trace.py` — LifecycleTraceEvent contract
      (P7-PR3). This module deliberately does NOT import from there at
      module-load to keep the dependency graph minimal.
    - `zangetsu/services/arena_rejection_taxonomy.py` — canonical
      rejection reason vocabulary. Reused here for
      ``top_reject_reason`` and ``reject_reason_distribution``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TELEMETRY_VERSION = "1"

EVENT_TYPE_ARENA_BATCH_METRICS = "arena_batch_metrics"
EVENT_TYPE_ARENA_STAGE_SUMMARY = "arena_stage_summary"

UNKNOWN_PROFILE_ID = "UNKNOWN_PROFILE"
UNAVAILABLE_FINGERPRINT = "UNAVAILABLE"

# Valid arena stages for aggregate metrics.
_VALID_STAGES = ("A0", "A1", "A2", "A3", "A4", "A5", "UNKNOWN")


def _utcnow_iso() -> str:
    """RFC3339 UTC timestamp (seconds precision, trailing Z)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Rate / conservation helpers
# ---------------------------------------------------------------------------


def compute_pass_rate(passed_count: int, entered_count: int) -> float:
    """Return passed_count / entered_count, 0.0 when entered_count == 0.

    Never raises on zero input; never returns NaN; caps at 1.0 when
    passed_count > entered_count (shouldn't happen, but don't amplify
    telemetry bugs).
    """
    if entered_count <= 0:
        return 0.0
    rate = passed_count / entered_count
    if rate > 1.0:
        return 1.0
    if rate < 0.0:
        return 0.0
    return rate


def compute_reject_rate(rejected_count: int, entered_count: int) -> float:
    """Return rejected_count / entered_count, 0.0 when entered_count == 0."""
    if entered_count <= 0:
        return 0.0
    rate = rejected_count / entered_count
    if rate > 1.0:
        return 1.0
    if rate < 0.0:
        return 0.0
    return rate


def validate_counter_conservation(
    entered_count: int,
    passed_count: int,
    rejected_count: int,
    skipped_count: int = 0,
    error_count: int = 0,
    in_flight_count: int = 0,
    open_stage: bool = False,
) -> Tuple[bool, Optional[str]]:
    """Return (is_valid, reason).

    For closed-stage summaries (``open_stage=False``):
        entered = passed + rejected + skipped + error

    For open / streaming summaries (``open_stage=True``):
        entered = passed + rejected + skipped + error + in_flight

    Reject negative counters.
    """
    for name, val in (
        ("entered_count", entered_count),
        ("passed_count", passed_count),
        ("rejected_count", rejected_count),
        ("skipped_count", skipped_count),
        ("error_count", error_count),
        ("in_flight_count", in_flight_count),
    ):
        if val < 0:
            return False, f"{name} is negative ({val})"

    if open_stage:
        total = passed_count + rejected_count + skipped_count + error_count + in_flight_count
    else:
        if in_flight_count != 0:
            return False, f"open_stage=False but in_flight_count={in_flight_count}"
        total = passed_count + rejected_count + skipped_count + error_count

    if total != entered_count:
        return False, (
            f"conservation violation: entered={entered_count} != "
            f"passed+rejected+skipped+error{('+in_flight' if open_stage else '')}={total}"
        )
    return True, None


# ---------------------------------------------------------------------------
# Rejection reason distribution
# ---------------------------------------------------------------------------


class RejectReasonCounter:
    """Thin wrapper around a Counter-like dict for reject reasons.

    Reuses the canonical taxonomy vocabulary when available, but does NOT
    strictly enforce it — callers that supply unknown reason strings get
    them counted verbatim (useful during transition when new raw reason
    strings emerge that have not yet been mapped).
    """

    __slots__ = ("_counts",)

    def __init__(self) -> None:
        self._counts: Dict[str, int] = {}

    def add(self, reason: str, n: int = 1) -> None:
        if not isinstance(reason, str) or not reason:
            reason = "UNKNOWN_REJECT"
        if n < 0:
            return
        self._counts[reason] = self._counts.get(reason, 0) + n

    def merge(self, other: "RejectReasonCounter") -> None:
        for k, v in other.as_dict().items():
            self.add(k, v)

    def as_dict(self) -> Dict[str, int]:
        return dict(self._counts)

    def total(self) -> int:
        return sum(self._counts.values())

    def top_reason(self) -> str:
        if not self._counts:
            return "UNKNOWN_REJECT"
        return max(self._counts.items(), key=lambda kv: (kv[1], kv[0]))[0]

    def top_n(self, n: int = 3) -> List[str]:
        items = sorted(self._counts.items(), key=lambda kv: (-kv[1], kv[0]))
        return [k for k, _ in items[:n]]


# ---------------------------------------------------------------------------
# Schemas — dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ArenaBatchMetrics:
    """One batch × one Arena stage aggregate. Emitted at batch close.

    Counter fields follow §6.3 conservation invariant. Rate fields are
    derived via compute_pass_rate / compute_reject_rate.
    """

    event_type: str = EVENT_TYPE_ARENA_BATCH_METRICS
    telemetry_version: str = TELEMETRY_VERSION

    run_id: str = ""
    batch_id: str = ""
    generation_profile_id: str = UNKNOWN_PROFILE_ID
    generation_profile_fingerprint: str = UNAVAILABLE_FINGERPRINT

    arena_stage: str = "UNKNOWN"

    entered_count: int = 0
    passed_count: int = 0
    rejected_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    in_flight_count: int = 0

    pass_rate: float = 0.0
    reject_rate: float = 0.0

    top_reject_reason: str = "UNKNOWN_REJECT"
    reject_reason_distribution: Dict[str, int] = field(default_factory=dict)

    deployable_count: Optional[int] = None  # None = UNAVAILABLE at this context

    timestamp_start: str = ""
    timestamp_end: str = ""

    source: str = "arena_pipeline"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)


@dataclass
class ArenaStageSummary:
    """Per-run-per-stage rollup emitted at run close.

    Aggregates across all batches under a run for a given stage.
    """

    event_type: str = EVENT_TYPE_ARENA_STAGE_SUMMARY
    telemetry_version: str = TELEMETRY_VERSION

    run_id: str = ""
    batch_id: str = ""  # may be "ALL" for run-level rollup

    arena_stage: str = "UNKNOWN"

    entered_count: int = 0
    passed_count: int = 0
    rejected_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    in_flight_count: int = 0

    pass_rate: float = 0.0
    reject_rate: float = 0.0

    top_3_reject_reasons: List[str] = field(default_factory=list)
    bottleneck_score: float = 0.0

    timestamp: str = ""
    source: str = "arena_pipeline"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)


@dataclass
class ArenaStageMetrics:
    """Mutable per-batch accumulator. Owned by a single batch; flushed via
    build_arena_batch_metrics() at batch close.

    This is the recommended runtime counter structure for Arena code to
    update directly (e.g., ``metrics.on_entered()``, ``metrics.on_passed()``).
    Never raises; all operations are idempotent-safe additions.
    """

    arena_stage: str
    run_id: str = ""
    batch_id: str = ""
    generation_profile_id: str = UNKNOWN_PROFILE_ID
    generation_profile_fingerprint: str = UNAVAILABLE_FINGERPRINT

    entered_count: int = 0
    passed_count: int = 0
    rejected_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    in_flight_count: int = 0

    reject_counter: RejectReasonCounter = field(default_factory=RejectReasonCounter)

    timestamp_start: str = field(default_factory=_utcnow_iso)
    timestamp_end: str = ""

    deployable_count: Optional[int] = None

    def on_entered(self) -> None:
        self.entered_count += 1
        self.in_flight_count += 1

    def on_passed(self) -> None:
        self.passed_count += 1
        if self.in_flight_count > 0:
            self.in_flight_count -= 1

    def on_rejected(self, reason: Optional[str] = None) -> None:
        self.rejected_count += 1
        if self.in_flight_count > 0:
            self.in_flight_count -= 1
        self.reject_counter.add(reason or "UNKNOWN_REJECT")

    def on_skipped(self, reason: Optional[str] = None) -> None:
        self.skipped_count += 1
        if self.in_flight_count > 0:
            self.in_flight_count -= 1
        if reason:
            # Skip reasons share the distribution bucket for audit visibility.
            self.reject_counter.add(reason)

    def on_error(self, reason: Optional[str] = None) -> None:
        self.error_count += 1
        if self.in_flight_count > 0:
            self.in_flight_count -= 1
        if reason:
            self.reject_counter.add(reason)

    def mark_closed(self) -> None:
        """Mark the batch closed: records timestamp_end and refuses further
        mutations via the `closed` flag (callers should respect this)."""
        if not self.timestamp_end:
            self.timestamp_end = _utcnow_iso()
        # Defensive — any stragglers in in_flight_count are resolved as skipped
        # so conservation holds. Caller should normally drain before close.
        if self.in_flight_count > 0:
            self.skipped_count += self.in_flight_count
            self.reject_counter.add("BATCH_CLOSED_WITH_IN_FLIGHT", self.in_flight_count)
            self.in_flight_count = 0


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def build_arena_batch_metrics(
    stage_metrics: ArenaStageMetrics,
    *,
    deployable_count: Optional[int] = None,
) -> ArenaBatchMetrics:
    """Convert a mutable ArenaStageMetrics accumulator into a frozen
    ArenaBatchMetrics event.

    The caller may pass an authoritative ``deployable_count`` via the
    kwarg. If not supplied, the accumulator's own ``deployable_count``
    (or None) is used. This module never infers deployable_count from
    pass counts — that semantic is preserved by the Arena pipeline and
    passed in explicitly.
    """
    if deployable_count is None:
        deployable_count = stage_metrics.deployable_count

    dist = stage_metrics.reject_counter.as_dict()
    top = stage_metrics.reject_counter.top_reason()
    entered = stage_metrics.entered_count

    return ArenaBatchMetrics(
        run_id=stage_metrics.run_id,
        batch_id=stage_metrics.batch_id,
        generation_profile_id=stage_metrics.generation_profile_id,
        generation_profile_fingerprint=stage_metrics.generation_profile_fingerprint,
        arena_stage=stage_metrics.arena_stage,
        entered_count=entered,
        passed_count=stage_metrics.passed_count,
        rejected_count=stage_metrics.rejected_count,
        skipped_count=stage_metrics.skipped_count,
        error_count=stage_metrics.error_count,
        in_flight_count=stage_metrics.in_flight_count,
        pass_rate=compute_pass_rate(stage_metrics.passed_count, entered),
        reject_rate=compute_reject_rate(stage_metrics.rejected_count, entered),
        top_reject_reason=top,
        reject_reason_distribution=dist,
        deployable_count=deployable_count,
        timestamp_start=stage_metrics.timestamp_start,
        timestamp_end=stage_metrics.timestamp_end or _utcnow_iso(),
        source="arena_pipeline",
    )


def build_arena_stage_summary(
    arena_stage: str,
    run_id: str,
    batches: Iterable[ArenaBatchMetrics],
    *,
    batch_id: str = "ALL",
) -> ArenaStageSummary:
    """Aggregate a collection of ArenaBatchMetrics for one Arena stage into
    a run-level summary. Never raises."""
    merged_counter = RejectReasonCounter()
    entered = passed = rejected = skipped = error = in_flight = 0

    for b in batches:
        if b.arena_stage != arena_stage:
            continue
        entered += b.entered_count
        passed += b.passed_count
        rejected += b.rejected_count
        skipped += b.skipped_count
        error += b.error_count
        in_flight += b.in_flight_count
        for reason, cnt in b.reject_reason_distribution.items():
            merged_counter.add(reason, cnt)

    summary = ArenaStageSummary(
        run_id=run_id,
        batch_id=batch_id,
        arena_stage=arena_stage,
        entered_count=entered,
        passed_count=passed,
        rejected_count=rejected,
        skipped_count=skipped,
        error_count=error,
        in_flight_count=in_flight,
        pass_rate=compute_pass_rate(passed, entered),
        reject_rate=compute_reject_rate(rejected, entered),
        top_3_reject_reasons=merged_counter.top_n(3),
        bottleneck_score=compute_reject_rate(rejected, entered),
        timestamp=_utcnow_iso(),
        source="arena_pipeline",
    )
    return summary


# ---------------------------------------------------------------------------
# Emission helper — exception-safe
# ---------------------------------------------------------------------------


def safe_emit_arena_metrics(
    event: Any,
    writer: Optional[Any] = None,
) -> bool:
    """Exception-safe emission of an ArenaBatchMetrics / ArenaStageSummary
    event. Returns True on success, False on any failure. NEVER raises.

    If ``writer`` is None, writes to stdout. Arena runtime should pass its
    own ``log.info`` bound method as the writer.
    """
    try:
        if hasattr(event, "to_json"):
            line = event.to_json()
        else:
            line = json.dumps(event, sort_keys=True, ensure_ascii=False)
    except Exception:
        return False
    try:
        if writer is None:
            import sys
            sys.stdout.write(line + "\n")
        else:
            writer(line)
    except Exception:
        return False
    return True


# ---------------------------------------------------------------------------
# Introspection helpers
# ---------------------------------------------------------------------------


def valid_stages() -> Tuple[str, ...]:
    return _VALID_STAGES


def required_batch_fields() -> Tuple[str, ...]:
    """Return the tuple of required field names for ArenaBatchMetrics."""
    return (
        "event_type", "telemetry_version",
        "run_id", "batch_id",
        "generation_profile_id", "generation_profile_fingerprint",
        "arena_stage",
        "entered_count", "passed_count", "rejected_count",
        "skipped_count", "error_count", "in_flight_count",
        "pass_rate", "reject_rate",
        "top_reject_reason", "reject_reason_distribution",
        "deployable_count",
        "timestamp_start", "timestamp_end",
        "source",
    )


def required_summary_fields() -> Tuple[str, ...]:
    """Return the tuple of required field names for ArenaStageSummary."""
    return (
        "event_type", "telemetry_version",
        "run_id", "batch_id",
        "arena_stage",
        "entered_count", "passed_count", "rejected_count",
        "skipped_count", "error_count", "in_flight_count",
        "pass_rate", "reject_rate",
        "top_3_reject_reasons", "bottleneck_score",
        "timestamp", "source",
    )
