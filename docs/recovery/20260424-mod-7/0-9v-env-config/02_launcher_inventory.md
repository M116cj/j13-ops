# 02 — Launcher Inventory

## 1. Cron-Triggered Launchers (relevant to this order)

| Cron line (verbatim) | Manages |
| --- | --- |
| `*/5 * * * * ~/j13-ops/zangetsu/watchdog.sh >> /tmp/zangetsu_watchdog.log 2>&1` | A1 workers (`arena_pipeline_w0..w3`), A2/A3 (`arena23_orchestrator`), A4/A5 (`arena45_orchestrator`) via lockfile reclaim + spawn |
| `*/5 * * * * cd ~/j13-ops/zangetsu && .venv/bin/python services/arena13_feedback.py` | Arena1 candidate feedback loop |
| `*/15 * * * * /home/j13/j13-ops/calcifer/calcifer_v071_watch.sh` | Calcifer watchdog (out of scope for this order) |

## 2. Watchdog Path

| Field | Value |
| --- | --- |
| Path | `/home/j13/j13-ops/zangetsu/watchdog.sh` |
| Tracked in repo | YES (`git ls-files zangetsu/watchdog.sh` → present) |
| Executable | YES |
| Log destination | `/tmp/zangetsu_watchdog.log` |

The watchdog spawns workers via `eval "$cmd > $log 2>&1 &"` where `$cmd` is constructed per-worker (see watchdog.sh §3 `restart_service` function in PR #28 evidence). Spawned children inherit cron's environment.

## 3. Worker / Venv

| Field | Value |
| --- | --- |
| Workers | `arena_pipeline.py`, `arena23_orchestrator.py`, `arena45_orchestrator.py` |
| Venv python | `/home/j13/j13-ops/zangetsu/.venv/bin/python3` (symlink to `/usr/bin/python3`, version 3.12.3) |
| Working directory | `/home/j13/j13-ops` |
| Lockfile dir | `/tmp/zangetsu/` |
| Worker logs | `/tmp/zangetsu_a1_w0..w3.log`, `/tmp/zangetsu_a23.log`, `/tmp/zangetsu_a45.log` |

## 4. HTTP APIs (preserved through this order)

| Service | Manager | EnvironmentFile (per `systemctl cat`) | Status |
| --- | --- | --- | --- |
| `cp-api.service` | systemd | `/home/j13/j13-ops/zangetsu/control_plane/cp_api/.env` (gitignored) | **active running** |
| `dashboard-api.service` | systemd | `/home/j13/j13-ops/zangetsu/secret/.env` (gitignored) | **active running** |
| `console-api.service` | systemd | `/home/j13/j13-ops/zangetsu/secret/.env` (gitignored) | **active running** |

→ HTTP APIs already have a working pattern for env injection. Workers (cron-launched) lack the equivalent.

## 5. Existing Secret Stores (non-repo, found via filesystem inventory)

```
$ stat -c '%a %U:%G %n' /home/j13/.env.global /home/j13/j13-ops/zangetsu/secret/.env
600 j13:j13 /home/j13/.env.global
600 j13:j13 /home/j13/j13-ops/zangetsu/secret/.env
```

Both files have `600` permissions, both owned by `j13`, both gitignored via `**/.env*` and `**/secret/` patterns in `.gitignore`.

| File | Tracked? | Contains ZV5_DB_PASSWORD entry? | Notes |
| --- | --- | --- | --- |
| `/home/j13/.env.global` | NO (not in repo) | NO (only `BINANCE_API_KEY` + `BINANCE_SECRET_KEY`) | Per CLAUDE.md `_global/server_alaya.md`, this is the j13-global secrets file |
| `/home/j13/j13-ops/zangetsu/secret/.env` | NO (gitignored: `.gitignore:51 **/secret/`) | YES (`grep -c '^\(export *\)\?ZV5_DB_PASSWORD=' = 1`) | Authoritative for HTTP APIs |

→ Existing authoritative source for `ZV5_DB_PASSWORD` is `/home/j13/j13-ops/zangetsu/secret/.env`. No new secret entry needs to be input by j13.

## 6. Current Process State (pre-repair)

```
$ ps aux | grep -iE "(zangetsu|arena13)" | grep -v grep
caddy   4639  ...  postgres: zangetsu zangetsu  (DB connections, unaffected)
j13  2537810 ...  cp_api server.py                (HTTP API, untouched)
j13  3871446 ...  uvicorn dashboard.run:app       (HTTP API, untouched)
j13  3871449 ...  uvicorn console.run:app         (HTTP API, untouched)
```

NO `arena_pipeline_w*`, `arena23_orchestrator`, or `arena45_orchestrator` process visible — workers spawned by latest watchdog cycle have already crashed and exited.

## 7. Crash Evidence (root cause confirmation)

```
$ tail -3 /tmp/zangetsu_a1_w0.log
File "/home/j13/j13-ops/zangetsu/config/settings.py", line 99, in <module>
    DB_PASSWORD: str = os.environ["ZV5_DB_PASSWORD"]  # no fallback — must be set in env
KeyError: ZV5_DB_PASSWORD
```

Reproduces in all 6 cron-spawned worker logs. Introduced by commit `fe1c0bc0` (2026-04-20 "security(repo): purge hardcoded DB password + untrack .env files").

## 8. Safe Presence Check (no value printed)

```python
$ python3 -c "import os; print('interactive_shell_ZV5_DB_PASSWORD=' + ('PRESENT' if os.getenv('ZV5_DB_PASSWORD') else 'MISSING'))"
interactive_shell_ZV5_DB_PASSWORD=MISSING
```

(Note: the interactive SSH shell I run as j13 also does NOT have `ZV5_DB_PASSWORD` exported — confirming the variable only exists inside the systemd-loaded EnvironmentFile namespace, not in the user's login shell.)

## 9. Phase B + C Verdict

→ **PASS.** Launcher fully inventoried. Crash root cause confirmed without printing secret. Authoritative non-repo source for the secret found. No `BLOCKED_LAUNCHER_UNKNOWN`, no `BLOCKED_DIFFERENT_ROOT_CAUSE`.
