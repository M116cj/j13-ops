# 01 — BASELINE FREQUENCY & COST SNAPSHOT

**TEAM ORDER**: 0-9Y-TF2-SIGNAL-AGGREGATION-PROTOTYPE
**Date**: 2026-04-28
**Phase**: 1 / 8

## Source
`/home/j13/j13-ops/zangetsu/logs/engine.jsonl` — most recent **300 arena_batch_metrics events** (event_type filter).

## Conservation identity (sanity)
| Field | Total over 300 batches |
|---|---|
| `entered_count` | **3000** |
| `passed_count` | 0 |
| `rejected_count` | 3000 |
| `skipped_count` | 0 |
| `in_flight_count` | 0 |
| `error_count` | 0 |
| **residual** = entered − Σ(passed+rejected+skipped+in_flight+error) | **0** ✅ |
| `UNKNOWN_REJECT` | 0 ✅ |
| `COUNTER_INCONSISTENCY` | 0 ✅ |

## Reject reason distribution
| Reason | Count |  % |
|---|---|---|
| `COST_NEGATIVE` | 2998 | **99.93%** |
| `LOW_BACKTEST_SCORE` | 2 | 0.07% |

**Cost is the dominant rejector** — confirms master-order economic decomposition `DECOMPOSED_GROSS_EDGE_LOST_TO_COST`.

## Pass / reject rate
- 300 / 300 batches at **reject_rate = 100%**
- **0 deployable_count** for all 300 batches (cold start, never produced live champion)

## Aggregate metrics summary (300 batches)
| Metric | n | median | min | max |
|---|---|---|---|---|
| `train_gross_pnl_median` (bps) | 300 | **2.358** | 1.513 | 4.458 |
| `train_gross_minus_net_median` (bps) | 300 | **3.496** | 2.344 | 6.357 |
| `train_net_pnl_median` (bps) | 300 | **−1.303** | −3.183 | −0.343 |
| `train_sharpe_median` | 300 | −2.405 | −5.878 | −0.660 |
| `train_win_rate_median` | 300 | **0.3135** | 0.2651 | 0.4862 |
| `train_total_trades_median` | 300 | **982** | 922 | 1149 |
| `train_total_trades_mean` | 300 | 979.75 | 745.6 | 1108.1 |
| `signal_density_per_bar` | 300 | **0.00700** | 0.00533 | 0.00792 |
| `round_total_cost_bps` | 300 | **14.5** | 11.5 | 23 |
| `alphas_with_train_backtest` | 300 | 10 | 10 | 10 |
| `val_net_pnl_median` | 1 | 0.001977 | — | — |
| `val_sharpe_median` | 1 | 0.057508 | — | — |
| `val_total_trades_median` | 1 | 43 | — | — |

(val_* metrics emitted in only 1 of 300 batches → val backtest not running for current cycles)

## Cost / Gross ratio (per batch)
- **median = 1.555** ✅ (master-order baseline says 1.54x)
- min 1.137 / max 2.924
- Distribution skewed right; some batches have cost > 2× gross.

## Gross-per-trade proxy
- (median train_gross_pnl_median) / (median train_total_trades_median) ≈ **0.00242 bps/trade**
- Confirms low edge-per-trade — diluted by ~982 trades/batch

## Symbol concentration (top 11)
| Symbol | Batches |
|---|---|
| LINKUSDT | 61 (20.3%) |
| AVAXUSDT | 47 (15.7%) |
| DOGEUSDT | 31 (10.3%) |
| GALAUSDT | 27 ( 9.0%) |
| 1000SHIBUSDT | 25 ( 8.3%) |
| FILUSDT | 24 ( 8.0%) |
| BNBUSDT | 21 ( 7.0%) |
| ETHUSDT | 19 ( 6.3%) |
| BTCUSDT | 18 ( 6.0%) |
| XRPUSDT | 15 ( 5.0%) |
| (others) | balance |

11 unique symbols across 300 batches; top-5 ≈ 63%. Mild concentration, **no single-symbol artifact** by 80% threshold.

## TF2 hypothesis link
TF1 finding: 9.5× sparser cohorts had WR ≈ 0.45 vs 0.32 baseline. Current `train_win_rate_median = 0.3135` matches the reported 0.32 baseline — sparser path is the working hypothesis to explore in Phase 2 design.

## Classification
**BASELINE_CONFIRMS_COST_BURN** ✅

- Telemetry available, conservation holds, no UNKNOWN/COUNTER errors
- Cost dominates rejection (99.93%)
- Cost/gross ratio = 1.555 vs gross 2.358 → net = −1.303 (cost overpowers gross by ~1.55×)
- Trade frequency very high (~982 trades / batch median); reducing trade count is the natural lever

## Next
Proceed to Phase 2 — Signal Aggregation Design.
