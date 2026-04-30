# 05 — Long-Side Maker-Fill Analysis

**TEAM ORDER**: 0-9ZA-COMPLETE — Phase 5
**Date**: 2026-04-30
**Mode**: READ-ONLY / SHADOW-ONLY / DECISION-ONLY

## Objective

Evaluate whether LONG entries can be passively filled at bid and remain profitable after fill delay, missed fills, queue risk, adverse selection, funding, and fees.

## Required vs. Available Market-Microstructure Data

| Data | Required | Available | Result |
|---|---|---|---|
| bid quote history | yes | no | DATA_BLOCKED |
| ask quote history | yes | no | DATA_BLOCKED |
| trade prints | yes | no | DATA_BLOCKED |
| top-of-book depth | yes | no | DATA_BLOCKED |
| queue position proxy | yes | no | DATA_BLOCKED |
| funding by timestamp | yes | partial (parquet, low resolution) | BLOCKED_OR_PARTIAL |
| mark price | yes | partial | BLOCKED_OR_PARTIAL |

Source: `03_orderbook_data_availability.md` confirms `data/` contains only OHLCV / funding / OI parquet files. No bid/ask, depth, or trade-print files exist at HEAD `3cb5e08f`.

## LONG Entry Model

LONG maker entry requires posting a passive buy order at the bid (or bid-offset).

Required proof:
- bid existed at signal timestamp
- limit buy would have joined the queue
- subsequent trade hit the bid level
- fill occurred before signal-edge decay
- post-fill adverse-movement window measured

Available proof:
- **unavailable** — no bid quote, no trade prints, no queue depth.

## LONG Exit Model

LONG exit requires a passive sell at the ask (or a defined fallback).

Required proof:
- ask existed at exit timestamp
- exit fill occurred
- exit delay measured
- adverse movement during exit delay measured

Available proof:
- **unavailable** — no ask quote, no trade prints.

## Why OHLCV Cannot Substitute

Per `03` and `04`, OHLCV cannot distinguish:
- a passive maker fill from a price-touch
- queue position
- partial fill vs. full fill
- missed fill
- spread capture
- fill delay
- post-fill adverse selection
- bid-side vs. ask-side execution quality

Inferring fills from OHLCV touches would fabricate fill rates and is forbidden by the order critical rule.

## Missing Measurements

| Metric | Status |
|---|---|
| long fill rate | DATA_BLOCKED |
| long missed-fill rate | DATA_BLOCKED |
| long median delay | DATA_BLOCKED |
| long p90 delay | DATA_BLOCKED |
| long queue haircut | DATA_BLOCKED |
| long adverse selection bps | DATA_BLOCKED |
| long post-maker net bps | DATA_BLOCKED |
| long A2 trade-count impact | DATA_BLOCKED |

## Verdict

**LONG_RESULT = DATA_BLOCKED**

**Reason**: Without bid quote history, trade prints, and orderbook/depth data, long-side maker-fill profitability cannot be empirically validated. Conservative inference from OHLCV would produce fabricated fill statistics and is rejected.
