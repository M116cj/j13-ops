# 01 — Predicate Trace (Subprogram B3)

## Spec reference

CLAUDE.md §17.3:

> Calcifer polls `<proj>_status` every 5 min. `deployable_count==0 AND last_live_at_age_h>6` → RED, write `/tmp/calcifer_deploy_block.json`. Claude MUST read before any `feat(<proj>/vN)` commit. Present → refuse. j13 override via Telegram `/unblock`.

## Pre-fix code state

The §17.3 outcome-watch `/tmp/calcifer_deploy_block.json` writer is **not implemented in main**.

| Component | Status |
|---|---|
| `calcifer/zangetsu_outcome.py` (referenced in docs as commit `ae738e37`) | **does not exist** in main; `git log --all -- calcifer/zangetsu_outcome.py` returns empty; only a stale `__pycache__/zangetsu_outcome.cpython-312.pyc` remains from a prior transient build |
| `calcifer/calcifer_v071_watch.sh` | exists, runs every 15 min via cron, **only writes the process-color file** (`/tmp/calcifer_process_<color>.json`). Does NOT write `/tmp/calcifer_deploy_block.json`. |
| `calcifer/supervisor.py` | runs as a long-lived service, but no outcome-watch predicate / deploy_block writer is found |
| `calcifer/calcifer_maintenance.py` | nightly maintenance; queries `zangetsu_status` for logging only; no deploy_block writer |
| `zangetsu/scripts/r2_n4_watchdog.py` | a one-shot 2h watchdog that DOES use `age is None` (NULL-safe) but only fires once at the 2h deadline; not a continuous watch |

## Static behavior of pre-fix system

```
              dc = deployable_count, age = last_live_at_age_h
+---+----------------------------+----------------------------------+
| dc| age                       | pre-fix outcome of /tmp/calcifer_deploy_block.json |
+---+----------------------------+----------------------------------+
|>0 | any                       | absent (correct: no block needed)               |
| 0 | NULL (cold-start)         | **absent (BUG: should block, but doesn't)**     |
| 0 | > 6 (regression)          | absent (BUG: writer never runs)                 |
| 0 | <= 6 (recovery window)    | absent (correct: transient)                     |
+---+----------------------------+----------------------------------+
```

The "absent" cells in rows 2 and 3 are the **false-green** bug. `feat(zangetsu/vN)` commits would proceed without §17.3 challenge despite the system being in a deploy-block state.

## SQL semantics analysis

The §17.3 spec literal `deployable_count == 0 AND last_live_at_age_h > 6` evaluated in SQL:

```sql
SELECT (deployable_count = 0 AND last_live_at_age_h > 6)
FROM zangetsu_status;
-- Row: (0, NULL)
-- Result: (true AND NULL) = NULL
```

`NULL` is **not TRUE**. A bash `if` test on this expression would NOT enter the RED branch. **This is the root cause** — the spec's literal SQL form silently fails the cold-start case.

## Post-fix predicate (this patch)

NULL-safe semantics adding a third state `UNKNOWN_BLOCKED` for cold-start:

```
+---+----------------------------+--------------------------------+
| dc| age                       | post-fix /tmp/calcifer_deploy_block.json |
+---+----------------------------+--------------------------------+
|>0 | any                       | absent (no block)               |
| 0 | NULL (cold-start)         | **UNKNOWN_BLOCKED**             |
| 0 | > 6 (regression)          | **RED**                         |
| 0 | <= 6 (recovery window)    | absent (transient)              |
+---+----------------------------+--------------------------------+
```

Both `UNKNOWN_BLOCKED` and `RED` block `feat(zangetsu/vN)` commits per §17.3 enforcement. The distinction is informational (post-mortem can tell cold-start from regression).

## Why `UNKNOWN_BLOCKED` instead of just `RED` for cold-start

- `RED` means a regression (had a live champion, now don't, > 6h ago)
- `UNKNOWN_BLOCKED` means cold-start (never had a live champion)
- Both block; distinction helps debugging (different root causes)
- Master order's B3 verdict allows either RED or UNKNOWN_BLOCKED policy

## Cron / runtime cadence

Pre-fix: `calcifer_v071_watch.sh` runs every 15 min via cron (per its header comment). Post-fix: same script, same cadence, additionally writes the deploy_block file when applicable.

§17.3 spec states 5-min cadence; current cron is 15 min. Tightening the cron is **out of scope** for B3 (that would be a cron-infrastructure change). The 15-min cadence is acceptable for governance gating because:
- The deploy-block file lifetime (RED / UNKNOWN_BLOCKED state) lasts much longer than 15 min when active
- Recovery (transition out of block) is observed within one cron cycle
- §17.3's worst-case is missing a 15-min window of newly-RED state, which a follow-up cron tightening can fix
