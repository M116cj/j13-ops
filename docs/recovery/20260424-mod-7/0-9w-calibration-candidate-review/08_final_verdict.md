# 0-9W-CALIBRATION-CANDIDATE-REVIEW — Final Verdict

## 1. Status

**REVIEW_REJECTS_SURVIVORS_AS_ARTIFACT**

The 8 cost=0.5x survivors discovered in PR #40 are unanimously classified as SINGLE_SYMBOL_ARTIFACT. None earn ROBUST_CANDIDATE or FRAGILE_CANDIDATE status. A direct cost-calibration implementation (lowering cost_bps from 1.0x to 0.5x) is BLOCKED by 5 HIGH-severity risks and 3 critical infrastructure / pipeline-contract gaps.

## 2. Previous Diagnosis Summary (from PR #40)

| Field | Value |
| --- | --- |
| Source order | TEAM ORDER 0-9W-COST-THRESHOLD-HORIZON-CALIBRATION-DIAGNOSIS |
| Previous verdict | DIAGNOSED_CALIBRATION_REQUIRED_SURVIVORS_FOUND (CASE D) |
| Matrix cells tested | 405 |
| Cost = 1.0x survivors | 0 |
| Cost = 0.5x survivors | 8 (all SOLUSDT) |
| Cost = 0 survivors | 63 |
| Primary hypothesis | H1 cost calibration too high vs alpha edge (90%) |
| Secondary hypothesis | H7 alpha universe edge weak (60%) |

## 3. Survivor Inventory Verdict

| Field | Value |
| --- | --- |
| Total survivors | 71 |
| At cost = 1.0x | 0 |
| At cost = 0.5x | 8 (100% SOLUSDT, formulas wqb_s01 + wqb_s01_vwap) |
| At cost = 0 | 63 |
| Best val_pnl at cost=0.5x | +0.1275 (`wqb_s01 SOL ET=0.70 MH=360`) |
| Best train_pnl at cost=0.5x | **−0.318** (no surviving cell has positive train PnL) |

## 4. Economic Realism Verdict

→ **COST_0_5X_OPTIMISTIC_BUT_PLAUSIBLE + COST_MODEL_NEEDS_EXECUTION_SPLIT**

Cost = 0.5x ≈ 100% maker execution with zero slippage. Achievable on Binance Futures, but requires maker order routing infrastructure that zangetsu does not yet have. The current 11.5 bps Stable tier round-trip cost is **realistic worst-case** (full taker, retail VIP 0 tier, market orders). Funding component is the only meaningfully over-conservative element (~0.75 bps over-count per RT).

## 5. Survivor Robustness Verdict

→ **ALL_SURVIVORS_REJECT_AS_ARTIFACT**

100% of cost=0.5x survivors are SINGLE_SYMBOL_ARTIFACT (mean robustness score 2.6/10, max 3/10). All 8 fail simultaneously on:
- TRAIN_NEG_VAL_POS (negative train, positive val — train-val divergence)
- COLLAPSE_AT_1.0x (positive→negative when cost increases by 5.75 bps)
- SINGLE_SYMBOL_ARTIFACT (only 1 of 3 symbols positive at same params)

This is the textbook signature of curve fit / regime artifact, not a stable edge.

## 6. Calibration Risk Verdict

→ **CALIBRATION_CHANGE_HIGH_RISK + CALIBRATION_CHANGE_BLOCKED**

5 of 12 risks are HIGH severity AND blocking:
- R1: Underestimating real execution cost
- R2: Creating fake survivors at modified cost level
- R3: Overfitting to SOLUSDT
- R9: Live execution mismatch (no maker fill measurement)
- R10: SOL regime shift from val period to live

3 critical blockers cannot be lifted without infrastructure work:
- B1: Maker-fill-rate measurement (R1, R9)
- B2: Multi-symbol validation gate (R3, R10)
- B3: Train+val combined Sharpe filter (R2)

## 7. Implementation Option Comparison

| Option | Recommendation |
| --- | --- |
| A — Lower cost_bps globally | **REJECT** |
| B — Execution-mode-aware cost | maybe later (additive, inert at default) |
| C — Symbol-specific cost | defer until B is in place |
| D — Dual-cost telemetry | maybe (observability only) |
| E — Formula universe redesign | **RECOMMENDED** |
| F — Expanded calibration matrix | **RECOMMENDED** |
| G — Maker order routing | parallel track (separate governance order) |

## 8. Final Recommendation

→ **Primary: R5 — REJECT calibration as artifact.**
→ **Secondary: R6 + R4 — tighten validator gates AND redesign formula universe.**

The 8 surviving cells are statistical artifacts, not promotable champions. Lowering cost_bps to "unlock" them would corrupt the survivor selection process.

## 9. Exact Next Order

**`TEAM ORDER 0-9X-VAL-FILTER-CONTRACT-UPGRADE-AND-EXPANDED-CALIBRATION-MATRIX`**

Concrete scope:
1. Add `train_pnl > 0 AND val_pnl > 0` gate to val_filter chain (rejects train-val divergent cells)
2. Add `combined_sharpe ≥ 0.4` gate
3. Add `cross_symbol_consistency ≥ 2/3 symbols positive at same parameter set` gate
4. Re-run expanded matrix (14 syms × 5 formulas × 3 cost × 5 ET × 5 MH ≈ 5,250 cells) with new gates active
5. Determine whether ANY cell survives the tightened gates
6. Defer cost-model changes until either Option G (maker routing) is in place or Option E (universe redesign) demonstrates edge at current 1.0x cost

## 10. Block Status

| Question | Answer |
| --- | --- |
| Does alpha_zoo injection remain blocked? | **YES** |
| Does live CANARY remain blocked? | **YES** |
| Is runtime calibration change justified? | **NO** |

The cost calibration block is enforced until the following no-go conditions (NG1-NG5) are all met:

| Condition | Description |
| --- | --- |
| NG1 | Maker order routing exists in zangetsu and provides per-symbol observed maker fill rate |
| NG2 | Combined train+val Sharpe gate active in val_filter chain |
| NG3 | Cross-symbol consistency gate active |
| NG4 | Expanded calibration matrix shows ≥3 cells classified as ROBUST_CANDIDATE under tightened gates |
| NG5 | At least 2 of those candidates exist on different symbols and have positive train AND positive val PnL |

## 11. Safety + Governance

| Item | Status |
| --- | --- |
| Source code mods | 0 |
| Schema mods | 0 |
| DB mutation | 0 |
| Alpha injection | 0 |
| Threshold weakening | 0 |
| A2_MIN_TRADES | 25 (unchanged) |
| Arena thresholds | unchanged |
| CANARY | NOT STARTED |
| Production rollout | NOT STARTED |
| Execution / capital / risk | UNCHANGED |
| Branch protection | intact (5/5 flags) |
| Signed commit | YES (ED25519, j13 SSH key on Alaya) |
| Forbidden ops count | **0** |

## 12. Final Declaration

```
TEAM ORDER 0-9W-CALIBRATION-CANDIDATE-REVIEW = REVIEW_REJECTS_SURVIVORS_AS_ARTIFACT
```

This order made **0 source code / 0 schema / 0 cron / 0 secret / 0 DB / 0 alpha injection** changes. Pure read-only governance review. Forbidden changes count = 0.

Recommended next order: **TEAM ORDER 0-9X-VAL-FILTER-CONTRACT-UPGRADE-AND-EXPANDED-CALIBRATION-MATRIX**.

Cost calibration block remains in force until NG1-NG5 conditions are simultaneously satisfied.
