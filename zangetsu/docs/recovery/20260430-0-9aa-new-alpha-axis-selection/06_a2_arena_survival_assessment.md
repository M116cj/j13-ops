# 06 — A2 Arena Survival Assessment

**TEAM ORDER**: 0-9AA — Phase 6
**Date**: 2026-04-30
**Mode**: READ-ONLY / DECISION-ONLY

## Hard Constraint

`A2_MIN_TRADES = 25` (verified at `zangetsu/services/arena_gates.py:48` and `zangetsu/config/settings.py:29`). This value **does not change** under 0-9AA (STOP-3).

Any axis whose natural signal frequency cannot deliver ≥ 25 trades in an Arena-2 evaluation window for both LONG and SHORT halves is structurally fragile.

## Per-Axis A2 Survival

| Axis | Natural Trade Count | Side-Split Risk (each side ≥25) | Sparse Signal Risk | A2 Compatibility | Verdict |
|---|---|---|---|---|---|
| **A — Microstructure** | very high (HFT) | safe per side | none | high | `A2_SAFE_BUT_DATA_BLOCKED` |
| **B — Funding / OI** | low — funding ticks every 8h, regime shifts months apart | **HIGH** — single-side may struggle to reach 25 in a short window | high | risky | `A2_FRAGILE_NEEDS_LONG_WINDOW_OR_MULTI_SYMBOL` |
| **C — Regime conditional** | medium — depends on gate tightness | tunable | medium — over-tight gate kills count | tunable | `A2_TUNABLE` |
| **D — Cross-sectional rank** | medium — rebalances per period × universe | medium — 14-symbol universe, top-K and bottom-K each yield K trades per rebalance | medium | medium | `A2_MEDIUM_REQUIRES_REBALANCE_FREQ_OR_K_SIZING` |
| **E — Liquidity / volume shock** | medium-high — volume events frequent | safe per side | low | high | `A2_SAFE` |
| **F — Volatility expansion** | medium-high — compressions resolve regularly | safe in raw count, but post-direction-filter could thin | low–medium | medium | `A2_SAFE_RAW_RISKY_FILTERED` |
| **G — Alt timeframe / universe** | inherits | inherits | inherits | inherits | `MODIFIER_ONLY` |
| **H — Hybrid C-gated B/D/E** | gated subset | gating reduces count — explicit ≥25 budget required | medium | tunable but risky | `A2_TUNABLE_BUT_REQUIRES_EXPLICIT_BUDGETING` |

## A2 Risk Reasoning

1. **B alone** is the most A2-fragile candidate: funding events have ~3 per day per symbol, but signal-grade events (sign flip + crowding) are rare. Multi-symbol pooling (across the 14 perps) is required to comfortably exceed 25 per side per window.
2. **C alone** is fully tunable — A2 survival becomes a gate-tightness hyperparameter.
3. **D** depends on the rebalance frequency × K. With 14 symbols and K=3, daily rebalance gives ~3 longs + 3 shorts per day → easily ≥25 per side per Arena window.
4. **E** is naturally A2-safe — volume events are common.
5. **F** is A2-safe in raw signal but can thin after direction filtering.
6. **H** inherits the gate components A2 risk; hybrid design must explicitly budget the post-gate trade count.

## Special A2 Treatment Considerations

- No axis requires changing `A2_MIN_TRADES`. Selection must adapt to the constraint, not relax it.
- Axes (B, H) at risk of falling below 25 must use multi-symbol pooling, longer evaluation windows, or post-gate count budgeting.
- Cross-sectional (D) naturally pools across symbols — A2 risk is universe-size driven, not signal-driven.

## Implication for Selection

- A2-fragility ranking (worst to best): **B > F (after filter) > D (universe-bound) > C (tunable) > H (gated, budgeted) > E > A (data-blocked)**
- Combining **C (regime gate) + B (funding/OI direction)** trades Bs sparsity for Cs tunability — a sound A2 design.
- **D + multi-symbol pooling** survives A2 if rebalance frequency × K is calibrated.

## Deliverable

`06_a2_arena_survival_assessment.md` — frozen.
