# 04 — Calibration Risk Review

Goal: assess the risk of changing cost calibration in production, given Phase 3 found 100% of survivors are SINGLE_SYMBOL_ARTIFACT.

## 1. Risk Register

| ID | Risk | Severity | Likelihood | Mitigation | Blocks Implementation? |
| --- | --- | --- | --- | --- | --- |
| R1 | Underestimating real execution cost — promoting candidates that fail in live | **HIGH** | HIGH | require maker-fill-rate measurement before any cost reduction | **YES** |
| R2 | Creating fake survivors at the modified cost level — passing val gate without true edge | **HIGH** | HIGH (Phase 3 shows 8/8 are already artifacts at 0.5x) | tighten survivor criteria (combined train+val sharpe ≥ 0.4, min trades 50, min symbols 2) | **YES** |
| R3 | Overfitting to SOLUSDT — strategy that exploits one symbol's val regime | **HIGH** | HIGH (8/8 survivors are SOL-only) | require multi-symbol validation as gate prerequisite | **YES** |
| R4 | Weakening validation indirectly via cost change — gate becomes easier to pass | MEDIUM | MEDIUM | preserve val_neg_pnl semantics; only adjust cost; never adjust gate criteria | NO (manageable) |
| R5 | Allowing poor alphas into staging — pipeline becomes noisier with marginal candidates | MEDIUM | HIGH | upstream filter: require positive train_pnl AND positive val_pnl simultaneously | NO if R5 mitigation applied |
| R6 | Increased turnover after calibration — strategies that "unlock" with lower cost are high-turnover by construction | MEDIUM | HIGH | rate-limit per-symbol trade frequency; impose min_hold or per-day trade cap | NO if rate limit applied |
| R7 | Hidden slippage on real exchange — modeled 0.5 bps slippage may be optimistic for size | MEDIUM | MEDIUM (depends on order size) | conservative slippage curve; halt promotion if observed slippage exceeds model by 50% | NO (monitorable) |
| R8 | Fee tier mismatch — account upgrades reduce cost but downgrades increase it | LOW | LOW | per-account fee tier sourced from API on each calibration run | NO |
| R9 | Live execution mismatch — modeling assumes 100% maker but real fills are mixed | **HIGH** | HIGH | require maker-fill-rate measurement (NOT YET IMPLEMENTED in zangetsu) before any cost reduction | **YES** |
| R10 | Regime shift on SOL — val-period favorability disappears in live | **HIGH** | MEDIUM | require multi-regime validation across multiple training windows | **YES** |
| R11 | Cost change cascades into Arena threshold tuning — A2_MIN_TRADES, deployable_count, etc. | MEDIUM | MEDIUM | freeze all downstream thresholds; cost change must NOT propagate | NO if frozen |
| R12 | Audit / governance trail for cost change — must be traceable + reversible | LOW | LOW | always change via VERSION_LOG entry + signed PR + decision record | NO |

## 2. Aggregate Risk Score

| Severity | Count | Blocking |
| --- | --- | --- |
| HIGH | 5 (R1, R2, R3, R9, R10) | **all 5 are blocking** |
| MEDIUM | 5 (R4-R7, R11) | 0 blocking with mitigations |
| LOW | 2 (R8, R12) | 0 blocking |

**5 of 12 risks are HIGH severity AND BLOCK implementation.** None have mitigations that can be implemented within this order's scope.

## 3. Critical Blockers (cannot be lifted without infrastructure work)

### Blocker B1 — Maker-fill-rate measurement infrastructure (R1, R9)

The cost=0.5x level corresponds to an execution profile where ≥80% of fills are maker. zangetsu currently:
- Does NOT route maker orders
- Does NOT measure real fill rate per symbol
- Does NOT split realized cost into maker/taker components

→ Lowering cost_bps without first building this measurement layer is **changing the model based on a profile we do not yet execute or observe.**

### Blocker B2 — Multi-symbol validation requirement (R3, R10)

Currently the val gate accepts any cell with val_pnl > 0 regardless of cross-symbol generalization. Phase 3 shows 100% of cost=0.5x survivors fail cross-symbol generalization. Without:
- A "minimum 2 of 3 symbols positive" gate, OR
- Multi-window train/val splits

…the calibration window will fill with single-symbol artifacts that fail in live.

### Blocker B3 — Train+val combined Sharpe filter (R2)

Currently the val gate is permissive enough that train-val divergent cells can pass (8/8 surviving cells have negative train PnL). Without:
- A "train_pnl > 0 AND val_pnl > 0" gate, OR
- A combined-Sharpe gate ≥ 0.4

…non-stationary artifacts will dominate the survivor pool.

## 4. Risk-Aware Implementation Path

If cost calibration were ever to proceed, the implementation order would NEED to address **all three blockers** before changing the cost constant:

| Order step | Purpose | Implementation type |
| --- | --- | --- |
| 1. Maker-fill-rate measurement | observed cost split | runtime instrumentation (no policy change) |
| 2. Combined train+val Sharpe gate | reject train-val divergent cells | val_filter contract upgrade |
| 3. Multi-symbol generalization gate | reject single-symbol artifacts | val_filter contract upgrade |
| 4. Execution-mode-aware cost model | replace flat per-symbol bps | cost_model.py extension (maker_bps + taker_bps separately weighted by observed fill mix) |
| 5. ONLY THEN — re-run calibration matrix with fixed gates | observe whether any survivor remains | offline replay |

Steps 1-4 are **prerequisites**, not the main change. Only after those are in place does step 5's calibration analysis become decision-grade.

## 5. Counter-Question: Should We Change Cost Calibration AT ALL?

| Question | Evidence-based Answer |
| --- | --- |
| Is the current 11.5 bps cost realistic for the project's current execution capability? | YES (taker-heavy, retail tier, market orders only) |
| Is cost the only barrier to alpha-zoo survival? | NO — Phase 8 found alpha universe weakness as the secondary cause; even at zero cost only 47% of cells survive |
| Would lowering cost unblock a meaningful number of stable winners? | NO — Phase 3 shows 100% of cost=0.5x survivors are artifacts |
| Is there parallel infrastructure work that addresses cost without changing the model? | YES — execution-mode-aware order routing reduces real cost while keeping the model conservative |

→ **Lowering cost_bps in the model is NOT the right intervention.** The right intervention is **reducing real execution cost** (via maker order routing) and only THEN reflecting it in the cost model after the new fill profile is measured.

## 6. Phase 4 Classification

| Verdict | Match? |
| --- | --- |
| CALIBRATION_CHANGE_LOW_RISK | NO |
| CALIBRATION_CHANGE_MEDIUM_RISK | NO |
| **CALIBRATION_CHANGE_HIGH_RISK** | **YES — 5 HIGH-severity blockers** |
| **CALIBRATION_CHANGE_BLOCKED** | **YES — 3 critical blockers (B1, B2, B3) cannot be lifted within current pipeline state** |

→ **Phase 4 verdict: CALIBRATION_CHANGE_HIGH_RISK + CALIBRATION_CHANGE_BLOCKED.**

A direct global cost reduction from 1.0x to 0.5x is not safe. The blockers are infrastructural (maker fill measurement) and pipeline-contract (combined-sharpe + multi-symbol gates), not just numeric. Until those are in place, the calibration window survivors are by construction unreliable.
