# 07 — FINAL REPORT

**TEAM ORDER**: 0-9Y-TF3-SIGNAL-AGGREGATION-SHADOW-ACTIVATION
**Date**: 2026-04-28
**Phase**: 7 / 8 (final)

## Final verdict
**COMPLETE_TF3_SHADOW_PROFILE_CONFIRMED**

Live A1 data confirms the TF2 hypothesis: signal aggregation reduces cost burn and increases per-trade quality. Three profiles (`STRENGTH_q0.95`, `TOPK_K=50`, `HYBRID_q0.90_K=50`) all classified `PROFILE_STRONGLY_IMPROVES_NET`. Best profile = **`STRENGTH_q0.95`** (largest cost-per-gross reduction, smallest negative net per trade).

Net per trade is still slightly negative across all profiles — the live strength→quality monotonicity is shallower than the TF2 fixture's synthetic Beta(2,5)+linear-gross model predicted, so filtering improves but does not flip net to positive at current cost levels. **Master-order success criteria ALL met** (improvement, cost reduction, trade-count reduction, win-rate increase, no artifact, conservation, telemetry clean) — verdict is `CONFIRMED`.

## HEAD
- **HEAD before**: `3decabd4dc9cc821e25dab7544a2ebe4ed7d0f82` (post-TF2)
- **HEAD after**: TBD (Phase 8 commit on `phase-8/0-9y-tf3-signal-aggregation-shadow-activation`)

## Profiles tested
| Key | Profile | Parameters | Live result |
|---|---|---|---|
| `strength` | STRENGTH_FILTER | quantile = 0.95 | PROFILE_STRONGLY_IMPROVES_NET (best) |
| `top_k` | TOP_K_PER_BAR | K = 50 | PROFILE_STRONGLY_IMPROVES_NET |
| `hybrid` | HYBRID_TOPK_STRENGTH | quantile = 0.90, K = 50 | PROFILE_STRONGLY_IMPROVES_NET |

## Number of live batches
**352 arena_batch_metrics events** with full `shadow_profiles` payload, covering **2 265 423 alpha entry edges** across **14 unique symbols** (top symbol share = 11.9%, no concentration artifact).

Master-order target: ≥100 minimum / 200-300 preferred → **352 exceeds preferred by 17%**.

## Best performing profile
**`STRENGTH_q0.95`**

| Metric | baseline | strength | Δ |
|---|---:|---:|---:|
| trade_count_median | 983 | 64.5 | **−93.4%** |
| cost / gross ratio | 1.4964 | **1.2970** | **−13.3%** |
| win_rate_median | 0.3125 | **0.3576** | **+4.5 pp** |
| net_pnl_median (bps) | −1.1768 | −0.0634 | **+1.1134 (less negative)** |
| net_per_trade_median (bps) | ≈ −0.00120 | **−0.000971** | **+19% improved** |
| gross_per_trade_median (bps) | ≈ +0.00250 | +0.003102 | **+24% improved** |
| skip_rate | 0 | 0.9344 | filtered ~93% of entries |
| errors | 0 | 0 | ✅ |

## Full metric comparison
See `04_live_shadow_metrics.md` and `05_comparative_analysis.md`.

| Profile | trade_ct | gross_pnl | net_pnl | win_rate | g/trade | n/trade | cost/gross |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 983.0 | +2.4554 | −1.1768 | 0.3125 | — | — | 1.4964 |
| **strength** (q=0.95) | 64.5 | +0.2111 | −0.0634 | 0.3576 | +0.003102 | **−0.000971** | **1.2970** |
| top_k (K=50) | 89.2 | +0.2893 | −0.0955 | **0.3601** | +0.003176 | −0.001099 | 1.3340 |
| hybrid (q=0.90, K=50) | 89.2 | +0.2809 | −0.0919 | 0.3585 | +0.003182 | −0.001098 | 1.3384 |

## Artifact check
- Symbol coverage: 14 unique symbols, top-1 = 11.9% — well below typical artifact threshold (≥80%) ✅
- No single-symbol dominance ✅
- baseline + shadow share the same per-symbol scan order (worker traverses symbols sequentially) → no introduced bias ✅

## Conservation verification
| Counter | Result |
|---|---|
| baseline `entered = sum(passed+rejected+skipped+in_flight+error)` | 3520 = 3520, residual = **0** ✅ |
| `UNKNOWN_REJECT` total | **0** ✅ |
| `COUNTER_INCONSISTENCY` total | **0** ✅ |
| Per-profile per-batch `entered = kept + skipped` | **0 / 352 batches** with residual ≠ 0 across all 3 profiles ✅ |

## Forbidden ops audit
**0 forbidden touches.** All criteria pass:

| Constraint | Result |
|---|---|
| Validation logic changed | NO (test #9 + tokenize-scan in TF3 test #9) |
| Cost model changed | NO (cost_bps is identical input to both baseline and shadow backtester calls) |
| `A2_MIN_TRADES = 25` changed | NO |
| `deployable_count` semantics changed | NO |
| champion promotion changed | NO |
| `alpha_zoo` execution | NOT TRIGGERED (`scripts/alpha_zoo_injection.py` unchanged) |
| CANARY started | NO |
| Production rollout started | NO |
| Execution / capital / risk modified | NO |
| DB schema / guards weakened | NO |

## Q1 / Q2 / Q3
- **Q1 (5 dims)**: PASS — input-boundary covered (NaN-safe via TF2), fail-closed on unknown profile (TF2 #6), external-dep absent (no DB / no live channels), no shared mutable state (per-profile accumulators), no scope creep (44 LOC additive only)
- **Q2**: PASS — pure helper, recovery path = `_tf3_shadow_accs is None` short-circuit when env disabled; per-profile try/except prevents propagation
- **Q3**: PASS — exactly what TF3 master order required (env-gated, additive shadow profile activation), no over-engineering

## Files changed
| Path | Status | LOC |
|---|---|---|
| `zangetsu/services/tf3_shadow.py` | NEW | 254 |
| `zangetsu/tests/test_tf3_shadow.py` | NEW | 292 |
| `zangetsu/services/arena_pipeline.py` | MOD | +44 / −0 |
| `zangetsu/docs/recovery/.../11-tf3-.../00_state_lock.md` | NEW | 67 |
| `zangetsu/docs/recovery/.../11-tf3-.../01_shadow_activation_design.md` | NEW | 129 |
| `zangetsu/docs/recovery/.../11-tf3-.../02_patch_report.md` | NEW | 136 |
| `zangetsu/docs/recovery/.../11-tf3-.../03_test_report.md` | NEW | 99 |
| `zangetsu/docs/recovery/.../11-tf3-.../04_live_shadow_metrics.md` | NEW | 126 |
| `zangetsu/docs/recovery/.../11-tf3-.../05_comparative_analysis.md` | NEW | 115 |
| `zangetsu/docs/recovery/.../11-tf3-.../06_controlled_diff_report.md` | NEW | 114 |
| `zangetsu/docs/recovery/.../11-tf3-.../07_final_report.md` | NEW (this) | — |

**Existing source files modified**: 1 (`arena_pipeline.py`, additive only).

## Tests result
- TF3 module suite: **9 / 9 PASS**
- TF2 + TF3 module suites: **22 / 22 PASS**
- Targeted regression suite: **187 / 187 PASS** (3 skipped)
- Pre-existing test-rig issue (`tests/policy/test_exception_overlay.py`): unchanged, ignored

## Live shadow run window
- Start: 2026-04-28T12:03:xx (workers restarted with `ARENA_TF3_SHADOW=1`)
- Stop: 2026-04-28T12:37:50Z (workers stopped, dataset frozen)
- Duration: ~35 minutes
- Throughput: ~10 batches/min during shadow run (slightly higher than baseline 7/min — most alphas hit COST_NEGATIVE early so backtest is short-circuited)
- Post-restoration: workers restarted with `ARENA_TF3_SHADOW` unset; baseline state confirmed via `/proc/<pid>/environ` ✅

## Next-step recommendation
Master-order Next-Step Decision Tree branch: **`COMPLETE_TF3_SHADOW_PROFILE_CONFIRMED`**

→ Recommended next order: **TEAM ORDER 0-9Y-TF4-INTEGRATION-DECISION**

In TF4, j13 reviews:
1. Whether to elevate one of the confirmed profiles from SHADOW to **A1 secondary lane / live A23 evaluation** (still NOT CANARY, NOT production), or
2. Whether to combine TF3 results with horizon-aware path (`HE1`-`HE5`) before any integration, or
3. Whether to refine aggregation parameters (e.g., quantile sweep at 0.97 / 0.99) before integration.

The data favours integrating `STRENGTH_q0.95` as the next experimental lane: largest cost reduction, smallest net per-trade loss, simplest single-parameter knob, conservation perfectly intact.

## REUSABLE pattern
```
# REUSABLE: env-gated-shadow-activation
# use-when: prototype must run alongside live path on production data without
#           changing baseline behavior; needs A/B comparison telemetry
# extract-if: used in >= 2 projects
```
Pattern: env var `*_SHADOW=1` cached at module-import; `is_shadow_enabled()` short-circuit; per-profile accumulators isolated; payload built only when enabled and attached as additive dict key. Validated by per-batch conservation (0 / 352 residuals).

## Final state
TF3 SHADOW activation is fully implemented, tested, ran on real production batches, and **confirmed TF2's directional hypothesis**. Per master-order Expected likely verdict: ✅ **COMPLETE_TF3_SHADOW_PROFILE_CONFIRMED**.

## Verdict (final)
**COMPLETE_TF3_SHADOW_PROFILE_CONFIRMED**
