# 01 — Metric Source Map (Subprogram B1)

Maps each field requested by the master order to its **runtime source of truth** in the existing codebase. "Available" means the value is already computed by the engine and only needs plumbing into telemetry.

## Required fields → source

| Field | Source | Status |
|---|---|---|
| `gross_pnl` | `zangetsu/engine/components/backtester.py:31` (`BacktestResult.gross_pnl`) | ✅ AVAILABLE |
| `net_pnl` | `BacktestResult.net_pnl` (line 32); also at `arena_pipeline.py:1083` reject site | ✅ AVAILABLE |
| `total_cost` | derived as `gross_pnl - net_pnl` per alpha; also `cost_model.get(sym).total_round_trip_bps` is the per-trade cost in bps | ✅ DERIVABLE |
| `fee_cost` | not separated in `BacktestResult`; `cost_per_trade` is a single bps value applied per round-trip | ❌ UNAVAILABLE (availability flag = False) |
| `slippage_cost` | same as fee_cost — bundled in `cost_per_trade` | ❌ UNAVAILABLE |
| `funding_cost` | same — bundled | ❌ UNAVAILABLE |
| `trade_count` | `BacktestResult.total_trades` (line 27) | ✅ AVAILABLE |
| `long_trade_count` | `trade_log` numpy array carries direction, but extracting requires post-processing not currently in BacktestResult | ❌ UNAVAILABLE without engine change |
| `short_trade_count` | same | ❌ UNAVAILABLE without engine change |
| `signal_density` | derivable as `total_trades / num_bars_in_train_window` (140000 bars constant) | ✅ DERIVABLE |
| `train_pnl` | `bt.net_pnl` from train backtest at `arena_pipeline.py:1062` | ✅ AVAILABLE |
| `val_pnl` | `bt_val.net_pnl` from val backtest at `arena_pipeline.py:1125` | ✅ AVAILABLE |
| `train_sharpe` | `bt.sharpe_ratio` (line 33) | ✅ AVAILABLE |
| `val_sharpe` | `bt_val.sharpe_ratio` | ✅ AVAILABLE |
| `combined_sharpe` | computed at `arena_pipeline.py:1160` as `(bt.sharpe + bt_val.sharpe)/2` | ✅ AVAILABLE |
| `primary_reject_gate` | implicit via `stats[reject_*]` increments + `top_reject_reason` in event | ✅ INDIRECT (top_reject_reason already on event) |
| `formula_family / profile_id` | already on event as `generation_profile_id` (0-9O-A) | ✅ ALREADY EXPOSED |

## Coverage decision

- **Available / Derivable (10 fields):** plumb through aggregate_metrics dict.
- **Unavailable (6 fields):** mark with availability flag = False (per master order: "add explicit null fields with availability flags rather than inventing values").

## Aggregation strategy

Each batch evaluates ~10–2000 alphas (POP_SIZE × N_GEN). Per-alpha values are accumulated into lists during the round; at batch close, both **median** and **mean** are computed for the most diagnostic fields. Median is preferred for skewed distributions (PnL, sharpe), mean as a sanity check.

```
train_gross_pnl_median, train_gross_pnl_mean
train_net_pnl_median,  train_net_pnl_mean
train_gross_minus_net_median (= total_cost equivalent)
train_total_trades_median, train_total_trades_mean
train_sharpe_median
train_win_rate_median
val_net_pnl_median
val_total_trades_median
val_sharpe_median
combined_sharpe_median
signal_density_per_bar (= mean_total_trades / 140000)
```

Plus identifiers: `symbol`, `regime`, `lane`, `round_total_cost_bps`, `alphas_with_train_backtest`, `alphas_with_val_backtest`, `alphas_with_combined_sharpe`.

## Schema location

Both fields are added to:
- `zangetsu/services/arena_pass_rate_telemetry.py: ArenaBatchMetrics` (the frozen event)
- `zangetsu/services/arena_pass_rate_telemetry.py: ArenaStageMetrics` (the mutable accumulator)

Defaults are `None` — backward-compat for any consumer that pre-dates 0-9Y-B1.
