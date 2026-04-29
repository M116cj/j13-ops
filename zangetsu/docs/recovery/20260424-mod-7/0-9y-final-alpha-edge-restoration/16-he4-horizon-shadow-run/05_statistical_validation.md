# 05 — STATISTICAL VALIDATION

**TEAM ORDER**: 0-9Y-HE4-HORIZON-SHADOW-RUN
**Date**: 2026-04-29
**Phase**: 5 / 8

## net_pnl_median distribution per horizon (per-batch values, n≈1088 each)
| Horizon | n | mean | median | std | p10 | p90 | min | max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 180 | 1088 | -1.268 | -1.261 | 0.375 | -1.73 | -0.82 | -2.59 | -0.36 |
| 240 | 1089 | -1.248 | -1.225 | 0.381 | -1.72 | -0.81 | -2.29 | **0.00** |
| 360 | 1089 | -1.244 | -1.219 | 0.375 | -1.72 | -0.80 | -2.29 | -0.27 |

**Observation**: All 3 distributions overlap heavily. Means are within 0.024 bps of each other. Standard deviations are nearly identical (~0.376–0.381). p10/p90 brackets are nearly identical. h=240 has one batch hitting net=0.0 exactly (max), but h=360's max is -0.27 (worse).

## gross_pnl_median distribution per horizon
| Horizon | n | mean | median | std | p10 | p90 |
|---|---:|---:|---:|---:|---:|---:|
| 180 | 1088 | +2.412 | +2.444 | 0.541 | +1.58 | +3.04 |
| 240 | 1089 | +2.416 | +2.429 | 0.539 | +1.58 | +3.05 |
| 360 | 1089 | +2.404 | +2.446 | 0.548 | +1.54 | +3.02 |

**Observation**: Gross is essentially identical across horizons. Means within 0.012 bps; medians within 0.018 bps.

## Pairwise Mann-Whitney U (two-tailed)
| Comparison | U | p-value | significant @ α=0.05? |
|---|---:|---:|---|
| h=180 vs h=240 (net_pnl_median) | 576 820 | **0.2875** | ❌ NO |
| h=180 vs h=360 (net_pnl_median) | 575 404 | **0.2460** | ❌ NO |
| h=240 vs h=360 (net_pnl_median) | 592 132 | **0.9549** | ❌ NO |

**All three pairwise comparisons fail to reject the null hypothesis** that the horizons produce the same net_pnl distribution. p-values range from 0.25 to 0.96 — far above any reasonable significance threshold.

## win_rate distribution per horizon
| Horizon | n | mean | median | std |
|---|---:|---:|---:|---:|
| 180 | 1088 | 0.30770 | 0.30544 | 0.03044 |
| 240 | 1089 | 0.30975 | 0.30562 | 0.03371 |
| 360 | 1089 | 0.31219 | 0.30591 | 0.03385 |

**Observation**: Win rate increases monotonically from h=180 (0.308) to h=360 (0.312), a Δ of +0.45 percentage points. The std is ~0.034 (about 7-8× larger than the effect size), so the trend is **swamped by per-batch variance**. Cohen's d ≈ (0.31219-0.30770) / 0.034 = 0.13, a "very small" effect by conventional benchmarks.

## trade_count distribution per horizon
| Horizon | n | mean | median | std |
|---|---:|---:|---:|---:|
| 180 | 1088 | 978.8 | 981.5 | 26.1 |
| 240 | 1089 | 975.7 | 980.0 | 50.1 |
| 360 | 1089 | 974.9 | 980.0 | 31.3 |

**Observation**: Trade count is essentially flat at ~975-979 across all horizons. The HE3 fixture predicted 462 trades at h=360 (-52% vs h=60 baseline). **Live data shows -0.4% — essentially no change.**

## Effect-size summary (Cohen's d on net_pnl_median)
| Comparison | mean Δ | pooled std | Cohen's d | interpretation |
|---|---:|---:|---:|---|
| 180 vs 360 | +0.024 | 0.375 | **0.063** | "negligible" (< 0.2) |
| 180 vs 240 | +0.020 | 0.378 | **0.054** | "negligible" |
| 240 vs 360 | +0.004 | 0.378 | **0.011** | "negligible" |

All effect sizes are an order of magnitude below Cohen's threshold for "small" (0.2). The horizon parameter has **no detectable practical effect** on per-batch net economics.

## Stability across batches
With n≈1088 batches per horizon and ~13% top-1 symbol share (no concentration artifact, see Phase 3), the dataset is well-mixed across symbols and time. The lack of horizon effect is **not driven by outliers**: medians, means, and quantile brackets all agree.

## Symbol-specific check
Top symbols per horizon (h=180 / 240 / 360):
- 180: DOTUSDT 13.1%, LINKUSDT, AAVEUSDT
- 240: LINKUSDT 12.8%, DOTUSDT, BTCUSDT
- 360: LINKUSDT 13.5%, BTCUSDT, AAVEUSDT

**No horizon is dominated by a single problematic symbol.** Top-3 symbols overlap heavily across all horizons.

## Classification (master-order Phase 5 enum)
**NO_HORIZON_ADVANTAGE** ✅

Per the master-order classification list:
- ❌ NOT `LIVE_CONFIRMED_H360_BEST` — h=360 is not statistically distinguishable
- ❌ NOT `LIVE_DIFFERENT_HORIZON_BEST` — no horizon shows a meaningful edge
- ✅ **`NO_HORIZON_ADVANTAGE`** — pairwise p > 0.24, Cohen's d < 0.07, effect sizes negligible
- ❌ NOT `INCONCLUSIVE_DATA` — sample size is large (n=3266 total, ~1088/horizon, ~10× minimum), telemetry clean, conservation = 0; the result is decisive null

## Key question answered
> Does h=360 still outperform in real data?

**No.** The HE3 fixture's monotone-improving prediction is **decisively falsified by live data**. h=180/240/360 produce statistically equivalent economics across all measured dimensions.

## Why fixture failed
See Phase 4 architecture analysis: `ALPHA_FORWARD_HORIZON` controls the **GP fitness target** but `alpha_to_signal` uses **fixed `min_hold=60`** for trade execution. So the surviving alphas trade with the same ~60-bar timescale regardless of GP-search horizon, producing similar trade counts and per-trade economics.

## Verdict
**PHASE_5_COMPLETE** — statistical validation confirms NO_HORIZON_ADVANTAGE with strong sample size (n=3266). HE4 has decisively answered the falsification question.

## Next
Phase 6 — controlled diff (HE4 is docs-only, no source change).
