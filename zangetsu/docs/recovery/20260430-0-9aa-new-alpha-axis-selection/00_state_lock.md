# 00 — State Lock

**TEAM ORDER**: 0-9AA-NEW-ALPHA-AXIS-SELECTION
**Date**: 2026-04-30
**Mode**: READ-ONLY / DECISION-ONLY / AXIS-SELECTION-ONLY

## Frozen Baseline

| Item | Value |
|---|---|
| HEAD | `6207bb1b` |
| Branch | `main` |
| Last completed order | 0-9ZA |
| 0-9Y verdict | `COMPLETE_HE5_EDGE_EXHAUSTED` |
| 0-9Z verdict | `PATH_A_CONDITIONAL` |
| 0-9ZA verdict | `PATH_A_DATA_BLOCKED` |
| 0-9ZA secondary | `EXECUTION_ARCH_REQUIRED_BEFORE_PATH_A_CAN_CONTINUE` |
| Runtime | baseline |
| arena_pipeline workers | 4 (verified `ps -ef`) |
| `champion_pipeline_staging` | 184 ARENA1_COMPLETE |
| `champion_pipeline_fresh` | 89 |
| `zangetsu_status.deployable_count` | 0 |
| `zangetsu_status.last_live_at_age_h` | NULL (never lived) |
| `A2_MIN_TRADES` | 25 (verified at `zangetsu/services/arena_gates.py:48`, `zangetsu/config/settings.py:29`) |
| CANARY | not started |
| Production rollout | not started |
| Live trading | not started |

## Working-Tree Sanity

Working tree contains modifications to runtime byproducts only:
```
 M calcifer/maintenance.log
 M calcifer/maintenance_last.json
 M calcifer/report_state.json
 M zangetsu/logs/engine.jsonl.1
```
These are emissions from the long-running calcifer + arena_pipeline workers and are NOT included in 0-9AA.

## STOP Verification

- STOP-1 (alpha generation impl): not attempted
- STOP-2 (Arena threshold): unchanged
- STOP-3 (A2_MIN_TRADES): 25, unchanged
- STOP-4 (runtime worker): unchanged
- STOP-5 (DB mutation): none — read-only queries only
- STOP-6 (CANARY/rollout): not started
- STOP-7 (live trading): none

## Deliverable

`00_state_lock.md` — frozen.
