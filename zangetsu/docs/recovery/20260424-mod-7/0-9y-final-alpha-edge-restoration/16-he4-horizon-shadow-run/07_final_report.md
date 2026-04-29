# 07 — FINAL REPORT

**TEAM ORDER**: 0-9Y-HE4-HORIZON-SHADOW-RUN
**Date**: 2026-04-29
**Phase**: 7 / 8 (final)

## Final verdict
**COMPLETE_HE4_NO_HORIZON_EDGE**

Live multi-horizon SHADOW activation collected 3266 batches over ~4h50min with virtually equal allocation across h=180/240/360 (1088/1089/1089). Statistical analysis decisively rejects the HE3 fixture's monotone-improving hypothesis: pairwise Mann-Whitney U on per-batch `net_pnl_median` produces p-values of 0.25-0.96 (all >> 0.05), and Cohen's d effect sizes are below 0.07 (negligible). All 3 tested horizons produce statistically equivalent economics in the current pipeline architecture.

The architectural reason: `ALPHA_FORWARD_HORIZON` controls the GP-fitness target series but NOT the trade-execution timescale (`alpha_to_signal` uses fixed `min_hold=60`/`cooldown=60`). Surviving alphas trade with similar lifespan regardless of GP-search horizon.

## HEAD
- **HEAD before**: `b83c710c8fa5e2e8087b817d723baa57203df402` (post-HE3, signed ED25519)
- **HEAD after**: TBD (Phase 8 commit on `phase-8/0-9y-he4-horizon-shadow-run`, **docs-only**)

## Total batches collected
**3266** arena_batch_metrics events spanning 2026-04-29T08:15:04Z → 13:04:30Z (~4h 50min, ~11 batches/min throughput).

## Per-horizon sample size
| Horizon | n | % of total |
|---|---:|---:|
| 180 | **1088** | 33.31% |
| 240 | **1089** | 33.34% |
| 360 | **1089** | 33.34% |

Allocation is **virtually exactly equal** (within 1 batch boundary). Master-order target ≥150/horizon **exceeded by 7×**.

## Best horizon
**No horizon is materially better.**

By individual ranking (within statistical noise):
- net_pnl_median: h=360 (-1.219) > h=240 (-1.225) > h=180 (-1.261) — Δ from worst to best = 0.042 bps
- cost_over_gross: h=240 (1.535) < h=180 (1.543) < h=360 (1.555)
- win_rate_median: h=360 (0.3059) > h=240 (0.3056) > h=180 (0.3054) — Δ = +0.05 pp

The differences are smaller than typical batch-to-batch variance.

## Full metrics table
| Horizon | n | Trades | Gross | Net | g/trade | n/trade | c/gross | Win Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 180 | 1088 | 981.5 | +2.4441 | -1.2607 | +0.002531 | -0.001297 | 1.5426 | 0.3054 |
| 240 | 1089 | 980.0 | +2.4289 | -1.2250 | +0.002518 | -0.001264 | 1.5348 | 0.3056 |
| 360 | 1089 | 980.0 | +2.4465 | -1.2187 | +0.002575 | -0.001235 | 1.5546 | 0.3059 |

## Statistical significance
| Comparison | Mann-Whitney p (two-tailed) | Cohen's d | Verdict |
|---|---:|---:|---|
| h=180 vs h=240 | 0.2875 | 0.054 | not significant |
| h=180 vs h=360 | 0.2460 | 0.063 | not significant |
| h=240 vs h=360 | 0.9549 | 0.011 | not significant |

**All pairwise comparisons fail to reject H₀**. With n≈1088 each, the test has ample statistical power to detect any meaningful effect.

## Comparison vs HE3 fixture
| Metric | HE3 fixture h=360 (Δ vs h=60) | HE4 live h=360 (Δ vs h=180) | Match? |
|---|---|---|---|
| Trade count | -52% (462 vs 971) | -0.2% (980 vs 982) | ❌ falsified |
| Gross PnL | +59% (3.83 vs 2.40) | +1.0% (2.45 vs 2.44) | ❌ falsified |
| Net PnL | -1.21 → +0.05 (positive crossing) | -1.26 → -1.22 (still negative) | ❌ falsified |
| Cost/gross | 1.50 → 0.99 (sub-1) | 1.54 → 1.55 (no change) | ❌ falsified |
| Win rate | +10 pp | +0.05 pp | ❌ falsified |

**HE3 fixture's monotone-improving-with-horizon hypothesis is decisively falsified by live data.**

## Confirmation or rejection of hypothesis
**REJECTED** — the hypothesis that longer horizons (180/240/360) improve net economics in the current zangetsu pipeline does NOT hold. Live evidence shows uniform performance across the tested horizons.

## Stability assessment
- 3266 batches with **conservation residual = 0** across all batches and all horizons ✅
- `UNKNOWN_REJECT = 0` per horizon ✅
- `COUNTER_INCONSISTENCY = 0` ✅
- No runtime crashes during the 4h50min window
- Per-horizon variance (std ≈ 0.38 bps for net) is consistent across horizons → distributions are stable, not driven by outliers

## Artifact check
| Horizon | Unique symbols | Top-1 share | Artifact? |
|---|---:|---:|---|
| 180 | 14 | DOTUSDT 13.1% | NO |
| 240 | 14 | LINKUSDT 12.8% | NO |
| 360 | 14 | LINKUSDT 13.5% | NO |

No single-symbol dominance across any horizon (top-1 << 80% threshold).

## Conservation check
```
entered_count = 32660 (3266 batches × 10 alphas)
sum(passed + rejected + skipped + in_flight + error) = 32660
residual = 0  ✅
```

## Forbidden ops audit
**0 forbidden ops.** HE4 is docs-only:
- No source code modified
- No CANARY / production / alpha_zoo / capital / risk changes
- No validator / cost / A2_MIN_TRADES / champion / deployable changes
- Workers temporarily ran with `ARENA_HORIZON_MODE`/`ACTIVE_A1_HORIZONS` env (allowed); restored to baseline at Phase 8 cleanup

## Whether validation / cost / A2 / alpha_zoo / CANARY / production changed
**ALL NO.** Confirmed by Phase 6 controlled diff (empty source diff).

## Architectural insight (key takeaway for HE5+)
The horizon parameter (`ALPHA_FORWARD_HORIZON`) currently affects only:
1. `_forward_returns(close, horizon)` — the target series for IC computation during GP evolution
2. `alpha_hash` composition — distinguishes formulas across horizons

It does NOT affect:
3. `alpha_to_signal()` trade execution — uses fixed `min_hold=60`/`cooldown=60`
4. Backtest cost model — same `cost_bps` regardless of horizon

So GP search at h=360 selects "alphas whose 360-bar forward IC is high", but those alphas still trade with ~60-bar lifespan, producing similar economics. To convert horizon into actual trading-timescale change, `alpha_to_signal` would need horizon-aware `min_hold` (e.g., `min_hold = horizon`). **This is a code change, not in HE4 scope** — but HE4's data points to it as a candidate for future investigation.

## Next-step recommendation
Master-order Phase 8 explicitly directs:
> Next: **TEAM ORDER 0-9Y-HE5-DEPLOYABLE-FLOW-RECHECK**

HE5 will assess whether **any** combination of HE/TF interventions has produced a deployable_count > 0 path, given that:
- TF (aggregation): improves per-trade quality (TF3 confirmed); not enough alone
- HE (horizon): no detectable edge in current pipeline architecture (HE4 — this report)

HE5's question: do TF + HE together produce deployables, or does the system need a different intervention axis (e.g., signal-execution `min_hold` tied to horizon, microstructure features, etc.)?

## Q1 / Q2 / Q3
- **Q1 (5 dims)**: PASS — invalid env / runtime instability / corrupted telemetry all handled by graceful HE1/HE2/HE3 fail-safe paths; no failure observed during 4h50min run
- **Q2**: PASS — recovery path = restore baseline env + restart; verified at Phase 8 cleanup
- **Q3**: PASS — minimal, exactly what the order required (env activate + collect + analyze + restore)

## Final state
- Workers running on baseline (no HE/TF env) — verified via `/proc/<pid>/environ` post-restoration
- 8 evidence documents written to `zangetsu/docs/recovery/.../16-he4-.../`
- HE3 telemetry pipeline validated under live data (3266/3266 batches with `horizon_metrics`)
- HE3 fixture hypothesis falsified — captured for future architectural decisions

Per master-order Expected verdict: was `COMPLETE_HE4_LIVE_HORIZON_CONFIRMED`; **actual verdict is the honest negative result `COMPLETE_HE4_NO_HORIZON_EDGE`**, which is one of the master-order's listed valid outcomes.

## Verdict (final)
**COMPLETE_HE4_NO_HORIZON_EDGE**
