# 04 — PER-HORIZON ANALYSIS

**TEAM ORDER**: 0-9Y-HE4-HORIZON-SHADOW-RUN
**Date**: 2026-04-29
**Phase**: 4 / 8

## Per-horizon medians (median-of-medians, n≈1088 batches each)

| Horizon | n | Trade Count | Gross PnL (bps) | Net PnL (bps) | Gross/Trade | Net/Trade | Cost/Gross | Win Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **180** | 1088 | 981.5 | +2.4441 | **−1.2607** | +0.002531 | -0.001297 | 1.5426 | 0.3054 |
| **240** | 1089 | 980.0 | +2.4289 | **−1.2250** | +0.002518 | -0.001264 | 1.5348 | 0.3056 |
| **360** | 1089 | 980.0 | +2.4465 | **−1.2187** | +0.002575 | -0.001235 | 1.5546 | 0.3059 |

(round_total_cost_bps = 14.5 across all horizons — uniform cost model, unchanged)

## Δ across horizons (180 → 240 → 360)
| Metric | 180 | 240 | 360 | Δ (180→360) |
|---|---:|---:|---:|---:|
| trade_count_median | 981.5 | 980.0 | 980.0 | **−1.5 (−0.15%)** |
| gross_pnl_median | +2.4441 | +2.4289 | +2.4465 | +0.0024 |
| net_pnl_median | −1.2607 | −1.2250 | **−1.2187** | +0.042 |
| net_per_trade | -0.001297 | -0.001264 | -0.001235 | +0.000062 (+4.8%) |
| cost/gross ratio | 1.5426 | 1.5348 | 1.5546 | +0.012 (worse) |
| win_rate_median | 0.3054 | 0.3056 | 0.3059 | +0.0005 (+0.05pp) |

## Critical finding: NO MATERIAL HORIZON EFFECT
Live multi-horizon evaluation shows **all three horizons (180, 240, 360) produce essentially identical economics**:
- Trade count is stable at ~980 across all horizons (NOT decreasing as fixture predicted)
- Gross PnL is flat at +2.43 bps (NOT increasing as fixture predicted)
- Net PnL improves marginally: −1.26 → −1.22 (Δ ≈ +0.04 bps, within batch-to-batch noise)
- Cost/gross ratio is essentially unchanged (1.53–1.55)
- Win rate is essentially unchanged (0.305–0.306)

**No horizon achieves net > 0.** None comes close to break-even.

## Comparison vs HE3 fixture prediction

| Metric | HE3 fixture h=360 | HE4 live h=360 | Match? |
|---|---|---|---|
| Trade count vs h=60 | -52% (462 vs 971) | -0.2% (980 vs ~982 baseline) | ❌ falsified |
| Gross PnL | +59% | +1.0% | ❌ falsified |
| Net PnL | +0.05 (positive) | -1.22 (negative) | ❌ falsified |
| Cost/gross | 0.99 (sub-1) | 1.55 (no improvement) | ❌ falsified |
| Win rate uplift | +10 pp | +0.05 pp | ❌ falsified |

**The HE3 fixture's monotone-improving hypothesis is decisively falsified by live data.**

## Interpretation: why fixture was wrong

The fixture **assumed** a causal chain:
```
longer horizon → wider price-move window → larger gross / fewer trades / more positive edge
```

This causal chain holds for the **forward-return target series** computed by `_forward_returns(close, horizon)` — which is how `ALPHA_FORWARD_HORIZON` was used historically. **However**, the actual trade execution in `alpha_to_signal` (`engine/components/alpha_signal.py`) uses **`min_hold=60`** and **`cooldown=60`** parameters that are independent of the GP-search horizon:

```python
def alpha_to_signal(alpha, ..., min_hold=60, cooldown=60, ...):
    ...
```

So changing `horizon` only affects:
1. **WHICH alphas survive GP evolution** (fitness IC computed against horizon-bar forward return)
2. **NOT** how the surviving alphas trade (they all enter/hold/exit on the same ~60-bar timescale)

The result: alphas selected under longer-horizon IC fitness still trade with `min_hold=60`-bar lifespan, hence trade count and per-trade economics remain similar.

This is a **architectural insight** that should be captured for HE5 / future orders:
> To convert a horizon parameter into actual trading-timescale change, `alpha_to_signal` must accept and use horizon-dependent `min_hold` (e.g., `min_hold = horizon`). HE-series infrastructure is in place; only one additional binding is missing.

## Per-horizon classification (master-order Phase 4 enum)

| Horizon | Net Δ vs others | Cost/Gross | Win Rate | Classification |
|---|---|---|---|---|
| 180 | most negative net (-1.26) | 1.54 | 0.305 | **HORIZON_NEUTRAL** (essentially baseline-equivalent) |
| 240 | mid (-1.22) | 1.53 (best c/g) | 0.306 | **HORIZON_NEUTRAL** |
| 360 | least negative (-1.22) | 1.55 | 0.306 (best wr) | **HORIZON_NEUTRAL** (marginally less negative within noise) |

**No horizon is materially better.** None of the master-order's "STRONGLY_BETTER / BETTER / WORSE" classifications applies cleanly — all 3 are NEUTRAL within statistical noise.

## Best horizon (purely by ranking, but practically NULL)
- By net_pnl_median: **h=360** (-1.2187 bps) — **only +0.04 bps better than h=180**
- By cost/gross: **h=240** (1.5348)
- By win_rate: **h=360** (0.3059)

The "best" horizon depends on the metric, and the differences are smaller than typical cross-batch variance.

## Verdict
**PHASE_4_COMPLETE** — live data falsifies the HE3 fixture monotone-improving hypothesis. All 3 horizons (180, 240, 360) are HORIZON_NEUTRAL relative to each other.

## Architectural recommendation
Future orders (HE5 or beyond) should consider whether to wire horizon into `alpha_to_signal`'s `min_hold` parameter so that horizon actually controls the trading timescale, not just the GP-search target. Without this, multi-horizon evaluation provides minimal economic differentiation in the current pipeline.

## Next
Phase 5 — statistical validation (variance, stability, significance test).
