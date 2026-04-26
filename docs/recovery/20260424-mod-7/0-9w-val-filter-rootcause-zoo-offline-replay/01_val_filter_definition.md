# 01 — `val_neg_pnl` Definition Audit

## 1. Exact Source Location

`zangetsu/services/arena_pipeline.py:1035-1037`:

```python
if float(bt_val.net_pnl) <= 0:
    stats["reject_val_neg_pnl"] += 1
    continue
```

Where `bt_val` is the result of:

```python
bt_val = backtester.run(
    sig_v,                                    # signals built from val (holdout) alpha values
    d_val["close"].astype(np.float32),         # holdout close
    sym,
    cost_bps,                                  # symbol-specific round-trip cost
    _STRATEGY_MAX_HOLD,                        # j01: 120 bars
    high=d_val["high"].astype(np.float32),
    low=d_val["low"].astype(np.float32),
    sizes=sz_v,
)
```

## 2. Exact Mathematical Condition

`bt_val.net_pnl <= 0` — **strict gate**. Even zero PnL is rejected.

## 3. PnL Type — gross or net?

**NET**. `bt_val` comes from `backtester.run(..., cost_bps, ...)`. cost_bps is the symbol-specific round-trip transaction cost (`cost_model.get(sym).total_round_trip_bps`, line 877) and is applied inside the backtester. So this is **profit AFTER costs** on the holdout slice.

## 4. Holdout Only?

YES. `d_val = data_cache[sym]["holdout"]` (line 988). NO train data leakage. The val backtest uses the holdout slice exclusively.

## 5. Costs Included?

YES. `cost_bps` is the round-trip cost in basis points; the backtester deducts cost on every entry/exit pair.

## 6. Funding Included?

The backtester signature uses `(sig, close, sym, cost_bps, max_hold, high=, low=, sizes=)`. **No funding rate parameter is passed**. Funding is therefore NOT included in this PnL. PnL is `(price-driven moves) - (round-trip cost_bps)`, no funding.

## 7. NaN / inf Handling

`av_val = np.nan_to_num(av_val, nan=0.0, posinf=0.0, neginf=0.0)` (line 1003). So NaN/inf in alpha values become 0.0. Subsequent `np.std(av_val) < 1e-10` catches the constant-zero case as `reject_val_constant` BEFORE the val backtest. Therefore NaN/inf does NOT route to `val_neg_pnl` — it routes to `val_constant`.

## 8. Validation Causal?

YES. Patch E (2026-04-19) explicitly swaps `engine.indicator_cache` to the holdout slice for the val evaluation, then restores the train cache via `finally`. So all indicator terminal lookups during val use the holdout time window only — no train-window leakage into val signal generation.

## 9. Rejected Excluded Before Persistence?

YES. Every gate uses `continue` to abort the per-candidate loop iteration. No INSERT runs unless ALL 9 stages pass.

## 10. Order of Gates

Sequential `continue` chain (each may fire):

| # | Gate | Source line | Condition |
| --- | --- | --- | --- |
| 1 | alpha→signal compile | 949 | exception → continue |
| 2 | train backtest | 957 | exception → continue |
| 3 | train sparse | 965 | `bt.total_trades < 30` |
| 4 | val constant | 998 | `np.std(av_val) < 1e-10` |
| 5 | val error | 1023 | exception → continue |
| 6 | val_few_trades | 1032 | `bt_val.total_trades < 15` |
| 7 | **val_neg_pnl** | 1035 | `bt_val.net_pnl <= 0` |
| 8 | val_low_sharpe | 1038 | `bt_val.sharpe_ratio < 0.3` |
| 9 | val_low_wr | 1042 | `wilson_lower(...) < 0.52` |
| → | INSERT staging | 1117 | success path |

→ **Phase 1 verdict**: `val_neg_pnl` is the **net-PnL-after-cost holdout-only honesty floor**. There is no earlier `train_neg_pnl` gate in arena_pipeline.py — the live A1 path tolerates negative train PnL but rejects negative val PnL.
