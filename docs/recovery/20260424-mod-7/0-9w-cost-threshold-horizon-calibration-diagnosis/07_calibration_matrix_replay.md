# 07 — Calibration Matrix Replay (Full Cross-Sweep)

## 1. Design

To find the **smallest combination** of (cost, ENTRY_THR, MAX_HOLD) that produces alpha-zoo survivors at the val_neg_pnl + val_sharpe + val_trades gates, we ran an offline cross-sweep:

| Axis | Values | N |
| --- | --- | --- |
| Formula | `sign_x(delta_20(close))`, `delta_20(bollinger_bw_20)`, `neg(protected_div(delta_20(close), close))`, `neg(sub(close, scale(close)))`, `protected_div(sub(vwap_20, close), add(vwap_20, close))` | 5 |
| Symbol | BTCUSDT, ETHUSDT, SOLUSDT | 3 |
| cost_factor | 0, 0.5x, 1.0x (of Stable tier 11.5 bps) | 3 |
| entry_threshold | 0.60, 0.70, 0.80 | 3 |
| max_hold_bars | 120, 360, 720 | 3 |
| **Total cells** | | **405** |

Acceptance criteria for a "calibration survivor":
- val_pnl > 0
- val_sharpe ≥ 0.3
- val_trades ≥ 15

(Same as the live arena_pipeline gate stack.)

## 2. Aggregate Results

```
total cells: 405
COST LEVEL    TOTAL  VAL>0  SURVIVORS
  cost=0      135      93      63
  cost=0.5x   135      12       8
  cost=1.0x   135       0       0
TOTAL                            71
```

| Observation | Implication |
| --- | --- |
| At full cost (1.0x = 11.5 bps RT), 0/135 cells produce a survivor | **mass rejection at val_neg_pnl is consistent and not a transient effect** |
| At 0.5x cost (5.75 bps RT), 8/135 cells survive — exclusively SOLUSDT | survivors emerge but only on the highest-volatility symbol |
| At 0x cost, 63/135 cells survive | gross alpha edge exists, just barely |
| Val>0 count drops from 93 → 12 → 0 with each cost level doubling | **cost dominates the val_neg_pnl filter linearly** |

## 3. Survivors Per Formula

```
delta_20(bollinger_bw_20):                    15 cells
neg(protected_div(delta_20(close), close)):   15 cells
neg(sub(close, scale(close))):                22 cells
protected_div(sub(vwap_20, close), add(vwap_20, close)): 16 cells
sign_x(delta_20(close)):                       3 cells
```

→ 4 of 5 formulas show **double-digit cell survivor counts** at zero or low cost, indicating the alpha universe **does** carry positive gross edge — the cost wall is what prevents survival under live config.

## 4. Survivors Per Symbol

```
BTCUSDT: 23 cells
ETHUSDT: 19 cells
SOLUSDT: 29 cells
```

→ SOLUSDT carries the strongest signal (29/45 = 64% of cells survive at low/zero cost). BTC/ETH are weaker but non-zero.

## 5. Combos With Survivors at COST > 0 (real-world setting)

```
cost=0.5x   neg(sub(close, scale(close)))                       SOLUSDT  -> 6 cells
cost=0.5x   protected_div(sub(vwap_20, close), add(vwap_20, close)) SOLUSDT  -> 2 cells
```

→ Only **two formula × symbol combos** survive at half-cost (5.75 bps round-trip). Both are on SOLUSDT.
→ Best single cell: `wqb_s01` (= `neg(sub(close, scale(close)))`) on SOLUSDT, cost=0.5x, ET=0.70, MH=360 → val_pnl=+0.1275, val_sharpe>0.3.

## 6. Top 10 Cells With Cost > 0 (verbatim from analyze script)

```
wqb_s01    SOLUSDT  cost=0.5x  et=0.70  mh= 360  | train_pnl=-0.3182 | val_pnl=+0.1275
wqb_s01    SOLUSDT  cost=0.5x  et=0.70  mh= 120  | train_pnl=-0.3462 | val_pnl=+0.1193
wqb_s01    SOLUSDT  cost=0.5x  et=0.70  mh= 720  | train_pnl=-0.4265 | val_pnl=+0.1185
wqb_s01    SOLUSDT  cost=0.5x  et=0.60  mh= 360  | train_pnl=-0.4369 | val_pnl=+0.0960
wqb_s01    SOLUSDT  cost=0.5x  et=0.60  mh= 720  | train_pnl=-0.4788 | val_pnl=+0.0901
wqb_s01    SOLUSDT  cost=0.5x  et=0.60  mh= 120  | train_pnl=-0.4117 | val_pnl=+0.0753
wq101_42   SOLUSDT  cost=0.5x  et=0.70  mh= 360  | train_pnl=-0.4779 | val_pnl=+0.0680
wq101_42   SOLUSDT  cost=0.5x  et=0.60  mh= 360  | train_pnl=-0.8472 | val_pnl=+0.0534
wq101_42   SOLUSDT  cost=0.5x  et=0.60  mh= 720  | train_pnl=-0.9024 | val_pnl=+0.0469
wq101_42   SOLUSDT  cost=0.5x  et=0.70  mh= 720  | train_pnl=-0.5664 | val_pnl=+0.0406
```

Important caveat: **all 10 top-cost-positive cells have negative train PnL** — they would be rejected by the train-side filter (if there were one) or would fail train+val combined Sharpe consistency checks. This is a **train↔val regime divergence**, not a stable edge.

## 7. Phase 7 Classification

| Verdict | Match? |
| --- | --- |
| **CALIBRATION_SURVIVORS_FOUND** | **YES — 71 cells in total, 8 with cost > 0** |
| CALIBRATION_NO_SURVIVORS | NO |
| CALIBRATION_SURVIVORS_AT_ZERO_COST_ONLY | partial — 88% of survivors are at cost=0; only 11% at cost=0.5x |
| CALIBRATION_TRAIN_VAL_DIVERGENT | YES at cost=0.5x (top cells have negative train PnL but positive val PnL — needs further investigation in candidate-review order) |
| CALIBRATION_UNKNOWN | NO |

→ **Phase 7 verdict: CALIBRATION_SURVIVORS_FOUND** — exactly matches CASE D in the order's decision tree (§451-475). Survivors exist offline; runtime calibration would need to drop cost ~50% (from 11.5 → ~5.75 bps), and even then most survivors are train↔val divergent and require candidate review before any live promotion.
