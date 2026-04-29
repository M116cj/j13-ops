# 00 — STATE LOCK

**TEAM ORDER**: 0-9Y-HE4-HORIZON-SHADOW-RUN
**Date**: 2026-04-29
**Phase**: 0 / 8

## Git
- HEAD: `b83c710c8fa5e2e8087b817d723baa57203df402` (post-HE3, signed ED25519)
- origin/main: `b83c710c8fa5e2e8087b817d723baa57203df402` ✅ in-sync
- Branch: `main`
- Working tree (zangetsu): only `zangetsu/logs/engine.jsonl.1` (runtime log) — no source dirty

## Worker baseline state (current)
Sample worker (PID 2963114):
```
$ cat /proc/2963114/environ | tr '\0' '\n' | grep -E 'ARENA|HORIZON' → no HE/TF env (baseline) ✓
```

## Batch state (pre-HE4)
30 most-recent `arena_batch_metrics` events:
- All 30 emit `horizon: 60` (HE2 telemetry — was loaded into prior worker restart)
- **0 / 30 have `horizon_metrics` field** — workers running pre-HE3 binary; HE3 code merged on commit `b83c710c` but **workers have not been restarted** to pick it up

This is expected: HE3 PR merged docs+code; live workers continue on the snapshot loaded at their last restart. Phase 2 of HE4 will restart workers, which simultaneously:
1. Loads HE3 code → `horizon_metrics` will appear in subsequent batches
2. Activates multi-horizon mode via new env vars
→ **HE4's restart accomplishes both**

| Metric | Pre-HE4 |
|---|---|
| Total arena batches in engine.jsonl | 548 |
| Latest batch timestamp | 2026-04-29T08:11:32Z |
| `horizon_metrics` field present | 0 / 30 (workers pre-HE3) |
| `horizon=60` field present | 30 / 30 (HE2 already loaded) |

## Telemetry sanity
- UNKNOWN_REJECT total: 0 ✅
- COUNTER_INCONSISTENCY total: 0 ✅
- Conservation residual: 0 ✅

## Order status
| Order | Status |
|---|---|
| OP1 | COMPLETE (`82056123`) |
| TF2 | COMPLETE (`3decabd4`) |
| TF3 | COMPLETE (`0cef908d`) |
| TF4 | COMPLETE (`986932df`) |
| HE1 | COMPLETE (`bbd6fb42`) |
| HE2 | COMPLETE (`48be8071`) |
| HE3 | COMPLETE (`b83c710c`) |

## STOP-conditions check (Phase 0 spec)
| STOP cause | Status |
|---|---|
| Telemetry broken | ❌ no |
| Runtime unstable | ❌ no — workers producing batches |
| HE3 fields missing | **NOTE**: HE3 fields ABSENT from current batches — but this is **expected** since workers haven't restarted to load HE3 binary. Phase 2 restart will load HE3 + activate horizon. Treated as expected, not STOP |

✅ **STATE_LOCK_PASS** with annotation — proceed to Phase 1.

## Pre-restart batch rate baseline (for Phase 3 sample-size estimation)
Baseline observed rate ≈ **7-10 batches/min** (per TF3/HE3 prior windows).

For HE4 target ≥100 batches/horizon × 3 horizons = **≥300 batches**:
- Conservative estimate (7 batches/min): 300/7 ≈ **43 minutes**
- Optimistic (10 batches/min): 300/10 ≈ **30 minutes**
- Preferred ≥150/horizon = **450 batches** ≈ 50-65 min

We will collect for ~45 min minimum, target ~60 min for preferred sample size.
