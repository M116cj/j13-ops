# 08 — Top Axis Deep Dive

**TEAM ORDER**: 0-9AA — Phase 8
**Date**: 2026-04-30
**Mode**: READ-ONLY / DECISION-ONLY

## Selection per Order

The order requires deep-dive on at least:
1. highest-scoring data-ready axis → **C (Regime, 87)**
2. highest-upside but data-blocked axis → **A (Microstructure, 55)**
3. best hybrid axis → **H (C×B×D, 88)**

A 4th candidate is included for shadow-tournament breadth: **D (Cross-sectional, 85)**.

---

## Deep Dive 1 — H — Hybrid (C-Regime × B-Funding/OI × D-Cross-Sectional)

### Signal hypothesis

Edge survives when:
- the **market regime** (volatility / trend / liquidity) is favorable for trend-continuation or mean-reversion (regime gate from C),
- the **funding/OI structure** indicates positioning imbalance pointing in the trade direction (B), and
- the candidate symbol is at the **rank extreme** of the 14-symbol universe (D).

### Data source

- OHLCV (`data/ohlcv/`) — regime features and price evolution
- Funding rate (`data/funding/`) — positioning sign
- Open Interest (`data/oi/`) — positioning size delta
- 14-symbol universe — cross-sectional rank pool

### Feature candidates

- **Regime gate (C)**: realized-vol bucket, ATR percentile, trend-direction confirmation across multi-horizon
- **Direction (B)**: funding sign + funding-magnitude percentile; OI delta direction over a rolling window; funding × OI interaction
- **Rank (D)**: relative momentum rank across the 14-symbol universe over a rebalance window; rank percentile

### Long logic

LONG when:
- regime ∈ {trending-up OR low-vol mean-reversion-from-bottom}
- funding < 0 (shorts paying longs) AND OI rising under recent low
- symbol rank ∈ top quartile of 14

### Short logic

SHORT when:
- regime ∈ {trending-down OR low-vol mean-reversion-from-top}
- funding > 0 (longs paying shorts) AND OI rising under recent high
- symbol rank ∈ bottom quartile of 14

### Expected turnover

Low-medium. Triple-gate (regime × direction × rank) significantly reduces fire rate vs. unconditional signals. Estimated 5–20 trades per side per symbol per Arena window; with 14 symbols pooled, comfortably ≥ 25.

### Expected cost / gross profile

- Per-trade gross: high (gated to high-conviction setups)
- Per-trade cost: 14.5 bps (current architecture, taker-only)
- Net positive plausible because gating raises gross-per-trade well above the cost floor (target ≥ 25–30 bps gross to leave net edge after cost)

### A2 risk

Medium — must explicitly budget that the gated trade count remains ≥ 25 per side per Arena window. Pooling across 14 symbols is the survival lever.

### Implementation difficulty

Medium. Three feature pipelines (regime, funding/OI, rank) + interaction logic. Estimate 2–4 days for first SHADOW.

### Failure modes

1. Regime classifier overfits → false confidence in current regime label.
2. Funding/OI signals lag actual positioning by hours → adverse fills.
3. Rank universe too thin (14 symbols) → not enough independent signals after triple-gate.
4. All three components agreeing too rarely → A2 trade-count failure.
5. All three components agreeing too often → no actual gating value, reduces to combined unfiltered signal.

### First falsification test

Build feature pipelines on 2023–2024 data, hold-out 2025+; require that gated-LONG and gated-SHORT each show **gross-per-trade ≥ 25 bps** before any net-bps test. If gross-per-trade fails, hybrid is rejected without further work.

---

## Deep Dive 2 — C — Regime-Conditional Fitness

### Signal hypothesis

Existing alpha primitives (or new ones) become net-positive when filtered through a regime classifier. Regime captures conditions (volatility, trend, session, liquidity) under which the underlying primitive carries an edge that overcomes cost.

### Data source

- OHLCV (regime features)
- Funding rate (funding regime)

### Feature candidates

- Realized vol regime (low / medium / high deciles)
- Trend regime (up / range / down by multi-horizon agreement)
- Session regime (Asia / Europe / US / overlap; 24/7 perps still show session liquidity patterns)
- Funding regime (positive / negative / sign-flipping)
- Liquidity regime (volume percentile)

### Long logic

LONG when underlying primitive fires AND regime ∈ {trending-up OR low-vol up-bias} — otherwise suppressed.

### Short logic

SHORT when underlying primitive fires AND regime ∈ {trending-down OR low-vol down-bias} — otherwise suppressed.

### Expected turnover

Medium. Tunable via gate tightness. With 5 regime buckets and primitives firing at the original rate, gating to the favorable bucket reduces fire rate by ~3–5×.

### Expected cost / gross profile

Improves cost / gross over 0-9Y by gating away cost-dominated regimes. Magnitude depends on how concentrated the gross edge actually is in specific regimes.

### A2 risk

Tunable — gate tightness is a hyperparameter. Shadow test must verify post-gate trade count.

### Implementation difficulty

Low–medium. Regime features are OHLCV-derivable. 1–3 days for first SHADOW.

### Failure modes

1. Regime classifier overfits.
2. Edge is uniformly distributed across regimes → no gating gain.
3. Gate too tight → A2 fails.

### First falsification test

Bucket existing 0-9Y trades by regime; check that any single regime bucket has **gross-per-trade ≥ 25 bps**. If no bucket exceeds that threshold, regime gating cannot rescue cost — axis is rejected.

---

## Deep Dive 3 — A — Microstructure Imbalance (HIGH-UPSIDE, DATA-BLOCKED)

### Signal hypothesis

Short-horizon price moves are predicted by orderbook imbalance, depth pressure, and trade-print direction at sub-second to sub-minute scales.

### Data source (REQUIRED, NOT AVAILABLE)

- bid/ask quote stream
- top-of-book and N-level depth
- trade prints
- (optional) liquidation prints

### Feature candidates

- Orderbook imbalance (bid_size / (bid_size + ask_size))
- Spread compression / expansion
- Depth-weighted mid drift
- Trade-print signed volume
- Queue position estimator

### Long / Short logic

LONG: bid-side imbalance + ask thinning → upward move imminent.
SHORT: ask-side imbalance + bid thinning → downward move imminent.

### Expected turnover

Very high. HFT-scale.

### Expected cost / gross profile

Per-trade gross: very small (sub-bp per signal).
Per-trade cost: even maker-only @ VIP3 is comparable.
Net positive only viable with maker-only routing AND queue-priority capture — both unverified per 0-9ZA.

### A2 risk

None — trade count abundant.

### Implementation difficulty

Very high — requires capture layer + replay simulator (the 0-9ZB candidate order) + maker-only execution architecture (the 0-9ZA secondary condition).

### Failure modes

1. Adverse selection wipes out imbalance edge after fill.
2. Queue position never first → fill rate too low.
3. Latency vs. competitors → all signals stale before action.

### First falsification test

CANNOT BE PERFORMED until `0-9ZB-MARKET-MICROSTRUCTURE-DATA-CAPTURE-SHADOW` produces empirical bid/ask + depth + trade-print history.

### Verdict

**DEFERRED — held in reserve until 0-9ZB lands.**

---

## Deep Dive 4 — D — Cross-Sectional Relative Strength

### Signal hypothesis

Within the 14-symbol perp universe, top-K by relative strength outperforms bottom-K by relative weakness over the next rebalance window. Long top-K, short bottom-K — a market-neutral or directional rotation.

### Data source

- OHLCV multi-symbol

### Feature candidates

- Multi-horizon momentum rank (1d / 3d / 7d)
- Beta-adjusted excess return rank
- Relative volume rank
- Sector/category rank (majors vs alts, where applicable)

### Long / Short logic

LONG top-K (e.g. K=3) ranked symbols.
SHORT bottom-K ranked symbols.
Rebalance daily or per N-hour window.

### Expected turnover

Low–medium. Rebalance-frequency × K trades per window.

### Expected cost / gross profile

Per-leg cost is the same 14.5 bps but spread across multiple symbols dilutes blow-ups. Rank-spread sized moves are typically 50–200 bps over the rebalance window in crypto perps.

### A2 risk

Medium. With K=3 and daily rebalance, ~3 longs + 3 shorts/day → ~90 trades/month per side, well above 25 in a typical Arena window.

### Implementation difficulty

Medium. Rank computation + rebalance scheduler + universe handling. 2–3 days for first SHADOW.

### Failure modes

1. Universe too thin (14 symbols) — top-K and bottom-K rotate frequently → high turnover.
2. Crypto perps are highly correlated in extreme regimes → rank dispersion collapses.
3. Funding asymmetry — long top usually pays funding, short bottom usually receives funding → funding tilt may dominate.

### First falsification test

Build daily rank, hold-out 2025+; check that **(top-K return − bottom-K return) > 30 bps** over the rebalance window before costs. If rank spread is below cost-plus-buffer threshold, axis is rejected.

---

## Top-Candidate Summary

| Rank | Axis | Score | Verdict |
|---|---|---:|---|
| 1 | **H — Hybrid (C×B×D)** | 88 | **PRIMARY** |
| 2 | **C — Regime** | 87 | **SHADOW PARALLEL** (also a component of H) |
| 3 | **D — Cross-sectional** | 85 | **SHADOW PARALLEL** (also a component of H) |
| 8 | **A — Microstructure** | 55 | **DEFERRED** — high upside, blocked on data |

## Deliverable

`08_top_axis_deep_dive.md` — frozen.
