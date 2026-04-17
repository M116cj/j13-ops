# Data Refactor Result — 2026-04-16

## Status: COMPLETED

## Changes Made

### 1. New File: `engine/components/data_preprocessor.py`
Nondimensionalization module — transforms raw OHLCV into scale-free features.

Functions:
- `compute_returns(close)` — simple returns: (C(t) - C(t-1)) / C(t-1)
- `compute_log_returns(close)` — log returns: ln(C(t) / C(t-1))
- `compute_normalized_range(high, low, close)` — (H - L) / C
- `compute_normalized_volume(volume, window=20)` — V / rolling_mean(V, 20)
- `compute_realized_volatility(log_returns, window=20)` — rolling std of log returns
- `compute_garman_klass(open, high, low, close, window=20)` — GK volatility estimator
- `enrich_data_cache(data_cache)` — adds all above to both train/holdout splits

All outputs are unitless (no USD units). Edge cases handled:
- Empty arrays → return empty
- Zero prices → return 0.0 (no division by zero)
- NaN/Inf → clamped to 0.0

### 2. Modified: `services/arena_pipeline.py`
- Added import: `from zangetsu_v5.engine.components.data_preprocessor import enrich_data_cache`
- After data loading loop (line ~348): calls `enrich_data_cache(data_cache)`
- Adds 6 new keys to each symbol's train/holdout dict
- **Original close/high/low/volume keys are untouched** — Rust indicators still receive raw data

### 3. New File: `scripts/fetch_funding_oi.py`
Downloads Binance Futures historical data:
- Funding rate: `GET /fapi/v1/fundingRate` (8h interval, forward pagination)
- Open interest: `GET /futures/data/openInterestHist` (5m interval, ~30 day limit)

Output stored as parquet:
- `data/funding/{SYMBOL}.parquet` — columns: timestamp, fundingRate, fundingTime
- `data/oi/{SYMBOL}.parquet` — columns: timestamp, sumOpenInterest, sumOpenInterestValue

### 4. Downloaded Data
| Type | Symbol | Rows | Date Range |
|------|--------|------|------------|
| Funding | BTCUSDT | 1095 | 2025-04-16 → 2026-04-16 |
| Funding | ETHUSDT | 1095 | 2025-04-16 → 2026-04-16 |
| Funding | SOLUSDT | 1095 | 2025-04-16 → 2026-04-16 |
| OI | BTCUSDT | 8928 | 2026-03-16 → 2026-04-16 |
| OI | ETHUSDT | 8928 | 2026-03-16 → 2026-04-16 |
| OI | SOLUSDT | 8928 | 2026-03-16 → 2026-04-16 |

Note: Binance OI history API only provides ~30 days at 5m resolution.

## What Was NOT Changed
- `engine/components/signal_utils.py` — V7.1 semantic continuous signals untouched
- `engine/components/backtester.py` — untouched
- Rust indicator engine (`zi.compute`) — still receives raw close/high/low/vol
- All existing indicator calculation logic — unchanged
- Train/holdout split ratios — unchanged

## New data_cache Keys After Enrichment
```
data_cache[sym]["train"].keys() = [
    "close", "high", "low", "volume",           # original (raw)
    "returns", "log_returns",                     # nondim price
    "normalized_range", "normalized_volume",      # nondim range/vol
    "realized_vol", "garman_klass",              # nondim volatility
]
```

## Next Steps
1. Wire funding rate into indicator computation (new indicator type)
2. Wire OI delta into signal_utils as additional vote dimension
3. Consider computing indicators on nondimensional returns instead of raw price
4. Set up cron job for daily funding/OI data refresh

## Q1 Adversarial Checklist
- [x] Input boundary: empty arrays, zero prices, NaN/Inf all handled → PASS
- [x] Failure propagation: enrich_data_cache failure would not corrupt original data (additive only) → PASS
- [x] External dependency: Binance API failure in fetch script is caught per-symbol, doesn't block others → PASS
- [x] Concurrency/race: data_cache enrichment runs before any threading starts → PASS
- [x] Scope creep: only data input layer changed, no indicator/signal/backtest logic modified → PASS
