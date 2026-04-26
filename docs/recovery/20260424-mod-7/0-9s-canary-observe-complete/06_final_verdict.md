# 06 — Final Verdict

## 1. Status

**OBSERVING_NOT_COMPLETE** (per order §12 / §17 / §1).

## 2. Why not COMPLETE_GREEN / COMPLETE_YELLOW / FAILED_OBSERVATION

Per order §17 acceptance criteria:

> "Do not use GREEN or YELLOW unless: rounds_observed >= 20, real
> records exist, F criteria do not fail, runtime safety passes."

Real post-CANARY-activation rounds available: **0**. The 5
reconstructed rounds from Phase A are fixture-grade synthetic batches
with `generation_profile_id = UNKNOWN_PROFILE` (fixtures predate
PR-A 0-9P) and explicitly redacted / partial provenance. The 3 live
rounds from Phase B are zero-input runs.

Per order §10 / §12:

> "Use FAILED_OBSERVATION if any F criterion fails."

The F4 / F6 triggers observed during synthetic replay are **artifacts
of fixture data limitations**, not real CANARY failures (per order §7
profile-diversity guidance). Treating them as real failures would be
fabricating a verdict.

Per order §12:

> "Use OBSERVING_NOT_COMPLETE if rounds_observed < 20 OR baseline
> insufficient OR telemetry insufficient OR observation could not run
> enough rounds."

All four conditions hold:

- `rounds_observed (real) = 0 < 20`
- baseline = INSUFFICIENT_BASELINE
- telemetry insufficient (no post-CANARY arena_batch_metrics in repo)
- observation could not run enough rounds in single CI execution

## 3. Acceptance-criteria checklist (per order §17)

| # | Criterion | Status |
| --- | --- | --- |
| 1 | Readiness preflight executed | ✓ (CR1-CR15: 14 PASS + 1 OVERRIDE) |
| 2 | Replay/backfill attempted before live waiting | ✓ (Phase A ran, 5 synthetic batches) |
| 3 | Replay source manifest produced | ✓ (`replay_source_manifest.json`) |
| 4 | Live observation attempted if replay insufficient | ✓ (3 invocations) |
| 5 | Observation records collected or lack of telemetry documented | ✓ (4 records + insufficiency documented) |
| 6 | Aggregate metrics produced | ✓ (`sparse_canary_aggregate.json`) |
| 7 | Baseline comparison produced or marked INSUFFICIENT_BASELINE | ✓ (marked INSUFFICIENT_BASELINE) |
| 8 | S1-S14 evaluated | ✓ (`05_criteria_evaluation.md`) |
| 9 | F1-F9 evaluated | ✓ (`05_criteria_evaluation.md`) |
| 10 | Final verdict produced | ✓ (this doc) |
| 11 | Runtime apply path remains absent | ✓ (no `apply_*` runtime symbol) |
| 12 | Runtime-switchable APPLY mode remains absent | ✓ (`mode=DRY_RUN_CANARY` hard-coded) |
| 13 | Consumer output remains disconnected from generation runtime | ✓ |
| 14 | applied=false invariant remains true | ✓ (3-layer enforcement) |
| 15 | A2_MIN_TRADES remains 25 | ✓ |
| 16 | No forbidden changes occur | ✓ |
| 17 | Controlled-diff has 0 forbidden | Expected EXPLAINED |
| 18 | Gate-A passes if PR opened | Expected PASS |
| 19 | Gate-B passes if PR opened | Expected PASS |
| 20 | Branch protection remains intact | Expected PASS |
| 21 | Local main synced after merge | After merge |

## 4. Forbidden-changes audit

| Item | Status |
| --- | --- |
| Alpha generation | UNCHANGED |
| Formula generation | UNCHANGED |
| Mutation / crossover | UNCHANGED |
| Search policy | UNCHANGED |
| Generation budget | UNCHANGED |
| Sampling weights | UNCHANGED |
| Thresholds | UNCHANGED |
| `A2_MIN_TRADES` | PINNED at 25 |
| Arena pass/fail | UNCHANGED |
| Champion promotion | UNCHANGED |
| `deployable_count` semantics | UNCHANGED |
| Execution / capital / risk | UNCHANGED |
| Production rollout | NOT STARTED |
| Apply path | NONE EXISTS |
| Runtime-switchable APPLY mode | NONE EXISTS |

## 5. Runtime safety

| Field | Value |
| --- | --- |
| apply path | NONE |
| runtime-switchable APPLY mode | NONE |
| consumer connected to generation runtime | NO |
| consumer output consumed by generation runtime | NO |
| execution / capital / risk touched | NO |
| production rollout | NOT STARTED |

## 6. Tests

```
$ python3 -m pytest \
    zangetsu/tests/test_sparse_canary_observer.py \
    zangetsu/tests/test_sparse_canary_readiness.py \
    zangetsu/tests/test_sparse_canary_observation_runner.py \
    zangetsu/tests/test_sparse_canary_replay.py
======================== 160 passed ========================
```

Adjacent suites: 453 PASS / 0 regression (P7-PR4B 54 + 0-9O-B 62 +
0-9P 40 + 0-9P-AUDIT 56 + 0-9R-IMPL-DRY 81 + 0-9S-CANARY 116 +
0-9S-OBSERVE-FAST 21 + 0-9S-CANARY-OBSERVE-COMPLETE 23 = 453).

## 7. Recommended next action

**TEAM ORDER 0-9S-CANARY-OBSERVE-LIVE** (separate continuation
order):

- Schedule the runner against actual production
  `arena_batch_metrics.jsonl` stream from Alaya
  (`arena23_orchestrator` post-PR-A passport persistence).
- Cron / systemd timer running every A1 round close, or daily
  cumulative aggregation.
- Accumulate ≥ 20 real rounds across ≥ 2 real profile_ids before
  re-evaluating S1-S14 / F1-F9.
- Construct a real baseline from pre-CANARY-activation data on Alaya.
- When the real evaluation is conclusive, issue a follow-up order to
  produce the final OBSERVATION_COMPLETE_GREEN / YELLOW verdict.

Continuation command (template):

```
python3 -m zangetsu.tools.run_sparse_canary_observation \
    --batch-events /home/j13/j13-ops/zangetsu/logs/arena_batch_metrics.jsonl \
    --plans       /home/j13/j13-ops/zangetsu/logs/sparse_candidate_dry_run_plans.jsonl \
    --output-dir  /home/j13/j13-ops/docs/recovery/20260424-mod-7/0-9s-canary-observe-live \
    --run-id      live-canary-N \
    --attribution-verdict GREEN \
    --readiness-verdict PASS
```

Run this on Alaya, accumulate records, then issue a separate signed
PR order for the final verdict.

## 8. Final declaration

```
TEAM ORDER 0-9S-CANARY-OBSERVE-COMPLETE = OBSERVING_NOT_COMPLETE
```

Replay attempted, live fallback attempted, evidence captured,
verdict honestly reported. Real post-CANARY observation deferred to a
separate live continuation order.
