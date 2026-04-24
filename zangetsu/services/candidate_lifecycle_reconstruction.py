"""Candidate Lifecycle Reconstruction (P7-PR2 / MOD-7 / Phase 7 / 0-9K).

Post-hoc reconstructs ``CandidateLifecycle`` records by parsing existing
engine.jsonl log streams. Joins A2/A3 events by ``id=<N>`` to produce a
per-candidate view of stage transitions, final resolution, and rejection
reasons. Computes ``deployable_count`` with full provenance via the
companion helper in :mod:`zangetsu.services.candidate_trace`.

INSTRUMENTATION-ONLY guarantee (0-9K §3):
    Read-only. No Arena runtime code is imported or executed. No thresholds,
    no alpha generation, no pass/fail logic is changed. This module takes
    a stream of existing logs as input and produces lifecycle records as
    output. It NEVER mutates production state, database, or runtime services.

Known coverage in the current engine.jsonl observation window
(2026-04-16 → 2026-04-23, sampled on origin/main `419f3d9f`):

    Event pattern                Count    Interpretation
    ---------------------------  -------  ----------------------------------
    "A2 PASS id=<N> ..."          7,153   A2 entry + exit PASS
    "A2 REJECTED id=<N>: <r>"     3,395   A2 entry + exit REJECT
    "A3 COMPLETE id=<N> ..."          6   A3 entry + exit PASS → DEPLOYABLE
    "A3 REJECTED id=<N>: <r>"        29   A3 entry + exit REJECT
    "A3 PREFILTER SKIP id=<N>"       23   A3 entry, exit SKIPPED (pre-filter)

A1 events do not log an explicit per-candidate PASS line in the current
runtime; a candidate reaching A2 is INFERRED to have passed A1. This
inference is explicitly recorded as a "missing field" when applicable.

Deployable definition (aligned with ``CandidateLifecycle.is_deployable``):
    a candidate is deployable iff A1 PASS AND A2 PASS AND A3 PASS (COMPLETE)
    AND no governance blocker. Per-stage PASS may be inferred from the
    absence of a corresponding reject/skip record, but the final A3 COMPLETE
    is the authoritative deployable signal in current logs.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from zangetsu.services.arena_rejection_taxonomy import classify
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
)


# Patterns for lifecycle-relevant log-line extraction.
# Each pattern captures (id, symbol, rest) where applicable.
_RE_A2_PASS = re.compile(r"^\s*A2\s+PASS\s+id=(\S+)\s+(\S+)")
_RE_A2_REJECTED = re.compile(r"^\s*A2\s+REJECTED\s+id=(\S+)\s+(\S+?)[:\s]\s*(.+?)(?:\s*\||$)")
_RE_A3_COMPLETE = re.compile(r"^\s*A3\s+COMPLETE\s+id=(\S+)\s+(\S+)")
_RE_A3_REJECTED = re.compile(r"^\s*A3\s+REJECTED\s+id=(\S+)\s+(\S+?)[:\s]\s*(.+?)(?:\s*\||$)")
_RE_A3_PREFILTER_SKIP = re.compile(r"^\s*A3\s+PREFILTER\s+SKIP\s+id=(\S+)\s+(\S+)")


@dataclass
class ReconstructionStats:
    """Counts captured during a reconstruction pass (for evidence reports)."""

    lines_scanned: int = 0
    events_matched: int = 0
    a2_pass: int = 0
    a2_reject: int = 0
    a3_complete: int = 0
    a3_reject: int = 0
    a3_prefilter_skip: int = 0
    unique_candidates: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            "lines_scanned": self.lines_scanned,
            "events_matched": self.events_matched,
            "a2_pass": self.a2_pass,
            "a2_reject": self.a2_reject,
            "a3_complete": self.a3_complete,
            "a3_reject": self.a3_reject,
            "a3_prefilter_skip": self.a3_prefilter_skip,
            "unique_candidates": self.unique_candidates,
        }


def _parse_jsonl_msg(line: str) -> Optional[Dict[str, Any]]:
    """Return the parsed JSONL event or None if the line is not JSON."""
    line = line.strip()
    if not line.startswith("{"):
        return None
    try:
        return json.loads(line)
    except Exception:
        return None


def _ensure_lifecycle(store: Dict[str, CandidateLifecycle], cid: str) -> CandidateLifecycle:
    """Return the lifecycle for ``cid``, constructing an empty one if absent."""
    if cid not in store:
        store[cid] = CandidateLifecycle(candidate_id=cid)
    return store[cid]


def _infer_upstream_passes(lc: CandidateLifecycle, up_to_stage: str) -> None:
    """When a candidate appears at stage N, its upstream stages (A0..N-1) must
    have passed (otherwise it would have been rejected upstream and never
    reached stage N). Infer those upstream stages as PASS iff they are NOT_RUN.
    Does not overwrite REJECT / SKIPPED / explicit PASS values."""
    order = ["A0", "A1", "A2", "A3", "A4"]
    stages_to_infer = order[: order.index(up_to_stage)]
    fields = {
        "A0": "arena_0_status",
        "A1": "arena_1_status",
        "A2": "arena_2_status",
        "A3": "arena_3_status",
        "A4": "arena_4_status",
    }
    for s in stages_to_infer:
        f = fields[s]
        if getattr(lc, f) == STATUS_NOT_RUN:
            setattr(lc, f, STATUS_PASS)


def _apply_a2_pass(lc: CandidateLifecycle, ts: Optional[str], symbol: Optional[str]) -> None:
    _infer_upstream_passes(lc, "A2")
    if lc.arena_2_entry is None or (ts and ts < lc.arena_2_entry):
        lc.arena_2_entry = ts
    lc.arena_2_status = STATUS_PASS
    if ts and (lc.arena_2_exit is None or ts > lc.arena_2_exit):
        lc.arena_2_exit = ts
    if symbol and lc.source_pool is None:
        lc.source_pool = symbol


def _apply_a2_reject(
    lc: CandidateLifecycle, ts: Optional[str], symbol: Optional[str], raw_reason: str
) -> None:
    _infer_upstream_passes(lc, "A2")
    if lc.arena_2_entry is None or (ts and ts < lc.arena_2_entry):
        lc.arena_2_entry = ts
    lc.arena_2_status = STATUS_REJECT
    if ts and (lc.arena_2_exit is None or ts > lc.arena_2_exit):
        lc.arena_2_exit = ts
    reason, category, _ = classify(raw_reason=raw_reason, arena_stage="A2")
    lc.reject_stage = "A2"
    lc.reject_reason = reason.value
    lc.reject_category = category.value
    # severity fetched from metadata
    from zangetsu.services.arena_rejection_taxonomy import metadata_for, RejectionReason
    lc.reject_severity = metadata_for(RejectionReason(reason.value)).severity.value
    if symbol and lc.source_pool is None:
        lc.source_pool = symbol


def _apply_a3_complete(lc: CandidateLifecycle, ts: Optional[str], symbol: Optional[str]) -> None:
    _infer_upstream_passes(lc, "A3")
    if lc.arena_3_entry is None or (ts and ts < lc.arena_3_entry):
        lc.arena_3_entry = ts
    lc.arena_3_status = STATUS_PASS
    if ts and (lc.arena_3_exit is None or ts > lc.arena_3_exit):
        lc.arena_3_exit = ts
    if symbol and lc.source_pool is None:
        lc.source_pool = symbol


def _apply_a3_reject(
    lc: CandidateLifecycle, ts: Optional[str], symbol: Optional[str], raw_reason: str
) -> None:
    _infer_upstream_passes(lc, "A3")
    if lc.arena_3_entry is None or (ts and ts < lc.arena_3_entry):
        lc.arena_3_entry = ts
    lc.arena_3_status = STATUS_REJECT
    if ts and (lc.arena_3_exit is None or ts > lc.arena_3_exit):
        lc.arena_3_exit = ts
    reason, category, _ = classify(raw_reason=raw_reason, arena_stage="A3")
    lc.reject_stage = "A3"
    lc.reject_reason = reason.value
    lc.reject_category = category.value
    from zangetsu.services.arena_rejection_taxonomy import metadata_for, RejectionReason
    lc.reject_severity = metadata_for(RejectionReason(reason.value)).severity.value
    if symbol and lc.source_pool is None:
        lc.source_pool = symbol


def _apply_a3_prefilter_skip(lc: CandidateLifecycle, ts: Optional[str], symbol: Optional[str]) -> None:
    _infer_upstream_passes(lc, "A3")
    if lc.arena_3_entry is None or (ts and ts < lc.arena_3_entry):
        lc.arena_3_entry = ts
    lc.arena_3_status = STATUS_SKIPPED
    if ts and (lc.arena_3_exit is None or ts > lc.arena_3_exit):
        lc.arena_3_exit = ts
    if symbol and lc.source_pool is None:
        lc.source_pool = symbol


def _finalize(lc: CandidateLifecycle) -> None:
    """Derive final_stage, final_status, deployable_count_contribution,
    provenance_quality, and missing_fields for a candidate."""
    # final_stage: last stage that moved off NOT_RUN
    lc.final_stage = lc.current_stage()
    # final_status: DEPLOYABLE, or per-stage outcome
    if lc.is_deployable():
        lc.final_status = "DEPLOYABLE"
        lc.deployable_count_contribution = 1
    elif lc.governance_blocker:
        lc.final_status = "GOVERNANCE_BLOCKED"
    elif lc.arena_3_status == STATUS_REJECT:
        lc.final_status = STATUS_REJECT
    elif lc.arena_3_status == STATUS_SKIPPED:
        lc.final_status = STATUS_SKIPPED
    elif lc.arena_2_status == STATUS_REJECT:
        lc.final_status = STATUS_REJECT
    elif lc.arena_2_status == STATUS_PASS and lc.arena_3_status == STATUS_NOT_RUN:
        # Stalled — passed A2 but never reached A3 resolution
        lc.final_status = "STALLED_AT_A2"
    elif lc.arena_1_status == STATUS_REJECT:
        lc.final_status = STATUS_REJECT
    else:
        lc.final_status = STATUS_NOT_RUN
    # provenance_quality + missing_fields derived from helper
    prov, missing = assess_provenance_quality(lc)
    lc.provenance_quality = prov
    lc.missing_fields = missing


def reconstruct_lifecycles(
    log_paths: Iterable[Path],
) -> Tuple[List[CandidateLifecycle], ReconstructionStats]:
    """Parse a set of engine.jsonl paths and return reconstructed lifecycles.

    Returns ``(lifecycles, stats)``. ``lifecycles`` is sorted by candidate_id
    for deterministic output; ``stats`` captures the match counts by event
    type for evidence reports.
    """
    store: Dict[str, CandidateLifecycle] = {}
    stats = ReconstructionStats()

    for p in log_paths:
        with open(p, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                stats.lines_scanned += 1
                event = _parse_jsonl_msg(line)
                if not event:
                    continue
                msg = event.get("msg", "")
                if not isinstance(msg, str):
                    continue
                ts = event.get("ts")
                matched = False

                m = _RE_A2_PASS.match(msg)
                if m:
                    cid, sym = m.group(1), m.group(2)
                    lc = _ensure_lifecycle(store, cid)
                    if lc.created_at is None or (ts and ts < lc.created_at):
                        lc.created_at = ts
                    _apply_a2_pass(lc, ts, sym)
                    stats.a2_pass += 1
                    matched = True

                if not matched:
                    m = _RE_A2_REJECTED.match(msg)
                    if m:
                        cid, sym, raw = m.group(1), m.group(2), m.group(3).strip()
                        lc = _ensure_lifecycle(store, cid)
                        if lc.created_at is None or (ts and ts < lc.created_at):
                            lc.created_at = ts
                        _apply_a2_reject(lc, ts, sym, raw)
                        stats.a2_reject += 1
                        matched = True

                if not matched:
                    m = _RE_A3_COMPLETE.match(msg)
                    if m:
                        cid, sym = m.group(1), m.group(2)
                        lc = _ensure_lifecycle(store, cid)
                        if lc.created_at is None or (ts and ts < lc.created_at):
                            lc.created_at = ts
                        _apply_a3_complete(lc, ts, sym)
                        stats.a3_complete += 1
                        matched = True

                if not matched:
                    m = _RE_A3_REJECTED.match(msg)
                    if m:
                        cid, sym, raw = m.group(1), m.group(2), m.group(3).strip()
                        lc = _ensure_lifecycle(store, cid)
                        if lc.created_at is None or (ts and ts < lc.created_at):
                            lc.created_at = ts
                        _apply_a3_reject(lc, ts, sym, raw)
                        stats.a3_reject += 1
                        matched = True

                if not matched:
                    m = _RE_A3_PREFILTER_SKIP.match(msg)
                    if m:
                        cid, sym = m.group(1), m.group(2)
                        lc = _ensure_lifecycle(store, cid)
                        if lc.created_at is None or (ts and ts < lc.created_at):
                            lc.created_at = ts
                        _apply_a3_prefilter_skip(lc, ts, sym)
                        stats.a3_prefilter_skip += 1
                        matched = True

                if matched:
                    stats.events_matched += 1

    # Finalize all lifecycles
    for lc in store.values():
        _finalize(lc)

    stats.unique_candidates = len(store)
    lifecycles = sorted(store.values(), key=lambda lc: lc.candidate_id)
    return lifecycles, stats


def reconstruct_from_logs_and_derive_deployable_count(
    log_paths: Iterable[Path],
    through_stage: str = "A3",
) -> Dict[str, Any]:
    """Convenience helper: run reconstruction and compute deployable_count
    with provenance in one call. Returns a merged evidence dict suitable for
    the 0-9K SHADOW validation report."""
    lifecycles, stats = reconstruct_lifecycles(log_paths)
    deployable = derive_deployable_count_with_provenance(
        lifecycles, through_stage=through_stage
    )
    return {
        "stats": stats.to_dict(),
        "deployable": deployable,
        "lifecycles_count": len(lifecycles),
    }
