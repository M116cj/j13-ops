# 02 — DEPLOYABLE ATTEMPT ANALYSIS

**TEAM ORDER**: 0-9Y-HE5-DEPLOYABLE-FLOW-RECHECK
**Date**: 2026-04-29
**Phase**: 2 / 8

## Two cohorts to analyze

### Cohort 1 — manual_seed alphas in DB pipeline (89 fresh + 184 staging)
| Metric | Fresh (n=89) | Staging (n=184) |
|---|---:|---:|
| arena1_score (avg) | 0.846 | 0.868 |
| arena1_win_rate (avg) | 0.615 | 0.619 |
| arena1_pnl (avg) | 0.301 | 0.325 |
| arena1_n_trades (avg) | 1076.4 | 1075.8 |
| arena1_pnl (max in staging) | — | **0.716** |
| arena2_win_rate | NULL | NULL |
| arena2_n_trades | NULL | NULL |

These bootstrapped alphas (v0.7.2 cold-start injection from `cold_start_hand_alphas.py`) **do not have A2 metrics** because A2's reconstruction phase rejected them at `total_trades < 25` gate (per `arena23_orchestrator.py:779`). The `arena2.error: see_engine_log_for_reject_reason` placeholder confirms this.

**Closest manual_seed alpha to deployable**: passport id=88, formula `add(sub(vwap_7, close), correlation_20(vwap_20, sub(close, delta_5(close))))`, A1 sharpe=0.998, A1 PnL=+0.65, A1 win_rate=0.61, A1 trades=1074. Strong A1 metrics but A2 rejection unresolved.

### Cohort 2 — GP-discovered alphas (HE4 live shadow window, 3266 batches × 10 alphas)
Top 5 batches by `train_net_pnl_median` (closest to break-even):

| Rank | Net PnL | Gross | Trades | Win Rate | Cost/Gross | Symbol | Horizon |
|---:|---:|---:|---:|---:|---:|---|---:|
| 1 | **+0.0000** | 0.0 | 0 | 0.0 | — | XRPUSDT | 240 |
| 2 | **+0.0000** | 0.0 | 0 | 0.0 | — | XRPUSDT | 240 |
| 3 | -0.2651 | +1.374 | 526 | 0.379 | 1.193 | XRPUSDT | 360 |
| 4 | -0.2876 | +2.780 | 922 | 0.385 | 1.103 | DOGEUSDT | 360 |
| 5 | -0.3178 | +2.841 | 997 | 0.332 | 1.112 | DOGEUSDT | 240 |

(Ranks 1-2 are degenerate batches with 0 trades — `gross=0, net=0` zero-vacuous; not real candidates.)

**Real-alpha closest cohort (rank 3+)**: `XRPUSDT @ h=360`, net=-0.27 bps, win_rate=0.379, trades=526, cost/gross=1.19. Best non-degenerate batch is **−0.27 bps below break-even**.

## Distribution: how close to positive?
| Threshold | Batches with net > X (out of 3266) | % |
|---|---:|---:|
| net > -0.10 | 2 (incl 2 zero-trade degenerate) | 0.06% |
| net > -0.05 | 2 | 0.06% |
| **net > 0.00** | **0** | **0.00%** |
| net > +0.05 | 0 | 0.00% |

**No GP-discovered batch has crossed net > 0.** The closest meaningful batch is -0.27 bps below break-even, and over 99.94% of batches are at net < -0.30 bps.

## How far from break-even?

### Manual_seed alphas (Cohort 1)
- A1 PnL = 0.30 (positive in A1 backtest with V10 alpha-expression cost model)
- A2 rejected because A2's V9 signal-reconstruction backtest produces fewer than 25 trades
- The **gap is not economic edge** but a **stage-mismatch** between A1 (uses alpha-expression directly) and A2 (reconstructs threshold signals from the alpha and re-tests)
- These alphas might pass A2 with code changes to the signal-reconstructor — but those changes potentially affect A2 pass/fail logic which is **forbidden** by HE5 hard rules

### GP-discovered alphas (Cohort 2)
- Best real batch: -0.27 bps below break-even
- Median: -1.22 bps below break-even
- 95th percentile: ≈ -0.80 bps below break-even
- Worst: -2.59 bps below break-even

The economic gap is **a function of cost burning roughly 1.5× of gross edge** — a structural cost-vs-gross imbalance, not a small tweak away from positive.

## Verdict
**No alpha — neither manual_seed nor GP-discovered — has crossed net > 0 in any window analyzed.** The closest meaningful gap is ~0.27 bps, and the median is ~1.22 bps below break-even.

Per master-order Phase 1 enum: **NEAR_DEPLOYABLE** classification does NOT apply — no alpha approaches deployable economic threshold.

## Next
Phase 3 — failure-mode decomposition (EDGE_TOO_WEAK / COST_TOO_HIGH / TRADE_POLICY_INEFFICIENT).
