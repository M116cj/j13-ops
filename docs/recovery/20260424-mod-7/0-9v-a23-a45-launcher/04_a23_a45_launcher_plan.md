# 04 — A23 / A45 Launcher Plan

## 1. Selected Method

**Lockfile bootstrap** (Outcome A per order §10).

The watchdog already has the launcher logic for `arena23_orchestrator` and `arena45_orchestrator` (verified in `02_launcher_inventory.md` §6). The only missing piece is a lockfile that the watchdog's `for lock in $LOCK_DIR/*.lock` loop can iterate over. Creating an empty placeholder lockfile makes the next watchdog cycle discover the service, classify it as DEAD (no live PID), and call `restart_service` — which spawns the orchestrator under the watchdog's preamble-loaded env.

**No source code change. No watchdog change. No cron change. No new launcher script.**

## 2. Bootstrap Commands

```bash
# Create empty lockfiles (umask 022 → world-readable; lockfile content is just a PID, not a secret).
: > /tmp/zangetsu/arena23_orchestrator.lock
: > /tmp/zangetsu/arena45_orchestrator.lock

# Trigger watchdog manually (cron will continue every 5 min).
bash /home/j13/j13-ops/zangetsu/watchdog.sh
```

After the watchdog runs:

1. Loop discovers `arena23_orchestrator.lock` and `arena45_orchestrator.lock`.
2. Reads empty PID → considers DEAD → calls `restart_service`.
3. `reclaim_lock` sees empty PID, `rm -f`s the bootstrap lockfile.
4. `restart_service` runs `eval "$cmd > $log 2>&1 &"` where `$cmd = $VENV $BASE/services/arenaXX_orchestrator.py`.
5. The Python process's `acquire_lock("arenaXX_orchestrator")` opens a fresh fd, flocks it exclusively, truncates and writes its own PID.
6. Subsequent watchdog cycles see live PID → no further restart needed.

## 3. Exact Commands After Bootstrap

| Component | Command (executed by watchdog, not by this order) |
| --- | --- |
| A23 | `/home/j13/j13-ops/zangetsu/.venv/bin/python3 /home/j13/j13-ops/zangetsu/services/arena23_orchestrator.py` (started with cwd `~/j13-ops/zangetsu`) |
| A45 | `/home/j13/j13-ops/zangetsu/.venv/bin/python3 /home/j13/j13-ops/zangetsu/services/arena45_orchestrator.py` (same cwd) |
| Working directory | `~/j13-ops/zangetsu` (`cd "$BASE"` in `restart_service`) |
| Python | `~/j13-ops/zangetsu/.venv/bin/python3` (3.12.3) |
| Env source | `~/.env.global` via watchdog preamble |
| A23 log | `/tmp/zangetsu_a23.log` |
| A45 log | `/tmp/zangetsu_a45.log` |
| Lockfile | `/tmp/zangetsu/arena23_orchestrator.lock` / `arena45_orchestrator.lock` (managed by `acquire_lock` and `_release_lock` atexit) |

## 4. Why This Is Launcher-Only and NOT Strategy Change

| Item | Diff |
| --- | --- |
| `arena23_orchestrator.py` | NOT modified |
| `arena45_orchestrator.py` | NOT modified |
| `arena_gates.py` | NOT modified |
| `arena_pipeline.py` | NOT modified |
| `settings.py` | NOT modified |
| Strategy parameters / thresholds / Arena pass-fail | NONE touched |
| `A2_MIN_TRADES` | UNCHANGED at 25 |
| `watchdog.sh` | NOT modified in this order (PR #31's preamble already there) |
| Cron entries | NOT modified |
| Env source | UNCHANGED (`~/.env.global`) |
| New file added to repo | none under `zangetsu/services/`; only docs in `docs/recovery/.../0-9v-a23-a45-launcher/` |
| Filesystem-level change | two empty placeholder lockfiles in `/tmp/zangetsu/` (transient, will be `rm`'d by watchdog within seconds and rewritten by orchestrator's `acquire_lock`) |

## 5. Stop / Rollback Method

If A23 / A45 misbehave or crash unexpectedly:

| Step | Command | Effect |
| --- | --- | --- |
| Stop A23 | `kill -TERM $(cat /tmp/zangetsu/arena23_orchestrator.lock 2>/dev/null)` | sends SIGTERM; `acquire_lock`'s `_sig_handler` releases lockfile cleanly |
| Stop A45 | `kill -TERM $(cat /tmp/zangetsu/arena45_orchestrator.lock 2>/dev/null)` | same |
| Prevent respawn | `rm -f /tmp/zangetsu/arena23_orchestrator.lock /tmp/zangetsu/arena45_orchestrator.lock` after the process is confirmed dead | watchdog's loop only manages services with live lockfiles |
| Full restart loop | watchdog's `*/5` cron remains untouched, so ALL changes here can be reversed with the four lines above without touching cron / repo / source |

## 6. Forbidden Behaviors (NOT performed)

| Behavior | Status |
| --- | --- |
| Modify `arena23_orchestrator.py` strategy logic | NOT performed |
| Modify `arena45_orchestrator.py` strategy logic | NOT performed |
| Modify thresholds | NOT performed |
| Modify champion promotion | NOT performed |
| Modify Arena pass / fail | NOT performed |
| Connect feedback consumer to generation runtime | NOT performed |
| Enable production trading | NOT performed |
| Print or commit secret value | NOT performed |
| Restart HTTP APIs | NOT performed |
| `git reset` / hard-reset / force-pull / merge | NOT performed |

## 7. Phase D Verdict

→ **PASS.** Plan is launcher-only, smallest possible, fully rollback-able. Proceed to Phase E (no source change needed) and Phase F-G.
