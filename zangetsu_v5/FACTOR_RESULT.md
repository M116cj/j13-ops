# Factor-Based Data Refactor — Implementation Result

## Date: 2026-04-16

## Status: ✅ COMPLETE — All services running with 5-factor data

## Changes Made

### NEW: engine/components/data_preprocessor.py (full rewrite)
- All compute functions now use Numba @njit with cache=True
- F1 Momentum: compute_returns, compute_log_returns
- F2 Volatility: compute_normalized_range, compute_normalized_atr, compute_realized_volatility, compute_bollinger_bw, compute_garman_klass
- F3 Volume: compute_relative_volume, compute_volume_ratio, compute_vwap_deviation, compute_volume_price_corr
- F4 Funding: compute_funding_zscore, compute_cumulative_funding
- F5 OI: compute_oi_change, compute_oi_relative, compute_oi_price_divergence
- enrich_data_cache() now processes all 5 factor categories

### NEW: services/data_collector.py
- ccxt-based Binance Futures downloader for funding rate + open interest
- fetch_funding_rate() — full history via ccxt unified API
- fetch_open_interest() — 5min intervals via ccxt unified API
- merge_funding_to_1m() / merge_oi_to_1m() — forward-fill to OHLCV timestamps
- Incremental append + dedup on re-run

### MODIFIED: services/arena_pipeline.py
- Loads `open` column from parquet (needed for Garman-Klass)
- Loads funding rate + OI data via merge_funding_to_1m / merge_oi_to_1m
- DIRECTIONAL list: removed MACD (has dimension), added 9 factor indicators
- Factor indicators bypass Rust engine (pre-computed, period=0 key)
- Enrichment log: "Factor enrichment complete: F1 F2 F3 F4 F5"

### MODIFIED: engine/components/signal_utils.py
- Removed MACD from INDICATOR_SIGNALS
- Added signal handlers for:
  - F2: normalized_atr, realized_vol, bollinger_bw (high vol = caution)
  - F3: relative_volume, vwap_deviation (mean-reversion)
  - F4: funding_rate (contrarian), funding_zscore (mean-reversion at ±2σ)
  - F5: oi_change (zero-cross), oi_divergence (pass-through ±1)

### MODIFIED: services/arena23_orchestrator.py
- Added factor data loading (open, funding, OI) + enrich_data_cache
- Backward compat: train split keys accessible at top level

### MODIFIED: services/arena45_orchestrator.py
- Removed MACD from DIRECTIONAL, added 9 factor indicators
- Added factor data loading (holdout split) + enrich_data_cache
- Backward compat: holdout split keys accessible at top level

## Data Collection Results

### Funding Rate (all 14 symbols)
| Symbol | Records | Coverage |
|--------|---------|----------|
| BTCUSDT | 1,095 | ~45 days (pre-existing) |
| ETHUSDT | 1,095 | ~45 days (pre-existing) |
| BNBUSDT | 6,772 | since 2020 |
| SOLUSDT | 1,095 | ~45 days (pre-existing) |
| XRPUSDT | 6,877 | since 2020 |
| DOGEUSDT | 6,319 | since 2020 |
| LINKUSDT | 6,844 | since 2020 |
| AAVEUSDT | 6,025 | since 2020 |
| AVAXUSDT | 6,096 | since 2020 |
| DOTUSDT | 6,196 | since 2020 |
| FILUSDT | 6,025 | since 2020 |
| 1000PEPEUSDT | 3,231 | since listing |
| 1000SHIBUSDT | 5,406 | since listing |
| GALAUSDT | 5,016 | since listing |

### Open Interest (all 14 symbols)
- BTC/ETH/SOL: ~8,931 records (~31 days)
- Other 11 symbols: 500 records (~1.7 days, Binance API limit)
- Note: OI history API has 30-day retention; will accumulate over time

## Validation

### Enrichment Test (BTCUSDT, 140k bars)
- F1: returns (nonzero=137,200), log_returns ✅
- F2: normalized_atr, realized_vol, bollinger_bw, garman_klass, normalized_range ✅
- F3: relative_volume, volume_ratio, vwap_deviation, volume_price_corr ✅
- F4: funding_rate (all bars filled), funding_zscore, cumulative_funding ✅
- F5: oi_change, oi_relative, oi_price_divergence (sparse — OI data only covers recent period)

### Service Startup
- arena-pipeline: active, producing champions (R22: SOL Sharpe=1.33, R23: FIL Sharpe=1.16)
- arena23-orchestrator: active, 14 symbols loaded with factor enrichment
- arena45-orchestrator: active, 14 symbols loaded (holdout split)
- Indicator cache: ~103 entries per symbol (was ~84 before)

## DIRECTIONAL Indicator List (21 indicators)
```
["rsi", "stochastic_k", "cci", "roc", "ppo", "cmo",
 "zscore", "trix", "tsi", "obv", "mfi", "vwap",
 "normalized_atr", "realized_vol", "bollinger_bw",
 "relative_volume", "vwap_deviation",
 "funding_rate", "funding_zscore", "oi_change", "oi_divergence"]
```

## Next Steps
1. Schedule periodic data_collector.py run (cron every 8h) to accumulate OI history
2. Backfill BTC/ETH/SOL funding rate to full history (currently only 45 days)
3. Monitor champion quality with new factor indicators vs baseline
