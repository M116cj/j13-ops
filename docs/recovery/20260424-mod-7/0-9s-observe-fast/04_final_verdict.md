# 04 — Final Verdict

## 1. Status

**OBSERVING_NOT_COMPLETE** (per order §5 / §7).

## 2. Why not COMPLETE

Per order §3 / §6.2 / §404:

> "Do not use COMPLETE unless the observation window is complete and the
> verdict is final."

Observation window state at PR-time invocation:

- `rounds_observed = 0`
- `profiles_observed = 0`
- `observation_window_complete = False`

Real telemetry collection requires a continuous observation loop running
against live `arena_batch_metrics` and `sparse_candidate_dry_run_plan`
JSONL streams over ≥ 20 rounds (`MIN_ROUNDS_FOR_COMPLETE`). That cannot
fit in a single CI execution.

This PR ships:

1. The runner module (`zangetsu/tools/run_sparse_canary_observation.py`)
2. CLI entry point (`python -m zangetsu.tools.run_sparse_canary_observation`)
3. Output schema (`sparse_canary_observations.jsonl` +
   `sparse_canary_aggregate.json`)
4. The runner's status machine (zero-round → OBSERVING_NOT_COMPLETE; F
   triggers → FAILED_OBSERVATION; ≥ 20 rounds + all S OK →
   OBSERVATION_COMPLETE_GREEN)
5. Test coverage (135 PASS) and adjacent regression check (428 PASS)
6. Evidence files (preflight + snapshot + criteria + this verdict)

So the **observer is fully operational and invocable**, but the
**multi-round observation window has not yet been collected**.

## 3. Acceptance criteria (per order §7)

| # | Criterion | Met |
| --- | --- | --- |
| 1 | Readiness preflight executed | ✓ (CR1-CR15: 14 PASS + 1 OVERRIDE) |
| 2 | Observation records are collected or observation launch is proven | ✓ (1 launch record in `sparse_canary_observations.jsonl`) |
| 3 | Aggregate metrics are produced if records exist | ✓ (`sparse_canary_aggregate.json`) |
| 4 | S1-S14 evaluated or marked PENDING / INSUFFICIENT_HISTORY | ✓ (see 03_criteria_evaluation.md) |
| 5 | F1-F9 evaluated or marked PENDING | ✓ (see 03_criteria_evaluation.md) |
| 6 | Final verdict produced | ✓ (this doc) |
| 7 | Runtime apply path remains absent | ✓ (no apply_* in services) |
| 8 | Runtime-switchable APPLY mode remains absent | ✓ (`mode = DRY_RUN_CANARY` hard-coded) |
| 9 | Consumer output remains disconnected from generation runtime | ✓ (no consumer import in arena_pipeline / arena23 / arena45) |
| 10 | applied=false invariant remains true | ✓ (3-layer enforcement) |
| 11 | A2_MIN_TRADES remains 25 | ✓ (`bt.total_trades < 25` still in arena23_orchestrator.py) |
| 12 | No forbidden changes occur | ✓ |
| 13 | Controlled-diff has 0 forbidden | Expected EXPLAINED (docs + thin runner + test) |
| 14 | Gate-A passes if PR opened | Expected PASS |
| 15 | Gate-B passes if PR opened | Expected PASS |
| 16 | Branch protection remains intact | Expected PASS |
| 17 | Local main synced after merge if PR opened | After merge |

## 4. Forbidden-changes audit

| Item | Status |
| --- | --- |
| Alpha generation | UNCHANGED |
| Formula generation | UNCHANGED |
| Mutation / crossover | UNCHANGED |
| Search policy | UNCHANGED |
| Real generation budget | UNCHANGED |
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

## 5. Recommended next action

**TEAM ORDER 0-9S-CANARY-OBSERVE** (separate continuous-observation
order):

- Run the runner periodically (e.g. on each A1 round close, or via cron)
- Append observation records to
  `docs/recovery/20260424-mod-7/0-9s-observe-fast/sparse_canary_observations.jsonl`
- Once `rounds_observed >= 20`, the runner's status machine flips to
  either `OBSERVATION_COMPLETE_GREEN` or `OBSERVING_NOT_COMPLETE`
  (depending on S/F evaluation)
- If any F1-F9 fires → status `FAILED_OBSERVATION` + auto-rollback per
  `0-9s-ready/03_rollback_plan.md`

Continuation command:

```
python3 -m zangetsu.tools.run_sparse_canary_observation \
    --batch-events <live arena_batch_metrics jsonl path> \
    --plans       <live sparse_candidate_dry_run_plan jsonl path> \
    --output-dir  docs/recovery/20260424-mod-7/0-9s-observe-fast \
    --run-id      canary-N \
    --attribution-verdict GREEN \
    --readiness-verdict PASS
```

## 6. Final declaration

```
TEAM ORDER 0-9S-OBSERVE-FAST = OBSERVING_NOT_COMPLETE
```

Observer launched, runner shipped, evidence skeleton populated. Multi-day
window deferred to separate explicit order.
