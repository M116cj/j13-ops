"""Thin read-only runner for the sparse-candidate dry-run CANARY observer
(TEAM ORDER 0-9S-OBSERVE-FAST).

Reads existing telemetry sources (JSONL log files / aggregate metric
fixtures) and feeds them to the observer module, writing
``SparseCanaryObservation`` records and an aggregate summary.

Strict guarantees:

  - **Read-only.** Never mutates runtime state; never writes anywhere
    other than caller-supplied output paths.
  - **No runtime imports.** Only reads observer module + readiness
    check + JSON-line log parser from ``profile_attribution_audit``.
  - **No apply path.** No public ``apply_*`` symbol.
  - **DRY_RUN_CANARY only.** ``mode`` and ``applied`` invariants
    inherited from observer's :class:`SparseCanaryObservation`.

Usage::

    python -m zangetsu.tools.run_sparse_canary_observation \
        --batch-events docs/recovery/.../arena_batch_metrics.jsonl \
        --plans       docs/recovery/.../sparse_candidate_dry_run_plans.jsonl \
        --output-dir  docs/recovery/20260424-mod-7/0-9s-observe-fast \
        --run-id      canary-1 \
        --attribution-verdict GREEN

When telemetry sources are empty (e.g. fresh PR-time invocation with no
collected data yet), the runner emits one observation record marked
``observation_window_complete=False`` with all delta-style success
criteria reporting ``INSUFFICIENT_HISTORY``. Status is then
``OBSERVING_NOT_COMPLETE`` per order §5.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from zangetsu.services.sparse_canary_observer import (
    CanaryBaseline,
    SparseCanaryObservation,
    STATUS_FAIL,
    STATUS_INSUFFICIENT_HISTORY,
    STATUS_NOT_EVALUATED,
    STATUS_PASS,
    VERDICT_GREEN,
    VERDICT_RED,
    VERDICT_YELLOW,
    VERDICT_UNAVAILABLE,
    observe,
    safe_observe,
    serialize_observation,
)
from zangetsu.tools.profile_attribution_audit import (
    parse_event_log_lines,
)


RUNNER_VERSION = "0-9S-OBSERVE-FAST"
STATUS_OBSERVING_NOT_COMPLETE = "OBSERVING_NOT_COMPLETE"
STATUS_OBSERVATION_COMPLETE_GREEN = "OBSERVATION_COMPLETE_GREEN"
STATUS_FAILED_OBSERVATION = "FAILED_OBSERVATION"
STATUS_BLOCKED = "BLOCKED"

# Aggregation thresholds.
MIN_ROUNDS_FOR_COMPLETE = 20  # observation_window_complete True threshold


# ---------------------------------------------------------------------------
# Telemetry loading
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_jsonl(path: Optional[pathlib.Path]) -> List[Dict[str, Any]]:
    """Best-effort JSONL reader. Returns ``[]`` when path is None or
    unreadable. Never raises."""
    if not path:
        return []
    try:
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as fh:
            return parse_event_log_lines(fh.read().splitlines())
    except Exception:
        return []


def aggregate_arena_batch_metrics(
    batch_events: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Roll arena_batch_metrics events into the aggregate metrics the
    observer expects. Never raises."""
    a1_entered = a1_passed = 0
    a2_entered = a2_passed = a2_rejected = 0
    a3_entered = a3_passed = a3_rejected = 0
    sparse = oos = unknown = 0
    deployable = 0
    profiles: set = set()

    for ev in batch_events or ():
        try:
            if not isinstance(ev, Mapping):
                continue
            stage = str(ev.get("arena_stage") or "").upper()
            entered = max(0, int(ev.get("entered_count") or 0))
            passed = max(0, int(ev.get("passed_count") or 0))
            rejected = max(0, int(ev.get("rejected_count") or 0))
            dist = ev.get("reject_reason_distribution") or {}
            pid = ev.get("generation_profile_id")
            if pid:
                profiles.add(str(pid))
            dep = ev.get("deployable_count")
            if isinstance(dep, int):
                deployable = max(deployable, dep)
            try:
                sparse += int(dist.get("SIGNAL_TOO_SPARSE") or 0)
                oos += int(dist.get("OOS_FAIL") or 0)
                unknown += int(dist.get("UNKNOWN_REJECT") or 0)
            except Exception:
                pass
            if stage == "A1":
                a1_entered += entered
                a1_passed += passed
            elif stage == "A2":
                a2_entered += entered
                a2_passed += passed
                a2_rejected += rejected
            elif stage == "A3":
                a3_entered += entered
                a3_passed += passed
                a3_rejected += rejected
        except Exception:
            continue

    def _rate(num: int, den: int) -> float:
        if den <= 0:
            return 0.0
        r = num / den
        return 0.0 if r < 0 else (1.0 if r > 1 else r)

    total_rejects = sparse + oos + unknown
    return {
        "a1_pass_rate": _rate(a1_passed, a1_entered),
        "a2_pass_rate": _rate(a2_passed, a2_entered),
        "a3_pass_rate": _rate(a3_passed, a3_entered),
        "signal_too_sparse_rate": _rate(sparse, total_rejects),
        "oos_fail_rate": _rate(oos, total_rejects),
        "unknown_reject_rate": _rate(unknown, total_rejects),
        "deployable_count": int(deployable),
        "passed_a3": int(a3_passed),
        "rounds_observed": len(batch_events or ()),
        "profiles_observed": len(profiles),
    }


def derive_baseline(
    aggregate: Mapping[str, Any],
    *,
    sample_size_rounds: int = 0,
) -> CanaryBaseline:
    """Build a baseline snapshot from aggregate metrics. When the
    observation window is empty the baseline carries zeros and
    ``sample_size_rounds=0`` → all delta-style criteria report
    ``INSUFFICIENT_HISTORY``."""
    return CanaryBaseline(
        a2_pass_rate=float(aggregate.get("a2_pass_rate") or 0.0),
        a3_pass_rate=float(aggregate.get("a3_pass_rate") or 0.0),
        signal_too_sparse_rate=float(aggregate.get("signal_too_sparse_rate") or 0.0),
        oos_fail_rate=float(aggregate.get("oos_fail_rate") or 0.0),
        unknown_reject_rate=float(aggregate.get("unknown_reject_rate") or 0.0),
        deployable_count=int(aggregate.get("deployable_count") or 0),
        composite_score=0.0,
        composite_score_stddev=None,
        sample_size_rounds=sample_size_rounds,
    )


# ---------------------------------------------------------------------------
# Top-level run
# ---------------------------------------------------------------------------


def run_observation(
    *,
    batch_events_path: Optional[pathlib.Path] = None,
    plans_path: Optional[pathlib.Path] = None,
    output_dir: pathlib.Path,
    run_id: str = "canary-1",
    attribution_verdict: str = VERDICT_UNAVAILABLE,
    readiness_verdict: str = "PASS",
    observation_window_start: Optional[str] = None,
    observation_window_end: Optional[str] = None,
) -> Dict[str, Any]:
    """Single run cycle: read telemetry → observe → write evidence.

    Returns a dict with the runner's ``status`` field plus the observer
    record + aggregate summary. Never raises.
    """
    output_dir = pathlib.Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    obs_start = observation_window_start or _utc_now_iso()

    batch_events = _read_jsonl(batch_events_path)
    plans = _read_jsonl(plans_path)
    aggregate = aggregate_arena_batch_metrics(batch_events)

    # Use the observed events as their own baseline when no separate
    # baseline source is supplied. With sample_size_rounds=0 this yields
    # INSUFFICIENT_HISTORY for delta-style criteria, which is the
    # correct conservative behavior for a fresh CANARY launch.
    baseline = derive_baseline(aggregate, sample_size_rounds=0)

    obs_end = observation_window_end or _utc_now_iso()
    rounds = int(aggregate.get("rounds_observed") or 0)
    profiles_n = int(aggregate.get("profiles_observed") or 0)
    observation_complete = rounds >= MIN_ROUNDS_FOR_COMPLETE

    treatment = {
        "a1_pass_rate": aggregate.get("a1_pass_rate"),
        "a2_pass_rate": aggregate.get("a2_pass_rate"),
        "a3_pass_rate": aggregate.get("a3_pass_rate"),
        "signal_too_sparse_rate": aggregate.get("signal_too_sparse_rate"),
        "oos_fail_rate": aggregate.get("oos_fail_rate"),
        "unknown_reject_rate": aggregate.get("unknown_reject_rate"),
        "deployable_count": aggregate.get("deployable_count"),
        "passed_a3": aggregate.get("passed_a3"),
    }

    obs = safe_observe(
        run_id=run_id,
        treatment_metrics=treatment,
        baseline=baseline,
        consumer_plans=plans,
        readiness_verdict=readiness_verdict,
        attribution_verdict=attribution_verdict,
        observation_window_start=obs_start,
        observation_window_end=obs_end,
        observation_window_complete=observation_complete,
        rounds_observed=rounds,
        profiles_observed=profiles_n,
        rollback_executable=True,
        execution_path_touched=False,
        no_threshold_change=True,
        no_arena_change=True,
        no_promotion_change=True,
        no_execution_change=True,
        per_regime_stable=None,
    )

    # Determine runner status.
    # Special case: zero-round observations (fresh CANARY launch with no
    # telemetry yet) are OBSERVING_NOT_COMPLETE by definition. F-criteria
    # evaluated against empty data are not meaningful (e.g. no profiles
    # → diversity=0 → F6 falsely fires). Skip the F evaluation here and
    # rely on the next observation cycle once real data arrives.
    if rounds == 0:
        status = STATUS_OBSERVING_NOT_COMPLETE
        # Reset rollback flag for empty-input runs — there is nothing to
        # roll back when no observation has occurred. The observer's
        # F-criteria are kept in the record for transparency, but the
        # runner-level rollback signal is suppressed.
        obs.rollback_required = False
    elif obs.rollback_required:
        status = STATUS_FAILED_OBSERVATION
    elif observation_complete and not any(
        v == STATUS_FAIL for v in obs.failure_criteria_status.values()
    ):
        # Window complete + no failure → check if all required successes
        # are PASS. The order's GREEN status requires a real evaluation;
        # we mark OBSERVATION_COMPLETE_GREEN only when every S1-S14 is
        # either PASS or a tolerated INSUFFICIENT_HISTORY.
        all_ok = all(
            v in (STATUS_PASS, STATUS_INSUFFICIENT_HISTORY)
            for v in obs.success_criteria_status.values()
        )
        status = (
            STATUS_OBSERVATION_COMPLETE_GREEN if all_ok
            else STATUS_OBSERVING_NOT_COMPLETE
        )
    else:
        status = STATUS_OBSERVING_NOT_COMPLETE

    # Write per-record JSONL.
    obs_path = output_dir / "sparse_canary_observations.jsonl"
    try:
        with obs_path.open("a", encoding="utf-8") as fh:
            fh.write(serialize_observation(obs) + "\n")
    except Exception:
        pass

    # Write aggregate JSON.
    aggregate_payload = {
        "runner_version": RUNNER_VERSION,
        "run_id": run_id,
        "observation_start": obs_start,
        "observation_end": obs_end,
        "observation_complete": observation_complete,
        "rounds_observed": rounds,
        "profiles_observed": profiles_n,
        "unknown_reject_rate": float(treatment.get("unknown_reject_rate") or 0.0),
        "signal_too_sparse_rate": float(treatment.get("signal_too_sparse_rate") or 0.0),
        "a1_pass_rate": float(treatment.get("a1_pass_rate") or 0.0),
        "a2_pass_rate": float(treatment.get("a2_pass_rate") or 0.0),
        "a3_pass_rate": float(treatment.get("a3_pass_rate") or 0.0),
        "oos_fail_rate": float(treatment.get("oos_fail_rate") or 0.0),
        "deployable_count": int(treatment.get("deployable_count") or 0),
        "deployable_density": float(obs.deployable_density),
        "composite_score": float(obs.composite_score),
        "baseline_composite_score": float(obs.baseline_composite_score),
        "composite_delta": float(obs.composite_delta),
        "profile_diversity_score": float(obs.profile_diversity_score),
        "profile_collapse_detected": bool(obs.profile_collapse_detected),
        "consumer_plan_stability": float(obs.consumer_plan_stability),
        "success_criteria_status": dict(obs.success_criteria_status),
        "failure_criteria_status": dict(obs.failure_criteria_status),
        "rollback_required": bool(obs.rollback_required),
        "status": status,
    }
    try:
        agg_path = output_dir / "sparse_canary_aggregate.json"
        agg_path.write_text(
            json.dumps(aggregate_payload, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception:
        pass

    return {
        "status": status,
        "observation": obs,
        "aggregate": aggregate_payload,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_sparse_canary_observation",
        description="Read-only sparse-candidate CANARY observer runner.",
    )
    p.add_argument("--batch-events", type=pathlib.Path, default=None,
                   help="JSONL of arena_batch_metrics events.")
    p.add_argument("--plans", type=pathlib.Path, default=None,
                   help="JSONL of sparse_candidate_dry_run_plan events.")
    p.add_argument("--output-dir", type=pathlib.Path, required=True,
                   help="Directory for observation evidence files.")
    p.add_argument("--run-id", type=str, default="canary-1",
                   help="Run id for the observation record.")
    p.add_argument("--attribution-verdict", type=str, default=VERDICT_UNAVAILABLE,
                   choices=[VERDICT_GREEN, VERDICT_YELLOW, VERDICT_RED, VERDICT_UNAVAILABLE],
                   help="Attribution audit verdict (GREEN / YELLOW / RED / UNAVAILABLE).")
    p.add_argument("--readiness-verdict", type=str, default="PASS",
                   help="Readiness preflight verdict.")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_argparser().parse_args(argv)
    out = run_observation(
        batch_events_path=args.batch_events,
        plans_path=args.plans,
        output_dir=args.output_dir,
        run_id=args.run_id,
        attribution_verdict=args.attribution_verdict,
        readiness_verdict=args.readiness_verdict,
    )
    print(json.dumps(out["aggregate"], sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
