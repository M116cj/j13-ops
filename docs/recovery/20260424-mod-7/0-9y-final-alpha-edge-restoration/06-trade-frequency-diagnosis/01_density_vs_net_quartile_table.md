# 01 — signal_density_per_bar quartiles vs net economics

n = 106 batches, all stage A1, B1 schema.

## Density quartile cuts

| Cut | density_per_bar |
|-----|-----------------|
| Q1 upper | 0.006795 |
| Q2 upper (median) | 0.007028 |
| Q3 upper | 0.007099 |

The bulk (Q2-Q4) sit in a tight band 0.0068-0.0081 → engine is producing dense signals on most batches; Q1 is the only sparse cohort (0.000567 - 0.006770).

## Quartile aggregates

| Q | n | density range | trades_med | gross_med | cost_med | **net_med** | sharpe_med | net>0 | sharpe>0 |
|---|---|---------------|-----------:|----------:|---------:|------------:|-----------:|------:|---------:|
| Q1 (sparse) | 27 | 0.000567-0.006770 |   635 | +1.4342 | 2.1024 | **-0.3296** | -1.3606 | 2 / 27 (7.4%) | 3 / 27 (11.1%) |
| Q2          | 26 | 0.006870-0.007022 |   977 | +2.5265 | 3.8144 | **-1.3342** | -1.9211 | 0 / 26 (0%) | 0 / 26 (0%) |
| Q3          | 26 | 0.007034-0.007091 |   990 | +2.7470 | 4.1879 | **-1.6736** | -2.9043 | 0 / 26 (0%) | 0 / 26 (0%) |
| Q4 (dense)  | 27 | 0.007101-0.008060 |  1047 | +2.4094 | 3.8441 | **-1.3723** | -2.4146 | 0 / 27 (0%) | 0 / 27 (0%) |

## Q1 vs Q4 head-to-head

| Metric | Q1 | Q4 | delta (Q1 − Q4) |
|--------|----|----|-----------------|
| net_med median | -0.3296 | -1.3723 | **+1.0428** |
| net_med mean   | -0.6024 | -1.4275 | **+0.8250** |
| P(Q1 > Q4) empirical AUC | — | — | **0.8354** (609/729 pairwise wins, 0 ties) |

AUC 0.8354 ≫ 0.5 chance baseline → density is strongly anti-correlated with net.

## Correlations (n=106)

- density vs net_pnl_median:   Pearson **-0.6511**, Spearman **-0.5009**
- density vs sharpe_median:    Pearson **-0.6021**, Spearman **-0.4267**

Both negative, both well above any reasonable significance threshold for n=106 (\|r\|≈0.19 ≈ p<0.05). Direction: **denser signals → worse net & sharpe.**

## Reading

The engine's gross PnL grows with density (Q1 +1.43 → Q3 +2.75) but cost grows faster (Q1 2.10 → Q3 4.19). Net inverts: sparse-quartile batches lose 4× less money than dense-quartile batches at the median. Only Q1 produces any net>0 batch (2/27); Q2-Q4 are 0/79 net-positive. Density is currently destroying net edge.
