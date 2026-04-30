# TEAM ORDER 0-9AA — FINAL REPORT

**Order**: 0-9AA-NEW-ALPHA-AXIS-SELECTION
**Date**: 2026-04-30
**Mode**: READ-ONLY / DECISION-ONLY / AXIS-SELECTION-ONLY

## Verdict

```
MULTI_AXIS_SHADOW_REQUIRED
```

## Baseline

| Item | Value |
|---|---|
| HEAD | `6207bb1b` |
| Parent chain | 0-9Y → 0-9Z → 0-9ZA |
| 0-9Y verdict | `COMPLETE_HE5_EDGE_EXHAUSTED` |
| 0-9Z verdict | `PATH_A_CONDITIONAL` |
| 0-9ZA verdict | `PATH_A_DATA_BLOCKED` (secondary `EXECUTION_ARCH_REQUIRED_BEFORE_PATH_A_CAN_CONTINUE`) |
| Current deployable | 0 |
| Current blocker | (1) existing alpha family exhausted; (2) maker-only path blocked on missing market microstructure data |

## Candidate Axes Evaluated (8, per AC3)

1. A — Microstructure imbalance
2. B — Funding / OI / Liquidation
3. C — Regime-conditional fitness
4. D — Cross-sectional relative strength / rotation
5. E — Liquidity / volume shock
6. F — Volatility expansion / compression
7. G — Alternative timeframe / instrument universe
8. H — Hybrid (C-Regime × B-Funding/OI × D-Cross-sectional)

## Scoring Result (out of 100)

| Rank | Axis | Total |
|---|---|---:|
| 1 | **H — Hybrid (C×B×D)** | 88 |
| 2 | **C — Regime conditional** | 87 |
| 3 | **D — Cross-sectional rank** | 85 |
| 4 | E — Liquidity / volume shock | 82 |
| 5 | B — Funding / OI standalone | 80 |
| 6 | F — Volatility expansion | 71 |
| 7 | G — Alt timeframe / universe | 59 |
| 8 | A — Microstructure imbalance | 55 (data-blocked) |

## Long / Short Result

| Question | Answer |
|---|---|
| Best LONG candidate | H (triple-gated long), C (regime-gated long) |
| Best SHORT candidate | H (triple-gated short), C (regime-gated short) |
| Two-sided candidates | A, B, C, D, E, F, H (all but G) |
| Side-specific candidates | none (no axis is selected as single-side-only) |

## Final Decision

| Field | Value |
|---|---|
| Primary next alpha axis | **H — Hybrid (Regime gate × Funding/OI direction × Cross-sectional rank)** |
| Secondary (shadow-parallel) axes | **C — Regime conditional**, **D — Cross-sectional rank** |
| Deferred axes | **A — Microstructure** (held for `0-9ZB` data-capture follow-up) |
| Tertiary fallback | **E — Liquidity / volume shock** (held if Ds 14-symbol universe proves too thin) |
| Rejected axes | **F** (lacks direction filter), **G** (modifier only); **B** absorbed into H |

## Why This Outcome (Not PATH_A_GO-style overreach, not NO_AXIS_SELECTED)

- Three top candidates (H, C, D) score within 3 points of each other; choosing one without empirical SHADOW data would be premature.
- C and D are Hs components, so running them as parallel shadows simultaneously validates Hs component assumptions and produces fall-back winners if Hs composition fails.
- A is held in reserve, not rejected — its high upside is real, and `0-9ZB` is the right gate to re-judge it.
- F and G are explicitly removed from primary contention with reasons (no direction filter / not a primary axis).

## Why This Does Not Repeat 0-9Y Exhaustion

- Components B (funding/OI) and D (cross-sectional rank) are **orthogonal** to the 0-9Y per-symbol OHLCV-GP primitives.
- Component C (regime gating) wraps existing or new primitives in a structural cost-gate the 0-9Y sweep never imposed.
- The hybrid construction H requires triple-confirmation, which structurally raises gross-per-trade — the missing ingredient that killed 0-9Y.

## Why This Does Not Repeat 0-9ZA Data Block

- A (microstructure) is explicitly deferred, not selected.
- All selected axes (H, C, D) are data-ready under the current `data/` inventory (OHLCV + funding + OI for 14 symbols).
- Liquidations data is missing but not on the critical path for H, C, or D.

## Next Order

```
0-9AB-MULTI-AXIS-SHADOW-TOURNAMENT
```

Objective:
- Build SHADOW pipelines for H, C, and D in parallel.
- Apply first-falsification tests from `08_top_axis_deep_dive.md`:
  - **H**: gross-per-trade ≥ 25 bps in gated long and gated short separately
  - **C**: at least one regime bucket of existing 0-9Y trades shows gross-per-trade ≥ 25 bps
  - **D**: rank-spread (top-K return − bottom-K return) ≥ 30 bps over rebalance window
- Compare A2 survival, cost-net, and L/S symmetry across the three.
- Recommend a single axis for `0-9AC-[AXIS]-PRODUCTION-DESIGN`.

In parallel (independent track):

```
0-9ZB-MARKET-MICROSTRUCTURE-DATA-CAPTURE-SHADOW
```

Objective: build read-only capture of bid/ask, depth, trade prints, mark price, funding (high-resolution), and timestamp alignment for future microstructure replay. Unlocks re-judgment of axis A.

## Acceptance Criteria Status

| AC | Status |
|---|---|
| AC1 — state locked at HEAD ≥ 6207bb1b | PASS |
| AC2 — 0-9Y / 0-9Z / 0-9ZA conclusions incorporated | PASS (`01_failure_context_from_0-9y_0-9z_0-9za.md`) |
| AC3 — at least 8 axes evaluated | PASS (8 axes in `02`) |
| AC4 — data availability per axis | PASS (`03`) |
| AC5 — LONG / SHORT / COMBINED notes per axis | PASS (`04`) |
| AC6 — cost / turnover risk per axis | PASS (`05`) |
| AC7 — A2 compatibility per axis | PASS (`06`) |
| AC8 — weighted scoring model ranks all axes | PASS (`07`) |
| AC9 — top 1–3 axes deep-dive | PASS (`08`, includes 4 candidates: H, C, A, D) |
| AC10 — microstructure not selected as immediately executable | PASS (deferred) |
| AC11 — no implementation or runtime mutation | PASS (`10`) |
| AC12 — controlled diff zero forbidden mutation | PASS (`10`, `FORBIDDEN_DIFF = 0`) |
| AC13 — final verdict among approved options | PASS (`MULTI_AXIS_SHADOW_REQUIRED`) |
| AC14 — next order explicitly recommended | PASS (`0-9AB-MULTI-AXIS-SHADOW-TOURNAMENT` + parallel `0-9ZB`) |

## Final Statement

0-9AA closes as a decision-closure task. Three data-ready, two-sided, cost-robust, novelty-positive axes are selected for parallel shadow tournament. Microstructure remains the highest-upside but data-blocked candidate, deferred to the dedicated data-capture order. No source mutation. No DB mutation. No live trading. No CANARY. No rollout. Controlled diff = 0 forbidden mutations.
