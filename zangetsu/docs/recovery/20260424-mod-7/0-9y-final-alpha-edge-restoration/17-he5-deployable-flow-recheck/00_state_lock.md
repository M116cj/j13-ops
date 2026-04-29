# 00 — STATE LOCK

**TEAM ORDER**: 0-9Y-HE5-DEPLOYABLE-FLOW-RECHECK
**Date**: 2026-04-29
**Phase**: 0 / 8

## Git
- HEAD: `37346fee5fa13e18409dad46c6db43cd6bae6812` (post-HE4, signed ED25519)
- origin/main: `37346fee5fa13e18409dad46c6db43cd6bae6812` ✅ in-sync
- Working tree: only `zangetsu/logs/engine.jsonl.1` (runtime log)

## Worker baseline state
Sample worker (PID 3864124): no `ARENA_*` / `HORIZON` / `ACTIVE_*` env (baseline). All workers running on commit `37346fee` post-HE4 cleanup.

## DB pipeline counts
| Table | Count | Status breakdown |
|---|---:|---|
| `champion_pipeline` | 89 | ARENA2_REJECTED: 89 |
| `champion_pipeline_staging` | 184 | ARENA1_COMPLETE: 184 |
| `champion_pipeline_fresh` | 89 | ARENA2_REJECTED: 89 |
| `champion_pipeline_rejected` | 0 | (table empty) |
| `engine_telemetry` | 0 | (table empty; telemetry in engine.jsonl) |

**Critical**: `0 alphas have ever passed Arena 2 in any state`. Pipeline blocked at A2.

## Source breakdown of pipeline entries
```sql
select status, count(*), case when passport ? 'manual_seed' then 'manual_seed' else 'other' end as source from champion_pipeline_fresh group by status, source;
→ ARENA2_REJECTED, 89, manual_seed

select status, count(*), case when passport ? 'manual_seed' then 'manual_seed' else 'other' end as source from champion_pipeline_staging group by status, source;
→ ARENA1_COMPLETE, 184, manual_seed
```

**Both fresh and staging entries are 100% `manual_seed` (v0.7.2 cold-start bootstrap injection)**, NOT GP-discovered. Confirmed via `passport->'manual_seed'->>'reason' = 'v0.7.2 bootstrap injection for observation window'`.

## GP-discovered candidates flow
From engine.jsonl A1 lifecycle events (current rotation):
- A1 lifecycle ENTERED: 540
- A1 lifecycle REJECTED: 536
- A1 pass rate: ~0.74% (4 / 540, if 4 indeed passed)
- A1 reject reason distribution (HE4 window across 3266 batches): COST_NEGATIVE 99.5%+

**Of GP-discovered alphas processed by all TF/HE/OP rounds: virtually all rejected at A1 due to COST_NEGATIVE.** A handful (≤4) may have passed A1, but none has propagated to a stable champion entry.

## Telemetry sanity (post-HE4 baseline window, n=27)
- `UNKNOWN_REJECT`: 0 ✅
- `COUNTER_INCONSISTENCY`: 0 ✅
- Conservation residual: 0 ✅
- All batches at horizon=60 (post-cleanup baseline)

## Order completion status (full TF + HE chain)
| Order | Status | Verdict |
|---|---|---|
| OP1 | COMPLETE (`82056123`) | OP1_PRIMITIVES_REGISTERED |
| TF2 | COMPLETE (`3decabd4`) | IMPLEMENTED_SHADOW_PENDING |
| TF3 | COMPLETE (`0cef908d`) | PROFILE_CONFIRMED (live: -13.3% cost/gross, +4.5pp win_rate, but net still slightly < 0) |
| TF4 | COMPLETE (`986932df`) | INTEGRATION_DEFINED |
| HE1 | COMPLETE (`bbd6fb42`) | PLUMBING_READY |
| HE2 | COMPLETE (`48be8071`) | HORIZON_AWARE_GENERATION |
| HE3 | COMPLETE (`b83c710c`) | ECONOMICS_MEASURED |
| HE4 | COMPLETE (`37346fee`) | **NO_HORIZON_EDGE** (live falsified fixture; p > 0.24, Cohen's d < 0.07) |

## STOP-conditions check (Phase 0 spec)
| STOP cause | Status |
|---|---|
| Telemetry broken | ❌ no |
| Runtime unstable | ❌ no — workers producing batches at 13:36Z |
| HE3 fields missing | ❌ no — HE3 telemetry was confirmed live during HE4 (3266/3266 batches with horizon_metrics) |

✅ **STATE_LOCK_PASS** — proceed to Phase 1.

## Pre-analysis hypothesis (to be tested)
Based on TF/HE chain evidence:
- Cost is the dominant rejector at A1 (cost/gross ≈ 1.5-1.55 stable)
- Aggregation alone improves but cannot flip net positive (TF3 confirmed)
- Horizon has no live effect on net (HE4 confirmed)
- Pipeline DB shows 0 GP-discovered champions ever produced; only 89 manual cold-start seeds reached A2 (all rejected on A2's own backtest gate)

→ **Working hypothesis for HE5**: the system in its current architecture cannot produce deployable alphas without one or more of: cost reduction, trade-policy redesign, or fundamentally different feature/execution axis.
