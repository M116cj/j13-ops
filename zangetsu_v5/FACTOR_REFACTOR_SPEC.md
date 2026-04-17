# Factor-Based Data Refactor — Full Implementation Spec

## Objective
Restructure ALL data into 5 nondimensional factor categories.
Every input to the signal system must be scale-free.

## 5 Factor Categories

### F1: Momentum (動量)
- returns = (C(t) - C(t-1)) / C(t-1)
- log_returns = ln(C(t) / C(t-1))
- RSI(close) — already nondimensional
- Stochastic(C,H,L) — already nondimensional
- PPO(close) — replaces MACD (nondimensional %)
- ROC(close) — already nondimensional
- CMO(close) — already nondimensional
- TSI(returns) — change input from close to returns
- TRIX(close) — already nondimensional

### F2: Volatility (波動率)
- normalized_atr = ATR(14) / close
- realized_vol = std(returns, 20) * sqrt(252*1440)
- bollinger_bandwidth = (upper_band - lower_band) / middle_band
- garman_klass = sqrt(0.5 * ln(H/L)^2 - (2*ln2-1) * ln(C/O)^2)
- normalized_range = (H - L) / C per bar

### F3: Volume (成交量)
- relative_volume = volume / SMA(volume, 20)
- volume_ratio = volume(t) / volume(t-1)
- MFI(C,H,L,V) — already nondimensional (0-100)
- vwap_deviation = (close - VWAP) / VWAP
- volume_price_corr = rolling_corr(returns, relative_volume, 20)

### F4: Funding Rate (資金費率)
- Data source: Binance GET /fapi/v1/fundingRate (8h intervals)
- Raw funding rate (already nondimensional, typically -0.01% to +0.03%)
- funding_zscore = (rate - rolling_mean(100)) / rolling_std(100)
- cumulative_funding = rolling_sum(rate, 30*3) — 30 day accumulation
- Integration: forward-fill 8h values to 1m bars

### F5: Open Interest (持倉量)
- Data source: Binance GET /fapi/v1/openInterest (5min intervals)
- oi_change = (OI(t) - OI(t-1)) / OI(t-1)
- oi_relative = OI / SMA(OI, 20)
- oi_price_divergence = sign(oi_change) vs sign(returns)
- Integration: resample 5min to 1m with forward-fill

## Implementation Steps

### Step 1: Build data_preprocessor.py
New file: engine/components/data_preprocessor.py
Functions:
  compute_returns(close) -> returns, log_returns
  compute_normalized_range(high, low, close) -> nrange
  compute_relative_volume(volume, window=20) -> rvol
  compute_normalized_atr(high, low, close, period=14) -> natr
  compute_realized_vol(returns, window=20) -> rvol
  compute_bollinger_bw(close, window=20) -> bw
  compute_garman_klass(open, high, low, close, window=20) -> gk
  compute_vwap_deviation(close, volume) -> vwap_dev
  compute_volume_price_corr(returns, rvol, window=20) -> vpc
All functions should be Numba @njit where possible.

### Step 2: Build data_collector.py
New file: services/data_collector.py
Functions:
  fetch_funding_rate(symbol, since) -> DataFrame
  fetch_open_interest(symbol, since) -> DataFrame
  merge_to_1m(ohlcv_df, funding_df, oi_df) -> combined_df
  save_parquet(combined_df, path)
Use ccxt or direct Binance API.

### Step 3: Update arena_pipeline.py data loading
After loading OHLCV parquet:
  1. Compute nondimensional features
  2. Load funding + OI if available
  3. Store in data_cache alongside raw OHLCV
  4. Pass nondimensional features to indicators that need them

### Step 4: Update indicator list (DIRECTIONAL)
Remove: MACD (has dimension)
Add: PPO (already exists, nondimensional)
Modify: TSI input from close to returns
Modify: zscore input from close to returns
Keep: RSI, stochastic_k, ROC, CMO, TRIX, CCI (already nondimensional)
Add new indicators: normalized_atr, realized_vol, bollinger_bw, relative_volume, vwap_deviation

### Step 5: Add funding + OI as new indicator channels
New INDICATOR_SIGNALS entries:
  "funding_rate": lambda v: continuous vote based on funding level
  "funding_zscore": lambda v: continuous vote based on z-score
  "oi_change": lambda v: continuous vote based on OI delta
  "oi_divergence": computed from oi_change vs returns

### Step 6: Run historical data collection
For all 13 symbols:
  1. Download funding rate history (all available)
  2. Download OI history (all available)
  3. Merge with existing OHLCV parquet
  4. Save as new parquet format

### Step 7: Restart and validate
  1. Restart all services
  2. Verify V7.1 produces champions with new factor data
  3. Compare output quality vs pre-refactor

## File Changes
- NEW: engine/components/data_preprocessor.py
- NEW: services/data_collector.py
- MODIFY: services/arena_pipeline.py (data loading)
- MODIFY: engine/components/signal_utils.py (indicator list + new votes)
- MODIFY: services/arena23_orchestrator.py (data loading if needed)
- MODIFY: services/arena45_orchestrator.py (data loading if needed)

## New Session Command
```
授權調用所有資源。實作 Zangetsu Factor-Based Data Refactor。
讀 spec: ssh j13@100.123.49.102 "cat ~/j13-ops/zangetsu_v5/FACTOR_REFACTOR_SPEC.md"
讀 arena_pipeline 數據載入: ssh j13@100.123.49.102 "sed -n 300,350p ~/j13-ops/zangetsu_v5/services/arena_pipeline.py"
讀 signal_utils indicators: ssh j13@100.123.49.102 "head -40 ~/j13-ops/zangetsu_v5/engine/components/signal_utils.py"
按 spec 的 7 個步驟依序執行。完成後寫 FACTOR_RESULT.md。
```
