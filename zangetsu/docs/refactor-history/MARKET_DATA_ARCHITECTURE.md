# Zangetsu V5 — Market Data Layer Architecture
# Generated: 2026-04-16 | Lead: Claude | Meeting: Agent Teams

---

## 1. Data Architecture — Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     MARKET DATA PIPELINE                            │
│                                                                     │
│  ┌──────────┐    ┌──────────────┐    ┌─────────────┐    ┌────────┐ │
│  │ RAW DATA │───>│ NONDIMENSION │───>│ FACTOR      │───>│ REGIME │ │
│  │ (1m bars)│    │ TRANSFORM    │    │ SCORES      │    │ LABEL  │ │
│  └──────────┘    └──────────────┘    └─────────────┘    └────────┘ │
│       │                │                    │                │      │
│   OHLCV+FR+OI     [-1,+1] per        5-dim vector      1 of 13   │
│   per symbol       indicator          per 1m bar        per 4h bar │
│                                                                     │
│  ┌──────────┐    ┌──────────────┐    ┌─────────────┐    ┌────────┐ │
│  │ 4H RESAM │───>│ 4H FACTOR    │───>│ STATE AXES  │───>│ REGIME │ │
│  │ (4h bars)│    │ AGGREGATION  │    │ (smoothed)  │    │ CLASSIF│ │
│  └──────────┘    └──────────────┘    └─────────────┘    └────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### Step-by-step

| Step | Input | Transform | Output | Granularity |
|------|-------|-----------|--------|-------------|
| S1 Raw Ingest | Exchange WS/REST | Validate, fill gaps, align timestamps | Clean OHLCV + funding_rate + open_interest | 1m |
| S2 Nondimensional | Raw values | Per-indicator transform (see §2) | Continuous score [-1,+1] per indicator | 1m |
| S3 Factor Scores | Nondimensional indicators | Weighted average within factor group | 5 factor scores [-1,+1] | 1m |
| S4 4H Resample | 1m OHLCV | Standard OHLC agg (open=first, high=max, low=min, close=last, volume=sum) | 4H bars | 4h |
| S5 4H Factor Agg | 1m factor scores within 4h window | EMA-weighted mean (recent-biased) | 5 factor scores per 4h bar | 4h |
| S6 State Axes | 4H factor scores | Identity (factors ARE the axes) | 5-dim state vector | 4h |
| S7 Regime Classify | 5-dim state vector + transition rules | Decision tree with factor thresholds | 1 of 13 regime labels | 4h |

### Nondimensional Transform — Cross-Symbol Invariance

All raw indicators are converted to [-1,+1] using one of three methods, chosen per indicator type:

| Method | Formula | When to use |
|--------|---------|-------------|
| **Percentile-rank** | `2 * rank(x, window=500) / window - 1` | Bounded indicators without natural center (ATR, volume, OI) |
| **Tanh-MAD** | `tanh(x / MAD)` where MAD = median absolute deviation | Zero-centered indicators (MACD, funding rate, price momentum) |
| **Sigmoid-threshold** | `2 / (1 + exp(-k*(x-center)/scale)) - 1` | Indicators with known semantic thresholds (RSI, ADX) |

**Critical**: Window for percentile-rank is CAUSAL (lookback only). Default 500 bars (1m) = ~8.3 hours. This preserves cross-symbol comparability without lookahead.

---

## 2. Five-Factor Feature Framework

### F1 — MOMENTUM (Directional Conviction)

**Semantic meaning**: How strongly is price moving in one direction? +1 = maximum bullish conviction, -1 = maximum bearish conviction, 0 = no directional bias.

| Sub-indicator | Raw input | Nondim method | Weight |
|---------------|-----------|---------------|--------|
| EMA slope (21) | EMA(close,21)[i] - EMA(close,21)[i-3] | Tanh-MAD | 0.30 |
| RSI deviation | RSI(14) - 50 | Sigmoid-threshold (center=0, k=0.08) | 0.25 |
| MACD histogram | MACD(12,26,9) histogram | Tanh-MAD | 0.25 |
| Price vs EMA(50) | (close - EMA50) / ATR | Tanh-MAD | 0.20 |

**Factor score**: F1 = Σ(weight_i × nondim_i)

### F2 — VOLATILITY (Uncertainty / Risk)

**Semantic meaning**: How uncertain is the current price action? +1 = extreme expansion (crisis-level), -1 = extreme compression (squeeze), 0 = normal volatility.

| Sub-indicator | Raw input | Nondim method | Weight |
|---------------|-----------|---------------|--------|
| ATR percentile | ATR(14) rank in 500-bar window | Percentile-rank | 0.30 |
| Bollinger bandwidth | (BB_upper - BB_lower) / BB_mid | Percentile-rank | 0.25 |
| Return kurtosis (rolling 100) | kurtosis of 1m returns | Tanh-MAD | 0.20 |
| ATR rate-of-change | (ATR[i] - ATR[i-20]) / ATR[i-20] | Tanh-MAD | 0.25 |

**Factor score**: F2 = Σ(weight_i × nondim_i)
**Note**: F2 is UNSIGNED for regime classification but the sign encodes direction of change (expanding vs compressing).

### F3 — VOLUME (Participation / Conviction)

**Semantic meaning**: Is money flowing in or fading out? +1 = extreme participation surge, -1 = volume desert, 0 = baseline activity.

| Sub-indicator | Raw input | Nondim method | Weight |
|---------------|-----------|---------------|--------|
| Volume percentile | Volume rank in 500-bar window | Percentile-rank | 0.35 |
| Volume-price trend | Σ(volume × (close-close[i-1])/close[i-1], 20 bars) | Tanh-MAD | 0.30 |
| OBV slope | OBV[i] - OBV[i-20] | Tanh-MAD | 0.20 |
| Volume acceleration | Vol_MA(5) / Vol_MA(20) - 1 | Tanh-MAD | 0.15 |

**Factor score**: F3 = Σ(weight_i × nondim_i)

### F4 — FUNDING RATE (Crowd Positioning)

**Semantic meaning**: Where is the crowd leaning? +1 = extreme long crowding (contrarian bearish signal), -1 = extreme short crowding (contrarian bullish signal), 0 = balanced.

| Sub-indicator | Raw input | Nondim method | Weight |
|---------------|-----------|---------------|--------|
| Funding rate | Raw funding rate (8h, interpolated to 1m) | Tanh-MAD (window=2000) | 0.50 |
| Funding rate momentum | FR[i] - EMA(FR, 100) | Tanh-MAD | 0.30 |
| Cumulative funding (24h) | Σ(FR, 1440 bars) | Tanh-MAD | 0.20 |

**Factor score**: F4 = Σ(weight_i × nondim_i)
**Data note**: Funding rate updates every 8h on most exchanges. Between updates, use last known value (constant interpolation). Do NOT linearly interpolate — this would leak future information.

### F5 — OPEN INTEREST (Leverage / Commitment)

**Semantic meaning**: How much leveraged capital is committed? +1 = extreme leverage buildup, -1 = mass deleveraging, 0 = stable commitment.

| Sub-indicator | Raw input | Nondim method | Weight |
|---------------|-----------|---------------|--------|
| OI percentile | OI rank in 2000-bar window | Percentile-rank | 0.35 |
| OI rate-of-change | (OI[i] - OI[i-60]) / OI[i-60] | Tanh-MAD | 0.35 |
| OI-volume divergence | sign(ΔOI) × sign(Δprice) disagreement score | Custom (see below) | 0.30 |

**OI-volume divergence**: When OI rises but price falls → forced longs (bearish signal = -1). When OI falls and price falls → liquidation cascade (extreme bearish). When OI rises and price rises → healthy leverage (+0.5). Encoded as discrete mapping then smoothed with EMA(20).

**Factor score**: F5 = Σ(weight_i × nondim_i)

---

## 3. Extreme-Value Preservation Policy

### Core Principle: Extremes = Information, Not Noise

**HARD RULES — no exceptions:**

1. **No winsorization.** Never clip raw data.
2. **No outlier removal.** Never discard bars or readings.
3. **No z-score capping.** Never cap at ±3σ.
4. **No min-max scaling.** This compresses history when new extremes appear.

### How Extremes Are Encoded

The nondimensional transforms naturally handle extremes:

| Transform | Extreme behavior | Why it works |
|-----------|-----------------|--------------|
| **Tanh-MAD** | tanh saturates smoothly at ±1 | Extreme values get scores near ±1 but never distort the [-0.5, +0.5] normal range. A 10-sigma move scores ~0.99, not 10.0. Information preserved: "this is extreme." Granularity preserved in normal range. |
| **Percentile-rank** | Extreme = rank 1.0 or 0.0 | By definition, the most extreme value in the window gets ±1. New extremes naturally push old extremes inward. No historical distortion. |
| **Sigmoid-threshold** | Smooth saturation with tunable steepness | k parameter controls how quickly extremes saturate. Lower k = more granularity at extremes, less in normal range. |

### Extreme Event Flagging

In addition to continuous scores, maintain a binary **extreme event flag** per factor:

```
extreme_flag[F] = 1 if abs(factor_score[F]) > 0.90
```

This flag is used downstream by:
- **Regime classifier**: LIQUIDITY_CRISIS requires F2 extreme flag
- **Position sizing**: Reduce size when any extreme flag is active
- **Signal confidence**: Discount signals that rely on factors currently in extreme territory

### Decay Behavior

When an extreme event ends (score drops below 0.90), the flag drops immediately — no smoothing. The continuous score itself provides the smooth transition. The flag is for discrete policy triggers only.

---

## 4. 13-Regime Factor-Based Support Structure

### Regime Definitions via Factor Space

Each regime is defined as a region in the 5-dimensional factor space [F1, F2, F3, F4, F5].

| # | Regime | F1 Momentum | F2 Volatility | F3 Volume | F4 Funding | F5 OI | Key discriminator |
|---|--------|-------------|---------------|-----------|------------|-------|-------------------|
| 0 | BULL_TREND | > +0.4 | [-0.3, +0.3] | > 0 | any | > 0 | Sustained directional momentum with normal vol |
| 1 | BULL_PULLBACK | [-0.2, +0.2] | [-0.2, +0.3] | < 0 | any | > -0.3 | Momentum fading within uptrend context (requires prior BULL_TREND) |
| 2 | BEAR_TREND | < -0.4 | [-0.3, +0.3] | < 0 | any | < 0 | Sustained downward momentum with normal vol |
| 3 | BEAR_RALLY | [-0.2, +0.2] | [-0.2, +0.3] | > 0 | any | < +0.3 | Momentum recovery within downtrend context (requires prior BEAR_TREND) |
| 4 | CONSOLIDATION | [-0.2, +0.2] | < -0.2 | [-0.3, +0.3] | [-0.3, +0.3] | [-0.3, +0.3] | No direction, low vol, balanced everything |
| 5 | SQUEEZE | [-0.15, +0.15] | < -0.5 | any | any | > +0.2 | Extreme low vol + OI building = energy storing |
| 6 | CHOPPY_VOLATILE | [-0.3, +0.3] | [+0.3, +0.7] | any | any | any | High vol but no direction — random walk territory |
| 7 | LIQUIDITY_CRISIS | any | > +0.7 | > +0.5 | extreme | < -0.3 | Extreme vol + volume surge + deleveraging |
| 8 | PARABOLIC | > +0.7 | > +0.3 | > +0.5 | > +0.3 | > +0.3 | Extreme momentum + vol expanding + crowd piling in |
| 9 | ACCUMULATION | [-0.1, +0.2] | < 0 | > +0.2 | < -0.2 | > 0 | Quiet + volume building + smart money (funding negative = shorts pay) |
| 10 | DISTRIBUTION | [-0.2, +0.1] | < +0.2 | > +0.2 | > +0.2 | < 0 | Quiet + volume present + OI declining + crowd long |
| 11 | TOPPING | [0, +0.3] | > +0.2 | > +0.3 | > +0.4 | > +0.3 | Still positive momentum but funding extreme + vol rising = fragile |
| 12 | BOTTOMING | [-0.3, 0] | > +0.2 | > +0.3 | < -0.4 | < -0.2 | Still negative but funding extreme short + vol rising = capitulation |

### Ambiguous Boundary Resolution

**DISTRIBUTION vs TOPPING** — both "end of uptrend":
- DISTRIBUTION: momentum already flat/negative, OI declining (smart money exiting quietly)
- TOPPING: momentum still weakly positive, funding rate extreme long, OI still high (crowd hasn't left yet)
- **Discriminator**: F4 (funding) and F5 (OI). Distribution = OI falling. Topping = OI still elevated + funding extreme.

**ACCUMULATION vs BOTTOMING** — both "end of downtrend":
- ACCUMULATION: low volatility, quiet volume buildup, funding rate negative (shorts paying = short crowding)
- BOTTOMING: elevated volatility, volume spike, extreme negative funding, OI dropping (liquidation/capitulation)
- **Discriminator**: F2 (volatility). Accumulation = calm. Bottoming = violent. Also F5: accumulation = OI building, bottoming = OI collapsing.

**CONSOLIDATION vs SQUEEZE** — both "low volatility":
- CONSOLIDATION: everything balanced — no buildup, no energy storage
- SQUEEZE: volatility extremely compressed + OI building = coiled spring
- **Discriminator**: F2 magnitude (squeeze requires < -0.5 vs consolidation just < -0.2) AND F5 (squeeze requires OI building > +0.2).

**CHOPPY_VOLATILE vs LIQUIDITY_CRISIS** — both "high volatility":
- CHOPPY_VOLATILE: elevated vol but contained, no extreme readings, directionless
- LIQUIDITY_CRISIS: extreme vol (F2 > 0.7) + volume surge + mass deleveraging (OI collapsing)
- **Discriminator**: F2 magnitude threshold (0.7 vs 0.3) AND F5 sign (crisis = OI collapsing) AND F3 (crisis = volume surge).

### Transition Rules (Hysteresis)

To prevent regime flicker at boundaries:

1. **Entry threshold**: Must satisfy all factor conditions for 2 consecutive 4h bars
2. **Exit threshold**: Must violate primary discriminator by > 0.1 for 2 consecutive bars
3. **Context dependency**: BULL_PULLBACK can only follow BULL_TREND (within last 5 bars). BEAR_RALLY can only follow BEAR_TREND (within last 5 bars).
4. **Priority order** (when multiple regimes match): LIQUIDITY_CRISIS > PARABOLIC > SQUEEZE > TOPPING > BOTTOMING > DISTRIBUTION > ACCUMULATION > BULL_TREND > BEAR_TREND > BULL_PULLBACK > BEAR_RALLY > CHOPPY_VOLATILE > CONSOLIDATION

### Mapping: Current Numeric → New Semantic

| Old # | Old name | New regime | Notes |
|-------|----------|------------|-------|
| 0 | quiet_range | CONSOLIDATION | Direct map |
| 1 | trending_up_weak | BULL_PULLBACK | Weak uptrend ≈ pullback within bull context |
| 2 | trending_up_strong | BULL_TREND | Direct map |
| 3 | trending_down_weak | BEAR_RALLY | Weak downtrend ≈ rally within bear context |
| 4 | trending_down_strong | BEAR_TREND | Direct map |
| 5 | high_vol_up | PARABOLIC | High vol + positive = parabolic |
| 6 | high_vol_down | LIQUIDITY_CRISIS | High vol + negative = crisis |
| 7 | mean_revert | CONSOLIDATION | Absorb into consolidation; accumulation requires volume signal |
| 8 | breakout_up | BULL_TREND | Breakout = trend initiation |
| 9 | breakout_down | BEAR_TREND | Breakout = trend initiation |
| 10 | compression | SQUEEZE | Direct map |
| 11 | expansion | (transition) | Not a steady state; expansion triggers re-evaluation into target regime |
| 12 | choppy | CHOPPY_VOLATILE | Direct map |
| — | (new) | ACCUMULATION | NEW — requires F3+F4+F5 data not in current labeler |
| — | (new) | DISTRIBUTION | NEW — requires F3+F4+F5 data not in current labeler |
| — | (new) | TOPPING | NEW — requires F4+F5 data not in current labeler |
| — | (new) | BOTTOMING | NEW — requires F4+F5 data not in current labeler |

**Key insight**: The current labeler can only produce 11 of 13 regimes (missing ACCUMULATION, DISTRIBUTION, TOPPING, BOTTOMING) because it lacks funding rate and open interest data. These four regimes are the primary motivation for the five-factor upgrade.

---

## 5. Storage Format Specification

### Schema Overview

Three storage layers, each serving different consumers:

```
zangetsu/data/
├── raw/                          # S1: Raw market data
│   └── {symbol}/
│       └── {YYYY}/{MM}/
│           └── {DD}.parquet      # 1m OHLCV + funding_rate + open_interest
│
├── factors/                      # S2-S3: Nondimensional + Factor scores
│   └── {symbol}/
│       └── {YYYY}/{MM}/
│           └── {DD}.parquet      # 1m: 5 factor scores + 5 extreme flags
│
├── regimes/                      # S5-S7: 4H regime labels
│   └── {symbol}/
│       └── {YYYY}.parquet        # 4h: regime label + 5 factor scores + confidence
│
└── meta/
    └── schema_version.json       # Version tracking
```

### Raw Layer — 1m bars

| Column | Type | Description |
|--------|------|-------------|
| timestamp | int64 (ms) | Unix timestamp, UTC |
| open | float64 | |
| high | float64 | |
| low | float64 | |
| close | float64 | |
| volume | float64 | Base asset volume |
| funding_rate | float64 | Last known 8h funding rate (constant between updates) |
| open_interest | float64 | Total open interest in contracts |

**Format**: Apache Parquet, ZSTD compression, row-group size = 1 hour (60 rows).
**Partitioning**: By symbol → year → month → day.
**Retention**: Indefinite. Raw data is never deleted.

### Factor Layer — 1m scores

| Column | Type | Description |
|--------|------|-------------|
| timestamp | int64 (ms) | Aligned to raw |
| f1_momentum | float32 | [-1, +1] |
| f2_volatility | float32 | [-1, +1] |
| f3_volume | float32 | [-1, +1] |
| f4_funding | float32 | [-1, +1] |
| f5_oi | float32 | [-1, +1] |
| f1_extreme | uint8 | 0 or 1 |
| f2_extreme | uint8 | 0 or 1 |
| f3_extreme | uint8 | 0 or 1 |
| f4_extreme | uint8 | 0 or 1 |
| f5_extreme | uint8 | 0 or 1 |

**Format**: Parquet, ZSTD, float32 sufficient (precision to 0.0001).
**Recomputable**: If factor weights change, regenerate from raw. Factor files are derived, not source-of-truth.

### Regime Layer — 4H labels

| Column | Type | Description |
|--------|------|-------------|
| timestamp | int64 (ms) | 4H bar open time |
| regime | string | One of 13 regime names (e.g. "BULL_TREND") |
| regime_id | uint8 | 0-12 numeric ID |
| f1_4h | float32 | 4H aggregated momentum score |
| f2_4h | float32 | 4H aggregated volatility score |
| f3_4h | float32 | 4H aggregated volume score |
| f4_4h | float32 | 4H aggregated funding score |
| f5_4h | float32 | 4H aggregated OI score |
| confidence | float32 | [0, 1] distance from nearest boundary |
| prev_regime | string | Previous bar regime (for transition tracking) |

**Format**: Parquet, ZSTD. One file per year per symbol (4H = ~2190 rows/year, trivial size).

### Versioning

```json
// meta/schema_version.json
{
  "schema_version": "2.0.0",
  "factor_weights_hash": "sha256:...",
  "regime_thresholds_hash": "sha256:...",
  "created": "2026-04-16T00:00:00Z",
  "breaking_changes": [
    "2.0.0: Five-factor framework replaces price-only labeler"
  ]
}
```

**Versioning rules**:
- Factor weight changes = minor version bump. Regenerate factor layer.
- Regime threshold changes = minor version bump. Regenerate regime layer.
- Schema column changes = major version bump. All layers regenerated.
- Raw layer never changes schema (append-only).

### Live Pipeline Integration

```
[Exchange WS] → [1m bar builder] → [raw/ append]
                                   → [factor compute] → [factors/ append]
                                   → [4h accumulator]
                                        └→ [on 4h close] → [regime classify] → [regimes/ append]
                                                         → [broadcast to engine]
```

Latency budget: 1m bar close → factor scores available < 50ms. 4H bar close → regime label available < 200ms.

---

## Appendix A: Reusable Patterns from signal_utils.py

The existing `_zero_cross_signal()` in signal_utils.py implements Tanh-MAD normalization:
```python
tanh(v / MAD)  # where MAD = median(abs(v - median(v)))
```
This is directly reusable for F1 (momentum) and F4 (funding rate) nondimensional transforms. The `_ob_os_signal()` pattern maps to Sigmoid-threshold for RSI/MFI type indicators.

# REUSABLE: tanh-mad-normalization | use-when: zero-centered indicator needs [-1,+1] nondim | extract-if: used in >= 2 projects
# REUSABLE: percentile-rank-normalization | use-when: unbounded indicator needs cross-symbol [-1,+1] | extract-if: used in >= 2 projects

---

## Appendix B: Implementation Priority

| Phase | Deliverable | Dependency |
|-------|-------------|------------|
| P1 | Raw data layer + funding rate + OI ingestion | Exchange API |
| P2 | F1 (momentum) + F2 (volatility) — price-only factors | P1 raw data |
| P3 | F3 (volume) + F4 (funding) + F5 (OI) — new data factors | P1 raw data |
| P4 | 4H aggregation + 13-regime classifier | P2 + P3 |
| P5 | Backtest validation: new labels vs old labels correlation | P4 |
| P6 | Live pipeline integration | P4 + existing engine |

P2 can be validated independently against the current labeler as a sanity check before P3 introduces new data sources.
