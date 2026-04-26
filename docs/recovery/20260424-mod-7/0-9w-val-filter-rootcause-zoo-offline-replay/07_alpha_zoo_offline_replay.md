# 07 — alpha_zoo Offline Validation Replay

## 1. Replay Setup

| Field | Value |
| --- | --- |
| Script | `/tmp/0-9wzr-offline-replay.py` (read-only, no DB connection) |
| Imports | `compile_formula`, `evaluate_and_backtest`, `load_symbol_data`, `build_indicator_cache`, `wilson_lower` from `cold_start_hand_alphas`; `AlphaEngine`, `Backtester`, `Settings`, `j01.fitness.fitness_fn` |
| Formulas | 30 from `alpha_zoo_injection.py:ZOO` |
| Symbols sampled | BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT (top 5 by liquidity / market cap) |
| Total evaluations | 30 × 5 = **150** |
| Wall time | 11.8 s (caches pre-built, evaluated 150 alpha-symbol combos in ~12 sec) |
| DB connection opened | NO |
| DB write attempted | NO |

## 2. Val Gates Applied (matching arena_pipeline.py:950-1043 exactly)

| # | Gate | Threshold |
| --- | --- | --- |
| 1 | compile success | exception → continue |
| 2 | train_few_trades | `bt_train.total_trades < 30` |
| 3 | val_few_trades | `bt_val.total_trades < 15` |
| 4 | val_neg_pnl | `bt_val.net_pnl <= 0` |
| 5 | val_low_sharpe | `bt_val.sharpe_ratio < 0.3` |
| 6 | val_low_wr | `wilson_lower(...) < 0.52` |
| 7 | val_error | exception during val backtest |

(The replay omits the train_neg_pnl gate that cold_start_hand_alphas adds, to match the live A1 path.)

## 3. Result Summary

```
total: 150
compile_fail: 0
train_few_trades: 0
val_few_trades: 0
val_neg_pnl: 130     ← 87% — the dominant rejection
val_low_sharpe: 0
val_low_wr: 0
val_error: 20       ← 13% — backtest exception, likely on extreme-cycle symbol
survivor: 0
```

| Result | Count | % |
| --- | --- | --- |
| compile-pass | 150 | 100% |
| train-pass (≥30 train trades) | 150 | 100% |
| val-error | 20 | 13% |
| **val_neg_pnl** | **130** | **87%** |
| **survivors** | **0** | **0%** |

## 4. Per-Source Pass Rate

| Source | Total | Survivors | Pass rate |
| --- | --- | --- | --- |
| wq101 (WorldQuant 101) | 35 | 0 | 0% |
| qlib (Alpha158) | 25 | 0 | 0% |
| alpha191 (GuotaiJunan) | 15 | 0 | 0% |
| qp (Quantpedia) | 10 | 0 | 0% |
| cogalpha (arXiv) | 5 | 0 | 0% |
| alphagen (arXiv) | 5 | 0 | 0% |
| alphaforge (arXiv) | 10 | 0 | 0% |
| wqb (WQ BRAIN) | 15 | 0 | 0% |
| ind (ZANGETSU indicator-based) | 30 | 0 | 0% |
| **all 9 sources** | **150** | **0** | **0%** |

## 5. Train PnL Distribution (the smoking gun)

For the 130 evaluations that completed train backtest:

| Stat | Value |
| --- | --- |
| min train_pnl | **-1.81** |
| max train_pnl | **-0.21** |
| mean train_pnl | -1.19 |
| median train_pnl | -1.21 |
| count train_pnl > 0 | **0** |
| count train_pnl == 0 | 0 |
| count train_pnl < 0 | 130 (100%) |

**Every single canonical hand-translated formula has negative train PnL on every tested symbol.**

## 6. Top 10 Best train_pnl (still all negative)

| Source tag | Symbol | train_pnl | train_trades | train_wr |
| --- | --- | --- | --- | --- |
| qp_tsmom | BTCUSDT | -0.2090 | 258 | 0.368 |
| qp_tsmom | ETHUSDT | -0.3661 | 241 | 0.432 |
| qp_tsmom | BNBUSDT | -0.3800 | 282 | 0.351 |
| qp_tsmom | XRPUSDT | -0.3886 | 349 | 0.395 |
| qp_tsmom | SOLUSDT | -0.5486 | 319 | 0.408 |
| wqb_s01 | SOLUSDT | -0.6156 | 1003 | 0.527 |
| wq101_42 | SOLUSDT | -0.7122 | 1000 | 0.522 |
| ind_bbw_delta | XRPUSDT | -0.7432 | 1016 | 0.422 |
| alpha191_5 | BTCUSDT | -0.8003 | 1107 | 0.385 |
| qlib_roc_20 | ETHUSDT | -0.8328 | 1057 | 0.403 |

The **best** alpha is `qp_tsmom = sign_x(delta_20(close))` — a textbook 20-bar time-series momentum signal — which loses 21% of equity on BTCUSDT TRAIN. That is the universally-cited starting point for crypto trend-following research.

## 7. Per-Formula Best Symbol PnL (top 10)

| max train_pnl | mean train_pnl across 5 syms | formula |
| --- | --- | --- |
| -0.21 | -0.38 | `sign_x(delta_20(close))` |
| -0.62 | -0.99 | `neg(sub(close, scale(close)))` |
| -0.71 | -0.99 | `protected_div(sub(vwap_20, close), add(vwap_20, close))` |
| -0.74 | -1.00 | `delta_20(bollinger_bw_20)` |
| -0.80 | -1.15 | `neg(ts_max_3(correlation_5(ts_rank_5(volume), ts_rank_5(high))))` |
| -0.83 | -1.25 | `neg(protected_div(delta_20(close), close))` |
| -0.84 | -1.14 | `neg(correlation_5(high, ts_rank_5(volume)))` |
| -0.91 | -1.08 | `neg(correlation_10(open, volume))` |
| -0.93 | -1.19 | `protected_div(sub(close, ts_min_20(low)), sub(ts_max_20(high), ts_min_20(low)))` |
| -0.94 | -1.28 | `neg(protected_div(mul(sub(low, close), pow5(open)), mul(sub(low, high), pow5(close))))` |

## 8. Phase 7 Classification

Per order §16:

| Verdict | Match? |
| --- | --- |
| ZOO_REPLAY_HAS_SURVIVORS | NO (0 survivors) |
| **ZOO_REPLAY_ALL_FAIL_VAL_NEG_PNL** | partial — accurate for the 130 that completed val backtest, all of which fell at val_neg_pnl |
| ZOO_REPLAY_NUMERIC_FAILURE | partial (val_error 20/150 = 13%) |
| ZOO_REPLAY_COMPILE_FAILURE | NO (0 compile failures) |
| ZOO_REPLAY_NOT_EXECUTABLE_READONLY | NO (replay ran successfully) |
| ZOO_REPLAY_BLOCKED | NO |

→ **Phase 7 verdict: ZOO_REPLAY_ALL_FAIL_VAL_NEG_PNL** with the additional finding that **train_pnl is also universally negative** — the failure is not just OOS; even canonical alphas can't make money on train under current cost / threshold / horizon settings.

## 9. Output Artifacts

| File | Content |
| --- | --- |
| `/tmp/0-9wzr-offline-replay-results.jsonl` | 150 lines, one per evaluation, full attribute dump |
| `/tmp/0-9wzr-offline-replay-survivors.jsonl` | 0 lines (no survivors) |
| `/tmp/0-9wzr-offline-replay-summary.json` | aggregated counts + by-source rollup |
