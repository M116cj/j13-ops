"""Sparse-Candidate CANARY Replay / Backfill Helper
(TEAM ORDER 0-9S-CANARY-OBSERVE-COMPLETE — Phase A).

Read-only helper that scans existing telemetry / log sources, attempts
to reconstruct synthetic ``arena_batch_metrics`` events from heterogeneous
input formats, and feeds them through the observer module.

Strict guarantees:

  - **Read-only.** Never mutates source files; only writes to
    caller-supplied output directory.
  - **No runtime imports.** Only reads observer / readiness modules
    from `zangetsu.tools` and `zangetsu.services.sparse_canary_observer`.
    Does not touch arena_pipeline / arena23_orchestrator /
    arena45_orchestrator / engine / live.
  - **Honest insufficiency reporting.** When source data is too thin
    or wrong-shape, the replay manifest documents the gap; never
    fabricates aggregate metrics.

Source types this helper understands
------------------------------------

  * ``arena_batch_metrics`` — direct format (post-P7-PR4B): events
    are passed through as-is.
  * ``per_candidate_event`` — older logs / fixtures with
    ``arena_stage`` + ``raw_reason_stem`` per candidate (0-9J / shadow
    samples). Reconstructed into a single synthetic batch grouped by
    ``arena_stage``.
  * ``lifecycle_record`` — 0-9K-style with ``final_stage`` /
    ``final_status``. Reconstructed into a deployable_count signal.
  * ``orchestrator_log`` — engine.jsonl with ``msg`` field containing
    ``A2 stats: ...`` / ``A3 stats: ...``. Reconstructed best-effort
    when format matches.

Anything else is logged in the replay manifest as
``unsupported_format`` and skipped.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from zangetsu.tools.profile_attribution_audit import parse_event_log_lines
from zangetsu.tools.run_sparse_canary_observation import (
    aggregate_arena_batch_metrics,
    derive_baseline,
    run_observation,
)


REPLAY_VERSION = "0-9S-CANARY-OBSERVE-COMPLETE"


# ---------------------------------------------------------------------------
# Manifest schema
# ---------------------------------------------------------------------------


@dataclass
class ReplaySource:
    source_path: str
    source_type: str
    line_count: int = 0
    record_count: int = 0
    time_start: str = ""
    time_end: str = ""
    contains_a1_metrics: bool = False
    contains_a2_metrics: bool = False
    contains_a3_metrics: bool = False
    contains_profile_id: bool = False
    contains_rejection_distribution: bool = False
    contains_deployable_count: bool = False
    usable_for_baseline: bool = False
    usable_for_observation: bool = False
    reason_if_excluded: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReplayManifest:
    replay_version: str = REPLAY_VERSION
    sources: List[ReplaySource] = field(default_factory=list)
    total_records_seen: int = 0
    total_synthetic_batches_built: int = 0
    rounds_observed: int = 0
    profiles_observed: int = 0
    unsupported_format_count: int = 0
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "replay_version": self.replay_version,
            "sources": [s.to_dict() for s in self.sources],
            "total_records_seen": self.total_records_seen,
            "total_synthetic_batches_built": self.total_synthetic_batches_built,
            "rounds_observed": self.rounds_observed,
            "profiles_observed": self.profiles_observed,
            "unsupported_format_count": self.unsupported_format_count,
            "notes": list(self.notes),
        }


# ---------------------------------------------------------------------------
# Source classification + reconstruction
# ---------------------------------------------------------------------------


def _classify_record(rec: Mapping[str, Any]) -> str:
    """Return source_type label based on record shape."""
    if not isinstance(rec, Mapping):
        return "unsupported_format"
    if rec.get("event_type") == "arena_batch_metrics" or "reject_reason_distribution" in rec:
        return "arena_batch_metrics"
    if "raw_reason_stem" in rec and "arena_stage" in rec:
        return "per_candidate_event"
    if "final_stage" in rec and "final_status" in rec:
        return "lifecycle_record"
    if rec.get("level") and rec.get("msg"):
        return "orchestrator_log"
    return "unsupported_format"


_A2_STATS_RE = re.compile(
    r"A2 stats:\s*processed=(\d+)\s*promoted=(\d+)\s*rejected=(\d+)"
)
_A3_STATS_RE = re.compile(
    r"A3 stats:\s*processed=(\d+)\s*completed=(\d+)"
)


def _reconstruct_orchestrator_log(rec: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """Best-effort reconstruction of synthetic batch metrics from old
    orchestrator log lines.

    Recognised messages:
      - ``A2 stats: processed=N promoted=N rejected=N (Xs)``
      - ``A3 stats: processed=N completed=N (Xs)``

    Returns synthetic ``arena_batch_metrics``-like dict or None.
    """
    msg = str(rec.get("msg") or "")
    m = _A2_STATS_RE.search(msg)
    if m:
        processed, promoted, rejected = (int(m.group(i)) for i in (1, 2, 3))
        return {
            "event_type": "arena_batch_metrics",
            "arena_stage": "A2",
            "entered_count": processed,
            "passed_count": promoted,
            "rejected_count": rejected,
            "skipped_count": max(0, processed - promoted - rejected),
            "error_count": 0,
            "in_flight_count": 0,
            "reject_reason_distribution": {},
            "deployable_count": None,
            "generation_profile_id": "UNKNOWN_PROFILE",
            "generation_profile_fingerprint": "UNAVAILABLE",
            "_replay_source": "orchestrator_log",
        }
    m = _A3_STATS_RE.search(msg)
    if m:
        processed, completed = (int(m.group(i)) for i in (1, 2))
        return {
            "event_type": "arena_batch_metrics",
            "arena_stage": "A3",
            "entered_count": processed,
            "passed_count": completed,
            "rejected_count": max(0, processed - completed),
            "skipped_count": 0,
            "error_count": 0,
            "in_flight_count": 0,
            "reject_reason_distribution": {},
            "deployable_count": None,
            "generation_profile_id": "UNKNOWN_PROFILE",
            "generation_profile_fingerprint": "UNAVAILABLE",
            "_replay_source": "orchestrator_log",
        }
    return None


def _reconstruct_per_candidate_batch(
    records: Iterable[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Group per-candidate events by stage and produce one synthetic
    batch per stage with rejection distribution.
    """
    by_stage: Dict[str, Dict[str, int]] = {}
    counts: Dict[str, int] = {"A1": 0, "A2": 0, "A3": 0}
    for r in records:
        if not isinstance(r, Mapping):
            continue
        stage = str(r.get("arena_stage") or "").upper()
        if stage not in ("A1", "A2", "A3"):
            continue
        reason = str(r.get("raw_reason_stem") or "UNKNOWN_REJECT")
        # Map common reasons to canonical taxonomy values.
        if "trades" in reason or "no_valid" in reason:
            canon = "SIGNAL_TOO_SPARSE"
        elif "OOS" in reason.upper() or "validation" in reason or "PnL divergence" in reason:
            canon = "OOS_FAIL"
        else:
            canon = "UNKNOWN_REJECT"
        by_stage.setdefault(stage, {})
        by_stage[stage][canon] = by_stage[stage].get(canon, 0) + 1
        counts[stage] = counts.get(stage, 0) + 1
    out: List[Dict[str, Any]] = []
    for stage in ("A1", "A2", "A3"):
        if counts.get(stage, 0) <= 0:
            continue
        n = counts[stage]
        rejected = sum(by_stage.get(stage, {}).values())
        out.append({
            "event_type": "arena_batch_metrics",
            "arena_stage": stage,
            "entered_count": n,
            "passed_count": max(0, n - rejected),
            "rejected_count": rejected,
            "skipped_count": 0,
            "error_count": 0,
            "in_flight_count": 0,
            "reject_reason_distribution": dict(by_stage.get(stage, {})),
            "deployable_count": None,
            "generation_profile_id": "UNKNOWN_PROFILE",
            "generation_profile_fingerprint": "UNAVAILABLE",
            "_replay_source": "per_candidate_event",
        })
    return out


def _reconstruct_lifecycle_records(
    records: Iterable[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Lifecycle records (final_stage / final_status) → synthetic A3
    batch with deployable_count derived from DEPLOYABLE finals."""
    a3 = 0
    deployable = 0
    for r in records:
        if not isinstance(r, Mapping):
            continue
        if str(r.get("final_stage") or "").upper() != "A3":
            continue
        a3 += 1
        if str(r.get("final_status") or "").upper() == "DEPLOYABLE":
            deployable += 1
    if a3 <= 0:
        return []
    return [{
        "event_type": "arena_batch_metrics",
        "arena_stage": "A3",
        "entered_count": a3,
        "passed_count": deployable,
        "rejected_count": max(0, a3 - deployable),
        "skipped_count": 0,
        "error_count": 0,
        "in_flight_count": 0,
        "reject_reason_distribution": {},
        "deployable_count": deployable,
        "generation_profile_id": "UNKNOWN_PROFILE",
        "generation_profile_fingerprint": "UNAVAILABLE",
        "_replay_source": "lifecycle_record",
    }]


# ---------------------------------------------------------------------------
# Source scanning
# ---------------------------------------------------------------------------


def scan_source(path: pathlib.Path) -> ReplaySource:
    """Scan a single source file and return classified manifest entry.
    Never raises."""
    src = ReplaySource(source_path=str(path), source_type="unknown")
    try:
        if not path.exists():
            src.reason_if_excluded = "file does not exist"
            return src
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        src.line_count = len(lines)
        records = parse_event_log_lines(lines)
        src.record_count = len(records)
        if not records:
            src.reason_if_excluded = "no parseable JSON records"
            return src
        # Classify by first parseable record.
        first_type = _classify_record(records[0])
        src.source_type = first_type
        # Quick coverage flags.
        for r in records:
            stage = str(r.get("arena_stage") or "").upper()
            if stage == "A1":
                src.contains_a1_metrics = True
            elif stage == "A2":
                src.contains_a2_metrics = True
            elif stage == "A3":
                src.contains_a3_metrics = True
            if r.get("generation_profile_id"):
                src.contains_profile_id = True
            if r.get("reject_reason_distribution") or r.get("raw_reason_stem"):
                src.contains_rejection_distribution = True
            if r.get("deployable_count") is not None:
                src.contains_deployable_count = True
        # Time bounds.
        ts_values = [r.get("ts") for r in records if r.get("ts")]
        if ts_values:
            src.time_start = str(min(ts_values))
            src.time_end = str(max(ts_values))
        # Usability.
        src.usable_for_observation = first_type in (
            "arena_batch_metrics", "per_candidate_event",
            "lifecycle_record", "orchestrator_log",
        )
        # Baseline usability requires real metrics + non-redacted data.
        if src.contains_rejection_distribution and src.record_count >= 20 and first_type == "arena_batch_metrics":
            src.usable_for_baseline = True
        else:
            src.usable_for_baseline = False
            if first_type != "arena_batch_metrics":
                src.reason_if_excluded = (
                    f"non-canonical format ({first_type}); used for partial replay only"
                )
            elif src.record_count < 20:
                src.reason_if_excluded = (
                    f"only {src.record_count} records (need >= 20 for baseline)"
                )
    except Exception as exc:  # noqa: BLE001
        src.reason_if_excluded = f"scan failed: {type(exc).__name__}"
    return src


def reconstruct_records(path: pathlib.Path, source_type: str) -> List[Dict[str, Any]]:
    """Read source and produce arena_batch_metrics-shaped events.
    Never raises."""
    try:
        if not path.exists():
            return []
        records = parse_event_log_lines(path.read_text(encoding="utf-8").splitlines())
    except Exception:
        return []

    if source_type == "arena_batch_metrics":
        return [dict(r) for r in records if isinstance(r, Mapping)]
    if source_type == "per_candidate_event":
        return _reconstruct_per_candidate_batch(records)
    if source_type == "lifecycle_record":
        return _reconstruct_lifecycle_records(records)
    if source_type == "orchestrator_log":
        out: List[Dict[str, Any]] = []
        for r in records:
            try:
                synth = _reconstruct_orchestrator_log(r)
                if synth is not None:
                    out.append(synth)
            except Exception:
                continue
        return out
    return []


# ---------------------------------------------------------------------------
# Top-level replay
# ---------------------------------------------------------------------------


def run_replay(
    *,
    sources: Iterable[pathlib.Path],
    output_dir: pathlib.Path,
    run_id: str = "replay-1",
    attribution_verdict: str = "GREEN",
) -> Dict[str, Any]:
    """Scan sources, reconstruct synthetic batches, run observer, write
    manifest + observation. Never raises."""
    output_dir = pathlib.Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = ReplayManifest()
    all_synthetic: List[Dict[str, Any]] = []
    profile_ids: set = set()

    for src_path in sources:
        path = pathlib.Path(src_path)
        src = scan_source(path)
        manifest.sources.append(src)
        manifest.total_records_seen += src.record_count
        if src.usable_for_observation:
            synth = reconstruct_records(path, src.source_type)
            all_synthetic.extend(synth)
            for s in synth:
                pid = s.get("generation_profile_id")
                if pid:
                    profile_ids.add(str(pid))
        elif src.source_type == "unknown":
            manifest.unsupported_format_count += 1

    manifest.total_synthetic_batches_built = len(all_synthetic)
    aggregate = aggregate_arena_batch_metrics(all_synthetic)
    manifest.rounds_observed = aggregate.get("rounds_observed", 0)
    manifest.profiles_observed = aggregate.get("profiles_observed", 0)

    # Write manifest.
    manifest_path = output_dir / "replay_source_manifest.json"
    try:
        manifest_path.write_text(
            json.dumps(manifest.to_dict(), sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception:
        pass

    # If any synthetic batches were built, write them as JSONL too so
    # the runner can re-read them later.
    synthetic_path = output_dir / "replay_synthetic_batch_metrics.jsonl"
    try:
        if all_synthetic:
            with synthetic_path.open("w", encoding="utf-8") as fh:
                for s in all_synthetic:
                    fh.write(json.dumps(s, sort_keys=True) + "\n")
    except Exception:
        pass

    # Run observer using synthetic batches as both treatment and
    # baseline (with sample_size_rounds=0 so delta-style criteria stay
    # INSUFFICIENT_HISTORY).
    runner_out = run_observation(
        batch_events_path=synthetic_path if all_synthetic else None,
        plans_path=None,
        output_dir=output_dir,
        run_id=run_id,
        attribution_verdict=attribution_verdict,
    )

    return {
        "manifest": manifest.to_dict(),
        "rounds_observed": manifest.rounds_observed,
        "profiles_observed": manifest.profiles_observed,
        "runner_status": runner_out["status"],
        "aggregate": runner_out["aggregate"],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


_DEFAULT_SOURCES = (
    "zangetsu/logs/engine.jsonl.1",
    "docs/recovery/20260424-mod-7/0-9j_canary_redacted_event_sample.jsonl",
    "docs/recovery/20260424-mod-7/0-9k_lifecycle_reconstruction_sample.jsonl",
    "docs/recovery/20260424-mod-7/p7_pr1_shadow_raw_event_sample.jsonl",
)


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="replay_sparse_canary_observation",
        description="Read-only sparse CANARY replay / backfill helper.",
    )
    p.add_argument("--source", action="append", type=pathlib.Path,
                   help="Source file path. Repeatable. If omitted, defaults are scanned.")
    p.add_argument("--output-dir", type=pathlib.Path, required=True)
    p.add_argument("--run-id", type=str, default="replay-1")
    p.add_argument("--attribution-verdict", type=str, default="GREEN")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_argparser().parse_args(argv)
    sources = args.source or [pathlib.Path(s) for s in _DEFAULT_SOURCES]
    out = run_replay(
        sources=sources,
        output_dir=args.output_dir,
        run_id=args.run_id,
        attribution_verdict=args.attribution_verdict,
    )
    print(json.dumps({
        "rounds_observed": out["rounds_observed"],
        "profiles_observed": out["profiles_observed"],
        "runner_status": out["runner_status"],
        "manifest_sources": len(out["manifest"]["sources"]),
        "synthetic_batches": out["manifest"]["total_synthetic_batches_built"],
    }, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
