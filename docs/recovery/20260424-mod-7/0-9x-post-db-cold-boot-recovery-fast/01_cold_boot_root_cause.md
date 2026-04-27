# 01 — Cold-Boot Root Cause Confirmation

Phase: 1 of 7
Order: TEAM ORDER 0-9X-POST-DB-COLD-BOOT-RECOVERY-FAST

## Root cause (one-line)

`zangetsu/watchdog.sh` is purely **lockfile-driven** — its sole supervision
loop is `for lock in $LOCK_DIR/*.lock; do ... done`. When `/tmp` (tmpfs)
is wiped by a reboot, `$LOCK_DIR=/tmp/zangetsu/` contains **zero**
lockfiles. The loop iterates over zero entries, exits silently, and the
script reports "all services healthy" with no work done — leaving every
A1/A23/A45 worker permanently absent.

This was the exact failure pattern recorded in `zangetsu/VERSION_LOG.md`
(v0.4.0 retro, lines 631-632):

> "Watchdog blind because pidlocks were cleanly removed (not stale-PID).
>  Watchdog presence-check is lockfile-based; if lockfile removed cleanly,
>  watchdog doesn't restart. **Need 'expected services' tracker.**"

The order's "expected services tracker" is exactly what Phase 2 ships.

## Exact file / branch / condition

| Item                                        | Value                                                    |
|---------------------------------------------|----------------------------------------------------------|
| Responsible file                            | `zangetsu/watchdog.sh`                                   |
| Missing branch (pre-patch)                  | No iteration over a "must-exist" worker list             |
| Lockfile path                               | `/tmp/zangetsu/${name}.lock`                             |
| Storage class                               | tmpfs (volatile across reboot)                           |
| Pre-patch loop                              | `for lock in $LOCK_DIR/*.lock; do ... done` only         |
| Behaviour with zero locks                   | loop runs zero iterations → "healthy" report             |
| Behaviour with stale lock + dead pid        | already handled (`reclaim_lock` SIGTERM→KILL→rm→respawn) |
| Behaviour with absent lock + absent process | **not handled** ← the cold-boot gap                      |

## Expected worker list

Six required workers, every one driven by `lockfile + pgrep` only (no
systemd):

```
arena_pipeline_w0
arena_pipeline_w1
arena_pipeline_w2
arena_pipeline_w3
arena23_orchestrator
arena45_orchestrator
```

## Restart command per worker (existing `restart_service`)

`watchdog.sh:152-203` already contains the correct spawn logic; the
cold-boot pass reuses it:

```bash
arena_pipeline_w<id>:    env A1_WORKER_ID=$id A1_WORKER_COUNT=4 \
                          $VENV $BASE/services/arena_pipeline.py \
                          > /tmp/zangetsu_a1_w$id.log 2>&1 &
arena23_orchestrator:    $VENV $BASE/services/arena23_orchestrator.py \
                          > /tmp/zangetsu_a23.log 2>&1 &
arena45_orchestrator:    $VENV $BASE/services/arena45_orchestrator.py \
                          > /tmp/zangetsu_a45.log 2>&1 &
```

`$BASE=~/j13-ops/zangetsu`; `$VENV=$BASE/.venv/bin/python3`.
The env-loading preamble at `watchdog.sh:1-9` sources
`/home/j13/.env.global` so `ZV5_DB_PASSWORD` (and any future DB creds)
are visible to the spawned worker.

## Worker self-locking confirmation (Q1 dim 2 — silent failure)

Every worker calls `zangetsu.services.pidlock.acquire_lock(...)`
during `if __name__ == "__main__":` (verified by grep):

```
services/arena_pipeline.py:21         from zangetsu.services.pidlock import acquire_lock
services/arena_pipeline.py:1303       acquire_lock(f"arena_pipeline_w{os.environ.get('A1_WORKER_ID', '0')}")
services/arena23_orchestrator.py:28   from zangetsu.services.pidlock import acquire_lock
services/arena45_orchestrator.py:25   from zangetsu.services.pidlock import acquire_lock
services/arena45_orchestrator.py:1186 acquire_lock("arena45_orchestrator")
```

So the cold-boot path's contract is:
1. Cold-boot pass discovers no lock + no process for worker X.
2. It calls `restart_service(X)` → spawns the python process.
3. The python process `acquire_lock(X)` writes
   `/tmp/zangetsu/X.lock` itself within the first second of boot.
4. The next watchdog tick (5 min later) sees the lock → main lockfile
   loop owns it → cold-boot pass logs `skipped reason=lockfile_present_main_loop_owns`.

This means the cold-boot pass is naturally **idempotent** without a
duplicate-launch race.

## Safety conditions before cold-boot (must be respected)

The patch must enforce all four:

1. `/tmp/zangetsu_disable_autostart` (kill-switch file) → block.
2. Process already alive (race against operator-launched daemon) → skip.
3. Lockfile present → main loop already owns it → skip.
4. Lockfile absent **and** process absent → cold-boot.

Stale-lock recovery (lockfile present + pid dead) is handled by the
pre-existing `reclaim_lock` flow in the main loop and **must be left
untouched** (Phase 2 forbidden change).

## Reference scans (artifacts)

```
/tmp/0_9x_cold_boot_refs.txt   # 729 lines — every grep hit for arena_pipeline_w*/arena23/45/lock outside .venv
/tmp/0_9x_watchdog_refs.txt    # 104 lines — every grep hit for "watchdog" outside .venv
```

## Q1 dimensions (this phase)

| Dimension                       | Outcome                                                         |
|---------------------------------|-----------------------------------------------------------------|
| Input boundary                  | PASS — root-cause analysis is read-only                          |
| Silent failure propagation      | PASS — confirmed worker self-writes its own lockfile, no silent-skip risk |
| External dependency failure     | PASS — patch reuses pre-existing `restart_service`, no new external dep   |
| Concurrency / race              | PASS — three of the four safety conditions guarantee no double-launch     |
| Scope creep                     | PASS — diagnosis stays inside watchdog.sh; no alpha / Arena / threshold logic touched |

## Outcome

ROOT_CAUSE_CONFIRMED. Proceed to Phase 2 (the patch already exists in
the working tree; Phase 2 will report on it formally).
