# 05 — LIVE OR FIXTURE VERIFICATION

**TEAM ORDER**: 0-9Y-HE2-A1-HORIZON-AWARE-GENERATION
**Date**: 2026-04-29
**Phase**: 5 / 8

## Mode chosen
**FIXTURE_VERIFICATION_PASS + LIVE_MULTI_HORIZON_DEFERRED_TO_HE4**

Per master-order Phase 5 preferred path:
> Preferred: Do not change running production env in HE2.
> Leave live workers baseline unless HE4 shadow activation authorizes horizon runtime.

HE2 implements the plumbing; **HE4 will be the order that activates multi-horizon shadow on production traffic**. HE2's verification is via comprehensive fixture testing.

## Fixture script
`/tmp/he2_fixture_verify.py` — 8 fixtures covering all master-order Phase 5 requirements.

```
$ /home/j13/j13-ops/zangetsu/.venv/bin/python3 /tmp/he2_fixture_verify.py
```

## Results

### Fixture 1 — env unset → baseline single horizon=60
```
active = (60,)
mode   = FIXED
cycle_unset = [60, 60, 60, 60, 60, 60, 60, 60]
```
✅ Default deployment is bit-equivalent to pre-HE1/HE2 baseline.

### Fixture 2 — redesign env (180/240/360 SIMPLE_CYCLE)
```
active = (180, 240, 360)
mode   = SIMPLE_CYCLE
cycle_redesign = [180, 240, 360, 180, 240, 360, 180, 240, 360, 180, 240, 360]
```
✅ Round-robin cycling through configured horizons. Master-order Phase 5 spec ✓

### Fixture 3 — AlphaEngine receives horizon
```
h=60:  engine.horizon=60   fr.shape=(500,)  fr[200]=0.085837
h=180: engine.horizon=180  fr.shape=(500,)  fr[200]=0.257511
h=240: engine.horizon=240  fr.shape=(500,)  fr[200]=0.343348
h=360: engine.horizon=360  fr.shape=(500,)  fr[200]=0.000000
```
✅ Horizon stored in `engine.horizon` and passed through `_forward_returns(close, horizon=...)`. Note `fr[200]=0.0` for `h=360` because index 200 is within 200 of array end (500), so no forward-return computable for that position with h=360 — correct edge-case behavior.

### Fixture 4 — AlphaResult.horizon
```
AlphaResult(h=60).horizon = 60;   to_dict()['horizon'] = 60
AlphaResult(h=180).horizon = 180; to_dict()['horizon'] = 180
AlphaResult(h=240).horizon = 240; to_dict()['horizon'] = 240
AlphaResult(h=360).horizon = 360; to_dict()['horizon'] = 360
```
✅ Candidate metadata carries horizon, exposed via `.horizon` property and `to_dict()` serialization.

### Fixture 5 — alpha_hash differs by horizon
```
h=60:  5609df57722950bf  (legacy md5(formula)[:16])
h=180: db5faccbe97e58b2  (md5(formula+|h180)[:16])
h=240: 93f6531f9a7493a5  (md5(formula+|h240)[:16])
h=360: db7ebdf30f55161d  (md5(formula+|h360)[:16])
```
✅ All 4 horizons produce 4 distinct identities. Same formula at h=60 preserves the legacy pre-HE1 hash format (verified via direct md5 comparison).

### Fixture 6 — Lifecycle trace extras carry horizon
```
trace event horizon field = 180
```
✅ `LifecycleTraceEvent.extras={"horizon": 180}` flattens into `to_dict()` output, so downstream lifecycle reconstruction can attribute candidates to their horizon.

### Fixture 7 — ChampionPassport.stamp_arena1 horizon
```
passport (h=180).arena1.horizon = 180
passport (h=240).arena1.horizon = 240
passport (h=360).arena1.horizon = 360
passport (no horizon kwarg): 'horizon' in arena1 = False
```
✅ Schema supports horizon attachment when provided (kwarg). Default omission preserves pre-HE2 schema bit-for-bit. Live wiring of passport stamping is out-of-scope; this is schema-support-only per master-order Phase 3 #5.

### Fixture 8 — Batch telemetry construction
```
telemetry (multi-horizon, h=180):
    horizon                    = 180
    selected_horizon           = 180
    active_horizons            = [180, 240, 360]
    horizon_mode               = SIMPLE_CYCLE
    generation_profile_horizon = gp_test:h180
```
✅ All HE2 telemetry fields construct correctly when multi-horizon mode is active. (Replicates the per-batch logic in `arena_pipeline.py` directly.)

### Post-test cleanup
```
active = (60,)
mode   = FIXED
```
✅ Env restored to baseline; no leakage from fixture run.

## Live runtime status (verified post-fixture-run)
Worker env on Alaya: still no `ARENA_HORIZON_*` / `ACTIVE_A1_HORIZONS` / `ALPHA_FORWARD_HORIZON` set → confirmed baseline mode. Workers continue running on commit `bbd6fb42`-equivalent baseline path.

## Live multi-horizon status
**DEFERRED TO HE4** (per master-order preferred path).

HE2 ships the plumbing dormant-by-default. The first authorized multi-horizon SHADOW activation on live production traffic will be a separate order (HE4). Production runtime in HE2's PR will continue running on baseline single-horizon=60 until that explicit operator decision.

## STOP-conditions check (Phase 5)
| STOP cause | Status |
|---|---|
| Verification blocked (env activation unsafe) | ❌ no — fixture path used; live runtime untouched |
| Hash collision in fixture | ❌ no — all 4 horizons produce 4 distinct hashes (Fixture 5) |
| Lifecycle trace fails to carry horizon | ❌ no — Fixture 6 verifies extras flow |
| Telemetry construction fails | ❌ no — Fixture 8 replicates arena_pipeline logic correctly |

✅ **No STOP triggered.**

## Verdict
**FIXTURE_VERIFICATION_PASS + LIVE_MULTI_HORIZON_DEFERRED_TO_HE4** — all 8 fixtures green; live workers untouched; HE4 will activate.

## Next
Phase 6 — controlled diff & forbidden audit.
