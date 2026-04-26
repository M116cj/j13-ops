# 06 — Process Start Report

## 1. Method

**Lockfile bootstrap + manual one-shot watchdog trigger.**

```bash
: > /tmp/zangetsu/arena23_orchestrator.lock      # empty placeholder
: > /tmp/zangetsu/arena45_orchestrator.lock      # empty placeholder
bash /home/j13/j13-ops/zangetsu/watchdog.sh      # one-shot trigger
```

Cron `*/5 * * * * watchdog.sh` continues unchanged.

## 2. Pre-trigger State

```
$ ps -ef | grep -E "(arena23|arena45|arena_pipeline)" | grep -v grep
(empty — between cron cycles, all workers had exited)

$ ls /tmp/zangetsu/*.lock
arena_pipeline_w0.lock  arena_pipeline_w1.lock  arena_pipeline_w2.lock  arena_pipeline_w3.lock  calcifer_supervisor.lock
```

→ No A23/A45 lockfiles, no A23/A45 process.

## 3. Watchdog Output

```
2026-04-26T09:52:52 WATCHDOG: arena23_orchestrator is DEAD (pid=), restarting...
2026-04-26T09:52:52 WATCHDOG: restarted arena23_orchestrator (pid=207186)
2026-04-26T09:52:52 WATCHDOG: arena45_orchestrator is DEAD (pid=), restarting...
2026-04-26T09:52:52 WATCHDOG: restarted arena45_orchestrator (pid=207195)
2026-04-26T09:52:52 WATCHDOG: arena_pipeline_w0 is DEAD (pid=198574), restarting...
2026-04-26T09:52:52 WATCHDOG: restarted arena_pipeline_w0 (pid=207204)
2026-04-26T09:52:52 WATCHDOG: arena_pipeline_w1 is DEAD (pid=198583), restarting...
2026-04-26T09:52:52 WATCHDOG: restarted arena_pipeline_w1 (pid=207213)
2026-04-26T09:52:52 WATCHDOG: arena_pipeline_w2 is DEAD (pid=198592), restarting...
2026-04-26T09:52:52 WATCHDOG: restarted arena_pipeline_w2 (pid=207222)
2026-04-26T09:52:52 WATCHDOG: arena_pipeline_w3 is DEAD (pid=198604), restarting...
2026-04-26T09:52:52 WATCHDOG: restarted arena_pipeline_w3 (pid=207231)
```

→ Watchdog detected the empty A23/A45 lockfiles, classified them DEAD (empty PID), called `restart_service`, which spawned the orchestrators under the env-loaded shell.

## 4. New PIDs (post-trigger)

| Service | New PID | Wall time at observation | State |
| --- | --- | --- | --- |
| `arena23_orchestrator` | 207186 | ~ 3 min alive | ALIVE (idle service loop) |
| `arena45_orchestrator` | 207195 | ~ 3 min alive | ALIVE (idle service loop) |
| `arena_pipeline_w0` | 207204 | ~ 41 s alive | ALIVE (99% CPU) |
| `arena_pipeline_w1` | 207213 | ~ 42 s alive | ALIVE (99% CPU) |
| `arena_pipeline_w2` | 207222 | ~ 42 s alive | ALIVE (99% CPU) |
| `arena_pipeline_w3` | 207231 | ~ 43 s alive | ALIVE (99% CPU) |

→ All 6 workers running on the post-PR-#31 code under the env-loaded shell.

## 5. Lockfile Takeover

```
$ ls -la /tmp/zangetsu/
arena_pipeline_w0.lock        6 B  09:52
arena_pipeline_w1.lock        6 B  09:52
arena_pipeline_w2.lock        6 B  09:52
arena_pipeline_w3.lock        6 B  09:52
arena23_orchestrator.lock     6 B  09:52
arena45_orchestrator.lock     6 B  09:52
calcifer_supervisor.lock      7 B  Apr 24
```

→ Bootstrap empty (0 B) lockfiles were `rm`-ed by `reclaim_lock` and re-created by the orchestrators' `acquire_lock` call (now containing the real PID, 6 bytes). Watchdog's next cycle will see live PIDs and not respawn.

## 6. HTTP API + Postgres Preservation

| Service | PID | Touched? |
| --- | --- | --- |
| `cp-api` | 2537810 | NO (since Apr 24) |
| `dashboard-api` | 3871446 | NO (since Apr 23) |
| `console-api` | 3871449 | NO (since Apr 23) |
| `postgres: zangetsu zangetsu` | 4639 | NO (since Apr 21) |

→ All preserved.

## 7. A23 / A45 Boot Logs (real engine activity, no error)

```
$ tail -8 /tmp/zangetsu_a23.log
2026-04-26 09:53:00 INFO Loaded 1000SHIBUSDT: train=140000 + holdout=60000 bars
2026-04-26 09:53:01 INFO Loaded GALAUSDT: train=140000 + holdout=60000 bars
2026-04-26 09:53:01 INFO Wavelet denoising active for BTCUSDT/train
2026-04-26 09:53:01 INFO Data cache: 14 symbols loaded (train split only, factor-enriched)
2026-04-26 09:53:01 INFO Service loop started

$ tail -8 /tmp/zangetsu_a45.log
2026-04-26 09:53:00 INFO Data loaded: 14 symbols (holdout split only, factor-enriched)
2026-04-26 09:53:00 INFO Arena 4+5 Orchestrator running (v9: shared_utils dedup + ATR/TP fixes)
2026-04-26 09:53:00 INFO Daily reset starting
2026-04-26 09:53:00 INFO Daily reset complete: kept=0 retired=0 across 0 regimes
```

→ A23 loaded 14 symbols' OHLCV + wavelet-denoised features and entered its service loop. A45 loaded the same 14 symbols' holdout split, performed its daily reset (no champions to retire — clean slate), and entered its main loop. Both **`KeyError: ZV5_DB_PASSWORD`** of 2026-04-23 is no longer reproduced (env preamble works for them too).

## 8. Errors

| Error category | Count |
| --- | --- |
| `KeyError: ZV5_DB_PASSWORD` recurrence | 0 |
| Tracebacks in new-PID logs | 0 |
| Worker exits within 30 s | 0 |
| HTTP API restart events | 0 |

## 9. Phase G Verdict

→ **PASS.** A23 / A45 / A1 all alive. No `BLOCKED_A23_START_FAILURE`, no `BLOCKED_A45_START_FAILURE`, no `BLOCKED_UNKNOWN_RUNTIME_ERROR`.
