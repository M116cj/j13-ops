# 0-9W-VAL-FILTER-ROOTCAUSE-AND-ZOO-OFFLINE-REPLAY — Final Verdict

## 1. Status

**DIAGNOSED_SYSTEMIC_OOS_FAILURE** (modified note: the failure is not just OOS — even TRAIN PnL is universally negative across canonical formulas).

The 99% `val_neg_pnl` rejection rate observed in live A1 after PR #37 is NOT a GP overfit problem and NOT a regime-drift-only problem. The val gate is correctly enforced, but the underlying **train PnL is negative for every hand-translated canonical formula tested** (including textbook signals like `sign_x(delta_20(close))` time-series momentum). This means the cost / threshold / horizon settings combined with the current market data make the entire formula universe — both GP-evolved and curated — unprofitable on the train slice itself, which then guarantees val gate failure.

**Cold-start injection of the existing 30-formula alpha_zoo would NOT unblock the pipeline** — the same val gate would reject all of them at the same rate.

## 2. Alaya

| Field | Value |
| --- | --- |
| Host | j13@100.123.49.102 |
| Repo | /home/j13/j13-ops |
| HEAD | 642b2d8e7a87b10c3f732cca4cf00f81acaf49f3 |
| Branch | main |
| Dirty state | clean |

## 3. Runtime

| Service | State |
| --- | --- |
| A1 | ALIVE 4 workers (post PR #37 patch, no UnboundLocalError recurrence) |
| stats sample | `R411830 1000PEPEUSDT/BULL_TREND champions=0/10 rejects val_neg_pnl=1295` (cumulative) |
| A13 | CLEAN every */5 cron tick |
| A23 (PID 207186) | ALIVE 3h 58m, idle |
| A45 (PID 207195) | ALIVE 3h 58m, idle |

## 4. Val Filter Definition

| Field | Value |
| --- | --- |
| Exact condition | `bt_val.net_pnl <= 0` (`arena_pipeline.py:1035`) |
| PnL type | NET (after `cost_bps` round-trip) |
| Holdout | YES (`d_val = data_cache[sym]["holdout"]`) |
| Costs | included |
| Funding | NOT included |
| NaN/inf behavior | clamped to 0 by `nan_to_num` → routes to `val_constant`, not `val_neg_pnl` |

## 5. Live Rejection Distribution

| Field | Value |
| --- | --- |
| Rounds sampled | 98 stats lines (~9 800 candidate evaluations) |
| Champions | 0 |
| `val_neg_pnl` | ~99% (dominant) |
| `val_few_trades` | <0.5% |
| Numeric / other | <0.5% |

## 6. Train / Holdout

| Field | Value |
| --- | --- |
| Split | TRAIN_SPLIT_RATIO = 0.7 |
| BTCUSDT train | 2019-09-18 → 2024-05-02 (4.5y) |
| BTCUSDT holdout | 2024-05-02 → 2026-04-26 (2y) |
| Train regime coverage | DeFi summer, COVID, 2021 bull, 2022 bear, FTX collapse, 2023 recovery, 2024 ETF |
| Holdout regime coverage | post-ETF, halving cycle, election rally, 2025 institutional era |
| Diagnosis | REGIME_DRIFT_LIKELY (boundary at BTC ETF / halving) — **but secondary**, since even TRAIN is unprofitable |

## 7. Numeric / Data

| Field | Value |
| --- | --- |
| numpy overflow | 4 events / worker / 37 min — non-blocking |
| NaN/inf | clamped via `nan_to_num` |
| Indicator-cache contamination | mitigated by Patch E |
| Data quality | OK (fresh as of 12:00Z today, valid OHLCV columns) |
| Verdict | NUMERIC_REJECTION_VALID + DATA_QUALITY_OK |

## 8. GP

| Field | Value |
| --- | --- |
| `POP_SIZE` | 100 |
| `N_GEN` | 20 |
| `TOP_K` | 10 |
| Overfit verdict | **GP_NOT_PRIMARY_CAUSE** (alpha_zoo also fails 100%) |

## 9. Alpha Zoo

| Field | Value |
| --- | --- |
| Tool | `zangetsu/scripts/alpha_zoo_injection.py` |
| Formula count | 30 across 7 sources |
| Dry-run support | NO (`--dry-run-one` flag is parsed but unimplemented) |
| Write target | `champion_pipeline_staging` (then `admission_validator` promotes) |
| Validation bypass risk | NONE (uses same val gates as A1) |
| Static readiness | ZOO_STATIC_READY_FOR_OFFLINE_REPLAY |

## 10. Offline Replay

| Field | Value |
| --- | --- |
| Replay executed | YES (`/tmp/0-9wzr-offline-replay.py`, no DB connection, 11.8 s wall time) |
| Formulas tested | 30 |
| Symbols tested | 5 (BTC, ETH, BNB, SOL, XRP) |
| Total evaluations | 150 |
| Compile-pass | 150 (100%) |
| Validation-pass | 0 |
| `val_neg_pnl` fail | 130 (87%) |
| `val_error` fail | 20 (13%) |
| `val_low_sharpe` fail | 0 (none reach this gate) |
| `val_low_wr` fail | 0 |
| Survivor count | **0** |
| **Train PnL — best** | **-0.21** (all 130 are negative; range -1.81 to -0.21) |

## 11. Comparison

| Field | Value |
| --- | --- |
| GP pass rate | 0% (~0 / 9 800) |
| zoo pass rate | 0% (0 / 150) |
| Verdict | **ZOO_EQUALS_GP_FAILURE** + **GP_FAILURE_IS_DATA_OR_VALIDATION_SYSTEMIC** |

## 12. Safety

| Item | Status |
| --- | --- |
| DB mutation | NO |
| Alpha injection | NO |
| Thresholds | UNCHANGED |
| `A2_MIN_TRADES` | 25 |
| CANARY | NOT STARTED |
| Production rollout | NOT STARTED |
| Execution / capital / risk | UNCHANGED |

## 13. Governance

| Item | Status |
| --- | --- |
| Controlled-diff | EXPLAINED (docs + data only); 0 forbidden |
| Gate-A | expected PASS |
| Gate-B | expected PASS |
| Branch protection | intact (5/5 flags unchanged) |
| Signed commit | YES |

## 14. Recommended Next Action

The order's Phase 9 decision tree CASE B says: "If val_neg_pnl appears valid and alpha_zoo also fails → DIAGNOSED_SYSTEMIC_OOS_FAILURE → next: TEAM ORDER 0-9W-GENERATION-UNIVERSE-EXPANSION-DIAGNOSIS."

However, "expansion" is unlikely to help when the universally-cited reference formulas (WorldQuant 101, Qlib Alpha158, Quantpedia time-series momentum, GuotaiJunan Alpha191) ALL produce **negative train PnL**. The bottleneck isn't formula universe size — it's the cost / threshold / horizon / backtester interaction.

**Recommended next order: `TEAM ORDER 0-9W-COST-THRESHOLD-HORIZON-CALIBRATION-DIAGNOSIS`** — read-only investigation of:

| H | Hypothesis | Evidence to gather |
| --- | --- | --- |
| H1 | `cost_bps` per symbol is too high vs current spreads / fees | dump cost_model.get(sym).total_round_trip_bps per symbol; compare to current Binance perp fees |
| H2 | `ENTRY_THR=0.80` filters too aggressively for normalized signals | log signal-distribution histogram for one alpha; show fraction of bars exceeding 0.80 |
| H3 | `MAX_HOLD_BARS=120` (j01 strategy) is too short for crypto trend signals | inspect strategy thresholds; sweep backtester result on one alpha at hold {60, 120, 240, 480} |
| H4 | Backtester defect — sanity-check by replaying a known-good buy-and-hold signal | run buy-and-hold on holdout; compare to expected return |
| H5 | Funding rate component missing from PnL but is a real PnL drain in live | inspect backtester signature; check if funding is supposed to be applied |
| H6 | Signal-to-trade conversion (`generate_alpha_signals`) is producing perverse trades | log enter/exit signal pairs for one alpha; sanity-check trade direction |

If H4 finds backtester defect → repair backtester.
If H1/H5 finds cost/funding mismatch → calibrate cost model.
If H2/H3/H6 finds threshold/horizon/signal logic mismatch → calibrate (not weakens — reflect actual operational reality).

**DO NOT inject the 30 alpha_zoo formulas into champion_pipeline_staging** until the cost/threshold/horizon calibration is resolved. They will be rejected at the same val_neg_pnl rate.

## 15. Final Declaration

```
TEAM ORDER 0-9W-VAL-FILTER-ROOTCAUSE-AND-ZOO-OFFLINE-REPLAY = DIAGNOSED_SYSTEMIC_OOS_FAILURE
```

(With the additional diagnostic note that "OOS failure" is itself downstream of a more systemic train-side unprofitability across all canonical formulas — the val gate is doing its job; the universe under current cost / threshold / horizon settings has no positive-PnL formulas. Recommended next order rephrased above to target the actual root cause.)

This order made **0 source code / 0 schema / 0 cron / 0 secret / 0 DB / 0 alpha injection** changes. Pure read-only investigation. Forbidden changes count = 0.
