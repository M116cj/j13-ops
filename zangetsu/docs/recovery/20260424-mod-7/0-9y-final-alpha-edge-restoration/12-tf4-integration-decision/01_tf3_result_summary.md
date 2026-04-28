# 01 — TF3 RESULT CONSOLIDATION

**TEAM ORDER**: 0-9Y-TF4-INTEGRATION-DECISION
**Date**: 2026-04-28
**Phase**: 1 / 8
**Source documents**: `../11-tf3-signal-aggregation-shadow-activation/04_live_shadow_metrics.md`, `../11-tf3-signal-aggregation-shadow-activation/05_comparative_analysis.md`, `../11-tf3-signal-aggregation-shadow-activation/07_final_report.md`

## Live shadow window
- Activation: 2026-04-28T12:03:xx (4 arena_pipeline workers, `ARENA_TF3_SHADOW=1`)
- Stop: 2026-04-28T12:37:50Z (35 minutes of live A1 traffic)
- Throughput: ~10 batches/min during shadow, slightly higher than baseline 7/min

## Sample size
| Metric | Value |
|---|---|
| `arena_batch_metrics` events with `shadow_profiles` payload | **352 batches** |
| Master-order TF3 minimum (≥100) / preferred (200-300) | exceeded (352 > 300) |
| Total alpha entries observed across profiles | **2 265 423** |
| Unique symbols | **14** (top-1 = 11.9%, no concentration artifact) |
| Errors in shadow harness | **0** |

## Full per-profile metric table (median-of-medians, n=352)
| Profile | Label | Trade Count | Gross PnL (bps) | Net PnL (bps) | Win Rate | Gross/Trade | Net/Trade | Cost/Gross |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | (existing path) | **983** | **+2.4554** | **−1.1768** | **0.3125** | — | — | **1.4964** |
| **strength** | STRENGTH_q0.95 | 64.5 | +0.2111 | −0.0634 | 0.3576 | +0.003102 | **−0.000971** | **1.2970** |
| top_k | TOPK_K=50 | 89.2 | +0.2893 | −0.0955 | **0.3601** | +0.003176 | −0.001099 | 1.3340 |
| hybrid | HYBRID_q0.90_K=50 | 89.2 | +0.2809 | −0.0919 | 0.3585 | +0.003182 | −0.001098 | 1.3384 |

## Improvement deltas vs baseline
| Profile | Δ trade_count | Δ cost/gross | Δ win_rate | Δ net_pnl_med (bps) | Δ net_per_trade (bps) |
|---|---:|---:|---:|---:|---:|
| **strength (q=0.95)** | **−93.4%** | **−13.3%** | **+4.5 pp** | **+1.1134** | **+19% improved** |
| top_k (K=50) | −90.9% | −10.9% | +4.8 pp | +1.0813 | +9% improved |
| hybrid (q=0.90, K=50) | −90.9% | −10.6% | +4.6 pp | +1.0849 | +9% improved |

## Best profile
**`STRENGTH_q0.95`** — wins 3/5 economic criteria including the two most meaningful (cost/gross reduction, smallest negative net per trade). All three profiles classified `PROFILE_STRONGLY_IMPROVES_NET`.

## Artifact check
- 14 unique symbols across 352 shadow batches
- Top symbol share = **11.9%** — well below typical artifact threshold (≥80%)
- baseline + shadow inherit the same per-symbol scan order → no introduced bias
- No single-symbol dominance ✅

## Conservation proof
| Counter | Value over 352 batches |
|---|---|
| baseline `entered = passed + rejected + skipped + in_flight + error` | 3520 = 3520 (residual = **0**) ✅ |
| `UNKNOWN_REJECT` total | **0** ✅ |
| `COUNTER_INCONSISTENCY` total | **0** ✅ |
| Per-profile per-batch `entered = kept + skipped` (3 profiles × 352 batches = 1056 instances) | **0 / 1056** with residual ≠ 0 ✅ |

## Conclusion (per master-order Phase 1 requirement)
Aggregation:
- ✅ improves net pnl (less negative — Δ +1.11 bps median)
- ✅ reduces cost (cost/gross ratio −13.3% on best profile)
- ✅ increases win rate (+4.5 pp)
- ❌ **does NOT reach positive edge** (net per trade still slightly negative across all profiles)

The TF1 hypothesis (stronger entries → better trade quality) is **directionally confirmed in real market data**, but the magnitude is **shallower than the TF2 fixture predicted**. Filtering reduces the cost burden but does not eliminate it; the gross edge per filtered trade (~+0.0031 bps) is still smaller than the per-trade cost (~0.0148 bps round-trip).

## Implication for next steps
Aggregation alone is **valid** (provable, repeatable, no artifact, conservation intact) but **insufficient** to flip net positive. To reach positive edge, the system must combine aggregation with one or more of:
1. **Horizon redesign** (HE1-HE5) — change what each trade tries to capture
2. **Even more aggressive filtering** (e.g., q=0.99) — risks insufficient sample at A2 (`A2_MIN_TRADES = 25`)
3. **Cost model improvement** — out of scope (LOCKED)

The master-order tree explicitly directs `COMPLETE_TF3_SHADOW_PROFILE_CONFIRMED → TEAM ORDER 0-9Y-TF4-INTEGRATION-DECISION → TEAM ORDER 0-9Y-HE1-HORIZON-TARGET-PLUMBING`. TF4 wires aggregation as a pre-filter that the HE-series can stack on top of.

## Classification
**TF3_CONFIRMED_VALID_BUT_INSUFFICIENT** ✅

## Verdict
**PHASE_1_COMPLETE** — TF3 results consolidated, TF1 hypothesis confirmed in live data with measurable economic improvement, but insufficient as a sole intervention. Aggregation must combine with horizon redesign in subsequent orders.

## Next
Phase 2 — Integration Design: define `aggregation_mode = PRE_FILTER + SHADOW` formally.
