# 02 — Launcher Inventory

## 1. Process State

| Process | State | Detail |
| --- | --- | --- |
| `arena_pipeline.py` (A1, w0..w3) | ACTIVE (cycling) | Last spawn `2026-04-26T09:45:01Z` PIDs `187987/187999/188008/188037`; watchdog respawns every 5 min |
| `arena23_orchestrator.py` (A2/A3) | STOPPED | No process visible; no lockfile exists in `/tmp/zangetsu/` |
| `arena45_orchestrator.py` (A4/A5) | STOPPED | Same |
| `arena13_feedback.py` | active (cron `*/5`) | Separate cron line, not via watchdog |
| `cp-api`, `dashboard-api`, `console-api` | systemd active | UNTOUCHED through this order |

## 2. Lockfiles

```
$ ls -la /tmp/zangetsu/
-rw-rw-r-- 1 j13 j13 6 Apr 26 09:45 arena_pipeline_w0.lock
-rw-rw-r-- 1 j13 j13 6 Apr 26 09:45 arena_pipeline_w1.lock
-rw-rw-r-- 1 j13 j13 6 Apr 26 09:45 arena_pipeline_w2.lock
-rw-rw-r-- 1 j13 j13 6 Apr 26 09:45 arena_pipeline_w3.lock
-rw-r--r-- 1 j13 j13 7 Apr 24 06:34 calcifer_supervisor.lock
```

→ Only A1 worker locks + Calcifer supervisor lock. **No `arena23_orchestrator.lock`, no `arena45_orchestrator.lock`.**

## 3. Cron Lines (pruned to relevant)

```
*/5 * * * * ~/j13-ops/zangetsu/watchdog.sh >> /tmp/zangetsu_watchdog.log 2>&1
*/5 * * * * cd ~/j13-ops/zangetsu && .venv/bin/python services/arena13_feedback.py >> /tmp/zangetsu_a13fb.log 2>&1
0  */6 * * * /home/j13/j13-ops/zangetsu/scripts/daily_data_collect.sh
*/15 * * * * /home/j13/j13-ops/calcifer/calcifer_v071_watch.sh >/dev/null 2>&1
```

→ No dedicated cron line for A23/A45. A23/A45 must be managed by the watchdog OR by a manual bootstrap.

## 4. Systemd Services (zangetsu/arena scope)

```
console-api.service        loaded  active  running
cp-api.service             loaded  active  running
dashboard-api.service      loaded  active  running
calcifer-supervisor.service loaded active running
calcifer-miniapp.service   loaded  active  running
calcifer-maintenance.service loaded inactive dead
arena-pipeline.service     (NOT in active list — service file may exist but is disabled / inactive)
arena23-orchestrator.service (same — recall AKASHA `_global/server_alaya.md` lists arena23 systemd as "active running" in older snapshot, but live `systemctl list-units` does not show it now)
```

→ None of A23 / A45 / arena-pipeline are managed by an active systemd unit currently.

## 5. tmux

```
$ tmux ls
(no tmux server running)
```

## 6. Watchdog Path + Capabilities

| Field | Value |
| --- | --- |
| Path | `/home/j13/j13-ops/zangetsu/watchdog.sh` (tracked in repo, ed25519-signed by PR #31) |
| Includes env preamble | YES (`source ~/.env.global`, post PR #31) |
| Iterates | `/tmp/zangetsu/*.lock` only |
| `restart_service` cases | `arena_pipeline_w*`, `arena23_orchestrator`, `arena45_orchestrator` (all three documented) |
| Skipped names | `arena13_feedback`, `calcifer_supervisor`, `alpha_discovery` (cron-managed elsewhere) |
| HTTP API path | `console-api`, `dashboard-api` are checked separately via `systemctl is-active` (no restart by this order) |

→ Watchdog has the **logic** to start A23/A45 — just lacks the lockfile that the loop iterates.

## 7. Orchestrator Source Pattern (read-only inspection, NO modification)

```
$ grep -n "^if __name__\|acquire_lock\|while running" zangetsu/services/arena23_orchestrator.py
1809:if __name__ == "__main__":
1810:    acquire_lock("arena23_orchestrator")
1811:    asyncio.run(main())
160:    while running:        # main daemon loop, polling-driven

$ grep -n "^if __name__\|acquire_lock\|while running" zangetsu/services/arena45_orchestrator.py
1185:if __name__ == "__main__":
1186:    acquire_lock("arena45_orchestrator")
1187:    asyncio.run(main())
123:    while running:        # main daemon loop
```

| Field | A23 | A45 |
| --- | --- | --- |
| Entry | `if __name__ == "__main__"` | same |
| Lock acquire | `acquire_lock("arena23_orchestrator")` | `acquire_lock("arena45_orchestrator")` |
| Main pattern | `asyncio.run(main())` with `while running:` daemon loop | same |
| Long-running | YES | YES |

→ Both orchestrators are async daemons; they will hold the lockfile for as long as the process is alive.

## 8. Pidlock Behavior (read-only inspection)

```
$ head -55 zangetsu/services/pidlock.py
def acquire_lock(service_name: str) -> None:
    os.makedirs(_PID_DIR, exist_ok=True)
    _lock_path = os.path.join(_PID_DIR, f"{service_name}.lock")
    _lock_fd = open(_lock_path, "a+")
    fcntl.flock(_lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    ...
    _lock_fd.seek(0); _lock_fd.truncate(0); _lock_fd.write(str(os.getpid())); _lock_fd.flush()
    atexit.register(_release_lock)
    signal.signal(SIGTERM, ...); signal.signal(SIGINT, ...)
```

→ Opens with `"a+"` (no truncation pre-lock). Truncates and writes own PID after acquiring `flock`. Releases on `atexit` / SIGTERM / SIGINT. This means an empty bootstrap lockfile will be cleanly taken over by the orchestrator.

## 9. Logs

| Component | Log | Last activity |
| --- | --- | --- |
| watchdog | `/tmp/zangetsu_watchdog.log` | active each `*/5` cycle |
| A1 w0..w3 | `/tmp/zangetsu_a1_w0..w3.log` | active each cycle |
| A23 | `/tmp/zangetsu_a23.log` | last write 2026-04-23T00:40:01Z (stale `KeyError`) |
| A45 | `/tmp/zangetsu_a45.log` | last write 2026-04-23T00:40:02Z (stale `KeyError`) |
| engine | `zangetsu/logs/engine.jsonl` | active (last 09:47:27 UTC) |
| arena batch metrics | `zangetsu/logs/arena_batch_metrics.jsonl` | MISSING |

## 10. Classification

| Component | Class |
| --- | --- |
| A1 | ACTIVE |
| A23 | STOPPED |
| A45 | STOPPED |
| Launcher (A1) | CRON / WATCHDOG |
| Launcher (A23) | CRON / WATCHDOG (logic present, lockfile missing) |
| Launcher (A45) | CRON / WATCHDOG (logic present, lockfile missing) |

→ No `BLOCKED_LAUNCHER_UNKNOWN` — the launcher is identified, only a lockfile-bootstrap is missing.

## 11. Phase B Verdict

→ **PASS.** Launcher fully inventoried. Bootstrap path identified. Proceed to Phase C env safety.
