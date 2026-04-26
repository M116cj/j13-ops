# 08 — GP vs alpha_zoo Comparative Analysis

## 1. Side-by-Side

| Metric | GP candidates (live A1) | alpha_zoo formulas (offline replay) |
| --- | --- | --- |
| Sample size | ~9 800 evaluations across 14 symbols | 150 evaluations across 5 top symbols |
| Compile failure rate | not separately logged | 0% |
| `val_neg_pnl` rejection rate | ~99% | **87% of 150 = 130/150** |
| `val_few_trades` rejection rate | <0.5% | 0% |
| `val_low_sharpe` rejection rate | <0.5% | 0% |
| `val_low_wr` rejection rate | <0.5% | 0% (none reach this gate; all rejected at val_neg_pnl first) |
| `val_error` rate | not separately logged | 13% |
| Champion / Survivor count | **0 / ~9 800** | **0 / 150** |
| Survivor rate | **0.000%** | **0.000%** |

## 2. Train-side PnL Comparison

| | GP candidates (live) | alpha_zoo formulas |
| --- | --- | --- |
| Best train PnL observed | not directly logged in stats line | **-0.21** (`sign_x(delta_20(close))` on BTCUSDT) |
| Train PnL ≥ 0 count | not directly visible | **0** |
| Train PnL distribution | inferred negative (since both populations fail same val gates with similar reject distribution) | **all 130 negative**, range −1.81 to −0.21, median −1.21 |

GP candidates would presumably show a similar train-PnL distribution. The fitness function selects the best candidates, but if the universe is systemically losing money, even the best are still negative.

## 3. Train / Holdout Gap

For alpha_zoo (we have full train+val PnL for the 20 evaluations that reached val):

- Best alpha_zoo train PnL: -0.21
- All val PnL: also negative (val_neg_pnl rejected all of them)
- Train / holdout gap: NOT a visible OOS deterioration; both windows are unprofitable.

For GP we don't have direct train+val numbers, but the symmetric reject pattern + alpha_zoo evidence strongly suggests the same: **systemic negative PnL on both windows, not an overfit-to-train pattern.**

## 4. Numeric Failure Rate

| | GP | zoo |
| --- | --- | --- |
| `val_constant` rate (NaN/inf clamped to 0) | <0.5% | 0/150 |
| `val_error` rate (val backtest exception) | not separately logged | 13% (20/150) |
| numpy RuntimeWarning emit rate | ~4 events / worker / 37 min | (not measured for replay) |

Numeric is NOT a primary differentiator. Both populations evaluate cleanly except for occasional val backtest errors.

## 5. Source Complexity

GP-evolved candidates have variable formula tree depth (typically 3-7). alpha_zoo formulas range from depth 2 (`delta_20(high)`) to depth 6 (`neg(protected_div(mul(sub(low, close), pow5(open)), mul(sub(low, high), pow5(close))))`). Complexity is comparable; alpha_zoo is mostly simpler (textbook formulas).

## 6. OOS Robustness

Neither population is OOS-robust. Both fail at the val_neg_pnl gate at near-100% rate. **alpha_zoo is NOT more OOS-robust than GP** under current cost / threshold / horizon settings.

## 7. Cold-Start Seed Injection — Likely to Unblock Staging?

| Question | Answer |
| --- | --- |
| Will cold-start injection of these 30 formulas produce staging rows? | **NO** — the same val_neg_pnl gate would reject them (Phase 7 evidence). |
| Will cold-start bypass val_neg_pnl? | NO — `cold_start_hand_alphas.py` enforces the same gates (Phase 6 evidence). |
| Would weakening val_neg_pnl let cold-start succeed? | This order's hard ban forbids any weakening. |
| Is the failure GP-specific? | NO — alpha_zoo replay shows universal failure across formula classes. |

## 8. Phase 8 Classification

Per order §16:

| Verdict | Match? |
| --- | --- |
| ZOO_OUTPERFORMS_GP_VALIDATION | NO |
| **ZOO_EQUALS_GP_FAILURE** | **YES — exact match** (both fail at ~100% rate at val_neg_pnl) |
| **GP_FAILURE_IS_DATA_OR_VALIDATION_SYSTEMIC** | **YES** (the universal failure across both populations points to a systemic issue in the cost / threshold / horizon / data interaction at the backtester level) |
| GP_ONLY_OVERFIT_LIKELY | NO (alpha_zoo also fails) |
| COMPARISON_INSUFFICIENT | NO (sufficient data: 9 800 GP + 150 zoo evaluations) |

→ **Phase 8 verdict: ZOO_EQUALS_GP_FAILURE + GP_FAILURE_IS_DATA_OR_VALIDATION_SYSTEMIC.** Cold-start injection of the existing 30-formula alpha_zoo would NOT unblock the pipeline. The next action is NOT cold-start; it is investigating the systemic cost/threshold/horizon/backtester interaction.
