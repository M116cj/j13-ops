"""Arena Rejection Telemetry (P7-PR1 / MOD-7 / Phase 7).

Defines the telemetry record schema that captures WHICH candidate was
rejected WHERE for WHICH canonical reason, along with sufficient context
to make the rejection auditable:

  - ``RejectionTrace`` — a single rejection event (20+ fields per 0-9E §7).
  - ``TelemetryCollector`` — an in-process accumulator that produces
    rejection counters, Arena-2 breakdown, UNKNOWN_REJECT ratio, and a
    JSON-serializable summary suitable for SHADOW-mode observation.

INSTRUMENTATION-ONLY guarantee (0-9E §8 / §9):
    This module never invokes Arena runtime, never mutates thresholds,
    never changes candidate pass/fail outcomes. Collectors are intended
    to be populated by SHADOW wrappers or future P7-PR2 integration;
    P7-PR1 only provides the schema + collector contract.

Design principles:
    - Dataclasses with explicit field types for static auditability.
    - JSON round-trip safe (stdlib ``json`` only).
    - No I/O side effects in this module — writing to disk / DB is the
      caller's decision.
    - Counters are pure aggregates, not live metrics — avoids double
      coupling with ops-metrics systems.

See: docs/recovery/20260424-mod-7/p7_pr1_execution_report.md
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from zangetsu.services.arena_rejection_taxonomy import (
    ArenaStage,
    RejectionCategory,
    RejectionReason,
    RejectionSeverity,
    REJECTION_METADATA,
    classify,
)


# Mandatory fields per 0-9E §7.
_REQUIRED_FIELDS: Tuple[str, ...] = (
    "candidate_id",
    "alpha_id",
    "formula_hash",
    "source_pool",
    "arena_stage",
    "previous_stage_status",
    "reject_reason",
    "reject_category",
    "reject_severity",
    "timestamp_utc",
    "run_id",
    "commit_sha",
    "config_hash",
    "dataset_id_or_window",
    "arena_0_status",
    "arena_1_status",
    "arena_2_status",
    "arena_3_status",
    "deployable_candidate",
    "notes",
)

# Arena-2 extended fields per 0-9E §7.
_ARENA2_EXTRA_FIELDS: Tuple[str, ...] = (
    "arena_1_score",
    "fresh_score",
    "oos_score",
    "cost_adjusted_score",
    "turnover",
    "drawdown",
    "hit_rate",
    "signal_count",
    "signal_density",
    "regime_label",
    "promotion_blocker",
)


def _utcnow_iso() -> str:
    """RFC3339-style UTC timestamp (stable for logging / snapshot comparison)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class RejectionTrace:
    """A single candidate rejection trace. All required fields per 0-9E §7."""

    # Required identity fields
    candidate_id: str
    alpha_id: Optional[str] = None
    formula_hash: Optional[str] = None
    source_pool: Optional[str] = None

    # Stage + outcome
    arena_stage: str = ArenaStage.UNKNOWN.value
    previous_stage_status: Optional[str] = None
    reject_reason: str = RejectionReason.UNKNOWN_REJECT.value
    reject_category: str = RejectionCategory.UNKNOWN.value
    reject_severity: str = RejectionSeverity.WARN.value

    # Run context
    timestamp_utc: str = field(default_factory=_utcnow_iso)
    run_id: Optional[str] = None
    commit_sha: Optional[str] = None
    config_hash: Optional[str] = None
    dataset_id_or_window: Optional[str] = None

    # Per-stage status (A0/A1/A2/A3 — "PASS", "REJECT", "SKIPPED", "NOT_RUN")
    arena_0_status: str = "NOT_RUN"
    arena_1_status: str = "NOT_RUN"
    arena_2_status: str = "NOT_RUN"
    arena_3_status: str = "NOT_RUN"

    # Deployable flag — True only if candidate reached final deployable pool.
    deployable_candidate: bool = False

    # Free-form notes (e.g. raw log line that produced the classification).
    notes: Optional[str] = None

    # Arena-2 extras. Populated where available; None otherwise.
    arena_1_score: Optional[float] = None
    fresh_score: Optional[float] = None
    oos_score: Optional[float] = None
    cost_adjusted_score: Optional[float] = None
    turnover: Optional[float] = None
    drawdown: Optional[float] = None
    hit_rate: Optional[float] = None
    signal_count: Optional[int] = None
    signal_density: Optional[float] = None
    regime_label: Optional[str] = None
    promotion_blocker: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain-dict view safe for JSON serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Return a canonical JSON string (stable key order, UTF-8 safe)."""
        return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RejectionTrace":
        """Rehydrate a trace from a JSON-compatible dict."""
        known = {k: data.get(k) for k in _REQUIRED_FIELDS + _ARENA2_EXTRA_FIELDS if k in data}
        return cls(**known)

    def missing_required_fields(self) -> Tuple[str, ...]:
        """List any required fields whose value is ``None``."""
        missing: List[str] = []
        for name in _REQUIRED_FIELDS:
            if getattr(self, name, None) is None:
                missing.append(name)
        return tuple(missing)


@dataclass
class TelemetryCollector:
    """In-process accumulator for rejection traces across a pipeline run.

    Intended use pattern (SHADOW mode):
        collector = TelemetryCollector(run_id="shadow-2026-04-24")
        collector.record(trace)
        summary = collector.summary()
        json.dumps(summary)  # write to shadow_execution_log.txt

    The collector never triggers I/O. Callers choose when/how to persist.
    """

    run_id: str
    traces: List[RejectionTrace] = field(default_factory=list)

    def record(self, trace: RejectionTrace) -> None:
        self.traces.append(trace)

    def total_rejections(self) -> int:
        return len(self.traces)

    def counts_by_reason(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for t in self.traces:
            out[t.reject_reason] = out.get(t.reject_reason, 0) + 1
        return out

    def counts_by_stage(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for t in self.traces:
            out[t.arena_stage] = out.get(t.arena_stage, 0) + 1
        return out

    def arena2_breakdown(self) -> Dict[str, int]:
        """Distribution of rejection reasons at Arena stage A2 only."""
        out: Dict[str, int] = {}
        for t in self.traces:
            if t.arena_stage == ArenaStage.A2.value:
                out[t.reject_reason] = out.get(t.reject_reason, 0) + 1
        return out

    def unknown_reject_ratio(self) -> float:
        """Fraction of traces classified as UNKNOWN_REJECT. 0..1, 0 if empty."""
        n = len(self.traces)
        if n == 0:
            return 0.0
        u = sum(
            1
            for t in self.traces
            if t.reject_reason == RejectionReason.UNKNOWN_REJECT.value
        )
        return u / n

    def summary(self) -> Dict[str, Any]:
        """JSON-serializable structured summary suitable for SHADOW reports."""
        return {
            "run_id": self.run_id,
            "total_rejections": self.total_rejections(),
            "counts_by_reason": self.counts_by_reason(),
            "counts_by_stage": self.counts_by_stage(),
            "arena2_breakdown": self.arena2_breakdown(),
            "unknown_reject_ratio": round(self.unknown_reject_ratio(), 6),
            "generated_at_utc": _utcnow_iso(),
        }

    def to_json(self) -> str:
        return json.dumps(self.summary(), sort_keys=True, ensure_ascii=False)


def make_rejection_trace(
    candidate_id: str,
    raw_reason: Optional[str] = None,
    arena_stage: Optional[str] = None,
    alpha_id: Optional[str] = None,
    formula_hash: Optional[str] = None,
    extras: Optional[Mapping[str, Any]] = None,
) -> RejectionTrace:
    """Build a ``RejectionTrace`` by classifying ``raw_reason`` via taxonomy.

    Convenience helper for callers that don't want to resolve classification
    themselves. Never raises; returns a UNKNOWN_REJECT trace if raw_reason
    is unmappable.
    """
    reason, category, stage = classify(raw_reason=raw_reason, arena_stage=arena_stage)
    meta = REJECTION_METADATA[reason]
    trace = RejectionTrace(
        candidate_id=candidate_id,
        alpha_id=alpha_id,
        formula_hash=formula_hash,
        arena_stage=stage.value,
        reject_reason=reason.value,
        reject_category=category.value,
        reject_severity=meta.severity.value,
    )
    if extras:
        for k, v in extras.items():
            if hasattr(trace, k):
                setattr(trace, k, v)
    return trace


def required_fields() -> Tuple[str, ...]:
    """Return the tuple of mandatory field names for a valid RejectionTrace."""
    return _REQUIRED_FIELDS


def arena2_extra_fields() -> Tuple[str, ...]:
    """Return the tuple of Arena-2 extended field names."""
    return _ARENA2_EXTRA_FIELDS
