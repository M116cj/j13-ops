# 06 — Telemetry Source Check

## 1. Required telemetry sources for live observation

Per 0-9S-CANARY-OBSERVE-COMPLETE order §6 / §11:

- `arena_batch_metrics.jsonl` — emitted by P7-PR4B-instrumented
  `arena23_orchestrator` (PR #18).
- `sparse_candidate_dry_run_plans.jsonl` — emitted by 0-9R-IMPL-DRY
  consumer when activated (PR #23).

## 2. Alaya pre-sync state

```
$ ls -lh zangetsu/logs/arena_batch_metrics.jsonl
ls: cannot access ... No such file or directory

$ ls -lh zangetsu/logs/sparse_candidate_dry_run_plans.jsonl
ls: cannot access ... No such file or directory
```

| File | Status |
| --- | --- |
| `arena_batch_metrics.jsonl` | **MISSING** |
| `sparse_candidate_dry_run_plans.jsonl` | **MISSING** |

This is **expected**:

- `arena_batch_metrics` aggregate emitter doesn't exist on Alaya yet (PR #18 not deployed).
- `sparse_candidate_dry_run_plan` event emission requires the consumer (PR #23) which isn't even on Alaya.

## 3. Existing log sources

| File | Size | Last write | Lines | Notes |
| --- | --- | --- | --- | --- |
| `zangetsu/logs/engine.jsonl` | 38 MB | 2026-04-23 00:35:54 UTC | 308579 | pre-P7-PR4B logs; arena pipeline stopped at this timestamp |
| `zangetsu/logs/engine.jsonl.1` | 2.5 MB | 2026-04-16 04:25 UTC | 14213 (per Mac scan) | rotated archive |
| `zangetsu/logs/dashboard.log` | 316 B | 2026-04-11 | small | dashboard runtime |
| `zangetsu/logs/pipeline-v2.log` | 9 KB | 2026-04-16 | small | older pipeline log |
| `zangetsu/logs/r2_n4_watchdog.stdout` | 4.5 KB | 2026-04-22 | small | watchdog |

Last engine.jsonl entry:

```json
{"ts": "2026-04-23T00:35:54", "level": "INFO", "msg": "Stopped. a4_processed=0 a4_passed=0 a5_matches=0"}
```

The arena pipeline itself was last shut down on Apr 23 with zero
champions promoted — meaning the pipeline has been **idle** for ~3 days
at audit time.

## 4. Why "MISSING" is acceptable for this PR

This PR (0-9V-REPLACE) is about **replacement readiness**, not live
observation. The order §6 hard ban explicitly says:

> "If telemetry missing: Do not synthesize telemetry. Replacement may
> still complete, but next action becomes telemetry enablement before
> observation."

So missing telemetry does NOT block replacement. It blocks the
**subsequent** order (0-9S-CANARY-OBSERVE-LIVE).

## 5. Enabling telemetry post-replacement

After dirty state cleanup + fast-forward + arena pipeline restart:

1. Watchdog cron (`*/5 * * * * ~/j13-ops/zangetsu/watchdog.sh`) will
   relaunch arena_pipeline / arena23 / arena45.
2. PR #18-instrumented arena23_orchestrator will start emitting
   `arena_batch_metrics` events to stdout (and from there to
   engine.jsonl per the existing logger config).
3. To pipe them to a dedicated `arena_batch_metrics.jsonl` separate
   file, a future order would need to add a logger handler. Until
   then, the audit / observer runners can ingest engine.jsonl and
   filter for `event_type == "arena_batch_metrics"` lines.

## 6. Current state for live observation readiness

| Field | Value |
| --- | --- |
| `arena_batch_metrics.jsonl` exists | NO |
| `sparse_candidate_dry_run_plans.jsonl` exists | NO |
| Enough telemetry for live observation | **NO** (pre-sync state) |
| After fast-forward + restart | **PENDING** (needs a few rounds of arena loop) |

## 7. Conclusion

**Phase F gate: PASS** for replacement scope (telemetry absence is
acceptable for code replacement). **Live observation is NOT yet
ready** — that requires a post-replacement order (0-9S-CANARY-OBSERVE-LIVE).
