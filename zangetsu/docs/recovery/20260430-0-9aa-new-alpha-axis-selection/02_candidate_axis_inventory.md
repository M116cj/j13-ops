# 02 — Candidate Axis Inventory

**TEAM ORDER**: 0-9AA — Phase 2
**Date**: 2026-04-30
**Mode**: READ-ONLY / DECISION-ONLY

## Inventory of 8 Candidate Alpha Axes

| Axis | Description | Primary Data Required | Data Ready? | L/S Splittable? | Novel vs 0-9Y? | Initial Verdict |
|---|---|---|---|---|---|---|
| **A — Microstructure imbalance** | bid/ask pressure, depth imbalance, queue imbalance, spread compression, short-term liquidity shock | bid/ask, top-of-book depth, trade prints | **NO** (proven by 0-9ZA Phase 3) | yes (bid-side vs ask-side) | YES (orthogonal to OHLCV-derived primitives) | `HIGH_VALUE_BUT_DATA_BLOCKED` |
| **B — Funding / OI / Liquidation** | funding rate, OI delta, liquidation clusters, long/short crowding, basis/perp premium, positioning squeeze | funding, OI, liquidations | **PARTIAL** (funding ✓, OI ✓, liquidations ✗) | yes (funding sign + OI direction) | YES (orthogonal to OHLCV primitives) | `HIGH_PRIORITY_PARTIAL_DATA` |
| **C — Regime-conditional fitness** | volatility regime, trend/range regime, liquidity regime, funding regime, session regime | OHLCV (+ funding for funding regime) | **YES** | yes (regime gates can be side-asymmetric) | PARTIAL — regime gating was *not* the primary axis in 0-9Y; closest precedent was `tf*` aggregation, which is a different mechanism | `MOST_DATA_READY` |
| **D — Cross-sectional relative strength / rotation** | relative momentum, symbol rank, leader-lagger, spread between coins, beta-adjusted outperformance | OHLCV (multi-symbol universe) | **YES** (14 symbols available) | yes (rank-based long top, short bottom) | YES — 0-9Y operated **per-symbol**, not cross-sectional | `DATA_READY_CANDIDATE` |
| **E — Liquidity / volume shock** | volume acceleration, liquidity expansion, liquidity vacuum, abnormal turnover, volume-price divergence, exhaustion | OHLCV volume (+ optionally OI) | **YES** | yes (long volume-confirmed up, short volume-confirmed down) | PARTIAL — `op1` registered volume primitives but not as a *shock-detection* axis | `MEDIUM_HIGH_PRIORITY` |
| **F — Volatility expansion / compression** | realized vol, ATR compression, breakout vol, post-compression expansion, vol-of-vol, range expansion | OHLCV | **YES** | yes (long breakout up, short breakout down) | PARTIAL — covered by some `op1` primitives; pure regime + breakout combination not isolated | `SECONDARY_CANDIDATE` |
| **G — Alternative timeframe / instrument universe** | different bar interval, top-liquidity-only universe, alts vs majors, perp vs spot proxy, session-specific | OHLCV (resampling) | **YES** | not a side question — universe-level | NO — 0-9Y `he*` already swept multi-horizon | `SUPPORTING_AXIS_ONLY` |
| **H — Hybrid meta-axis** | regime + funding, regime + relative strength, liquidity shock + trend, OI/funding + price exhaustion, volume shock + cross-sectional rank | composition of B/C/D/E components | **YES** if components data-ready | yes if components are | YES — no hybrid was tested in 0-9Y | `BEST_IF_SELECTION_SCORE_SUPPORTS` |

## Novelty Filter (Reject Duplicates of Exhausted Work)

| Axis | Reason it is/is-not a duplicate of 0-9Y |
|---|---|
| A | Not a duplicate — 0-9Y was OHLCV-only; microstructure is a different data layer |
| B | Not a duplicate — 0-9Y did not consume funding/OI as alpha primitives, only as cost components |
| C | **Partial novelty** — `tf*` was aggregation, not regime-gating; regime axis can be designed orthogonal |
| D | Not a duplicate — 0-9Y operated per-symbol; cross-sectional rank is a different signal type |
| E | **Partial novelty** — volume primitives were in the GP set, but as features not as a shock-detection axis |
| F | **Partial novelty** — vol metrics existed; pure compression-then-expansion was not isolated |
| G | **Likely duplicate** — `he1`-`he5` swept timeframes; treat as supporting only |
| H | Novel by construction (component-level novelty preserved) |

## Acceptance

- 8 axes inventoried
- Each tagged for data readiness, L/S splittability, novelty, and initial verdict
- Microstructure tagged `DATA_BLOCKED` per 0-9ZA, not silently passed forward as ready
- G (alt timeframe) tagged as supporting-only to avoid re-running 0-9Y `he*` work

## Deliverable

`02_candidate_axis_inventory.md` — frozen.
