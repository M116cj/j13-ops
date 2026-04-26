# 01 — A1 Runtime Loop Completion Audit

## 1. Per-Cycle Sequence Observed

Each cron cycle (every 5 min, watchdog respawn), an A1 worker:

1. **Imports settings** (post-PR-#31 env injection, no KeyError) ✓
2. **Builds indicator caches** ("Built indicator cache: 110 arrays, 25.2 MB" and "Indicator cache built for XRPUSDT/DOGEUSDT/BNBUSDT/..." log lines) ✓
3. **Reports regime distribution + Bloom filter loaded** ✓
4. **Loads A13 guidance** (post-PR-#33 + PR-#34, mode=observe, BASE_WEIGHTS) ✓
5. **"Pipeline V10 running"** ✓ (worker enters main loop)
6. **"Resumed from checkpoint: round=49450, champions=0"** ✓
7. **"AlphaEngine ready: 126 indicator terminals, 35 operators"** ✓
8. **Generation loop emits ENTRY events** (~16 candidates per cycle observed at the second-mark; e.g. 2026-04-26T12:27:14Z multiple alphas ENTERED for XRPUSDT) ✓
9. **Generation loop CRASHES with a Python UnboundLocalError** at `arena_pipeline.py:1224` ✗ ← terminal failure

## 2. Verbatim Final Traceback (worker w0, latest cycle)

```
Traceback (most recent call last):
  File "/home/j13/j13-ops/zangetsu/services/arena_pipeline.py", line 1270, in <module>
    asyncio.run(main())
  File "/usr/lib/python3.12/asyncio/runners.py", line 194, in run
    return runner.run(main)
  File "/usr/lib/python3.12/asyncio/runners.py", line 118, in run
    return self._loop.run_until_complete(task)
  File "/usr/lib/python3.12/asyncio/base_events.py", line 687, in run_until_complete
    return future.result()
  File "/home/j13/j13-ops/zangetsu/services/arena_pipeline.py", line 1224, in main
    run_id=getattr(_pb, "run_id", "") or "",
                   ^^^
UnboundLocalError: cannot access local variable '_pb' where it is not associated with a value
```

The same traceback appears in /tmp/zangetsu_a1_w0..w3.log for every cron cycle today.

## 3. Cycle Outcome

| Field | Value |
| --- | --- |
| ENTRY events emitted per cycle | ~16 (one per alpha that enters generation) |
| EXIT_PASS / EXIT_REJECT events | 0 (loop crashes before stage_event=EXIT can be reached) |
| INSERT INTO champion_pipeline_staging | 0 |
| stats counters logged at cycle end | 0 (line 1207 'rejects:' summary never reached) |
| 'final_stats' or 'Stopped.' line | 0 (line 1264 cleanup never reached) |
| asyncio loop completion | NO (loop terminates with UnboundLocalError, propagates to asyncio.run, kills worker) |
| Process exit code | non-zero (Python UnhandledException) |
| Watchdog respawn next cycle | YES (cron */5 spawns a fresh worker, same crash) |

## 4. "High CPU" Explanation

Workers run at 99% CPU during the indicator-cache build phase (numpy + wavelet denoising on 14 symbols × 110 indicators). This phase **completes successfully**. The crash happens **inside main() after the inner per-alpha loop finishes**. The high-CPU activity is genuine generation work, not a stuck loop.

## 5. Phase 1 Classification

Per order §6:

| Verdict | Match? |
| --- | --- |
| A1_LOOP_COMPLETES_NO_WRITE | NO (loop never completes; it crashes on UnboundLocalError) |
| **A1_LOOP_EARLY_EXIT** (loop crashes before reaching the persistence path) | **YES — exact match** |
| A1_LOOP_EXCEPTION_SUPPRESSED | NO (the exception is NOT suppressed — it crashes asyncio.run) |
| A1_LOOP_STUCK_RECOMPUTING_CACHE | NO |
| A1_LOOP_WAITING_QUEUE | NO |
| A1_LOOP_UNKNOWN | NO |

→ **Phase 1 verdict: A1_LOOP_EARLY_EXIT** (Python UnboundLocalError crashes asyncio main).
