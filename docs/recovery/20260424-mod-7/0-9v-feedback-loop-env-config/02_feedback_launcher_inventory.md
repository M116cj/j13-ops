# 02 — `arena13_feedback` Launcher Inventory

## 1. Cron Entry (verbatim)

```
*/5 * * * * cd ~/j13-ops/zangetsu && .venv/bin/python services/arena13_feedback.py >> /tmp/zangetsu_a13fb.log 2>&1
```

| Field | Value |
| --- | --- |
| Schedule | `*/5 * * * *` (every 5 min, same as watchdog) |
| Working directory (cd) | `~/j13-ops/zangetsu` (= `/home/j13/j13-ops/zangetsu`) |
| Python interpreter (relative) | `.venv/bin/python` (= `/home/j13/j13-ops/zangetsu/.venv/bin/python`) |
| Script (relative) | `services/arena13_feedback.py` (= `/home/j13/j13-ops/zangetsu/services/arena13_feedback.py`) |
| Log destination | `/tmp/zangetsu_a13fb.log` |

## 2. Watchdog Involvement

| Field | Value |
| --- | --- |
| Routed through `watchdog.sh` | NO (cron invokes Python directly) |
| Inherits PR #31 env preamble | NO (the preamble is only in `watchdog.sh`, not in this cron line) |
| Lockfile-managed by watchdog | NO (`/tmp/zangetsu/arena13_feedback.lock` is in watchdog's skip list per source: `case "$name" in arena13_feedback\|calcifer_supervisor\|alpha_discovery) continue ;; esac`) |

→ This is a **bare-cron launch path** that does not benefit from any earlier env-config repair.

## 3. Source Path Discovery

```
$ find /home/j13/j13-ops -name "arena13_feedback.py" -print
/home/j13/j13-ops/zangetsu/services/arena13_feedback.py
```

→ Single canonical location. No ambiguity.

## 4. Current Process State

```
$ ps -ef | grep arena13_feedback | grep -v grep
(none — script exits immediately on import-time KeyError)
```

→ The script crashes during `from zangetsu.config.settings import Settings` (at line 99 of `settings.py`) and exits, so no long-running feedback process exists.

## 5. Crash Evidence (current cron cycle, no secret printed)

```
$ tail -8 /tmp/zangetsu_a13fb.log
    from zangetsu.config.settings import Settings
  File "/home/j13/j13-ops/zangetsu/config/__init__.py", line 2, in <module>
    from .settings import Settings
  File "/home/j13/j13-ops/zangetsu/config/settings.py", line 99, in <module>
    DB_PASSWORD: str = os.environ["ZV5_DB_PASSWORD"]  # no fallback — must be set in env
                       ~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "<frozen os>", line 685, in __getitem__
KeyError: 'ZV5_DB_PASSWORD'
```

Log file size: 900 KB of accumulated tracebacks since 2026-04-23.

→ Failure mode is confirmed identical to the original issue PR #31 fixed for the watchdog path. **Same root cause, same fix, different launcher.**

## 6. Other Inspection (non-secret only)

```
$ systemctl list-units --type=service --all 2>/dev/null | grep -E "feedback|arena13"
(no systemd unit for arena13_feedback)

$ tmux ls 2>/dev/null
(no tmux server)

$ grep -R "arena13_feedback" /home/j13/j13-ops --exclude-dir=.git --exclude='*.jsonl' --exclude='*.log' | head -10
zangetsu/services/arena13_feedback.py:[its own source]
zangetsu/watchdog.sh:case "$name" in arena13_feedback|calcifer_supervisor|alpha_discovery) continue ;;  # explicitly skipped
... (only design / decision docs reference it)
```

→ No other launcher candidate. Cron is the sole launch mechanism.

## 7. Side-Effect Audit (HTTP APIs / A1 / A23 / A45 are NOT affected by this order)

| Service | State | Will this order touch? |
| --- | --- | --- |
| `cp-api` / `dashboard-api` / `console-api` | running on systemd | NO |
| A1 (`arena_pipeline_w*`) | cycling on watchdog | NO |
| A23 (`arena23_orchestrator`) | alive on watchdog | NO |
| A45 (`arena45_orchestrator`) | alive on watchdog | NO |
| `arena13_feedback.py` cron | crash-loop | YES (this order's target) |

## 8. Phase B + C Verdict

→ **PASS.** Launcher fully inventoried (single bare-cron line). Failure mode confirmed (`KeyError: 'ZV5_DB_PASSWORD'`). No secret value printed. No `BLOCKED_FEEDBACK_LAUNCHER_UNKNOWN`, no `BLOCKED_DIFFERENT_ROOT_CAUSE`.
