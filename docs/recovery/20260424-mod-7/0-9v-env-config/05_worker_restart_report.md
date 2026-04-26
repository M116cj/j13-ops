# 05 — Worker Restart Report

## 1. Method

Manual one-shot trigger of the watchdog from a login shell with the new preamble in place:

```bash
bash /home/j13/j13-ops/zangetsu/watchdog.sh
```

Plus a 45-second wait before re-inspecting the process table.

## 2. Pre-Trigger State

```
$ ps -ef | grep -iE "(arena_pipeline|arena23_orchestrator|arena45_orchestrator)" | grep -v grep
(empty — no arena worker alive)
```

Last cron cycle (`2026-04-26T09:00:01Z`) had spawned `arena_pipeline_w0..w3` from the un-patched watchdog → all crashed on `KeyError: ZV5_DB_PASSWORD`.

## 3. Watchdog Output (this trigger)

```
2026-04-26T09:03:19 WATCHDOG: arena_pipeline_w0 is DEAD (pid=94122), restarting...
2026-04-26T09:03:19 WATCHDOG: restarted arena_pipeline_w0 (pid=103233)
2026-04-26T09:03:19 WATCHDOG: arena_pipeline_w1 is DEAD (pid=94147), restarting...
2026-04-26T09:03:19 WATCHDOG: restarted arena_pipeline_w1 (pid=103242)
2026-04-26T09:03:19 WATCHDOG: arena_pipeline_w2 is DEAD (pid=94156), restarting...
2026-04-26T09:03:19 WATCHDOG: restarted arena_pipeline_w2 (pid=103251)
2026-04-26T09:03:19 WATCHDOG: arena_pipeline_w3 is DEAD (pid=94165), restarting...
2026-04-26T09:03:19 WATCHDOG: restarted arena_pipeline_w3 (pid=103260)
```

→ Watchdog detected all 4 A1 worker locks as DEAD (the previous cron cycle's worker PIDs had exited on KeyError) and respawned each. New PIDs `103233`, `103242`, `103251`, `103260` were spawned **with** the preamble-loaded env.

## 4. Post-Trigger State (after 45 s wait)

```
$ ps -ef | grep -iE "(arena_pipeline)" | grep -v grep
j13  103233  1 99 09:03 ?  00:00:58  python3 .../zangetsu/services/arena_pipeline.py
j13  103242  1 99 09:03 ?  00:00:57  python3 .../zangetsu/services/arena_pipeline.py
j13  103251  1 99 09:03 ?  00:00:58  python3 .../zangetsu/services/arena_pipeline.py
j13  103260  1 99 09:03 ?  00:00:58  python3 .../zangetsu/services/arena_pipeline.py
```

→ All 4 A1 workers ALIVE for ≥ 58 s (i.e. they passed `import zangetsu.config.settings` without crashing).

## 5. Worker Log Activity (real engine work, no env error)

Trailing lines from `/tmp/zangetsu_a1_w0..w3.log`:

```
zangetsu_a1_w0  2026-04-26 09:04:02  INFO  Regime AVAXUSDT: BEAR_RALLY (...)
zangetsu_a1_w1  2026-04-26 09:04:02  INFO  Regime DOTUSDT: BEAR_RALLY (...)
zangetsu_a1_w2  2026-04-26 09:04:02  INFO  Regime FILUSDT: BEAR_RALLY (...)
zangetsu_a1_w3  2026-04-26 09:04:02  INFO  Regime 1000PEPEUSDT: CHOPPY_VOLATILE (...)
```

→ Workers are processing real market regime classifications. The `KeyError: ZV5_DB_PASSWORD` traceback no longer appears in any A1 log line **after** PID `103233+`.

## 6. Old Stale Logs (a23 / a45)

`/tmp/zangetsu_a23.log` and `/tmp/zangetsu_a45.log` still show old `KeyError: 'ZV5_DB_PASSWORD'` tracebacks at their tail. Those tracebacks are **stale** — they were produced by previous manual launches **before** any A23/A45 lockfile existed. Watchdog's lockfile-driven loop only iterates `*.lock` files in `/tmp/zangetsu/`, and there is no `arena23_orchestrator.lock` / `arena45_orchestrator.lock` in that directory:

```
$ ls /tmp/zangetsu/*.lock
/tmp/zangetsu/arena_pipeline_w0.lock
/tmp/zangetsu/arena_pipeline_w1.lock
/tmp/zangetsu/arena_pipeline_w2.lock
/tmp/zangetsu/arena_pipeline_w3.lock
/tmp/zangetsu/calcifer_supervisor.lock
```

→ A23 / A45 are NOT being launched by the current watchdog cycle. Their absence pre-dates this order (documented in PR #28's `09_runtime_switch_report.md` as "STOPPED — no process visible") and is a separate launcher question, NOT an env-injection regression. This order's mission was specifically the cron worker that crashes on `KeyError: ZV5_DB_PASSWORD`, i.e. the A1 path that the watchdog actually touches.

## 7. KeyError Recurrence

| Worker | New PID | KeyError on new PID? |
| --- | --- | --- |
| `arena_pipeline_w0` | 103233 | NO |
| `arena_pipeline_w1` | 103242 | NO |
| `arena_pipeline_w2` | 103251 | NO |
| `arena_pipeline_w3` | 103260 | NO |
| `arena23_orchestrator` | (not launched this cycle — watchdog has no lockfile to manage) | n/a |
| `arena45_orchestrator` | (same) | n/a |

→ For every worker the watchdog actually spawns on this trigger, the env-load preamble succeeded.

## 8. Hard-Ban Compliance

| Item | Status |
| --- | --- |
| HTTP APIs restarted | NO (PIDs `2537810`, `3871446`, `3871449` unchanged from before this order) |
| Production rollout enabled | NO |
| Optimizer apply enabled | NO |
| Strategy/threshold/budget changed | NO |

## 9. Phase H Verdict

→ **PASS.** Workers no longer crash on `KeyError: ZV5_DB_PASSWORD`. No `BLOCKED_WORKER_ENV_STILL_MISSING`. No `BLOCKED_NEW_RUNTIME_ERROR`.
