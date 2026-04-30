# 04 — Long / Short Axis Viability

**TEAM ORDER**: 0-9AA — Phase 4
**Date**: 2026-04-30
**Mode**: READ-ONLY / DECISION-ONLY

## Mandatory Rule

Every axis must be evaluated separately for LONG and SHORT. No combined-only conclusion is allowed. If only one side is viable, axis is `SIDE_SPECIFIC_CANDIDATE`. If both sides have plausible mechanisms, axis is `TWO_SIDED_CANDIDATE`.

## L/S Viability Matrix

| Axis | LONG Hypothesis | SHORT Hypothesis | Symmetric? | Funding Risk (LONG) | Funding Risk (SHORT) | Cost Risk | Side-Specific Risk | Verdict |
|---|---|---|---|---|---|---|---|---|
| **A — Microstructure** | bid-side imbalance / depth dominance precedes upward price movement | ask-side imbalance / depth dominance precedes downward price movement | yes (bid↔ask symmetry) | bid-side adverse selection if maker fill assumed | ask-side adverse selection if maker fill assumed | very high (HFT-grade fees + queue cost) | both sides equally data-blocked | `TWO_SIDED_CANDIDATE_BUT_DATA_BLOCKED` |
| **B — Funding / OI** | negative funding + rising OI → shorts overcrowded → squeeze upside; OI build under price floor → reversal up | positive funding + rising OI → longs overcrowded → squeeze downside; OI build under price ceiling → reversal down | yes (funding sign-flip + OI direction) | LONG receives funding when funding<0 → carries-positive | SHORT receives funding when funding>0 → carries-positive | low-medium (8h holds, low turnover) | one side may dominate in regime where funding rarely flips sign | `TWO_SIDED_CANDIDATE` |
| **C — Regime conditional** | trend-up regime + low-vol gates LONG entries; vol-expansion + bullish session gates LONG breakouts | trend-down regime + low-vol gates SHORT entries; vol-expansion + bearish session gates SHORT breakouts | yes (regime gates can mirror) | mild | mild | medium (turnover depends on regime gating tightness) | regime classifier may bias to one side in long bull/bear stretches | `TWO_SIDED_CANDIDATE` |
| **D — Cross-sectional rank** | LONG top-K relative-strength symbols | SHORT bottom-K relative-strength symbols | yes (rank-based natural symmetry) | LONG of strong-trend symbols often pays funding (positive funding regime) | SHORT of weak/falling symbols often receives funding | low (rebalance frequency controllable) | universe of 14 symbols may be too small for robust K-quartiles | `TWO_SIDED_CANDIDATE_WITH_UNIVERSE_RISK` |
| **E — Liquidity / volume shock** | volume-confirmed up move → continuation up | volume-confirmed down move → continuation down; volume vacuum → mean-reversion both ways | partially (continuation symmetric; vacuum may be asymmetric in crypto) | mild | mild | medium-high (event-driven, can be high turnover) | volume regime asymmetry — bull markets more volume on up moves | `TWO_SIDED_CANDIDATE` |
| **F — Volatility expansion** | post-compression breakout up | post-compression breakout down | yes | mild | mild | high (false breakouts cost) | breakout-direction filter is a separate problem; without it, both sides equally fragile | `TWO_SIDED_CANDIDATE_NEEDS_DIRECTION_FILTER` |
| **G — Alt timeframe / universe** | timeframe / universe is a *modifier*, not a primary side hypothesis | same | n/a | n/a | n/a | n/a | not a side question | `MODIFIER_ONLY` |
| **H — Hybrid** | inherits from chosen components | inherits from chosen components | depends on components | depends | depends | depends | inherits component risks | `TWO_SIDED_IF_COMPONENTS_TWO_SIDED` |

## Verdict Application Rules

- An axis cannot be `AXIS_SELECTED` if LONG/SHORT cannot be separately evaluated.
- Microstructure (A) is `TWO_SIDED` in mechanism but `DATA_BLOCKED` in evidence — does not advance.
- Funding/OI (B) and Regime (C) have the cleanest two-sided mechanisms with available data.
- Cross-sectional (D) is two-sided but carries universe-size risk (14 symbols).
- Volatility (F) is two-sided but needs an external direction filter — better as a hybrid component.
- Alt-timeframe (G) is a modifier, not a side hypothesis — supporting only.

## Implication for 0-9AA Final Selection

- Strongest two-sided + data-ready candidates: **C (Regime), B (Funding/OI), D (Cross-sectional), E (Liquidity shock)**.
- Hybrid (H) becomes attractive when it combines a regime gate (C) with a directional component (B/D/E).
- Microstructure (A) is two-sided in theory and deferred until data exists.

## Deliverable

`04_long_short_axis_viability.md` — frozen.
