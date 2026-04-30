# 09 — Final Axis Decision

**TEAM ORDER**: 0-9AA — Phase 9
**Date**: 2026-04-30
**Mode**: READ-ONLY / DECISION-ONLY

## Decision Type

`DUAL_AXIS_SHADOW_SELECTED` (mapped to final-report verdict `MULTI_AXIS_SHADOW_REQUIRED`).

Reasoning: the score table puts H (88), C (87), and D (85) within ~3 points of each other. H is structurally the strongest because it gates components together, but C and D are independently strong and also serve as Hs components — running them in parallel as shadow tournaments simultaneously validates Hs component assumptions and produces fall-back candidates if the hybrid composition fails.

## Primary Axis

**H — Hybrid (C-Regime gate × B-Funding/OI direction × D-Cross-sectional rank)**

Why H is primary:
- highest weighted score (88)
- only axis that simultaneously addresses (1) the cost wall (cost-robust gating), (2) the novelty requirement (orthogonal data sources), and (3) two-sided viability (each component is two-sided)
- triple-gate naturally produces high gross-per-trade, the structural answer to 0-9Y exhaustion

## Secondary (Shadow-Parallel) Axes

**C — Regime-Conditional Fitness** (score 87) — also serves as the gate component of H
**D — Cross-Sectional Relative Strength** (score 85) — also serves as the rank component of H

These run in shadow alongside H so that:
- if H underperforms because component composition is wrong, C or D survives as the fallback
- C and D individually de-risk H by validating their own contributions
- the tournament avoids over-committing to H if its triple-gate is too sparse

## Deferred Axis

**A — Microstructure Imbalance** (score 55, data-blocked)

Held in reserve. Re-judged after the 0-9ZA-recommended `0-9ZB-MARKET-MICROSTRUCTURE-DATA-CAPTURE-SHADOW` produces empirical bid/ask, depth, and trade-print history. Not selected for 0-9AA execution.

## Rejected Axes

| Axis | Score | Reason |
|---|---:|---|
| F — Volatility expansion | 71 | Two-sided but lacks intrinsic direction filter; better as a hybrid component than a standalone axis |
| G — Alt timeframe / universe | 59 | Modifier only, not a primary axis; 0-9Y already swept timeframes via `he*` |
| E — Liquidity / volume shock | 82 | High score, but redundant overlap with Ds volume-based rank component; held as third-tier shadow if D fails universe-thin test |
| B (standalone) — Funding/OI | 80 | Strong cost profile, but A2-fragile alone; absorbed into H rather than run standalone |

## Reasons for Rejection (Summary)

- **F**: rejected as standalone, considered as future hybrid component for breakout direction.
- **G**: not a primary axis by definition.
- **E**: redundant with Ds rank-volume composition; reserved as fallback.
- **B (standalone)**: absorbed into H because Bs sparsity is best handled by combining with Cs gating.

## Final Verdict

**Decision Type**: `DUAL_AXIS_SHADOW_SELECTED` (Phase 9 token)
**Final-Report Verdict**: `MULTI_AXIS_SHADOW_REQUIRED` (Phase 11 token)

**Primary**: H — Hybrid (C × B × D)
**Shadow-parallel**: C, D
**Deferred**: A
**Rejected**: F, G; E reserved tertiary; B absorbed into H

## Next Order

`0-9AB-MULTI-AXIS-SHADOW-TOURNAMENT`

Objective:
- Build SHADOW pipelines for H, C, and D in parallel.
- Validate first-falsification tests (08): gross-per-trade ≥ 25 bps for H and 30 bps for Ds rank spread.
- Compare A2 survival, cost-net, and L/S symmetry across the three.
- Recommend a single axis for `0-9AC-[selected]-PRODUCTION-DESIGN` (or extend deferred A via parallel `0-9ZB-MARKET-MICROSTRUCTURE-DATA-CAPTURE-SHADOW`).

## Deliverable

`09_final_axis_decision.md` — frozen.
