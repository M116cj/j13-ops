# 07 — FINAL REPORT (CLOSURE)

**TEAM ORDER**: 0-9Y-HE5-DEPLOYABLE-FLOW-RECHECK
**Date**: 2026-04-29
**Phase**: 7 / 8 (final closure)
**Type**: System-wide closure judgment for `0-9Y-FINAL-ZANGETSU-ALPHA-EDGE-RESTORATION-PROGRAM`

## Final verdict
**COMPLETE_HE5_EDGE_EXHAUSTED**

Within the explored axes (OP1 + TF + HE) and master-order forbidden constraints (no change to validation / cost / A2_MIN_TRADES / champion / deployable / execution / capital / risk / alpha_zoo / CANARY / production), the system **cannot produce deployable alpha**. The "edge axis" has been fully tuned out — every alpha-side intervention available without forbidden modifications has been tested and either (a) showed insufficient effect or (b) was decisively falsified by live data.

Future deployable production requires moving OUTSIDE the alpha-side axes — specifically into structural cost reduction, fundamental execution-policy redesign, or an entirely new improvement axis (microstructure, alternative validation, etc.).

## HEAD
- HEAD before: `37346fee5fa13e18409dad46c6db43cd6bae6812` (post-HE4)
- HEAD after: TBD (Phase 8 docs-only commit on `phase-8/0-9y-he5-deployable-flow-recheck`)

## Question 1 — Is there a deployable path?
**NO.**
- 0 alphas have ever crossed `net > 0` across 3266 batches × 32 660 alpha entries (HE4 dataset)
- Closest GP-discovered batch: -0.27 bps (XRPUSDT @ h=360)
- Closest manual_seed alpha: A1 PnL = +0.65 bps but A2 reconstruction rejects (V9-V10 stage mismatch)
- 0 alphas have ever passed Arena 2 in any state across the entire codebase generation
- `deployable_count = 0` permanent

## Question 2 — If no path, which bottleneck?
**TWO bottlenecks, decoupled:**

### Bottleneck 1 (primary) — `COST_TOO_HIGH`
- gross > 0 in **99.94%** of batches → edge exists
- cost (14.5 bps round-trip × ~980 trades / batch) routinely exceeds gross
- cost / gross ratio = **1.55** stable across all observations
- 99.77% of A1 rejects = `COST_NEGATIVE`

### Bottleneck 2 (secondary) — A2 RECONSTRUCTION GAP
- 89 manual_seed alphas (only ones that passed A1) reach A2
- All 89 rejected at A2's `bt.total_trades < 25` gate
- Cause: V9 threshold-voting reconstruction in A2 produces fewer trades than V10 alpha-expression backtest in A1
- A2 reject reason in passport: `"see_engine_log_for_reject_reason"` (historical logs rotated)
- This is a **stage-mismatch** between A1 and A2's signal-generation paths, not an economic edge issue

## Question 3 — Can a "small change" solve it?
**No.** Master-order forbidden list explicitly blocks every small-change candidate:
- ❌ Cost model unchanged (would need 35%+ reduction; cost is forbidden)
- ❌ `A2_MIN_TRADES = 25` unchanged (forbidden)
- ❌ Validation thresholds unchanged (forbidden)
- ❌ Champion promotion / deployable semantics unchanged (forbidden)

The only "small change" candidates are:
- TF3-style aggregation (already tested live: improves but cannot flip net positive)
- Horizon variation (HE4 falsified)
- Primitive expansion (OP1 done; doesn't address cost)

**No small change within constraints can produce deployable alpha.**

## Question 4 — Is a new axis required?
**YES.** The viable next-phase axes (all OUTSIDE current explored space):

1. **Cost reduction (operator-side)** — exchange-tier negotiation, maker-only execution routing, smart-order routing. Outside zangetsu's algorithmic scope.
2. **Win-rate uplift via deeper feature space** — microstructure features (orderbook, trade flow), alternative IC formulations, regime-conditional fitness. Counterfactual: +5pp win_rate would flip system net to +1.18 bps (estimated symmetric model).
3. **Execution-policy redesign** — horizon-aware `min_hold` (currently fixed at 60); HE4's discovery that horizon controls only GP-search target, NOT trading lifespan, suggests a small architectural fix here could unlock real horizon-induced trade-frequency change.
4. **A2 reconstruction fix** — bring V10 alpha-expression backtest path into A2 (eliminating the V9-V10 mismatch); would let manual_seed alphas pass A2. May or may not respect "no change to A2 pass/fail logic" depending on whether the fix is purely the pass route or the gate criteria.
5. **Strategic pivot** — new market segment, alternative timeframe (1H instead of 1m), spot vs perpetuals, etc.

## Per-axis summary table

| Axis | Status |
|---|---|
| horizon (HE1-4) | ❌ NO_HORIZON_EDGE (live falsified, p > 0.24) |
| aggregation (TF2-4) | ⚠️ improves (-13% cost/gross) but insufficient |
| feature space (OP1) | ⚠️ richer primitives but no observable economic uplift |
| cost | 🔒 LOCKED (real, structural) |
| execution policy (`min_hold=60`) | 🔒 LOCKED |
| validation thresholds | 🔒 LOCKED |
| `A2_MIN_TRADES=25` | 🔒 LOCKED |
| champion promotion | 🔒 LOCKED |
| `deployable_count` semantics | 🔒 LOCKED |
| `alpha_zoo` execution | 🔒 BLOCKED |
| CANARY | 🔒 BLOCKED |
| production rollout | 🔒 NOT STARTED |

## Counterfactual lever summary
| Lever | Effect | Feasibility within HE5 constraints |
|---|---|---|
| Cost = 0.5x | 99.57% batches positive | ❌ forbidden |
| Cost = 0.7x | 25.78% batches positive (tipping point) | ❌ forbidden |
| Trade halving (TF3-style) | net stays negative | ⚠️ tested live, insufficient |
| Win-rate +5pp | net flips to +1.18 bps | ⚠️ no proven path within current architecture |

**No single lever within constraints flips the system positive.**

## Stability assessment
- Telemetry conservation = 0 across all observed batches ✅
- UNKNOWN_REJECT = 0 ✅
- COUNTER_INCONSISTENCY = 0 ✅
- Workers running stable on baseline post-HE4 cleanup ✅
- DB pipeline state unchanged throughout HE5 (no writes) ✅

## Forbidden ops audit
**0 forbidden ops.** HE5 is docs-only. No source / DB / env / runtime mutation.

## Whether validation / cost / A2 / alpha_zoo / CANARY / production changed
**ALL NO.**

## Q1 / Q2 / Q3
- **Q1 (5 dims)**: PASS — analysis is read-only; no input boundary, fail-closed, dependency, concurrency, or scope-creep risks
- **Q2**: PASS — recovery path = retain prior state; HE5 introduces no failure modes
- **Q3**: PASS — minimal, exactly what closure order required

## Next-step recommendation
This is a **system-wide closure order**. The TF + HE + OP series (OP1 → TF2 → TF3 → TF4 → HE1 → HE2 → HE3 → HE4 → HE5) is **complete**. Next steps are j13's strategic call:

### Option A — Structural cost intervention
Negotiate exchange tier, implement maker-only routing, smart-order execution. Outside zangetsu codebase.

### Option B — Architectural redesign (within zangetsu)
- Horizon-aware `min_hold` in `alpha_signal.py` (small code change; not in TF/HE forbidden list)
- A2 reconstruction unification (V10-only)
- Microstructure features (new primitives, new data ingestion)

### Option C — Strategic pivot
Different market / different timeframe / different instrument class. Possibly fresh design from `0-9Z-MASTER` or successor mission.

### Option D — Project closure / pause
Document the negative result thoroughly (this PR), pause active development, redirect resources.

## Honest acknowledgement
The HE5 closure verdict is a **negative result on a deployable production**. This is not a failure of effort — it is a successful determination that the explored design space (OP1+TF+HE) is closed. Knowing this is more valuable than continuing to tune within it.

## Final state
- Complete TF + HE + OP series across 9 PRs (PR #65 → #72) merged signed (ED25519, M116cj)
- Fully tested infrastructure (217+ tests across all orders, 0 failures)
- Conservation invariant preserved across ~36 000 alpha entries observed
- Forbidden constraints honored throughout
- Documented architectural insights for next-phase decisions

Per master-order Expected verdict: `COMPLETE_HE5_EDGE_EXHAUSTED` (j13's most-likely prediction confirmed).

## Verdict (final)
**COMPLETE_HE5_EDGE_EXHAUSTED**

The current design space is exhausted. Future deployable alpha production requires a new axis OUTSIDE OP1+TF+HE.
