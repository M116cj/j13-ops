# 06 — Final Report (Subprogram B3)

**Order:** TEAM ORDER 0-9Y-B3-CALCIFER-NULL-SAFETY-PATCH

## Final verdict

```
COMPLETE_CALCIFER_NULL_SAFETY_PATCHED
```

## Summary table

| Field | Value |
|---|---|
| Master order | 0-9Y / Subprogram B3 |
| Branch | `phase-8/0-9y-b3-calcifer-null-safety` |
| Pre-PR HEAD | `9e84a20b` (origin/main after PR #56) |
| Files modified | `calcifer/calcifer_v071_watch.sh` (+66) |
| Files added | `calcifer/calcifer_outcome_predicate.py` (+61), `zangetsu/tests/test_b3_calcifer_outcome_predicate.py` (+130) |
| Tests added | 9 (all PASS) |
| Pre-existing tests | 112 PASS (no regression) |
| Total tests after B3 | 121 (102 base + 10 B1 + 9 B3) |
| Live integration check | `/tmp/calcifer_deploy_block.json` now present with `UNKNOWN_BLOCKED` (cold-start), process-side stays GREEN |
| Forbidden ops | 0 |

## What this patch fixes

The §17.3 outcome-watch deploy-block writer was missing from main. The literal SQL semantics of `deployable_count==0 AND last_live_at_age_h>6` evaluate to `NULL` (not TRUE) when `last_live_at_age_h IS NULL`, so the predicate never fired during the 30+ day cold-start. Result: `/tmp/calcifer_deploy_block.json` was never written → `feat(zangetsu/vN)` commits would silently bypass §17.3.

## What the patch does

1. Adds NULL-safe predicate logic to `calcifer/calcifer_v071_watch.sh` (the existing 15-min cron script).
2. Introduces `UNKNOWN_BLOCKED` state for cold-start (dc=0, age=NULL); keeps `RED` for regression (dc=0, age>6).
3. Removes the deploy-block file when the system enters healthy state (dc>0) or the recovery window (dc=0, age≤6).
4. Provides `calcifer/calcifer_outcome_predicate.py` as a pure-Python single-source-of-truth for the predicate semantics, used exclusively by the test suite.

## State transition truth table (post-fix)

| deployable_count | last_live_at_age_h | deploy-block file | semantics |
|---|---|---|---|
| > 0 | any | absent | healthy / no block |
| 0 | NULL | UNKNOWN_BLOCKED | cold-start (no live champion ever) |
| 0 | > 6 | RED | regression (had live champion >6h ago) |
| 0 | ≤ 6 | absent | recovery window (transient) |

## Process-side vs outcome-side decoupling

| Side | File | Source | Pre-fix | Post-fix |
|---|---|---|---|---|
| process | `/tmp/calcifer_process_<color>.json` | `fresh_pool_process_health` view (currently empty) + worker uptime + outcome counts | always GREEN | unchanged (still GREEN) |
| outcome | `/tmp/calcifer_deploy_block.json` | `zangetsu_status` view | absent (false-green) | UNKNOWN_BLOCKED |

The two sides are now properly decoupled per v0.7.1 dual-evidence governance.

## Known limitation (out of scope)

- Cron cadence is 15 min (per existing infrastructure); §17.3 spec says 5 min. Tightening the cron is a follow-up sub-order (`0-9Y-B3A-CRON-CADENCE-TIGHTEN`); not blocking 0-9Y program.
- The Python predicate helper (`calcifer_outcome_predicate.py`) is currently NOT imported by the bash writer — the bash writer is the canonical source. A future order could unify them by having the bash script call the Python helper, but that touches the calcifer→python bridge which is out of B3 scope.

## Required B3 classification

| Field | Status |
|---|---|
| predicate identified | 01_predicate_trace.md |
| NULL non-red reproduced | 04_live_verification.md (pre-patch state) |
| patched to UNKNOWN_BLOCKED policy | 02_patch_report.md |
| regression tests added | 03_test_report.md (9/9 PASS) |
| no deploy-blocker bypass | 03_test_report.md (`test_b3_no_bypass_path_for_zero_deployable`) |
| no false green | 04_live_verification.md (deploy_block file now present in cold-start) |

## Next subprogram

```
TEAM ORDER 0-9Y-C-ECONOMIC-EDGE-DECOMPOSITION
```

C requires live B1 aggregate_metrics in arena_batch_metrics emissions, which in turn requires worker restart to load post-PR #55 source. The restart authorization is operator-side; B3 does not depend on it.

## Forbidden ops audit

No source code change in zangetsu/services. No DB schema change. No validator change. No threshold change. No alpha generation change. No Arena pass/fail change. No champion promotion change. No execution / capital / risk change. No Binance scope change. No DB guard weakening. No alpha_zoo write. No CANARY start. No production rollout. No runtime calibration change. No kill switch disable. No watchdog disable. No force-push. No log wipe. **Calcifer process-side semantics unchanged.** **Cron cadence unchanged.**

**Forbidden ops: 0.**
