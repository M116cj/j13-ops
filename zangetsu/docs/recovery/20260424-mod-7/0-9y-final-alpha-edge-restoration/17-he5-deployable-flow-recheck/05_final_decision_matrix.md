# 05 — FINAL DECISION MATRIX

**TEAM ORDER**: 0-9Y-HE5-DEPLOYABLE-FLOW-RECHECK
**Date**: 2026-04-29
**Phase**: 5 / 8

## Decision matrix — all explored axes

| Axis | Status | Live evidence | Constraint |
|---|---|---|---|
| **Horizon** (HE1/HE2/HE3/HE4) | ❌ NO_HORIZON_EDGE | HE4 live: p > 0.24, Cohen's d < 0.07 across 180/240/360 | Falsified by live data |
| **Aggregation / signal filtering** (TF2/TF3/TF4) | ⚠️ improves but insufficient | TF3 live: cost/gross 1.55 → 1.30, net/trade -0.00125 → -0.00097, total net -1.22 → -0.06 | Cannot flip net positive within current cost model |
| **Feature space (primitives)** (OP1) | ⚠️ richer but no observable economic uplift | A1 alphas use 9 new primitives at (60,180,240) periods; gross essentially unchanged | Primitive expansion doesn't address cost burn |
| **Cost model** | 🔒 LOCKED (forbidden) | round_total_cost_bps = 14.5 stable; cost/gross = 1.55 | Master order forbids modification |
| **Execution policy (`min_hold=60`)** | 🔒 LOCKED | Hard-coded in alpha_signal.py | Master order forbids modification |
| **A2_MIN_TRADES=25** | 🔒 LOCKED | Manual seeds reach A2 but reconstruction produces <25 trades → reject | Master order forbids modification |
| **Validation thresholds** | 🔒 LOCKED | unchanged | Master order forbids modification |
| **Champion promotion / `deployable_count` semantics** | 🔒 LOCKED | unchanged | Master order forbids modification |

## Three-path decision (per master-order Phase 5 enum)

### Path A — `SYSTEM_HAS_PATH_TO_DEPLOYABLE`
**REJECTED.** No observed alpha (GP-discovered or manual_seed) has crossed net > 0 in any window analyzed. Closest GP batch: −0.27 bps. 0/3266 batches achieve break-even. The 89 manual_seeds reach A2 but reject at trades-gate (decoupled mechanism, not solvable by axis tuning).

### Path B — `SYSTEM_REQUIRES_STRUCTURAL_CHANGE`
**SECONDARY OPTION.** Two specific structural changes would resolve the bottleneck:
1. **Cost reduction (~35%+)**: would tip 26% of batches positive at 0.7x; 99.57% positive at 0.5x. Feasible only via exchange-tier negotiation, maker-only execution routing, or cost model recalibration — outside zangetsu's algorithmic scope.
2. **Win-rate +5pp uplift**: would flip net to +1.18 bps. No proven path within current OP1/TF/HE axes; would require microstructure features, alternative validation regimes, or fundamentally different alpha-discovery mechanism.
3. **A2 reconstruction fix**: solving the V9-V10 stage mismatch in `arena23_orchestrator.py` would let manual_seed alphas pass A2 — but this potentially crosses the "do not change A2 pass/fail logic" forbidden line, requires careful scoping.

### Path C — `SYSTEM_EDGE_EXHAUSTED` (the j13-predicted verdict)
**PRIMARY OPTION.** Within the explored axes (OP1 + TF + HE) and forbidden constraints, the system cannot produce deployable alphas. The "edge axis" — i.e., the dimension along which alphas can be improved without touching cost, validation, or execution — has been **fully tuned out**:
- Primitive set expanded (OP1) — gross unchanged
- Aggregation tested (TF2/TF3/TF4) — improves quality but not enough
- Horizon tested (HE1/HE2/HE3/HE4) — no live edge
- Statistical, fixture-validated, and live-tested

Any further improvement requires moving OUTSIDE these axes — i.e., a structural / cost / execution change, or a new axis entirely (microstructure, validation regime, etc.).

## Combined verdict
**Path B + Path C are simultaneously true:**
- Edge-side axis is **EXHAUSTED** (no more tuning within OP/TF/HE will help)
- Resolution requires a **STRUCTURAL CHANGE** (cost or execution-side)

Per master-order Phase 7 verdict enum, `COMPLETE_HE5_EDGE_EXHAUSTED` is the most concise representation: the system has fully explored the alpha-side axes available without forbidden modifications, and the explored axes do not produce deployable alphas. **Future progress requires a different axis**, not finer tuning of the explored ones.

## Forbidden constraints status (final audit)
| Constraint | Status throughout HE5 |
|---|---|
| Validation logic | unchanged |
| Cost model | unchanged |
| `A2_MIN_TRADES = 25` | unchanged |
| Champion promotion | unchanged |
| `deployable_count` semantics | unchanged |
| `alpha_zoo` execution | NOT TRIGGERED |
| CANARY started | NO |
| Production rollout | NOT STARTED |
| Execution / capital / risk | NO modifications |
| DB schema | unchanged |

## Verdict
**PHASE_5_COMPLETE** — decision matrix consolidated. Expected verdict for HE5: `COMPLETE_HE5_EDGE_EXHAUSTED` with documented structural-change candidates as the only forward path.

## Next
Phase 6 — controlled diff (HE5 is docs-only).
