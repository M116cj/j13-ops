# 02 — Trade count decomposition: net, cost, win_rate, gross/trade

n = 106. Per-batch metric is the median across the 10 alphas in that batch. `gross_per_trade = train_gross_pnl_median / train_total_trades_median` (in summed-bps space — interpret as relative ranking, not literal bps).

## Trade-count quartile cuts

| Cut | trades_med |
|-----|-----------:|
| Q1 upper | 976 |
| Q2 upper (median) | 987 |
| Q3 upper | 996 |

Q2-Q4 sit in a tight 976-1133 range. Q1 alone reaches as low as 23 trades.

## Quartile aggregates

| Q | n | trades range | gross_med | cost_med | **net_med** | sharpe_med | win_rate_med | **gross/trade_med** |
|---|---|--------------|----------:|---------:|------------:|-----------:|-------------:|---------------------:|
| Q1 (few)  | 29 | 23-976  | +1.5704 | 2.4195 | **-0.4995** | -1.1922 | 0.3471 | **+0.002595** |
| Q2        | 24 | 976-986 | +2.5380 | 4.0460 | **-1.4069** | -2.1787 | 0.3081 | **+0.002596** |
| Q3        | 26 | 988-995 | +2.7878 | 4.6157 | **-1.7476** | -2.7630 | 0.3195 | **+0.002815** |
| Q4 (many) | 27 | 997-1133 | +2.2232 | 3.8215 | **-1.2459** | -2.3019 | 0.3777 | **+0.002131** |

## Q1 vs Q4 head-to-head (trade count)

- net_med Q1 median = -0.4995 vs Q4 median = -1.2459 → **delta +0.7464**
- P(tradesQ1 > tradesQ4) empirical AUC = **0.8289** (649/783 pairwise wins)

## Cost decomposition

Cost scales near-linearly with trade count: Q1 cost 2.42 → Q4 cost 3.82 (+58%). Gross PnL grows from Q1 +1.57 → Q3 +2.79 (+78%) then drops at Q4. Cost outpaces gross at Q3-Q4: per-trade gross declines (Q3 +0.00282 → Q4 +0.00213), suggesting **late marginal trades have lower expectancy than early ones — classic over-trading signature.**

## Correlations (n=106)

| pair | Pearson | Spearman |
|------|--------:|---------:|
| trades vs **net_pnl** | **-0.6479** | **-0.4810** |
| trades vs gross_pnl | +0.8106 | +0.3400 |
| trades vs **cost** | **+0.8263** | +0.4559 |
| trades vs sharpe | -0.5817 | -0.4397 |
| trades vs win_rate | -0.5188 | +0.1624 |
| trades vs **gross/trade** | **-0.3664** | -0.2793 |
| density vs net_pnl | -0.6511 | -0.5009 |
| density vs sharpe | -0.6021 | -0.4267 |

Key reads:

1. **trades ↔ cost (+0.83 P)**: cost is mechanically driven by trade count. No surprise but quantifies the leak.
2. **trades ↔ gross (+0.81 P)**: more trades capture more raw PnL — alpha exists.
3. **trades ↔ net (-0.65 P / -0.48 S)**: but cost wins, so net flips sign of the relationship.
4. **trades ↔ gross/trade (-0.37 P / -0.28 S)**: per-trade expectancy decays with frequency — the **alpha is not uniform**, late trades are weaker.
5. **trades ↔ win_rate**: Pearson is misleading (-0.52) because Q4 actually has the highest win_rate (0.378) due to leverage of high-frequency outliers; Spearman (+0.16) is closer to truth — weakly positive, no monotone signal.

## Profitability rate

| Quartile | net>0 batches | gross>0 batches | sharpe>0 batches |
|----------|---------------|-----------------|------------------|
| trades Q1 | 2 / 29 (6.9%) | 29 / 29 (100%) | 3 / 29 (10.3%) |
| trades Q2 | 0 / 24 (0%) | 24 / 24 (100%) | 0 / 24 (0%) |
| trades Q3 | 0 / 26 (0%) | 26 / 26 (100%) | 0 / 26 (0%) |
| trades Q4 | 0 / 27 (0%) | 27 / 27 (100%) | 0 / 27 (0%) |

Gross is 100% positive everywhere — alpha exists at all densities. Net and Sharpe positive batches concentrate exclusively in Q1 (low-trade cohort).

## Verdict (this dimension)

Trade frequency is materially anti-correlated with net edge: |Pearson| 0.65 with strong p<0.001 at n=106. Cost mechanism (+0.83 with trades) explains most of it. Per-trade gross decay (-0.37 with trades) explains the rest — the engine is forcing weaker-quality trades when it ramps frequency.
