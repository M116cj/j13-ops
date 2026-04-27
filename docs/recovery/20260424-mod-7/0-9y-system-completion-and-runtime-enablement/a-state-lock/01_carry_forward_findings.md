# 01 — Carry-Forward Findings (Subprogram A)

Each item references a prior order whose evidence is the source of truth.

## ✅ Confirmed-stable carry-forward (no regression)

| Item | Source order | Status now |
|---|---|---|
| HEAD == origin/main | 0-9X-CANARY readiness PR #52 → 0-9X-PIPELINE-DEPLOYABLE-FLOW PR #53 | `294bf4ef`, in sync |
| §17.6 stale-check FRESH | 0-9X-POST-RESTART PR #51 | 4/4 workers post-source-mtime |
| A1 telemetry CI=0 | PR #50 (`_compute_a1_reject_deltas` per-round delta accounting) | last 100 batches: 0 |
| A1 telemetry UNKNOWN_REJECT=0 | PR #49 (taxonomy fix) | last 100 batches: 0 |
| Conservation residual=0 | PR #50 + PR #49 | last 100 batches: residuals = {0:100} |
| DB v0.7.1 schema | PR #44 (multi-stage migration) | 8/8 objects present |
| Watchdog cold-boot recovery | PR #45 + PR #46 | watchdog defers to lockfiles, no spurious restarts |

## ⚠️ Confirmed-still-broken carry-forward (no regression but no fix yet)

| Item | Source diagnosis | Status now | Owned subprogram |
|---|---|---|---|
| `engine_telemetry` 0 rows ever (since v0.7.1) | 0-9X-CANARY-READINESS-REVIEW (#52) Phase 1 | still 0 | **B2** |
| §17.3 NULL-safety predicate gap (`last_live_at_age_h` NULL → never RED) | 0-9X-CANARY-READINESS-REVIEW (#52) Phase 2 | still NULL | **B3** |
| Pipeline metrics not exposing gross_pnl / cost components | 0-9X-PIPELINE-DEPLOYABLE-FLOW-DIAGNOSIS (#53) Phase 3 caveats | unchanged | **B1** |

## ⚠️ Strategic blockers (require redesign decision, not a bug fix)

| Item | Source diagnosis | Status now | Owned subprogram |
|---|---|---|---|
| `deployable_count = 0` ever | #52 + #53 | still 0 | **C / D / E / F** |
| Last admission 2026-04-21 04:34Z (~6.5 d stale at #53; now ~6.7 d) | #53 Phase 1 | still stale | **C / D / E** |
| 89 fresh alphas all `ARENA2_REJECTED` (degenerate raw-OHLCV, indicator_ratio = 0) | #53 Phase 1 + Phase 5 | unchanged | **D / E** |
| A1 reject distribution: ~98.7% `COST_NEGATIVE` | #53 Phase 2 | last 100: 986/1000 = 98.6% (consistent) | **C / D / E** |
| Feature-space exhaustion under "60-bar fwd return on OHLCV+indicator" | #53 Phase 5 + AKASHA | unchanged | **D / E** |
| order_router (real-capital execution) not built | #52 Phase 2 | unchanged | future (post G) |
| live CANARY blocked | constitution + #52 | unchanged | gated by D, E, F, G |
| alpha_zoo BLOCKED (write-guard intact) | constitution + #52 | unchanged | possible **E3** path |
| production rollout NOT STARTED | constitution | unchanged | gated by all of the above |
| runtime calibration BLOCKED | constitution | unchanged | gated |

## Confidence anchors

- The validation gate stack (A1/A2/A3/A4) **is mathematically correct** per #53 Phase 4. Loosening any of it admits money-losing alphas. **Cannot weaken.**
- Cost model is realistic Binance Futures schedule (5–10 bps taker tiers). **Cannot reduce** — PR #41 retro proved that lowering cost manufactures `SINGLE_SYMBOL_ARTIFACT` survivors.
- The pipeline IS producing diverse formulas (4454 unique alpha_ids, bloom_hits=0). The block is genuine economic edge absence under the current target / horizon / feature triplet.

## Net carry-forward verdict

The system is **stable and observable enough to start the 0-9Y program**. The bugs are well-scoped (B1/B2/B3) and the strategic blocker (no economic edge) is well-diagnosed and ready for D's redesign plan.
