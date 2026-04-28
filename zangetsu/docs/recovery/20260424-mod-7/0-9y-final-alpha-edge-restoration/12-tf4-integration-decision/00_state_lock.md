# 00 — STATE LOCK

**TEAM ORDER**: 0-9Y-TF4-INTEGRATION-DECISION
**Date**: 2026-04-28
**Phase**: 0 / 8

## Git
- Branch: `main`
- HEAD: `0cef908d36bc892240be6ccaa50469550fa0a1b6` (post-TF3, signed ED25519)
- origin/main: `0cef908d36bc892240be6ccaa50469550fa0a1b6` ✅ in-sync
- Working tree (zangetsu): only `zangetsu/logs/engine.jsonl.1` (runtime log) — no source dirty.

## TF3 modules present
```
zangetsu/services/signal_aggregation.py   (TF2 helper)
zangetsu/services/tf3_shadow.py           (TF3 shadow harness)
```
Verified via `ls`. TF2 + TF3 module test suite (`tests/test_signal_aggregation.py` + `tests/test_tf3_shadow.py`) passing on commit `0cef908d`.

## Shadow path off by default
Live worker env (sample PID 2220816):
```
$ cat /proc/<pid>/environ | grep ARENA → no_ARENA_*_env (baseline) ✓
```
`ARENA_TF3_SHADOW` is **not set** — TF3 shadow path is dormant. Production runtime is on the bit-equivalent baseline path.

## Recent baseline metrics sanity
- 50 most-recent `arena_batch_metrics` events: `with_shadow_profiles = 0 / 50` ✅ (expected — baseline)
- Latest batch timestamp: 2026-04-28T15:22:43Z (live A1 still producing)
- Conservation residual / UNKNOWN_REJECT / COUNTER_INCONSISTENCY: 0 in all 50 (carryover from TF3 Phase 4 verification)

## OP1 / TF2 / TF3 status
| Order | Status |
|---|---|
| OP1 | COMPLETE (`82056123`) |
| TF2 | COMPLETE (`3decabd4`) |
| TF3 | COMPLETE_TF3_SHADOW_PROFILE_CONFIRMED (`0cef908d`) |

## Calcifer deploy block (informational)
`/tmp/calcifer_deploy_block.json` continues to report `cold_start_no_live_champion_ever` (predicate `0-9Y-B3-NULL-SAFE`). Cold-start state — TF4 is **definition + minimal wiring** (NOT a deployable advancement) → not gated by §17.3.

## STOP-conditions check (Phase 0 spec)
| STOP cause | Status |
|---|---|
| Baseline behavior differs from pre-TF4 | ❌ no |
| Telemetry regression | ❌ no |
| TF3 code missing | ❌ no — both modules + tests present |
| Shadow accidentally enabled in production | ❌ no — workers have no ARENA_* env |

✅ **STATE_LOCK_PASS** — proceed to Phase 1.
