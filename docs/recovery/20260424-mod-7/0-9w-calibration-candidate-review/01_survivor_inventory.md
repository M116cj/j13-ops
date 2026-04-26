# 01 — Survivor Inventory Review

## 1. Source

- `0-9wch-calibration-matrix.jsonl` (405 cells, 7,127 lines wide raw evals)
- `calibration_matrix_summary.json` (aggregate breakdown)

## 2. Aggregate Counts

| Field | Value |
| --- | --- |
| Total matrix cells | 405 |
| Total evaluations | 405 |
| Total survivors (val_pnl>0 + val_sharpe≥0.3 + val_trades≥15) | **71** |

## 3. Survivors by Cost Level

```
cost = 0     (perfect execution)        : 63 / 135 cells (47%)
cost = 0.5x  (5.75 bps round-trip)      :  8 / 135 cells (6%)
cost = 1.0x  (11.5 bps RT — current)    :  0 / 135 cells (0%)
```

## 4. Survivors by Symbol

```
SOLUSDT : 29 (41% of survivors)
BTCUSDT : 23 (32%)
ETHUSDT : 19 (27%)
```

## 5. Survivors by Formula

```
neg(sub(close, scale(close)))                                 : 22  (= wqb_s01)
protected_div(sub(vwap_20, close), add(vwap_20, close))       : 16  (= mean reversion vs vwap)
delta_20(bollinger_bw_20)                                     : 15  (= volatility expansion)
neg(protected_div(delta_20(close), close))                    : 15  (= momentum-flipped normalised return)
sign_x(delta_20(close))                                       :  3  (= raw 20-bar momentum)
```

## 6. Survivors by ENTRY_THR

```
ET = 0.60 : 26 cells
ET = 0.70 : 25 cells
ET = 0.80 : 20 cells
```

## 7. Survivors by MAX_HOLD

```
MH = 120 : 26 cells
MH = 360 : 24 cells
MH = 720 : 21 cells
```

## 8. Best PnL Cells

| Metric | Value | Cell |
| --- | --- | --- |
| Best train PnL | +0.4798 | wqb_s01 / SOL / cost=0 / ET=0.80 / MH=120 |
| Best val PnL | **+0.3721** | wqb_s01 / SOL / cost=0 / ET=0.70 / MH=120 |
| Best net PnL after cost (cost=0.5x) | **+0.1275** | wqb_s01 / SOL / cost=0.5x / ET=0.70 / MH=360 |
| Highest val_sharpe | +1.96 | wqb_s01 / SOL / cost=0 / ET=0.70 / MH=120 |
| Highest val_wr | 0.661 | wqb_s01_vwap / SOL / cost=0 / ET=0.70 / MH=360 |

## 9. Top 15 Survivors by val_pnl (any cost level)

```
cost   formula                                          sym       et    mh   tr_pnl   tr_t  val_pnl  v_t  v_sh  v_wr
0      wqb_s01: neg(sub(close, scale(close)))           SOLUSDT  0.70  120  +0.2481  1081  +0.3721  463  1.96 0.648
0      wqb_s01                                          SOLUSDT  0.60  120  +0.2101  1130  +0.3394  482  1.77 0.639
0      wqb_s01                                          SOLUSDT  0.70  360  +0.1341   790  +0.3226  340  1.77 0.656
0      wqb_s01                                          SOLUSDT  0.70  720  +0.0174   772  +0.3100  333  1.77 0.655
0      wqb_s01_vwap: protected_div(sub(vwap-close)…)    SOLUSDT  0.60  120  -0.1989  1129  +0.3028  477  1.65 0.618
0      wqb_s01                                          SOLUSDT  0.60  360  +0.0430   837  +0.3000  356  1.68 0.649
0      wqb_s01                                          SOLUSDT  0.60  720  -0.0067   821  +0.2908  349  1.62 0.648
0      wqb_s01_vwap                                     SOLUSDT  0.70  120  +0.1094  1077  +0.2852  459  1.51 0.654
0      wqb_s01_vwap                                     SOLUSDT  0.70  360  -0.0241   792  +0.2621  339  1.59 0.661
0      wqb_s01_vwap                                     SOLUSDT  0.60  360  -0.3658   840  +0.2579  357  1.61 0.613
0      wqb_s01_vwap                                     SOLUSDT  0.60  720  -0.4292   823  +0.2481  350  1.41 0.611
0      wqb_s01_vwap                                     SOLUSDT  0.70  720  -0.1208   775  +0.2315  332  1.35 0.657
0      wqb_s01                                          BTCUSDT  0.70  120  +0.0744  1069  +0.1638  461  1.18 0.657
0      wq101_42: neg(protected_div(delta_20(close)…))   ETHUSDT  0.80  120  +0.3823  1057  +0.1437  449  0.80 0.563
0      wq101_42                                         ETHUSDT  0.80  360  +0.3689  1056  +0.1437  449  0.80 0.563
```

Observation:
- 12 of top 15 are SOLUSDT
- 11 of top 15 are formula `wqb_s01` (= `neg(sub(close, scale(close)))`)
- Only the BTCUSDT and ETHUSDT cells in top 15 have **positive train AND positive val PnL** simultaneously. The SOL cells with the highest val_pnl mostly have weakly-positive or **negative** train_pnl.

## 10. Survivors at Cost > 0 (real-world setting, 8 cells, ALL SOLUSDT)

```
cost   formula                              et    mh   tr_pnl   tr_t  val_pnl  v_t  v_sh  v_wr
0.5x   wqb_s01                            0.70  360  -0.3182   790  +0.1275  340  0.70 0.594
0.5x   wqb_s01                            0.70  120  -0.3462  1081  +0.1193  463  0.63 0.594
0.5x   wqb_s01                            0.70  720  -0.4265   772  +0.1185  333  0.68 0.595
0.5x   wqb_s01                            0.60  360  -0.4369   837  +0.0960  356  0.54 0.567
0.5x   wqb_s01                            0.60  720  -0.4788   821  +0.0901  349  0.50 0.570
0.5x   wqb_s01                            0.60  120  -0.4117  1130  +0.0753  463  0.39 0.573
0.5x   wqb_s01_vwap                       0.70  360  -0.4779   792  +0.0680  339  0.41 0.596
0.5x   wqb_s01_vwap                       0.60  360  -0.8472   840  +0.0534  357  0.33 0.560
```

## 11. Critical Observations

| Observation | Implication |
| --- | --- |
| **All 8 cost>0 survivors are SOLUSDT** (no BTC, no ETH) | **single-symbol artifact suspect** |
| **All 8 cost>0 survivors have NEGATIVE train PnL** | the formulas are **train-val divergent** — they fail on the IS data |
| Only 2 distinct formulas at cost>0 (wqb_s01 + wqb_s01_vwap, both mean-reversion) | extremely narrow signal type |
| ET=0.80 has ZERO survivors at cost>0 | survivors only emerge by widening the entry zone (more trades, more cost) — a self-defeating dynamic |
| Train PnL is consistently negative at cost=0.5x even for surviving cells | the alpha **does not** generalize to the train slice — it "happens" to work on val |

## 12. Turnover for Surviving Cells (cost > 0)

```
val_trades range: 339 — 482 trades over ~140k bars holdout (= ~3-4 days bar-equivalent)
                  → ~0.24% trades per bar = ~3.4 trades per hour
                  → high turnover, cost-sensitive
```

## 13. Stability Across Symbols

For the dominant formula `wqb_s01`:
- SOLUSDT cost=0.5x: 6 surviving cells (val_pnl avg=+0.099)
- BTCUSDT cost=0.5x: **0** surviving cells (best val_pnl=−0.07 at cost=0.5x)
- ETHUSDT cost=0.5x: **0** surviving cells (best val_pnl=−0.06 at cost=0.5x)

→ **The cross-symbol generalization is BROKEN** at the cost=0.5x level. SOL is a 1-of-3 outlier.

## 14. Phase 1 Output

| Output | Status |
| --- | --- |
| `survivor_inventory.jsonl` (71 rows, sorted by val_pnl desc) | written |
| Aggregate counts | recorded |
| Per-symbol / per-formula / per-axis breakdowns | recorded |
| Best-PnL cells | recorded |
| Cost>0 deep-dive | recorded |
| Cross-symbol stability | recorded |

→ **The 8 cost=0.5x survivors are concentrated in a single symbol (SOL) and a single formula family (mean-reversion vs scaled close / vwap). Train-val divergence is universal across all 8 cells. This is the primary input to Phase 3 robustness review.**
