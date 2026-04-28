# 00 — STATE LOCK

**TEAM ORDER**: 0-9Y-TF2-SIGNAL-AGGREGATION-PROTOTYPE
**Date**: 2026-04-28
**Phase**: 0 / 8

## Git
- Branch: `main`
- HEAD: `82056123a3e28eb3361b1dacf13acace843ab44b`
- origin/main: `82056123a3e28eb3361b1dacf13acace843ab44b` ✅ in-sync
- Last signed commit: `feat(zangetsu/op1): register 9 GP primitives × (20,60,240) + fallback parity`
- Signature: ED25519 (M116cj) — Good

## Repo cleanliness
Working tree dirty **only with runtime artifacts** (no unexplained source changes):
- `calcifer/maintenance.log` (runtime)
- `calcifer/maintenance_last.json` (runtime)
- `calcifer/report_state.json` (runtime)
- `zangetsu/logs/engine.jsonl.1` (runtime log)

✅ No source-code changes outside main.

## Mac / Alaya sync
- Mac has no local clone of `j13-ops` (verified 2026-04-28). All git operations performed on Alaya.
- "Sync" semantic = Alaya HEAD == origin/main HEAD (verified above).

## Runtime processes (`ps aux | grep ...`)
- `arena_pipeline.py` — 4 instances (PIDs 1451007, 1914251, 1939010, 1944685) ✅
- `arena23_orchestrator.py` (PID 1365067) ✅
- `arena45_orchestrator.py` (PID 1365092) ✅
- `calcifer/supervisor.py` (PID 1365473) ✅
- `calcifer-miniapp/server.py` (PID 1023) ✅

`/tmp/zangetsu_watchdog.log`: shows `lockfile_present_main_loop_owns` repeating at 5-min cadence — **expected**, indicates main loop owns lock and watchdog correctly defers.

`zangetsu/logs/engine.jsonl` tail timestamp: **2026-04-28T08:59:20Z** — A1 actively producing candidate lifecycle events.

## DB (Postgres in `deploy-postgres-1`)
- `select now()` → `2026-04-28 09:00:01+00` ✅
- `current_database()` → `zangetsu` / `current_user` → `zangetsu`
- `champion_pipeline`: **89**
- `champion_pipeline_staging`: **184**
- `champion_pipeline_fresh`: **89**
- `champion_pipeline_rejected`: **0**
- `engine_telemetry`: **0** (table empty — telemetry resides in `engine.jsonl`)

## Telemetry sanity (300 most-recent arena_batch_metrics)
- `UNKNOWN_REJECT` total: **0** ✅
- `COUNTER_INCONSISTENCY` total: **0** ✅
- `aggregate_metrics_availability`: present in 300/300 batches
- `event_type=arena_batch_metrics`: 300/300
- Schema version: present (uniform)
- Conservation identity (`entered = passed + rejected + skipped + in_flight + error`): holds trivially (skipped_count=0 in baseline)
- Top reject reason: **COST_NEGATIVE** (2998 / 3000 ≈ 99.93%) — confirms master-order finding `DECOMPOSED_GROSS_EDGE_LOST_TO_COST`

## OP1 primitive registration
- `engine/components/alpha_engine.py:748-750` — `log_x` / `exp_x` registered ✅
- 23 GP operators registered (18 unary + 3 binary + 2 pointwise) verified in PR #65
- Fallback `_FallbackPrims.{ts_sum,ts_mean,ts_std,ts_argmax,ts_argmin,covariance,rolling_scale,log_x,exp_x}` present (line 224 docstring + impls 273–445)

## Blocker summary
| Block | State | Source |
|---|---|---|
| `alpha_zoo` | BLOCKED | master order |
| `CANARY` | BLOCKED | master order |
| `production` | NOT STARTED | master order |
| `runtime calibration` | BLOCKED | master order |
| `A2_MIN_TRADES=25` | LOCKED | master order |
| Cost model | LOCKED | master order |
| Validator | LOCKED | master order |

## Calcifer deploy block
`/tmp/calcifer_deploy_block.json` exists:
```
status        = "UNKNOWN_BLOCKED"
reason        = "cold_start_no_live_champion_ever"
deployable_count = 0
last_live_at_age_h = null
predicate     = "0-9Y-B3-NULL-SAFE"
```
**Interpretation**: cold-start state (no live champion has ever existed), not a regression. Master order's TF2 explicitly says "Do not require deployables in this prototype order." TF2 commit will be `feat(zangetsu/tf2): ...` (not a `feat(zangetsu/vN)` version bump), so §17.3 deploy-block predicate does not gate this PR.

## Verdict
**STATE_LOCK_PASS** — proceed to Phase 1.

No STOP conditions triggered:
- Repo not dirty with source changes ✅
- HEAD == origin/main ✅
- A1 runtime alive ✅
- DB available ✅
- No telemetry regression (UNKNOWN_REJECT=0, COUNTER_INCONSISTENCY=0) ✅
- OP1 primitives present ✅
