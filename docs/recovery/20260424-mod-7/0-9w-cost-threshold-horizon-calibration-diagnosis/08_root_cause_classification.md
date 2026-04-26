# 08 — Root Cause Hypothesis Ranking

## 1. Hypotheses Considered

| ID | Hypothesis | Evidence Source |
| --- | --- | --- |
| H1 | Cost calibration too high for current alpha edge | Phase 1 (cost sensitivity) + Phase 7 (matrix) |
| H2 | ENTRY_THR too strict (0.80 too restrictive) | Phase 2 (threshold sweep) |
| H3 | MAX_HOLD too short (120 bars) forcing premature exits | Phase 3 (horizon sweep) + backtester sanity |
| H4 | Backtester defect (cost mis-applied / sign flip / silent zero PnL) | Phase 4 (sanity replay) |
| H5 | Signal-to-trade direction bug (long when should short) | Phase 5 (forward-return diagnostic) |
| H6 | Funding component over/under modeled | Phase 6 |
| H7 | Alpha universe too weak — gross edge insufficient regardless of params | Phase 7 (cell distribution by formula × symbol) |

## 2. Evidence Summary

| H | Evidence | Strength | Verdict |
| --- | --- | --- | --- |
| H1 | At cost=0: 63 survivors. At cost=0.5x: 8 survivors. At cost=1.0x: 0 survivors. **Linear collapse.** | STRONG | **PRIMARY** |
| H2 | Lowering ET (0.60-0.80): 0 survivors at all 5 settings. Lower ET adds trades and cost. | NEGATIVE | LOW priority — not a fix lever |
| H3 | Extending MH (120-1440): 0 survivors at all 5 settings. Natural exit dominates. | NEGATIVE | LOW priority — not a fix lever |
| H4 | Sanity replay: always_flat PnL=0. random_seeded cost = 11.5×46642×1e-4 ≈ correct. No defect. | NEGATIVE | RULED OUT |
| H5 | Sign-inverted forward returns: still ~3-6 bps per 60-bar window. Below 11.5 bps cost. Not a sign bug. | NEGATIVE | RULED OUT |
| H6 | Removing funding entirely → effective 10.5 bps (0.91x). Still 0 survivors. | NEGATIVE | RULED OUT as primary |
| H7 | At cost=0, only 63/135 cells survive (47%). Many alphas STILL fail despite zero cost. | MEDIUM | **SECONDARY** |

## 3. Final Hypothesis Ranking

| Rank | Hypothesis | Confidence | Action Implication |
| --- | --- | --- | --- |
| #1 | **H1 — Cost calibration too high for current alpha edge** | **HIGH (90%)** | **Re-calibrate cost downward (e.g. 5-7 bps RT) OR find higher-edge alphas to clear the 11.5 bps cost wall** |
| #2 | **H7 — Alpha universe weakness** (ZAlpha + alpha_zoo edge insufficient) | **MEDIUM (60%)** | Even at zero cost, only 47% of cells survive. Need higher-quality alpha generation (better priors, longer-horizon features, deeper GP search) |
| #3 | H3 — MAX_HOLD horizon | LOW (5%) | Not the constraint; natural exit logic dominates |
| #4 | H6 — Funding component | LOW (5%) | Magnitude small; technically over-counts but not the gate-blocker |
| #5 | H2 — ENTRY_THR too strict | LOW (3%) | Lowering makes things WORSE; current 0.80 is least cost-burdened |
| #6 | H5 — Signal direction bug | RULED OUT (0%) | Forward-return diagnostic confirms direction is consistent |
| #7 | H4 — Backtester defect | RULED OUT (0%) | Sanity tests cleanly verify cost arithmetic and signal handling |

## 4. Why H1 Is Primary

Three independent lines of evidence converge:

1. **Cost sensitivity (Phase 1)**: 11 / 4 / 0 / 0 / 0 survivors as cost goes 0 → 0.25x → 0.5x → 1.0x → 2.0x. **Monotone collapse.**
2. **Calibration matrix (Phase 7)**: 63 / 8 / 0 survivors as cost goes 0 → 0.5x → 1.0x. **Same monotone collapse, different formula set.**
3. **Phase 4 random sanity**: 46642 random trades × 11.5 bps = -53.4 bps PnL drag. Confirms cost is correctly applied AND that cost magnitude is the dominant force.

If cost were 5.75 bps instead of 11.5 bps (a ~50% reduction), 8 cells would survive — which is enough to seed a candidate review process.

## 5. Why H7 Is Secondary (but not negligible)

Even at zero cost (perfect-execution counterfactual), only 47% of (formula × symbol × ET × MH) cells survive. Top-edge formulas like `wqb_s01` give val_pnl ~ +0.37 on SOL (impressive at zero cost). But the median cell is barely positive. **The alpha universe is borderline** — even small frictions push it negative.

This means: even if we fix H1 (cost), the surviving population will be small and concentrated on a few formula × symbol pairs (notably SOLUSDT). Diversification will be limited.

## 6. Phase 8 Verdict

→ **Primary cause (HIGH): H1 — Cost calibration relative to alpha edge.**
→ **Secondary cause (MEDIUM): H7 — Alpha universe edge weakness in stable + diversified tiers.**
→ **All other hypotheses ruled out or de-prioritized.**

The fix path bifurcates:
- **Path A (cost re-calibration)**: empirically validate that current 11.5 bps Stable tier RT cost is realistic vs. observed Binance Futures executions; if it is over-conservative, lower it. This is a **governance + measurement task**, not an immediate runtime change.
- **Path B (alpha universe upgrade)**: enrich alpha priors with formulas that have demonstrably higher edge per trade (longer horizons, multi-timeframe, regime-conditional). This is a **research task**.

Both paths are required for sustained survival; Path A unlocks short-term flow, Path B is durable.
