# 05 — Backtest and Validation Parameter Audit

## 1. Train / Holdout Split

| Parameter | Source | Value |
| --- | --- | --- |
| `TRAIN_SPLIT_RATIO` | `arena_pipeline.py:283` | **0.7** (hardcoded) |
| Train window | computed at line 508: `split = int(w * TRAIN_SPLIT_RATIO)` | 70% of OHLCV history |
| Holdout window | remaining 30% | applied to val backtest |

Per data loader: 200,000 bars → 140,000 train + 60,000 holdout (1-min bars on each symbol).

## 2. Cost Model

| Parameter | Source | Value |
| --- | --- | --- |
| `cost_bps` | `arena_pipeline.py:877` (`cost_model.get(sym).total_round_trip_bps`) | per-symbol from `cost_model.py` |
| Cost application | per round-trip (entry + exit pair) | confirmed by PR #40 Phase 4 random sanity (46642 trades × 11.5 bps ≈ -53.4 bps cumulative) |
| Slippage | included in `total_round_trip_bps` | 0.5 bps Stable / 1.0 Diversified / 2.0 High-Vol |
| Funding | flat-added per RT (NOT hold-duration weighted) | 1.0 bps |
| Stable tier RT | (5×2) + 0.5 + 1.0 | **11.5 bps** |
| Diversified tier RT | (6.25×2) + 1.0 + 1.0 | 14.5 bps |
| High-Vol tier RT | (10×2) + 2.0 + 1.0 | 23.0 bps |

## 3. Horizon

| Parameter | Source | Value |
| --- | --- | --- |
| `MAX_HOLD_BARS` (j01 strategy) | `j01/config/thresholds.py` | **120** |
| `MAX_HOLD_BARS` (j02 strategy) | `j02/config/thresholds.py` | 120 |
| `_STRATEGY_MAX_HOLD` | `arena_pipeline.py:280` | int(j01.MAX_HOLD_BARS) = 120 |
| `ALPHA_FORWARD_HORIZON` | `j01/config/thresholds.py` | 60 (matches alpha_signal.min_hold) |
| Bar timeframe | data ingest | 1-min |

## 4. Active Validation Gates (`arena_pipeline.py:1033-1050`)

In execution order:

```python
if bt_val.total_trades < 15:                  # gate 1
    stats["reject_val_few_trades"] += 1
    continue
if float(bt_val.net_pnl) <= 0:                # gate 2
    stats["reject_val_neg_pnl"] += 1
    continue
if float(bt_val.sharpe_ratio) < 0.3:           # gate 3
    stats["reject_val_low_sharpe"] += 1
    continue
val_wilson = wilson_lower(bt_val.winning_trades, bt_val.total_trades)
if float(val_wilson) < 0.52:                   # gate 4
    stats["reject_val_low_wr"] += 1
    continue
```

| Gate | Active | Threshold | Source |
| --- | --- | --- | --- |
| `reject_val_constant` (NaN/inf → constant signal) | YES | std < 1e-10 | line 1004 |
| `reject_val_error` (exception during backtest) | YES | any exception | line 1024 |
| `reject_val_few_trades` | YES | < 15 trades | line 1033 |
| `reject_val_neg_pnl` | YES | net_pnl <= 0 | line 1036 |
| `reject_val_low_sharpe` | YES | sharpe < 0.3 | line 1039 |
| `reject_val_low_wr` | YES | wilson_wr < 0.52 | line 1043 |

## 5. Inactive / Proposed Gates (recommended in PR #41 review, NOT YET IMPLEMENTED)

| Proposed gate | Status | Source |
| --- | --- | --- |
| **`train_pnl > 0` requirement** | **INACTIVE** — current code does NOT require positive train PnL | absent in arena_pipeline.py |
| **`combined_sharpe ≥ 0.4` (train+val combined)** | **INACTIVE** | absent |
| **Cross-symbol consistency ≥ 2/3 positive** | **INACTIVE** | absent |
| Single-symbol artifact block | INACTIVE | absent |

→ **The exact gates that PR #41 (3-13) recommended adding to block SOL-only artifacts are NOT in code.** This is documented as a known gap (NG2/NG3 in PR #41).

## 6. Cost Indices Trace

| Step | Code | Effect |
| --- | --- | --- |
| Train backtest | line 964: `backtester.run(signals, close_f32, sym, cost_bps, _STRATEGY_MAX_HOLD, ...)` | applies cost during train fitness |
| Val backtest | line 1018: `... cost_bps, _STRATEGY_MAX_HOLD, ...` | applies cost during val gate |
| Both use same `cost_bps = cost_model.get(sym).total_round_trip_bps` | identical cost in train and val | symmetric — no train/val cost mismatch |

## 7. Special Focus Per Order

| Question | Answer |
| --- | --- |
| Is `train_pnl > 0` required? | **NO** |
| Is `val_pnl > 0` required? | YES (gate `reject_val_neg_pnl`) |
| Is `combined_sharpe ≥ 0.4` required? | **NO** |
| Is cross-symbol consistency ≥ 2/3 required? | **NO** |
| Are SOL-only artifacts blocked? | **NO** — cross-symbol gate absent; SOL-only candidates can pass |

## 8. Classification

| Verdict | Match? |
| --- | --- |
| VALIDATION_PARAMS_OK | partial — current 4 gates exist and are strict on val |
| **VALIDATION_CONTRACT_TOO_WEAK** | **YES** — train+val combined gate, cross-symbol gate, train_pnl>0 gate are ALL ABSENT |
| VALIDATION_CONTRACT_TOO_STRICT | NO |
| COST_MODEL_RISK | partial — funding component over-counts at typical hold (~0.75 bps/RT bias); not blocking |
| HORIZON_RISK | NO (PR #40 Phase 3 confirmed horizon is not the constraint) |
| SPLIT_RISK | NO (0.7/0.3 train/val split is standard; train regime covers 4.5y including DeFi summer, COVID, 2021 bull, 2022 bear, FTX, halving, ETF) |

→ **Phase 5 verdict: VALIDATION_CONTRACT_TOO_WEAK.** The validation contract is missing 3 gates required to block the artifact pattern documented in PR #41. Current contract permits SOL-only train-val divergent artifacts. **This is a known gap (NG2/NG3 in PR #41) and is the primary reason cold-start would still produce artifacts under current parameters.**
