# 03 — Per-Cohort Breakdown (Subprogram-C)

**Source**: Alaya `/tmp/c_batches_snapshot.jsonl` (106 post-restart `arena_batch_metrics` events, all with valid `train_gross_pnl_median` + `train_gross_minus_net_median`).
**Method**: group by `symbol`, `regime`, `lane`, plus `symbol × regime` cross-tab. All metrics are medians of batch-level medians (no double-aggregation distortion: each batch contributes one observation).
**Cost** = `train_gross_minus_net_median`, **Gross** = `train_gross_pnl_median`. "g>c" = batches in cohort where `gross > cost`.

## Population baseline
- Batches where `gross > cost`: **4 / 106 (3.8%)**.
- Net median across all batches: negative everywhere.

## By symbol (sorted best gross/cost ratio first)

| symbol         | n  | med_gross | med_cost | med_net | g>c | gross/cost |
|----------------|----|-----------|----------|---------|-----|------------|
| XRPUSDT        | 10 |  2.528    |  3.139   | -0.615  |  0  | 0.806      |
| DOGEUSDT       |  6 |  2.700    |  3.420   | -0.784  |  0  | 0.790      |
| SOLUSDT        |  8 |  0.433    |  0.577   | -0.182  |  3  | 0.750      |
| ETHUSDT        |  2 |  2.261    |  3.150   | -0.870  |  0  | 0.718      |
| AAVEUSDT       | 13 |  2.576    |  3.642   | -0.747  |  1  | 0.707      |
| FILUSDT        |  8 |  3.041    |  4.388   | -1.376  |  0  | 0.693      |
| AVAXUSDT       |  4 |  2.349    |  3.465   | -1.183  |  0  | 0.678      |
| 1000PEPEUSDT   |  7 |  3.293    |  4.989   | -1.730  |  0  | 0.660      |
| BTCUSDT        |  3 |  1.570    |  2.433   | -0.896  |  0  | 0.645      |
| BNBUSDT        |  7 |  1.480    |  2.407   | -0.828  |  0  | 0.615      |
| DOTUSDT        |  4 |  2.680    |  4.373   | -1.671  |  0  | 0.613      |
| GALAUSDT       | 13 |  2.791    |  4.677   | -1.904  |  0  | 0.597      |
| LINKUSDT       | 13 |  2.002    |  3.437   | -1.433  |  0  | 0.582      |
| 1000SHIBUSDT   |  8 |  2.316    |  4.048   | -1.721  |  0  | 0.572      |

**No symbol** has `med_gross > med_cost`. Best ratio (XRPUSDT) recovers only 80.6% of cost.

## By regime

| regime         | n  | med_gross | med_cost | med_net | g>c | gross/cost |
|----------------|----|-----------|----------|---------|-----|------------|
| BEAR_TREND     | 40 |  2.494    |  3.612   | -0.978  |  1  | 0.690      |
| BULL_TREND     | 40 |  2.242    |  3.440   | -1.385  |  3  | 0.652      |
| CONSOLIDATION  | 26 |  2.528    |  4.046   | -1.376  |  0  | 0.625      |

All three regimes shortfall ~30–37% of cost. Tight band; no regime exception.

## By lane

| lane         | n  | med_gross | med_cost | med_net | g>c | gross/cost |
|--------------|----|-----------|----------|---------|-----|------------|
| baseline     | 50 |  2.538    |  3.905   | -1.565  |  0  | 0.650      |
| exploration  | 56 |  2.050    |  3.509   | -1.224  |  4  | 0.584      |

Both lanes lose. All 4 individual `gross > cost` batches sit in `exploration` (rare hits, not cohort-level edge).

## Top 5 (symbol × regime) cells by gross-cost differential

| rank | symbol      | regime         | n  | med_gross | med_cost | diff    | g>c | ratio  |
|------|-------------|----------------|----|-----------|----------|---------|-----|--------|
| 1    | SOLUSDT     | BULL_TREND     |  8 |  0.433    |  0.577   | -0.144  | 3   | 0.750  |
| 2    | XRPUSDT     | CONSOLIDATION  | 10 |  2.528    |  3.139   | -0.611  | 0   | 0.806  |
| 3    | DOGEUSDT    | BULL_TREND     |  6 |  2.700    |  3.420   | -0.720  | 0   | 0.790  |
| 4    | BTCUSDT     | BEAR_TREND     |  3 |  1.570    |  2.433   | -0.863  | 0   | 0.645  |
| 5    | ETHUSDT     | BULL_TREND     |  2 |  2.261    |  3.150   | -0.889  | 0   | 0.718  |

`CELLS_WITH_MED_GROSS_GT_MED_COST = 0 / 14`. The closest cohort (SOLUSDT/BULL_TREND) is closest only because its **cost is also tiny** (0.577) — gross is the lowest of any cohort, the alpha is weak in absolute terms, not strong-net-of-cost.

## Concentration test

- CV of `med_gross` across symbols: **0.321**
- CV of `med_cost`  across symbols: **0.328**

Gross dispersion mirrors cost dispersion almost exactly — symbols with bigger alphas also have proportionally bigger cost drag. Rejection is **uniform**, not concentrated.

## Interpretation

No symbol, no regime, no lane, and no (symbol × regime) cell has median gross exceeding median cost. The best ratio (XRPUSDT, 0.806) still leaves ~19% of cost uncovered. The 4 individual batches where `gross > cost` (out of 106) are scattered across SOLUSDT (3) and AAVEUSDT (1), all in `exploration` — long-tail noise, not a stable cohort. CV(gross) ≈ CV(cost) confirms gross and cost scale together; the population mean is **not** masking a hidden cohort edge.

## Verdict for Subprogram-C synthesis

**UNIFORM** — no cohort beats cost. Rejection is genuinely cost-driven across the entire post-restart batch population. There is no per-symbol, per-regime, or per-lane segmentation that would unlock economic edge. The reject-100% outcome reflects the alpha generator's economic state, not a population-mean artifact.
