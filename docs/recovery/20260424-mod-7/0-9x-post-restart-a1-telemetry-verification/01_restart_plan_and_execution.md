# 01 — Restart Plan and Execution (Phase 1 + Phase 2)

**Phase 1 Verdict:** `RESTART_NOT_REQUIRED_ALREADY_POST_PATCH`
**Phase 2 Status:** Skipped (per Phase 1 verdict)

## Phase 1 evidence — workers loaded HEAD 29c757e

### Process start vs source mtime

```
HEAD commit ts:                      2026-04-27T15:38:05+00:00
arena_pipeline.py mtime:             2026-04-27 15:38:10.465 UTC
arena_rejection_taxonomy.py mtime:   2026-04-27 15:07:38.589 UTC

A1 worker PIDs and start time (from `ps -eo pid,lstart,cmd`):
  pid=884780  Mon Apr 27 17:02:16 2026 UTC  → 84 min POST source mtime (FRESH)
  pid=884803  Mon Apr 27 17:02:16 2026 UTC  → 84 min POST source mtime (FRESH)
  pid=884895  Mon Apr 27 17:02:16 2026 UTC  → 84 min POST source mtime (FRESH)
  pid=884919  Mon Apr 27 17:02:17 2026 UTC  → 84 min POST source mtime (FRESH)
```

§17.6 stale-service rule: process start ≥ source mtime → **FRESH (4/4)**

### `/proc/<pid>/cwd` and environment

| PID | cwd | A1_WORKER_ID | A1_WORKER_COUNT | A1_LANE | STRATEGY_ID | ZV5_DB_PASSWORD |
|---|---|---|---|---|---|---|
| 884780 | /home/j13/j13-ops | PRESENT | PRESENT | PRESENT | PRESENT | PRESENT |
| 884803 | /home/j13/j13-ops | PRESENT | PRESENT | PRESENT | PRESENT | PRESENT |
| 884895 | /home/j13/j13-ops | PRESENT | PRESENT | PRESENT | PRESENT | PRESENT |
| 884919 | /home/j13/j13-ops | PRESENT | PRESENT | PRESENT | PRESENT | PRESENT |

cwd matches expected repo root; env vars from `zangetsu_ctl.sh start` invocation present and correctly partitioned (w0,w1 → j01 baseline; w2,w3 → j02 exploration per ctl.sh source).

### Source-side fix presence

Phase 0 confirmed all three sentinel tokens (`_compute_a1_reject_deltas`, `_A1_REJECT_STATS_KEYS`, `_A1_PREV_REJECT_STATS_SNAPSHOT`) are present in `zangetsu/services/arena_pipeline.py`. Workers loaded this file at 17:02:16Z, after the 15:38:10Z mtime. Therefore the per-round delta accounting helper is in the running interpreter image.

## Phase 1 Classification

```
RESTART_NOT_REQUIRED_ALREADY_POST_PATCH
```

### Provenance note

A safe restart was already executed earlier in the same session (operator-authorized) via the canonical path:

```
ssh j13@100.123.49.102 "cd /home/j13/j13-ops/zangetsu && ./zangetsu_ctl.sh restart"
```

Sequence used by ctl.sh (Phase 0 also enforces governance pre-flight):

1. `stop`: SIGTERM via lockfile PIDs → 3s grace → SIGKILL residual `services/arena*` → wipe `/tmp/zangetsu/*.lock`
2. `start`:
   - governance pre-flight: `scripts/verify_no_archive_reads.sh` (passed: "clean")
   - clear stale Numba `*.nbi/*.nbc` (excluding `.venv`)
   - launch 4× workers with `STRATEGY_ID`, `A1_WORKER_ID`, `A1_WORKER_COUNT=4`, `A1_LANE`
   - launch A23 + A45 orchestrators
   - 5s warmup + emit `status`

Restart artifacts in this session:
- 3 `force killed` notices on w0/w1/w2 (SIGTERM timeout — expected for long-running numpy/numba workers)
- New PIDs assigned: 884780/884803/884895/884919/885011/885036
- All 8 services reported `RUNNING` post-start
- `Total: 7 locked services, 0 orphans` (pipeline status check)

Watchdog log post-restart shows `action=skipped reason=lockfile_present_main_loop_owns` for all workers — correct deferral behavior.

## Phase 2 — Skipped

Because Phase 1 verdict is `RESTART_NOT_REQUIRED_ALREADY_POST_PATCH`, Phase 2 (Safe Restart Plan and Execution) was not re-executed in this evidence cycle. The earlier in-session restart already satisfies its goal.

### Phase 2 classification (recorded for completeness)

```
RESTART_NOT_REQUIRED
```

| Required outcome | Status |
|---|---|
| A1 w0–w3 alive | ✅ |
| A23 alive | ✅ |
| A45 alive | ✅ |
| no duplicate workers | ✅ (1 PID per slot) |
| no uncontrolled restart loop | ✅ (no watchdog trigger on these PIDs) |
| no bash error | ✅ |
| watchdog stable | ✅ ("all 8 services healthy" at 17:00:01) |
