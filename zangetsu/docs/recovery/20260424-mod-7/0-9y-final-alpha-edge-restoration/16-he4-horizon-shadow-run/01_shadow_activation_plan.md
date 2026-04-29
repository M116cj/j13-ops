# 01 — SHADOW ACTIVATION PLAN

**TEAM ORDER**: 0-9Y-HE4-HORIZON-SHADOW-RUN
**Date**: 2026-04-29
**Phase**: 1 / 8

## Runtime config (per master-order Phase 1 spec)

```bash
export ARENA_HORIZON_MODE=SIMPLE_CYCLE
export ACTIVE_A1_HORIZONS=180,240,360
```

**Explicitly excluded**: `60` is NOT in `ACTIVE_A1_HORIZONS`. Per master-order:
> DO NOT include 60 in this run (baseline already known)

This means the SIMPLE_CYCLE rotation is purely over `(180, 240, 360)`:
- Round 1 → h=180
- Round 2 → h=240
- Round 3 → h=360
- Round 4 → h=180
- ...

**Determinism**: SIMPLE_CYCLE uses `round_index % len(active)`, so allocation is exactly equal across the 3 horizons (modulo final-batch boundary).

## TF stack state during HE4
HE4 runs with:
- HE1/HE2/HE3 loaded (after restart picks up HE3 code)
- TF3 SHADOW: **OFF** (no `ARENA_TF3_SHADOW=1`)
- TF4 PRE-FILTER: **OFF** (no `ARENA_AGGREGATION_MODE`)
- only horizon path differs from baseline

This isolates the horizon variable: any difference in net/cost/win_rate is attributable to horizon, not aggregation.

## Duration target

| Tier | Sample / horizon | Total batches | Estimated wall-time @ 7-10 batch/min |
|---|---|---|---|
| Minimum | ≥100 | ≥300 | ~30-45 min |
| Preferred | ≥150 | ≥450 | ~45-65 min |
| Stretch | ≥200 | ≥600 | ~60-90 min |

We aim for **preferred (≥150 / horizon)** ≈ 50 min collection window. If batch rate matches TF3 baseline (~10/min), we may reach stretch target.

## Monitoring
- `tail -F /home/j13/j13-ops/zangetsu/logs/engine.jsonl` to spot-check live emission
- After 5 minutes: verify `horizon` field varies among 180/240/360 (not stuck on one)
- After 30 minutes: check per-horizon batch counts approximately equal

## Execution sequence
1. Stop workers cleanly: `./zangetsu_ctl.sh stop`
2. Export env vars in shell
3. Start workers: `./zangetsu_ctl.sh start`
4. Verify env propagation: `cat /proc/<pid>/environ | grep -E 'ARENA_HORIZON|ACTIVE_A1_HORIZONS'`
5. Tail engine.jsonl, confirm horizon=180/240/360 cycling
6. Wait collection window (~50 min)
7. Stop collection: snapshot frozen `engine.jsonl` to `/tmp/0_9y_he4_shadow_collected.jsonl`
8. Phase 8 cleanup: `./zangetsu_ctl.sh stop` → unset env vars → `./zangetsu_ctl.sh start` (baseline)

## Rollback plan (always-applicable)
If Phase 2/3 fails (workers crash, no horizon variation, telemetry corruption):
1. `./zangetsu_ctl.sh stop`
2. `unset ARENA_HORIZON_MODE ACTIVE_A1_HORIZONS`
3. `./zangetsu_ctl.sh start`
4. Verify worker env: should show no `ARENA_HORIZON_*` / `ACTIVE_A1_HORIZONS`
5. Document failure in `02_runtime_commands.md` and `07_final_report.md` with verdict `BLOCKED_RUNTIME_UNSTABLE` or `INCONCLUSIVE`

## Forbidden during HE4
- No commit to source code (HE4 commit is **docs-only**)
- No CANARY / production / alpha_zoo / capital change
- No env that activates TF3 / TF4 (isolate horizon variable)
- No DB schema change

## Post-HE4 baseline restoration
Workers must return to baseline (no HE/TF env) before Phase 8 ends. Verified via `/proc/<pid>/environ` grep returning empty for `ARENA_HORIZON_*`/`ACTIVE_A1_HORIZONS`.

## Verdict
**ACTIVATION_PLAN_READY** — proceed to Phase 2 runtime execution.
