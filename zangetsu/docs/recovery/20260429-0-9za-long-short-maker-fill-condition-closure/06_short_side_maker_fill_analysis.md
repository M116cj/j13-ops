# 06 — Short-Side Maker-Fill Analysis

**TEAM ORDER**: 0-9ZA-COMPLETE — Phase 6
**Date**: 2026-04-30
**Mode**: READ-ONLY / SHADOW-ONLY / DECISION-ONLY

## Objective

Evaluate whether SHORT entries can be passively filled at ask and remain profitable after fill delay, missed fills, queue risk, adverse selection, funding, and fees.

## Required vs. Available Market-Microstructure Data

| Data | Required | Available | Result |
|---|---|---|---|
| ask quote history | yes | no | DATA_BLOCKED |
| bid quote history | yes | no | DATA_BLOCKED |
| trade prints | yes | no | DATA_BLOCKED |
| top-of-book depth | yes | no | DATA_BLOCKED |
| queue position proxy | yes | no | DATA_BLOCKED |
| funding by timestamp | yes | partial (parquet, low resolution) | BLOCKED_OR_PARTIAL |
| mark price | yes | partial | BLOCKED_OR_PARTIAL |

Source: `03_orderbook_data_availability.md` confirms `data/` contains only OHLCV / funding / OI parquet files. No bid/ask, depth, or trade-print files exist at HEAD `3cb5e08f`.

## SHORT Entry Model

SHORT maker entry requires posting a passive sell order at the ask (or ask-offset).

Required proof:
- ask existed at signal timestamp
- limit sell would have joined the queue
- subsequent trade lifted the ask level
- fill occurred before signal-edge decay
- post-fill adverse-movement window measured

Available proof:
- **unavailable** — no ask quote, no trade prints, no queue depth.

## SHORT Exit Model

SHORT exit requires a passive buy at the bid (or a defined fallback).

Required proof:
- bid existed at exit timestamp
- exit fill occurred
- exit delay measured
- adverse movement during exit delay measured

Available proof:
- **unavailable** — no bid quote, no trade prints.

## Why OHLCV Cannot Substitute

Same as LONG case (see 05). OHLCV touches cannot prove queue priority, partial fills, missed fills, adverse selection after passive fill, or side-aware spread capture. Inferring SHORT fills from OHLCV would fabricate fill rates and is forbidden.

## Funding Asymmetry Note

SHORT funding is not symmetric to LONG funding — perp funding rate paid by longs to shorts (or vice-versa) is regime-dependent. Without per-timestamp side-aware funding evidence, SHORT carrying-cost cannot be netted into final bps.

## Missing Measurements

| Metric | Status |
|---|---|
| short fill rate | DATA_BLOCKED |
| short missed-fill rate | DATA_BLOCKED |
| short median delay | DATA_BLOCKED |
| short p90 delay | DATA_BLOCKED |
| short queue haircut | DATA_BLOCKED |
| short adverse selection bps | DATA_BLOCKED |
| short post-maker net bps | DATA_BLOCKED |
| short A2 trade-count impact | DATA_BLOCKED |

## Verdict

**SHORT_RESULT = DATA_BLOCKED**

**Reason**: Without ask quote history, trade prints, and orderbook/depth data, short-side maker-fill profitability cannot be empirically validated. Funding asymmetry compounds the data gap. Conservative inference from OHLCV would produce fabricated fill statistics and is rejected.
