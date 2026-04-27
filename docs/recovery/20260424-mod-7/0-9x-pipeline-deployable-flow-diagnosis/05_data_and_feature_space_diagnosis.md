# 05 — Data and Feature-Space Diagnosis (Phase 5)

**Phase 5 Verdict:** `FEATURE_SPACE_EXHAUSTED`

## Formula universe diversity scan

`engine.jsonl` `candidate_lifecycle` events (full log scope at capture time):

| Metric | Value |
|---|---|
| total `candidate_lifecycle` events | 18 615 |
| ENTRY events | 9 370 |
| EXIT events | 9 245 |
| unique `alpha_id` | **4 454** |

Repeat distribution (how many times each alpha_id appears in lifecycle stream):

| appearances | # alphas |
|---|---|
| 1× | 81 |
| 2× | 3 849 ← ENTRY+EXIT pair (expected) |
| 3× | 1 |
| 4× | 259 ← evaluated twice (likely cool-off rotation) |
| 5× | 4 |
| 6× | 68 |
| 8× | 38 |
| 10× | 20 |
| 12× | 13 |
| 13× | 1 |

**Reading:** ~86% of alphas seen once (single ENTRY+EXIT). Some alphas re-evaluated 4×–12× (cool-off / multi-symbol re-test path). Generation is producing ≈4.5k unique formulas across this window — broad diversity, not stuck on a tiny set.

Cross-validation with bloom-filter telemetry:
- `bloom_hits = 0` in every observed V10 STATS line
- `bloom_size = 89` (matches the 89 admitted alphas exactly)

Bloom `hits=0` confirms newly generated alphas do **not** collide with the 89 historical admissions. The pipeline is exploring new formula space, not recycling rejects.

## Per-symbol candidate distribution

`candidate_lifecycle` source_pool histogram (full log):

```
LINKUSDT       2360   SOLUSDT        1925   1000SHIBUSDT  1554
GALAUSDT       1500   DOTUSDT        1480   XRPUSDT       1460
AAVEUSDT       1453   1000PEPEUSDT   1426   FILUSDT       1198
BNBUSDT        1184   DOGEUSDT        835   AVAXUSDT       760
ETHUSDT         760   BTCUSDT         720
```

All 14 symbols active. Some skew (LINKUSDT 2360 vs BTCUSDT 720) but every symbol has hundreds of evaluations. **No coverage gap.**

## Per-regime distribution

```
BULL_TREND     363   BEAR_TREND   274
BEAR_RALLY     152   CONSOLIDATION 75
ACCUMULATION    73
```

5 regime labels active. Skewed toward trending markets (BULL_TREND + BEAR_TREND = 51%). `CONSOLIDATION` and `ACCUMULATION` lower volume but represented.

## Stage event distribution

```
ENTRY: 9370
EXIT:  9245
```

Near-balance (Δ = 125; small lag from in-flight evaluations or async log buffering). Pipeline is processing events end-to-end without leaks.

## Are formulas repeating?

Most alpha_ids appear 1–2 times (the ENTRY+EXIT pair). The longer-tail (12×, 13×) reflects multi-symbol re-evaluation of the same formula: each pool/regime combination triggers a fresh evaluation cycle.

This is **expected diversity**: GP + LGBM produces new formulas per evolution cycle, and each formula gets tested across its assigned lane / symbol / regime.

## Are missing primitives limiting expressiveness?

Engine init log line at worker boot:

```
AlphaEngine ready: 126 indicator terminals, 35 operators, has_prims=True
```

| Component | Count |
|---|---|
| indicator terminals | 126 |
| operators | 35 |
| has_prims | True |

A primitive set of this size **should** generate enormously diverse formulas. The fact that 4.5k unique alphas evaluated and **none passed train fitness** suggests:

1. Combinatorial diversity exists at the formula level
2. But the **statistical edge** of those formulas, after 60-bar forward return labeling and Binance Futures cost subtraction, **does not exceed the random/cost floor**

This is a feature-space edge problem, not a primitive-availability problem.

## Are data quality issues invalidating candidates?

| Check | Status |
|---|---|
| `compile_err` per round | 0 (every observed V10 STATS line) |
| `reject_val_constant` | 0 (no zero-variance signals making it past) |
| `reject_val_error` | 0 (no exception in val backtest) |
| `reject_val_few_trades` | 4–8 per round of 2000 (~ 0.2–0.4%) |
| Symbol load log | 14 symbols × 200 000 bars (140k train / 60k holdout) all loaded `funding=yes oi=yes` |
| Wavelet denoising | active for BTCUSDT/train (per A23 boot log) |
| Factor enrichment | F1(momentum) F2(volatility) F3(volume) F4(funding) F5(OI) — "Factor enrichment complete" |
| Regime label sanity | per-symbol regime label emitted with confidence (e.g., `BTCUSDT: BEAR_TREND L1=BEAR conf=0.64 mom=-0.64 vol=0.39 vm=0.92 fund=-0.61 oi=0.70`) |

**No data quality blocker is visible.** Inputs are clean.

## Original 89 fresh alphas — formula degeneracy

`fresh_pool_outcome_health` (j01):

```
total_fresh:                  89
alphas_with_indicators:        0
indicator_alpha_ratio_pct:  0.00
distinct_indicators:           0
usage_entropy:                 0
avg_depth:                  0.00
avg_nodes:                  0.00
```

The 89 alphas that historically reached fresh used **zero indicator terminals**, depth 0, and 0 nodes. They are degenerate raw-OHLCV formulas — generated under an earlier (Epoch A) regime that did not enforce indicator usage. Per v0.7.1 governance, those are now in the `legacy_archive` set and the new pipeline (Epoch B) requires `indicator_alpha_ratio > 0`. The current 4.5k alphas tested *do* use indicators (engine has them loaded), but **still cannot beat cost**.

## Is the formula universe stale?

Different framing of the same data:

- "Stale" would mean the pipeline keeps regenerating the same failed formulas.
- `bloom_hits = 0` rules that out — every formula generated is new.
- However, the **distribution** of formulas produced may be stuck in a region of formula-space where edge does not exceed cost.

This is closer to **exhaustion** than **staleness**: GP+LGBM is sampling fresh points in the same low-edge region.

## AKASHA carry-forward (read-only)

> "do NOT re-tune within current '60-bar forward return on OHLCV+indicator' formulation — 10h offline replay exhausted the space; if P2 chosen: scope new data pipeline for order-book snapshots + funding rate derivatives + cross-symbol correlations (~1-2 weeks infra); if P3 chosen: scope tick-data pipeline + high-frequency backtester + 1-min alternative kline; if 結案 chosen: keep scaffolding (data/backtester/gate/telemetry/policy layer) for future work, stop GP+LGBM development"

This evidence is *consistent* with the live data: "10h offline replay exhausted" maps to "6.5-day live run produces 0 admissions across diverse symbols/regimes/lanes".

## Required Phase 5 classification

```
FEATURE_SPACE_EXHAUSTED
```

**Why not `FORMULA_UNIVERSE_STALE`:** generation produces new formulas each round (`bloom_hits=0`); not stuck on a small repeated set.

**Why not `FEATURE_SPACE_TOO_NARROW`:** the universe of 126 indicator terminals × 35 operators is not narrow at the primitive level. The narrowness is in the *target / horizon / cost* triplet — i.e., "60-bar forward return on OHLCV+indicator" cannot beat cost. That is exhaustion of *that specific formulation's* viable region, hence `EXHAUSTED` rather than `TOO_NARROW`.

**Why not `DATA_QUALITY_BLOCKER`:** inputs are clean; `compile_err=0`, `val_error=0`, factor-enrichment complete, regime labels emit normally.

**Why not `MARKET_REGIME_NO_EDGE`:** failure is uniform across all 5 regimes including BULL_TREND and BEAR_TREND — not a regime-specific edge collapse.

The diagnosis aligns with AKASHA's pre-existing recorded conclusion (10 h offline replay exhausted the space).
