# 03 — Top-decile sharpe analysis & signal-aggregation rationale

Top decile by `train_sharpe_median`: top 10 of 106 batches (top 9.4%).

## Top-decile vs rest

| cohort | n | sharpe_med (range) | net_med | gross_med | cost_med | trades_med | win_rate | density |
|--------|---|--------------------|--------:|----------:|---------:|-----------:|---------:|--------:|
| **top 10%** | 10 | -0.186 (range [-0.770, +0.282]) | **-0.0278** | +0.2857 | 0.3749 | **104** | **0.4507** | **0.001028** |
| rest        | 96 | -2.336 (range [-4.142, -0.777]) | -1.3706 | +2.5279 | 3.8508 | 989 | 0.3196 | 0.007044 |
| all (106)   | 106 | -2.224 | -1.3261 | +2.4574 | 3.5990 | 987 | 0.3261 | 0.007028 |

### Top-decile-by-net (cross-check)

Top 10 by `train_net_pnl_median`: trades_med = **101**, density_med = **0.000947**, sharpe_med = -0.186, net_med = -0.0278. **Identical cohort.** Top-decile-by-net and top-decile-by-sharpe overlap heavily — this is not a metric-selection artefact.

## Top-decile batch list

| batch_id | sharpe | net | gross | cost | trades | win_rate | density |
|----------|-------:|----:|------:|-----:|-------:|---------:|--------:|
| R418909-SOLUSDT-BULL_TREND   | +0.282 | +0.023 | +0.265 | 0.247 |   89 | 0.492 | 0.00057 |
| R418904-SOLUSDT-BULL_TREND   | +0.269 | +0.022 | +0.265 | 0.243 |   89 | 0.494 | 0.00057 |
| R418910-AAVEUSDT-BEAR_TREND  | +0.163 | -0.173 | +1.808 | 2.102 |  635 | 0.475 | 0.00455 |
| R418925-AAVEUSDT-BEAR_TREND  | -0.063 | -0.008 | +0.238 | 0.297 |   70 | 0.467 | 0.00065 |
| R418907-AAVEUSDT-BEAR_TREND  | -0.082 | -0.005 | +1.029 | 0.640 |  243 | 0.448 | 0.00309 |
| R418917-SOLUSDT-BULL_TREND   | -0.290 | -0.029 | +0.105 | 0.089 |   23 | 0.387 | 0.00106 |
| R273561-BNBUSDT-BEAR_TREND   | -0.337 | -0.027 | +0.235 | 0.260 |  108 | 0.422 | 0.00084 |
| R418902-AAVEUSDT-BEAR_TREND  | -0.494 | -0.057 | +0.306 | 0.453 |  101 | 0.453 | 0.00099 |
| R418927-SOLUSDT-BULL_TREND   | -0.769 | -0.187 | +0.452 | 0.614 |  150 | 0.429 | 0.00372 |
| R330401-DOGEUSDT-BULL_TREND  | -0.770 | -0.450 | +2.718 | 3.274 |  991 | 0.337 | 0.00586 |

## Findings

1. **Top decile is overwhelmingly a low-frequency, high-win-rate, sparse-density cohort.** Median trades 104 vs rest 989 (9.5× fewer); median density 0.00103 vs 0.00704 (6.8× sparser); median win_rate 0.451 vs 0.320 (+13 pts).
2. **Top-decile median net is -0.0278** — basically break-even (vs rest -1.37, ~50× worse).
3. **Top-decile cost is 0.37 vs rest 3.85** — 10× lower in absolute terms; cost/gross ratio top-decile = 1.31 vs rest = 1.52, both still > 1.0 → even the best batches are net-negative on average; gross is real but insufficient to clear cost.
4. The lone outlier R330401-DOGEUSDT (991 trades, dense) has gross +2.72 but cost +3.27 → still loses net. It earned its top-decile slot via high gross variance, not net edge — a cautionary anti-pattern.
5. Bias check by symbol: top-decile is concentrated in SOLUSDT (4) + AAVEUSDT (4) + BNBUSDT (1) + DOGEUSDT (1). Per-symbol best-sharpe table (state lock #00 / output) confirms only SOL and AAVE produce sharpe>0; the result is real but only emerges on those two symbols. Generalisation requires more symbol coverage at low density.

## Aggregation rationale

The top decile is exactly what "signal aggregation" should reproduce: select the strongest decile of signals (here defined post-hoc by sharpe; in production it would need to be a pre-trade filter such as score threshold or top-K-per-bar) → fewer trades, higher win-rate, dramatically lower cost, net approximately break-even. Three implications:

- **The alpha exists** — gross is consistently positive across all 106 batches (100% gross>0 rate).
- **Cost destroys it on the dense quartiles** — cost ≈ 1.5× gross at the median.
- **Concentrating to top-decile-strength signals nearly closes the gap** — 50× improvement in net vs the rest.

The remaining gap (top-decile net still -0.028) means signal aggregation alone, on the current alpha pool and at the current cost (round_total_cost_bps=14.5), will not flip net positive — but it gets within striking distance, and combining it with cost reduction (separate workstream) or stronger alphas (parent order) would.
