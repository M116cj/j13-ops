# 04 — Live Verification (Subprogram B3)

## Pre-patch state

```
$ ls -la /tmp/calcifer_deploy_block.json
ls: cannot access '/tmp/calcifer_deploy_block.json': No such file or directory

$ docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu -c 'SELECT deployable_count, last_live_at_age_h FROM zangetsu_status'
 deployable_count | last_live_at_age_h
------------------+--------------------
                0 |
```

The system has been in this state since project init (~30+ days). Per the pre-fix predicate, no deploy-block file was ever written, and any `feat(zangetsu/vN)` commit would have proceeded without §17.3 challenge. **False-green confirmed.**

## Patched script execution

```
$ bash /home/j13/j13-ops/calcifer/calcifer_v071_watch.sh
(no stdout output — script writes files only)
```

## Post-patch state

```
$ ls -la /tmp/calcifer_deploy_block.json
-rw-rw-r-- 1 j13 j13 ... Apr 27 18:53 /tmp/calcifer_deploy_block.json

$ cat /tmp/calcifer_deploy_block.json
{
  "status": "UNKNOWN_BLOCKED",
  "iso": "2026-04-27T18:53:27Z",
  "reason": "cold_start_no_live_champion_ever",
  "deployable_count": 0,
  "last_live_at_age_h": null,
  "predicate": "0-9Y-B3-NULL-SAFE",
  "writer": "calcifer_v071_watch.sh"
}
```

## Process-side decoupling check

```
$ ls /tmp/calcifer_process_*.json
/tmp/calcifer_process_green.json

$ cat /tmp/calcifer_process_green.json
{
  "ts": "2026-04-27T18:53:27Z",
  "color": "GREEN",
  "notes": "",
  "worker_uptime_sec": 6669,
  "j01": {"outcome": {"total_fresh": 89, ...}, "process": {...}},
  "j02": {"outcome": {"total_fresh": 0, ...},  "process": {...}}
}
```

The process-side color file remained GREEN (89 alphas in j01 fresh pool, no process exceptions). The two sides are now properly decoupled per v0.7.1 dual-evidence governance:

- **Process side:** healthy (no compile/evaluate/indicator errors, no zero-variance, etc.)
- **Outcome side:** UNKNOWN_BLOCKED (deployable_count = 0 for the project's lifetime)

## Bypass-test verification

The deploy-block file is now PRESENT at `/tmp/calcifer_deploy_block.json`. Per §17.3 enforcement:

> Claude MUST read before any `feat(<proj>/vN)` commit. Present → refuse.

The CLAUDE.md §-1 verification protocol explicitly checks for this file. Any future `feat(zangetsu/vN)` proposal will see this file and be refused, matching the §17.3 spec intent.

## State transition expectations

| Future state change | Expected file behavior |
|---|---|
| Pipeline produces 1+ deployable alpha | next cron cycle removes `/tmp/calcifer_deploy_block.json` (status returns to ungated) |
| `deployable_count` returns to 0 within 6h | next cron cycle removes the file (recovery window; no block) |
| `deployable_count` stays 0 for > 6h | next cron cycle writes `status=RED` (regression detected) |
| Worker not running | file untouched (consistent with process-side NOT_RUNNING semantics; do not judge) |

## Cron-installed verification (post-merge)

Once this PR merges and the next 15-min cron cycle fires (per existing cron entry for `calcifer_v071_watch.sh`), the deploy_block file should remain in UNKNOWN_BLOCKED state until the system actually produces a deployable. The continuous file lifetime is governed entirely by the cron cadence + state transitions above.
