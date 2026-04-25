# 02 — Observation Snapshot

## 1. Runner

`zangetsu/tools/run_sparse_canary_observation.py` (~280 LOC, read-only).

Invocation:

```
python3 -m zangetsu.tools.run_sparse_canary_observation \
    --output-dir docs/recovery/20260424-mod-7/0-9s-observe-fast \
    --run-id canary-1 \
    --attribution-verdict GREEN \
    --readiness-verdict PASS
```

## 2. Telemetry sources at PR time

| Source | Path | Records |
| --- | --- | --- |
| `arena_batch_metrics` JSONL | (none supplied) | 0 |
| `sparse_candidate_dry_run_plan` JSONL | (none supplied) | 0 |

Reason: no live Arena pipeline running with PR-A passport persistence
fully propagated yet. Real telemetry collection is governed by a
separate continuous observation order.

## 3. Generated evidence files

| File | Format | Purpose |
| --- | --- | --- |
| `sparse_canary_observations.jsonl` | JSONL (1 line / observation cycle) | Append-only observation records |
| `sparse_canary_aggregate.json` | JSON object | Latest aggregate snapshot |

## 4. Observation record (live snapshot)

```json
{
  "mode": "DRY_RUN_CANARY",
  "applied": false,
  "canary_version": "0-9S-CANARY",
  "run_id": "canary-1",
  "rounds_observed": 0,
  "profiles_observed": 0,
  "observation_window_complete": false,
  "rollback_required": false,
  "readiness_verdict": "PASS",
  "attribution_verdict": "GREEN",
  ...
}
```

(Full record in `sparse_canary_observations.jsonl`.)

## 5. Aggregate metrics (live snapshot)

```json
{
  "runner_version": "0-9S-OBSERVE-FAST",
  "run_id": "canary-1",
  "observation_complete": false,
  "rounds_observed": 0,
  "profiles_observed": 0,
  "unknown_reject_rate": 0.0,
  "signal_too_sparse_rate": 0.0,
  "a1_pass_rate": 0.0,
  "a2_pass_rate": 0.0,
  "a3_pass_rate": 0.0,
  "oos_fail_rate": 0.0,
  "deployable_count": 0,
  "deployable_density": 0.0,
  "composite_score": 0.0,
  "baseline_composite_score": 0.0,
  "composite_delta": 0.0,
  "profile_diversity_score": 0.0,
  "profile_collapse_detected": false,
  "consumer_plan_stability": 0.0,
  "rollback_required": false,
  "status": "OBSERVING_NOT_COMPLETE"
}
```

(Full payload in `sparse_canary_aggregate.json`.)

## 6. Observation window state

| Field | Value |
| --- | --- |
| `observation_start` | live UTC timestamp at PR-time invocation |
| `observation_end` | live UTC timestamp at PR-time invocation |
| `observation_window_complete` | **False** |
| `rounds_observed` | **0** |
| `profiles_observed` | **0** |

The runner correctly reports `OBSERVING_NOT_COMPLETE` for empty-input
runs. F-criteria evaluation is suppressed at zero rounds because
empty inputs would falsely trigger F6 (no profiles → diversity=0
treated as "exploration floor violated"); the runner's status logic
short-circuits this case so no rollback is reported when there is
literally nothing to roll back.

## 7. How to continue

Future continuous-observation order (`0-9S-CANARY-OBSERVE`) will:

1. Stream live `arena_batch_metrics` JSONL into the runner per round.
2. Stream `sparse_candidate_dry_run_plan` events into the runner.
3. Re-invoke the runner periodically (e.g. on each A1 round close).
4. Aggregate appends to `sparse_canary_observations.jsonl`.
5. After ≥ 20 rounds, evaluate S1-S14 / F1-F9 against a fresh
   baseline derived from the prior observation window.

Continuation command (template):

```
python3 -m zangetsu.tools.run_sparse_canary_observation \
    --batch-events <live arena_batch_metrics jsonl path> \
    --plans <live sparse_candidate_dry_run_plan jsonl path> \
    --output-dir docs/recovery/20260424-mod-7/0-9s-observe-fast \
    --run-id canary-N \
    --attribution-verdict GREEN \
    --readiness-verdict PASS
```
