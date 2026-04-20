# Data Refactor — Nondimensionalization + Extended Features

## Goal
Transform raw OHLCV into clean nondimensional features that express pure market state.

## Current State
- Raw OHLCV (float64) → directly fed to Rust indicators → no preprocessing
- Price scale varies 100x across history ($3,706 ~ $126,086 BTC)
- Only 6 columns: timestamp, open, high, low, close, volume
- No funding rate, open interest, or orderbook data

## Proposed Changes

### 1. Nondimensionalization
All features must be scale-free (no USD units):
- Returns: r(t) = (close(t) - close(t-1)) / close(t-1)
- Log returns: ln(close(t) / close(t-1))
- Normalized range: (high - low) / close
- Normalized volume: volume / rolling_mean(volume, N)
- All indicators computed on returns or normalized values, not raw price

### 2. Feature Categories
- Momentum: returns, ROC, RSI, MACD (on returns), CMO, TSI
- Volatility: realized vol, ATR/close, Bollinger bandwidth, Garman-Klass
- Volume: normalized volume, OBV on returns, volume-price correlation, MFI
- Funding rate: Binance perpetual funding rate (8h interval, needs new data source)
- Open interest: total OI changes (needs new data source)

### 3. Data Pipeline
Raw OHLCV + Funding + OI
  → nondimensionalize (returns, normalized range, normalized volume)
  → compute indicators on nondimensional features
  → feed to signal_utils (V7.1 semantic continuous votes)

### 4. New Data Sources Needed
- Binance Futures funding rate API: GET /fapi/v1/fundingRate
- Binance Futures open interest API: GET /fapi/v1/openInterest
- Both need to be collected and stored alongside OHLCV

## Discussion Points for Meeting
1. Should indicators be computed on raw price or nondimensional returns?
2. How to handle funding rate (8h interval vs 1m bars)?
3. How to integrate OI (snapshot vs delta)?
4. What nondimensional form best preserves indicator semantics?
5. How does this affect existing V7.1 semantic vote thresholds?

## New Session Command
```
授權調用所有資源。開會討論 Zangetsu 數據重構。
讀 spec: ssh j13@100.123.49.102 "cat ~/j13-ops/zangetsu/DATA_REFACTOR_SPEC.md"
讀現有數據: ssh j13@100.123.49.102 "head -5 ~/j13-ops/zangetsu/services/arena_pipeline.py"
讀 V7.1 結果: ssh j13@100.123.49.102 "cat ~/j13-ops/zangetsu/V71_RESULT.md"
```
