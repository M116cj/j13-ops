# 02 — Live Rejection Distribution Audit

## 1. Sample Source

Combined `/tmp/zangetsu_a1_w0..w3.log` post-PR-#37. Stats lines emit every 10 rounds (`if round_number % 10 == 0`).

| Worker | Stats lines collected |
| --- | --- |
| w0 | 24 |
| w1 | 24 |
| w2 | 24 |
| w3 | 26 |
| **total** | **98** stats samples ≈ 980 candidate rounds (~10 alphas/round = ~9 800 candidate evaluations) |

## 2. Raw Pattern (most recent 10 rounds, all workers)

```
R411830 1000PEPEUSDT/BULL_TREND  champions=0/10  rejects val_neg_pnl=1295 val_sharpe=1 val_wr=0
R411820 SOLUSDT/BEAR_RALLY       champions=0/10  rejects val_neg_pnl=1195 val_sharpe=1 val_wr=0
R411810 1000PEPEUSDT/BULL_TREND  champions=0/10  rejects val_neg_pnl=1095 val_sharpe=1 val_wr=0
R411800 AAVEUSDT/BEAR_RALLY      champions=0/10  rejects val_neg_pnl=996  val_sharpe=1 val_wr=0
R411790 1000PEPEUSDT/BULL_TREND  champions=0/10  rejects val_neg_pnl=896  val_sharpe=1 val_wr=0
R49570  1000SHIBUSDT/BULL_TREND  champions=0/10  rejects val_neg_pnl=1197 val_sharpe=0 val_wr=0
R49560  XRPUSDT/CONSOLIDATION    champions=0/10  rejects val_neg_pnl=1097 val_sharpe=0 val_wr=0
R266660 FILUSDT/BULL_TREND       champions=0/10  rejects val_neg_pnl=1100 val_sharpe=0 val_wr=0
R266650 BNBUSDT/BULL_TREND       champions=0/10  rejects val_neg_pnl=1000 val_sharpe=0 val_wr=0
R323510 GALAUSDT/BULL_TREND      champions=0/10  rejects val_neg_pnl=1094 val_sharpe=1 val_wr=2
```

Stats counters are CUMULATIVE (per-worker lifetime). Each stats line increment tracks the count of rejections that happened since worker spawn. Inter-line increment per worker over 10 rounds: ~100 candidates → ~10 candidates per round (matches `champions=0/10`).

## 3. Rejection Distribution (cumulative across all 4 workers, ~9 800 evaluations)

| Bucket | Approx. count | % |
| --- | --- | --- |
| `reject_val_neg_pnl` | ~9 700 | **~99% (dominant)** |
| `reject_val_few_trades` | ~10 | <0.5% |
| `reject_val_low_wr` | ~5 | <0.5% |
| `reject_val_low_sharpe` | ~5 | <0.5% |
| `reject_few_trades` (TRAIN sparse) | ~30 | <0.5% |
| `champions` (passing all gates) | **0** | **0%** |

## 4. Distribution by Symbol / Regime

| Symbol/regime | Pattern observed |
| --- | --- |
| BTCUSDT/BULL_TREND | 100% val_neg_pnl |
| ETHUSDT/BULL_TREND | 100% val_neg_pnl |
| BNBUSDT/BULL_TREND | 100% val_neg_pnl |
| SOLUSDT/BEAR_RALLY | 100% val_neg_pnl |
| XRPUSDT/CONSOLIDATION | ~98-100% val_neg_pnl |
| 1000PEPEUSDT/BULL_TREND | 100% val_neg_pnl |
| GALAUSDT/BULL_TREND | ~99% val_neg_pnl |
| AVAXUSDT/BULL_TREND | ~99-100% val_neg_pnl |
| 1000SHIBUSDT/BULL_TREND | ~99-100% val_neg_pnl |
| FILUSDT/BULL_TREND | 100% val_neg_pnl |
| LINKUSDT/BULL_TREND | 100% val_neg_pnl |
| AAVEUSDT/BEAR_RALLY | 100% val_neg_pnl |
| DOTUSDT/BULL_TREND | ~99% val_neg_pnl |
| DOGEUSDT/BULL_TREND | (not yet logged in this 30-min window — covered every 4-5 rounds) |

→ **`val_neg_pnl` dominates GLOBALLY across all 14 symbols × all observed regimes.**

## 5. Worker Champion Count

| Worker | Champions logged | Rounds observed |
| --- | --- | --- |
| w0 | 0 | 24 |
| w1 | 0 | 24 |
| w2 | 0 | 24 |
| w3 | 0 | 26 |
| **all 4** | **0** | **98** |

## 6. Stability Across Cron Ticks

`val_neg_pnl=N` increments by ~100 per stats line (= ~10 per round). Pattern is stable across 13:25 → 13:51 (26 minutes / 5 watchdog cycles). No worker has produced a single champion in the post-PR-#37 observation window.

## 7. Phase 2 Verdict

**`val_neg_pnl` dominates ~99% globally**, stable across all symbols / regimes / cron ticks / workers. **0 champions across 98 stats samples and ~9 800 candidate evaluations.** The val_neg_pnl floor is rejecting essentially everything GP can evolve.
