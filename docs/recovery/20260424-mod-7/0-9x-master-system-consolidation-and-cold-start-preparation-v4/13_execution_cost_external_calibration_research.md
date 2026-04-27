# Zangetsu Execution Cost Model — External Calibration Research
# Document ID: 42-13_execution_cost_external_calibration
# Date: 2026-04-27
# Author: Claude (Lead Architect, j13)
# Status: DESIGN ONLY — no runtime config / no code patch
# Related PRs: #40 Phase 2, #41 Phase 2 (cost=0.5x SOL survivors → SINGLE_SYMBOL_ARTIFACT)

---

## 0. Problem Statement

Current `zangetsu/config/cost_model.py` uses a flat round-trip model:

```
total_round_trip_bps = (taker_bps * 2) + slippage_bps + funding_8h_avg_bps
```

Three structural defects:

1. **100% taker assumption** — funding never accounts for maker fills, even
   though Binance's maker rebate-vs-taker-charge gap is 3.0 bps per side
   (5.0 - 2.0). PR #40/#41 found cost=0.5x (~5.75 bps RT) only achievable
   with ~100% maker fills + zero slippage; the 8 SOL survivors at that
   regime were SINGLE_SYMBOL_ARTIFACT, confirming the regime is unrealistic
   without a maker order router which Zangetsu does not have.
2. **Funding flat-added per round-trip regardless of hold duration** —
   `funding_8h_avg_bps = 1.0` is added once per RT. At a typical 10-20 min
   hold (10-20 bars on 1m, well below the 480-bar 8h funding interval), the
   accrued funding cost is `(hold_bars / 480) × 1.0 ≈ 0.02-0.04 bps`, not
   1.0 bps. Over-counts by ~0.96 bps per RT, ~96% absolute over-attribution
   on a typical alpha trade.
3. **No depth-awareness, no spread component, no symbol overrides** — every
   stable-tier symbol carries identical 11.5 bps RT regardless of order
   size, time of day, or microstructure regime.

This document specifies a richer model. **No code modification in this
document — output is a spec for a future PR.**

---

## 1. Component-by-Component Calibration

### 1.1 Maker / Taker Split

**Current**: implicit 100% taker.
**Proposed**:
```
fee_bps = maker_bps × maker_fill_rate + taker_bps × (1 − maker_fill_rate)
```

| Source | Maker | Taker | Notes |
|--------|-------|-------|-------|
| Binance VIP 0 USDⓈ-M Futures (April 2026) | 0.020% (2.0 bps) | 0.050% (5.0 bps) | binance.com/en/fee/futureFee |
| Binance VIP 9 | 0.000% | 0.017% | aspirational floor — only after $50B+ 30d volume |
| BNB-paid 10% discount | 0.018% | 0.045% | optional, requires BNB-fee toggle |

**Realistic range for VIP 0 retail**:
- Pure aggressor (Zangetsu today): `maker_fill_rate = 0.0` → 5.0 bps/side, 10.0 bps RT.
- Hybrid post-only with 5s timeout fallback: `maker_fill_rate ≈ 0.4-0.7`
  → 2.6-3.8 bps/side, 5.2-7.6 bps RT.
- Pure maker (passive limit, no timeout): `maker_fill_rate = 1.0`
  → 2.0 bps/side, 4.0 bps RT — but adverse selection risk uncovered here.

**Adversarial — Q1 dimensions**:
- Input boundary: maker_fill_rate ∉ [0,1] → clamp.
- Silent failure: if `maker_fill_rate=1.0` is set but live fill rate is
  0.3 due to thin book, model under-estimates by 1.8 bps/side → live PnL
  systematically below sim. Mitigation: maker_fill_rate must be measured
  ex-post per symbol from live fills, not assumed.
- External dependency: Binance fee schedule changes — not breaking but
  must be re-fetched quarterly.
- Concurrency: per-fill mode (M vs T) needs to be recorded in a fills
  table; today only post-trade aggregate PnL is observed in arena_pipeline
  (`backtester.run` consumes a scalar `cost_bps`). **GAP**.

**Recommended default**: `maker_fill_rate = 0.0` (current behavior, taker-only),
explicit override required to shift. Conservative-floor rule (§1.7) prevents
over-optimistic sim.

---

### 1.2 Spread Cost

**Current**: implicit zero (taker fee only on top of mid).
**Proposed**: half-spread × 2 (entry crosses, exit crosses).

```
spread_cost_bps = (best_ask - best_bid) / mid × 10000 × 0.5 × 2
                = (best_ask - best_bid) / mid × 10000      (per RT)
```

**Realistic range on Binance USDⓈ-M Futures (VIP 0)**:

| Symbol class | Typical spread (bps) | Source |
|--------------|----------------------|--------|
| BTCUSDT, ETHUSDT (perpetual, normal hours) | 0.1-0.5 bps | Kaiko Cheatsheet for Bid Ask Spreads + observed Binance L1 ticker |
| SOL/BNB/XRP (stable tier) | 0.5-2 bps | extrapolated from Kaiko study (mid-cap perp) |
| AVAX/LINK/DOT (diversified) | 1-4 bps | as above |
| 1000PEPE/1000SHIB/GALA (high-vol) | 3-15 bps, spikes >50 bps in stress | order book snapshot variance |
| BTC during US-open volatility/CPI release | 2-10 bps temporary | 2024-2026 incident archives |
| Academic baseline (general crypto BTCUSD) | ~3 bps avg (0.0298%) | Aleti 2021, Wiley J. Futures Markets |

**Measurement needed**: per-symbol per-bar best_bid/best_ask snapshot.
Currently NOT in arena_pipeline observation — only OHLCV+volume+funding+OI
factors are loaded (arena_pipeline.py:484, F4=funding F5=OI). **GAP**.

**Q1 adversarial**:
- Input boundary: spread can be NaN at session open or stale-feed → must
  fallback to last-good with TTL.
- External dependency: WebSocket disconnect → spread snapshot stale.
- Scope creep: spread can be a state variable updated every bar — but for
  backtest sim, a per-symbol time-of-day median (288 bars × N days) is
  sufficient, no per-bar granularity needed at gate level.

**Recommended default**:
- Stable tier: 0.4 bps RT (matches BTC/ETH typical)
- Diversified: 1.5 bps RT
- High-Vol: 8.0 bps RT

These DELIVER spread as a separate observable, not folded into slippage.

---

### 1.3 Depth-Aware Slippage

**Current**: flat slippage (0.5 / 1.0 / 2.0 bps for 3 tiers).
**Proposed**: linear in (notional / orderbook depth at top-5 levels).

```
slippage_bps = base_slippage_bps + impact_coef × (notional_usd / depth_top5_usd)
```

**Realistic Binance USDⓈ-M depth (April 2026, normal hours)**:

| Symbol | Top-5 aggregate depth (USD) | Source |
|--------|------------------------------|--------|
| BTCUSDT | $30M-$80M (median ~$50M) | CoinGlass merge, CryptoMeter live snapshot |
| ETHUSDT | $15M-$40M | inferred from BTC/ETH OI ratio |
| SOLUSDT | $3M-$10M | order-book screenshot 2026-04 |
| BNBUSDT | $2M-$8M | as above |
| XRP/DOGE | $1M-$5M | as above |
| LINK/AAVE/AVAX/DOT/FIL | $0.5M-$3M | mid-cap typical |
| 1000PEPE/1000SHIB/GALA | $0.2M-$1M, drops <$50K in stress | high-vol typical |

**Stress events** (depth collapse): during March 2020, May 2021, Nov 2022
(FTX), April 2024 (Iran-Israel flash), Aug 2024 (yen carry unwind),
top-5 depth dropped to 5-15% of normal across all majors for 2-30 min
windows. Slippage on $100K BTC market order spiked from <1 bp to 20-50 bps.

**Measurement needed**: per-symbol per-bar top-5 sum of (price × qty) on
both sides. Captureable from `depth5` channel or `depthUpdate` deltas;
historical via Binance archive or third-party (Tardis.dev, Amberdata).

**`impact_coef`** estimate:
- Linear-impact heuristic: a market order of size N% of top-5 notional
  walks the book by ~N/2 bps (assuming roughly uniform liquidity in those
  5 levels). E.g. notional=2% of depth → ~1 bp linear slippage.
- Square-root variant (Almgren-Chriss-style for crypto): 
  `slippage = k × sqrt(notional/ADV)`, but at typical Zangetsu order sizes
  ($100-$10K notional vs $30M+ depth on majors) the linear approximation
  is fine at <0.1% of depth.

**Q1 adversarial**:
- Input boundary: notional → 0 means no slippage — correct.
- Silent failure: depth feed down → fallback to historical median, log warn.
- Concurrency: depth snapshot races with market move; <5s lag acceptable
  since slippage estimate is statistical, not per-fill.
- Scope creep: do NOT model nonlinear impact for now — Zangetsu order
  sizes at expected $1K-$50K bracket sit in the linear regime for all
  stable+diversified symbols.

**Recommended default**: `impact_coef = 50 bps` (i.e. eating 100% of top-5
depth costs ~50 bps; eating 1% costs 0.5 bps). Floor of 0.3 bps base.

---

### 1.4 Funding-Per-Hold (Replace Flat Add)

**Current**:
```
funding_term_bps = funding_8h_avg_bps   (added flat per RT, regardless of hold)
```

**Proposed**:
```
funding_term_bps = (hold_bars / 480) × funding_8h_avg_bps × side_mult
```
where 480 bars = 8h on 1m bars and `side_mult = +1 if long, −1 if short
× sign(funding_rate)`.

**Realistic Binance perpetual funding range (2025-2026)**:

| Period | Median 8h funding (BTC) | 95th pct (BTC) | Source |
|--------|--------------------------|------------------|--------|
| 2025 average | ~+0.005% (~0.5 bps) | ~+0.025% (~2.5 bps) | Coinalyze BTCUSDT funding chart |
| 2026 YTD | ~+0.003% to +0.008% | ~+0.020% | binance.com/en/futures/funding-history |
| Stress regimes (long-squeeze) | up to +0.15% (~15 bps) | rare | Binance arbitrage data archive |
| Negative regimes (bear contango unwind) | down to −0.05% | rare | as above |

**Historical absolute median** ≈ 0.7-1.2 bps per 8h on majors — consistent
with the current 1.0 default, BUT current code adds it per RT not per
hold-fraction.

**At typical Zangetsu hold** (10-20 bars on 1m, MAX_HOLD ≈ 48 bars per
backtester.py:49): accrued funding = `(15/480) × 1.0 = 0.03 bps`.

**Over-attribution** of current model: 1.0 − 0.03 = 0.97 bps per RT,
≈ 8% of total stable-tier RT cost. Compounded across thousands of trades
this systematically under-promotes alphas with short holds.

**Q1 adversarial**:
- Input boundary: hold_bars=0 (single-bar trade) → funding=0, correct.
- Silent failure: funding rate sign — long pays positive funding, short
  receives. Current model ignores side. New model must include side_mult
  or it will under-cost long-positive-funding trades.
- External dependency: funding rate published 8h, must be cached and
  interpolated for in-flight bars.
- Concurrency: funding-time crossings. If a position spans the 00:00 UTC
  funding boundary, full 8h funding is paid even if hold=1 bar. Hold-fraction
  model must be replaced with **boundary-crossings counter** for accurate
  modeling of funding-boundary-straddle trades.
- Scope creep: skip boundary-crossing for v1 (use hold-fraction approx),
  flag as known under-attribution for trades that straddle 00:00/08:00/16:00 UTC.

---

### 1.5 Turnover Penalty / Cumulative Hold Cost

**Proposed**:
```
turnover_penalty_bps = max(0, (hold_bars - target_hold_bars) / 480) × funding_8h_avg_bps × penalty_mult
```

Penalizes alphas that hold positions longer than the strategy's target
window (forces concentration in low-cost-per-time alphas, not "hold
forever and hope" alphas).

**Realistic range**: `penalty_mult = 1.0` (just adds linear funding past
target) to `2.0` (doubles funding cost beyond target as risk-aversion
proxy for staleness).

**Recommended default**: penalty_mult = 1.0 (effectively just continued
linear funding accrual past target hold). This is conservative — does not
over-penalize legit long-hold alphas, just removes "free hold" assumption.

**Q1 adversarial**: this is a soft regularizer, not a real cost. Risk:
double-count vs §1.4. Mitigation: §1.4 already covers all funding accrued;
§1.5 is OFF by default and only activated if a strategy needs an explicit
turnover regularizer.

---

### 1.6 Symbol-Specific Override

**Current**: tier-based identical defaults.
**Proposed**: per-symbol full SymbolCost record allowed via console hook,
with tier defaults as fallback.

**Realistic divergence within stable tier**:
- BTC top-5 depth ≈ 25× SOL top-5 depth → impact_coef divergence material.
- BTC funding rate volatility lower than SOL → funding stddev should be
  per-symbol if used in confidence intervals.
- BNB has ad-hoc maker fee discount when fees paid in BNB — symbol-level.

Recommended: extend `SymbolCost` with `top5_depth_usd`, `spread_bps`,
`maker_fill_rate`, `impact_coef`, `funding_8h_avg_bps`, `funding_8h_std_bps`.
Console hook already exists (`update_symbol`); just extend schema.

---

### 1.7 Conservative Floor — "Never Below 100% Taker"

**Rule**: in absence of explicit override flag `OVERRIDE_FLOOR=True`, the
modeled cost must be ≥ 100%-taker estimate:

```
floor_bps = 2 × taker_bps + spread_bps + base_slippage_bps + funding_per_hold
```

This blocks the failure mode of PR #40 cost=0.5x — silently optimistic
maker assumptions producing alphas that look profitable in sim but lose
in live.

**Rationale**: Zangetsu lacks a maker router. Modeled cost must reflect
Zangetsu's actual execution capability (taker-only) until the router is
built.

**When to lift floor**: only after (a) maker router is live, (b) live
fills table exists, (c) ex-post `maker_fill_rate` per symbol is measured
and verified. Until then, floor enforced.

---

## 2. Data Availability in arena_pipeline

Current observation surface (arena_pipeline.py + backtester.py):

| Data field | Currently observed? | Needed for proposed model |
|------------|---------------------|----------------------------|
| OHLCV per 1m bar | YES | YES (for impact and bar-level cost) |
| funding_rate | YES (F4 factor) | YES (per-symbol) |
| OI | YES (F5 factor) | NO (not used for cost) |
| best_bid/best_ask per bar | NO | YES (for spread cost) |
| top5 cumulative depth (bid+ask) | NO | YES (for depth-aware slippage) |
| per-fill mode (M/T flag) | NO | YES (for live maker_fill_rate) |
| per-trade hold_bars | DERIVABLE from signals (entry→exit indices) | YES |
| per-trade side (long/short) | DERIVABLE from signals | YES (funding sign) |
| funding boundary crossings | NO (would need timestamp arithmetic) | OPTIONAL (v1 skip) |

**Gap summary**:
- Spread + depth → require new data ingestion pipeline:
  - Historical: Binance archive (`https://data.binance.vision/?prefix=data/futures/um/daily/bookDepth/`)
    or Tardis.dev for L2 snapshots.
  - Live: WebSocket `<symbol>@depth5@100ms` channel.
- Per-fill mode → requires live trading infrastructure (Zangetsu live/
  module, post-deployment) to log fills to a `fills` table. Backtest can
  use `maker_fill_rate=0` (taker-only) until then.

---

## 3. Path to Integration

**Phase A — Backtest-side enrichment (offline, no live impact)**

A1. Add per-symbol `spread_bps_estimate` and `top5_depth_usd_estimate`
    fields to `SymbolCost` (default values in the spec JSON).
A2. Replace `total_round_trip_bps` property with `cost_for_trade(hold_bars,
    notional_usd, maker_fill_rate=0)` method that returns a structured
    breakdown: `{maker_taker, spread, slippage_base, slippage_impact,
    funding, total}`.
A3. Update `backtester.run` to accept either scalar `cost_bps` (legacy)
    OR a callable `cost_fn(hold_bars, notional_usd) → bps`. Backwards-compat
    legacy path stays.
A4. Add unit test: trade with hold_bars=15 should pay ~0.03 bps funding,
    not 1.0; trade with hold_bars=480 should pay ~1.0 bps funding.

**Phase B — Data ingestion for spread/depth (offline, before live)**

B1. New `scripts/fetch_binance_bookdepth.py` to download daily bookDepth
    archives → per-symbol per-day median spread + top5 depth.
B2. Bake median values into `SymbolCost` defaults (refresh quarterly).
B3. Optional: per-bar spread/depth time-series stored in
    `data/microstructure/<symbol>.parquet` for higher-fidelity backtests.

**Phase C — Live integration (post Zangetsu live/ deployment)**

C1. `live/execution.py` logs every fill to `fills` table with
    `(timestamp, symbol, side, qty, price, mode, fee_bps)`.
C2. Periodic job aggregates `fills` → per-symbol `measured_maker_fill_rate`,
    `measured_avg_slippage_bps`. Feeds back to override `SymbolCost`.
C3. Floor §1.7 lifts only after measured data exists for ≥30 days per
    symbol.

**Phase D — Schema Migration**

D1. Add `cost_breakdown_jsonb` column to `champion_pipeline` so each
    promoted alpha records the cost components it was evaluated against
    (auditability).
D2. Calcifer outcome watch (§17.3) extends to flag deploys where modeled
    cost diverges from measured live cost by >2 bps RT.

---

## 4. Q1/Q2/Q3 — Whole-Spec Quality Gate

**Q1 Adversarial Robustness**:
- Input boundary: PASS — every component has clamp/fallback.
- Silent failure: PASS — conservative floor §1.7 prevents under-cost
  failure mode that bit PR #40.
- External dependency: PASS — fee schedule, depth, spread all have
  fallbacks (cached medians).
- Concurrency: PARTIAL — funding boundary-crossing skipped in v1, flagged.
- Scope creep: PASS — no nonlinear impact, no per-bar microstructure model
  in v1; deliberately bounded.

**Q2 Structural Integrity**: PASS — backwards-compat scalar `cost_bps`
path preserved, new method-based path is additive only. No data loss
risk.

**Q3 Execution Efficiency**: PASS — components are O(1) per-trade lookups;
data ingestion is offline batch (Phase B); live data feed (Phase C)
piggybacks on existing WebSocket infrastructure.

---

## 5. Cited Assumptions Table

See `/tmp/cost_assumption_table.json` for machine-readable values.
Key citations:
- Binance VIP 0 fees: binance.com/en/fee/futureFee (April 2026)
- BTC funding 2025-2026: Coinalyze BTCUSDT chart, Binance funding-history
  page
- BTC top-5 depth: CoinGlass merge view, CryptoMeter live tape
- Crypto spread baseline: Kaiko Cheatsheet for Bid-Ask Spreads,
  Aleti 2021 (J. Futures Markets, Wiley)
- Linear impact heuristic: standard market microstructure result for
  sub-1% top-of-book consumption.

---

## 6. Recommendations (Top 5)

1. **Add hold-fraction funding immediately** (§1.4) — biggest absolute
   correction. Current model over-attributes ~0.96 bps/RT systematically.
   Single-line change once SymbolCost gains a `cost_for_trade(hold_bars)`
   method. No new data needed.

2. **Keep maker_fill_rate=0 as default** (§1.1) — until Zangetsu has a
   maker router, modeling any non-zero maker rate creates the same trap
   PR #40 hit (cost=0.5x SOL artifact). Conservative floor §1.7 enforces.

3. **Spread + depth defaults baked from Binance archive** (Phase B) —
   one-shot offline ingest, refresh quarterly. Avoids live data dependency
   while still adding the two missing components. Per-symbol divergence
   matters most in Diversified and High-Vol tiers.

4. **Decouple cost components in champion_pipeline schema** (D1) — every
   promoted alpha records cost breakdown, not aggregate. Enables ex-post
   sensitivity analysis: "did this alpha pass A4 because spread was modeled
   too low?".

5. **Defer live-fill calibration until Phase C** — do not bake
   `measured_maker_fill_rate` into defaults until live fills table has
   ≥30d data for that symbol. §1.7 floor stays on until then.

---

## 7. Out-of-Scope (Explicit Non-Goals)

- Nonlinear market impact (square-root model) — Zangetsu order sizes are
  too small to need it.
- Per-tick spread/depth in backtest — daily median per symbol is sufficient
  for gate-level evaluation.
- Maker rebate optimization — no router, no rebate-seeking.
- Cross-exchange arbitrage cost — Zangetsu is single-venue (Binance).
- Borrow cost / margin interest — perpetual futures only, no spot margin.
- Listing/delisting risk premium — handled at universe-selection layer.

---

# END OF DESIGN SPEC
# To convert to implementation: open new PR with this doc as design rationale,
# follow Phase A → B → C → D in §3.
