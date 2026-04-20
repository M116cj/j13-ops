# Zangetsu Market Data Layer — Architecture Meeting Spec

## Meeting Directive
Rebuild the data foundation under the 13-regime framework.
Five-factor market state description.
Preserve extremes and uncertainty.
Cross-symbol nondimensional.

## Current 13 Regimes (KEEP ALL)
BULL_TREND, BULL_PULLBACK, BEAR_TREND, BEAR_RALLY,
CONSOLIDATION, SQUEEZE, CHOPPY_VOLATILE, LIQUIDITY_CRISIS,
PARABOLIC, ACCUMULATION, DISTRIBUTION, TOPPING, BOTTOMING

## Current Regime Labeler
4h bars → L1 macro (BULL/BEAR/NEUTRAL via EMA20 vs EMA50 + ADX) → L2 fine (13 states via ATR, ADX, EMA slope, volatility) → L1→L2 constraint

## Five Factor Categories to Design

### F1 Momentum — directional conviction
### F2 Volatility — uncertainty/risk
### F3 Volume — participation/conviction
### F4 Funding Rate — crowd positioning
### F5 Open Interest — leverage/commitment

## Discussion Requirements

### 1. Data Architecture
- Raw → Nondimensional → Factor Scores → State Axes → Regime Mapping
- Every step must be defined

### 2. Five-Factor Feature Framework
For each factor: raw inputs, nondimensional transform, output range, semantic meaning

### 3. Extreme-Value Preservation
- No winsorization, no outlier removal
- Extreme = information, not noise
- How to encode extremes without distorting normal-range behavior

### 4. Regime Support Logic
Ambiguous boundaries that need factor-based clarification:
- DISTRIBUTION vs TOPPING: both are "end of uptrend" — what factor separates them?
- ACCUMULATION vs BOTTOMING: both are "end of downtrend" — what factor separates them?
- CONSOLIDATION vs SQUEEZE: both are "low volatility" — what factor separates them?
- CHOPPY_VOLATILE vs LIQUIDITY_CRISIS: both are "high volatility" — what factor separates them?

### 5. Storage Format
- Labels: regime string per 4h bar
- Scores: per-factor continuous score [-1, +1] per 1m bar
- State axes: 5-dimensional vector per bar
- How to version and persist

## New Session Command
```
授權調用所有資源。開啟 Agent Teams 會議：Zangetsu Market Data Layer Architecture。
讀 meeting spec: ssh j13@100.123.49.102 "cat ~/j13-ops/zangetsu/MARKET_DATA_LAYER_MEETING.md"
讀 current regime labeler: ssh j13@100.123.49.102 "cat ~/j13-ops/zangetsu/engine/components/regime_labeler.py"
讀 current signal_utils: ssh j13@100.123.49.102 "head -60 ~/j13-ops/zangetsu/engine/components/signal_utils.py"

Claude leads. 產出:
1. Market data architecture diagram
2. Five-factor feature framework (每個 factor 的完整定義)
3. Extreme-value preservation policy
4. 13-regime factor-based support structure
5. Storage format specification
寫結果到 ~/j13-ops/zangetsu/MARKET_DATA_ARCHITECTURE.md
```
