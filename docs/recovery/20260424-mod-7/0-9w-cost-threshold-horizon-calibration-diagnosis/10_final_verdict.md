# 0-9W-COST-THRESHOLD-HORIZON-CALIBRATION-DIAGNOSIS — Final Verdict

## 1. Status

**DIAGNOSED_CALIBRATION_REQUIRED_SURVIVORS_FOUND** (CASE D in order §451-475)

The mass `val_neg_pnl` rejection observed in live A1 (and confirmed in PR #39 zoo offline replay) is dominantly driven by **cost calibration relative to current alpha edge**, not by GP overfit, threshold mis-set, horizon mis-set, backtester bug, signal-direction bug, or funding mis-modeling.

Calibration matrix offline replay (405 cells: 5 formulas × 3 symbols × 3 cost × 3 ET × 3 MH) shows:
- At **cost = 0**: 63 / 135 cells survive
- At **cost = 0.5x** (5.75 bps RT): 8 / 135 cells survive (all SOLUSDT, formulas `wqb_s01` and `wq101_42`)
- At **cost = 1.0x** (11.5 bps RT — current Stable tier): **0 / 135 cells survive**

This proves a real calibration window exists where alpha-zoo formulas survive the val gate, but the current Stable tier round-trip cost (11.5 bps) is above that window for all tested formula × symbol combinations.

## 2. Alaya State

| Field | Value |
| --- | --- |
| Host | j13@100.123.49.102 |
| Repo | /home/j13/j13-ops |
| HEAD (start) | `9f69067cb063cf831c935735e768fc2ccce472c7` |
| Branch | main |
| Working tree (start) | clean |

## 3. Runtime State (unchanged across investigation)

| Service | State |
| --- | --- |
| A1 | ALIVE 4 workers (post PR #37 patch, no UnboundLocalError recurrence) |
| A23 | ALIVE, idle |
| A45 | ALIVE, idle |
| A13 | CLEAN every */5 cron tick |
| engine.jsonl writer | WRITING |
| stats sample | val_neg_pnl ~99% (consistent with prior orders) |

## 4. Phase Summary Table

| Phase | Investigation | Verdict |
| --- | --- | --- |
| 0 — State lock | preflight HEAD = 9f69067c, services alive | PASS |
| 1 — Cost calibration | 5 cost levels × 5 formulas × 3 syms = 75 evals | **COST_DOMINATES_DUE_TURNOVER + COST_TOO_HIGH_LIKELY** |
| 2 — ENTRY_THR sweep | 5 thresholds × 5 formulas × 3 syms = 75 evals | ENTRY_THRESHOLD_NOT_PRIMARY_CAUSE |
| 3 — MAX_HOLD sweep | 5 horizons × 5 formulas × 3 syms = 75 evals | HORIZON_NOT_PRIMARY_CAUSE |
| 4 — Backtester sanity | 5 sanity strategies × 3 syms × 2 slices = 30 evals | BACKTESTER_SANITY_PASS |
| 5 — Signal-to-trade | forward-return diagnostic on 3 syms = 3 evals | SIGNAL_TO_TRADE_OK |
| 6 — Funding component | source inspection + impact estimate | FUNDING_MINOR_OVER_COUNT, FUNDING_NOT_PRIMARY_CAUSE |
| 7 — Calibration matrix | 5 formulas × 3 syms × 3 cost × 3 ET × 3 MH = 405 evals | **CALIBRATION_SURVIVORS_FOUND** |
| 8 — Hypothesis ranking | 7 hypotheses, evidence-weighted | H1 = HIGH primary, H7 = MEDIUM secondary, all others LOW or RULED OUT |
| 9 — Safety / governance | 0 forbidden ops, 0 source mods | GOVERNANCE_PASS |

Total evaluations: **663** offline cells. Wall-clock: 29.6 seconds. Zero DB writes, zero service restarts.

## 5. Root Cause Hypothesis Ranking (Phase 8)

| Rank | Hypothesis | Confidence |
| --- | --- | --- |
| #1 | **H1 — Cost calibration too high vs current alpha edge** | **HIGH (90%)** |
| #2 | **H7 — Alpha universe edge weakness** | **MEDIUM (60%)** |
| #3 | H3 — MAX_HOLD horizon | LOW (5%) |
| #4 | H6 — Funding component | LOW (5%) |
| #5 | H2 — ENTRY_THR too strict | LOW (3%) — lowering makes it WORSE |
| #6 | H5 — Signal direction bug | RULED OUT |
| #7 | H4 — Backtester defect | RULED OUT |

## 6. Survivors Found in Calibration Matrix

```
COST LABEL    TOTAL  VAL>0  SURVIVORS (val_pnl>0 + val_sharpe>=0.3 + val_trades>=15)
  cost=0      135      93      63
  cost=0.5x   135      12       8
  cost=1.0x   135       0       0
```

Per formula at any cost level (out of max 81 cells per formula):
```
delta_20(bollinger_bw_20):                                 15
neg(protected_div(delta_20(close), close)):                15
neg(sub(close, scale(close))):                             22  ← strongest
protected_div(sub(vwap_20, close), add(vwap_20, close)):   16
sign_x(delta_20(close)):                                    3  ← weakest
```

Per symbol (out of max 135 cells per symbol):
```
BTCUSDT: 23
ETHUSDT: 19
SOLUSDT: 29  ← strongest
```

Survivors at cost > 0 (real-world setting, 0.5x = 5.75 bps RT):
- `wqb_s01` on SOLUSDT — 6 cells (best val_pnl=+0.1275)
- `wq101_42` on SOLUSDT — 4 cells (best val_pnl=+0.0680)

## 7. Caveat: Train-Val Divergence at Surviving Cells

All 8 cells that survive at cost=0.5x have **negative train PnL** but positive val PnL. This means:
- The formula was unprofitable on the train slice
- It "happened" to be profitable on the val slice (regime shift?)
- A train+val combined Sharpe filter would still reject these

→ These survivors are **not yet champions**. They demonstrate a calibration window exists, but **further candidate review is required** before any of them could be promoted to live config.

## 8. Safety + Governance

| Item | Status |
| --- | --- |
| DB mutation | NO |
| Alpha injection | NO |
| Thresholds | UNCHANGED (A2_MIN_TRADES=25) |
| Source code mods | 0 |
| Schema mods | 0 |
| Service restarts | 0 |
| CANARY | NOT STARTED |
| Production rollout | NOT STARTED |
| Execution / capital / risk | UNCHANGED |
| Branch protection | intact (5/5 flags unchanged) |
| Signed commit | YES (ED25519, j13 SSH key on Alaya) |
| Forbidden ops count | **0** |

## 9. Decision Branch (per order §451-475)

| Case | Condition | Match? |
| --- | --- | --- |
| CASE A | Backtester defect found → repair backtester | NO (Phase 4 PASS) |
| CASE B | Signal-direction bug found → fix sign | NO (Phase 5 OK) |
| CASE C | All hypotheses ruled out, no survivors at any cost → escalate to alpha-universe expansion | NO (survivors exist) |
| **CASE D** | **Valid calibration survivors appear under offline matrix → DIAGNOSED_CALIBRATION_REQUIRED_SURVIVORS_FOUND. Next: TEAM ORDER 0-9W-CALIBRATION-CANDIDATE-REVIEW.** | **YES** |
| CASE E | All settings give 0 survivors regardless → escalate to data quality / regime drift investigation | NO |

## 10. Recommended Next Order

**`TEAM ORDER 0-9W-CALIBRATION-CANDIDATE-REVIEW`**

Purpose (per order §467-475): Review candidate config changes under governance before any runtime change. Specifically:

1. **Validate the cost-model calibration**: empirically measure observed Binance Futures round-trip cost (taker × 2 + actual slippage from filled orders + actual funding paid) vs current model's 11.5 bps assumption. Determine if the model is over-conservative.
2. **Review the 8 surviving cells** (`wqb_s01` and `wq101_42` on SOLUSDT) for train-val regime divergence; require a combined train+val sharpe filter before promoting any.
3. **Plan a candidate-promotion governance gate**: even if cost is recalibrated, no formula should be promoted to live without `train_pnl > 0 AND val_pnl > 0 AND combined_sharpe ≥ 0.4 AND val_trades ≥ 50`.
4. **Decide on alpha-universe enrichment** (Path B from Phase 8) as a parallel track: queue research on longer-horizon and multi-timeframe formulas.

**DO NOT lower cost_bps in production without governance review** — even if our analysis suggests 5.75 bps is a more realistic round-trip, this requires independent measurement and risk sign-off.

**DO NOT inject the surviving 8 candidate cells into champion_pipeline_staging** — they are train-val divergent and not stable winners.

## 11. Final Declaration

```
TEAM ORDER 0-9W-COST-THRESHOLD-HORIZON-CALIBRATION-DIAGNOSIS = DIAGNOSED_CALIBRATION_REQUIRED_SURVIVORS_FOUND (CASE D)
```

This order made **0 source code / 0 schema / 0 cron / 0 secret / 0 DB / 0 alpha injection** changes. Pure read-only investigation. Forbidden changes count = 0.

Recommended next order: **TEAM ORDER 0-9W-CALIBRATION-CANDIDATE-REVIEW**.
