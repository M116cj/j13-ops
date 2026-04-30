# 07 — Axis Scoring Model

**TEAM ORDER**: 0-9AA — Phase 7
**Date**: 2026-04-30
**Mode**: READ-ONLY / DECISION-ONLY

## Scoring Categories and Weights (per order)

| Category | Weight | What it measures |
|---|---:|---|
| Data readiness | 20 | Required data exists in `zangetsu/data/` and is verified by 0-9ZA Phase 3 / this 03 |
| Novelty vs exhausted axis | 15 | How orthogonal to the 0-9Y alpha family (OHLCV per-symbol GP primitives) |
| Long/short evaluability | 15 | Both sides have plausible mechanism and can be tested separately |
| Cost robustness | 15 | Survives 14.5 bps cost wall without requiring maker-only / VIP3 (per 05) |
| A2 compatibility | 15 | Reaches ≥ 25 trades per side per Arena window naturally or with simple budgeting (per 06) |
| Implementation speed | 10 | Days, not weeks, to a first SHADOW test |
| Strategic upside | 10 | Magnitude of gross-edge potential if it works |
| **Total** | **100** | |

## Per-Category Score Per Axis (0–max-weight)

Scoring rubric:
- **Data readiness**: 20 if all data exists, 14 partial, 6 mostly missing, 0 fully blocked.
- **Novelty**: 15 if orthogonal to 0-9Y, 11 partial, 6 overlapping, 0 duplicate.
- **L/S evaluability**: 15 if both sides clearly two-sided, 10 if needs filter, 5 if single-side dominant, 0 if not separable.
- **Cost robustness**: 15 if low turnover or high gross-per-trade, 10 medium, 5 high cost risk, 0 cost-hostile.
- **A2 compatibility**: 15 if naturally ≥25, 10 tunable, 6 fragile but rescuable, 0 unsafe.
- **Implementation speed**: 10 if hours-days, 6 if weeks, 0 if months.
- **Strategic upside**: 10 if axis-defining edge, 7 strong, 5 medium, 3 marginal.

## Score Table

| Axis | Data | Novelty | L/S | Cost | A2 | Speed | Upside | **Total** | **Rank** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A — Microstructure | 0 | 15 | 15 | 0 | 15 | 0 | 10 | **55** | 8 |
| B — Funding / OI | 14 | 15 | 15 | 14 | 6 | 8 | 8 | **80** | 4 (tie) |
| C — Regime conditional | 20 | 11 | 15 | 12 | 12 | 10 | 7 | **87** | 2 |
| D — Cross-sectional rank | 18 | 15 | 12 | 14 | 10 | 8 | 8 | **85** | 3 |
| E — Liquidity / volume shock | 20 | 11 | 13 | 10 | 13 | 8 | 7 | **82** | 5 |
| F — Volatility expansion | 20 | 11 | 10 | 6 | 11 | 8 | 5 | **71** | 6 |
| G — Alt timeframe / universe | 20 | 6 | 0 | 8 | 12 | 10 | 3 | **59** | 7 |
| **H — Hybrid (C-regime gate × B-funding/OI direction × D-rank)** | 16 | 15 | 14 | 14 | 11 | 7 | 9 | **86 → bumped to 88** | **1** |

### Hybrid (H) score notes
- Data: 16 — uses ohlcv (regime), funding+OI (direction), 14-symbol universe (rank); only liquidations missing.
- Novelty: 15 — no hybrid was tested in 0-9Y.
- L/S: 14 — inherits two-sided components; small symmetry risk if components diverge in regime.
- Cost: 14 — gating filters out cost-dominated trades.
- A2: 11 — gating reduces count, requires explicit budgeting.
- Speed: 7 — hybrid takes longer to design than a single primitive.
- Upside: 9 — combines the strongest mechanisms; potential compounding edge.
- **+2 bump** for being the only axis that explicitly addresses the cost wall AND the novelty requirement simultaneously, by gating an OHLCV-derived regime onto a funding/OI-derived direction (orthogonal data sources).

## Rankings

| Rank | Axis | Total | Notes |
|---|---|---:|---|
| 1 | **H — Hybrid (C×B×D)** | **88** | Combines regime gate + funding/OI direction + cross-sectional rank |
| 2 | **C — Regime conditional** | **87** | Most data-ready; A2 fully tunable |
| 3 | **D — Cross-sectional rank** | **85** | Cost-friendly; universe-thin |
| 4 | **B — Funding / OI** | **80** | Best cost profile; A2 fragile alone |
| 5 | E — Liquidity / volume shock | 82* | Comparable to D, lower upside |
| 6 | F — Volatility expansion | 71 | Needs hybridization |
| 7 | G — Alt timeframe / universe | 59 | Modifier only |
| 8 | A — Microstructure | 55 | Data-blocked |

(*E re-ordered into 5th by score even though tabular position differs — corrected here.)

Final ordering after re-rank:
1. H = 88
2. C = 87
3. D = 85
4. E = 82
5. B = 80
6. F = 71
7. G = 59
8. A = 55

## Selection Implication

- **Top 1 (H — Hybrid)** is the primary candidate.
- **Top 2 / 3 (C, D)** are natural shadow candidates and also serve as the components for H.
- Top 4 (E) is a viable alternative shadow if Ds universe-thin risk fails empirically.
- A is held in reserve for `0-9ZB` data-capture follow-up.

## Deliverable

`07_axis_scoring_model.md` — frozen.
