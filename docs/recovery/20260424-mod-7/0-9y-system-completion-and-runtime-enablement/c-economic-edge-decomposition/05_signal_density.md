# 05 — Signal Density Analysis

Source: Alaya `/tmp/c_batches_snapshot.jsonl` (n=106 batches)

## Distributions

### `signal_density_per_bar` (= total_trades / 140000 bars)
| stat | value |
|---|---|
| n | 106 |
| min | 0.000567 |
| p10 | 0.003751 |
| p25 | 0.006770 |
| p50 (median) | 0.007022 |
| p75 | 0.007101 |
| p90 | 0.007587 |
| max | 0.008060 |
| mean | 0.006386 |
| stdev | 0.001780 |

Interpretation: ~1 signal per ~140 bars (≈ every 23 minutes on 1m data); tightly clustered around 0.007. Only the bottom decile is genuinely sparse.

### `train_total_trades_median`
| stat | value |
|---|---|
| n | 106 |
| min | 23 |
| p10 | 243 |
| p25 | 976 |
| p50 | 986.5 |
| p75 | 997 |
| p90 | 1099 |
| max | 1133 |
| mean | 902.4 |
| stdev | 284.4 |

Median alpha generates ~987 trades over the 140k-bar window — ample sample size; sparsity is not the bottleneck.

### `train_win_rate_median`
| stat | value |
|---|---|
| n | 106 |
| min | 0.2755 |
| p10 | 0.2937 |
| p25 | 0.3063 |
| p50 | 0.3244 |
| p75 | 0.3834 |
| p90 | 0.4404 |
| max | 0.4944 |
| mean | 0.3489 |

Win-rate fractions: WR ≥ 40% → 21/106 (19.8%); WR ≥ 45% → 5/106 (4.7%); **WR ≥ 50% → 0/106 (0%)**; WR ≥ 55% → 0/106.

## Quartile bins — density vs net

| Q | density range | n | net_med | wr_med | trades_med |
|---|---|---|---|---|---|
| Q1 (sparsest) | 0.00057 – 0.00670 | 26 | **−0.288** | **0.420** | 606 |
| Q2 | 0.00677 – 0.00702 | 27 | −1.333 | 0.297 | 977 |
| Q3 | 0.00703 – 0.00709 | 26 | −1.674 | 0.319 | 991 |
| Q4 (densest) | 0.00710 – 0.00806 | 27 | −1.372 | 0.352 | 1047 |

## Quartile bins — trades vs net

| Q | trades range | n | net_med | wr_med |
|---|---|---|---|---|
| Q1 (fewest trades) | 23 – 975 | 26 | **−0.288** | 0.404 |
| Q2 | 976 – 986.5 | 27 | −1.404 | 0.306 |
| Q3 | 987.5 – 995 | 26 | −1.748 | 0.320 |
| Q4 (most trades) | 997 – 1133 | 27 | −1.246 | 0.378 |

## Interpretation

Counter-intuitively, the **sparsest** quartile has the **best** net (−0.29) and the **highest** win rate (0.42), while dense quartiles cluster around net ≈ −1.3 to −1.7. This inverts a "sparsity → rejection" hypothesis: more signals → more cost-bleed at WR ≈ 0.31, not less. The dominant problem is not insufficient signal — median alpha fires 987 trades, gross_pnl_med = 2.41 — but that with WR_med = 0.32 (zero alphas reach 50%) and round-trip cost 14.5 bps, every additional trade burns 14.5 bps × (1 − 2·WR) ≈ negative expectancy. Cutting trade count (Q1 strategies) reduces cost-bleed faster than it loses gross, hence the better net. To beat 14.5 bps round-trip, an alpha needs avg_win/avg_loss ≈ (1−W)/W × (1 + cost/edge) — at WR = 0.32 this requires ~2.2× payoff ratio, which the gross/win-rate combo isn't producing.

## Verdict

**SUFFICIENT_DENSITY_BUT_LOW_WIN_RATE** — density and trade count are adequate (median ~987 trades, p25 = 976); the binding constraint is win rate (median 0.32, **0/106 reach 50%**) compounded by round-trip cost 14.5 bps. Sparser alphas perform better precisely because they bleed less cost at the prevailing low WR.
