# 03 — Data Availability Matrix

**TEAM ORDER**: 0-9AA — Phase 3
**Date**: 2026-04-30
**Mode**: READ-ONLY / DECISION-ONLY

## Direct File Survey (`zangetsu/data/`)

| Subdir | File count | Schema | Notes |
|---|---:|---|---|
| `data/ohlcv/` | 14 symbols (parquet) | `timestamp, open, high, low, close, volume` | 1-minute bars; e.g. 1000PEPEUSDT has 1,565,281 rows starting 2023-05-09 |
| `data/funding/` | 14 symbols (parquet) | `timestamp, fundingRate, fundingTime` | 8h funding cycles; ~3,272 rows per symbol |
| `data/oi/` | 14 symbols (parquet) | `timestamp, sumOpenInterest, sumOpenInterestValue` | 5-min OI snapshots; ~4,388 rows per symbol (recent coverage) |

**Universe = 14 perp symbols** (mix of majors + alts): `BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT, AVAXUSDT, DOGEUSDT, DOTUSDT, LINKUSDT, AAVEUSDT, FILUSDT, GALAUSDT, 1000PEPEUSDT, 1000SHIBUSDT`.

## Full Data-Type Audit

| Data Type | Exists? | Source | Coverage / Resolution | Timestamp Quality | Needed By Axis | Verdict |
|---|---|---|---|---|---|---|
| OHLCV | **YES** | `data/ohlcv/*.parquet` | 14 symbols × 1-min bars × ~1.5M rows | epoch-ms, dense | A (none directly), B (price overlay), C, D, E, F, G, H | `READY` |
| Funding rate | **YES** | `data/funding/*.parquet` | 14 symbols × 8h cycles | epoch-ms | B (primary), C (regime), H | `READY` |
| Open Interest | **YES** | `data/oi/*.parquet` | 14 symbols × 5-min snapshots, recent only | epoch-ms | B (primary), H | `READY_RECENT_ONLY` |
| Liquidations | **NO** | n/a | n/a | n/a | B (cluster sub-feature) | `DATA_BLOCKED` |
| Mark price | **NO** distinct file | OHLCV close as proxy | OHLCV resolution | adequate proxy | A (adverse selection), B (basis) | `PROXY_ONLY` |
| Index price | **NO** | n/a | n/a | n/a | B (basis vs perp) | `DATA_BLOCKED` |
| Bid / Ask | **NO** | n/a | n/a | n/a | A (primary) | `DATA_BLOCKED` (re-confirmed from 0-9ZA Phase 3) |
| Top-of-book depth | **NO** | n/a | n/a | n/a | A (queue risk) | `DATA_BLOCKED` |
| Trade prints | **NO** | n/a | n/a | n/a | A (fill inference, adverse) | `DATA_BLOCKED` |
| Symbol metadata | **PARTIAL** | filename only | universe is the 14 listed above | n/a | D (cross-sectional universe), G | `READY_LIMITED` |
| Session / time calendar | **DERIVABLE** | from OHLCV timestamp | 24/7 perps (no session breaks intrinsic) | n/a | C (session regime) | `DERIVABLE` |

## Per-Axis Data Readiness Roll-Up

| Axis | Required Data | Available | Verdict |
|---|---|---|---|
| A — Microstructure | bid/ask, depth, trade prints | none | `BLOCKED` |
| B — Funding/OI/Liq | funding ✓, OI ✓, liquidations ✗ | partial | `READY_PARTIAL` (funding+OI ready, liquidations blocked) |
| C — Regime conditional | OHLCV, funding (optional) | yes | `READY` |
| D — Cross-sectional | OHLCV multi-symbol | yes (14 symbols) | `READY` |
| E — Liquidity / volume shock | OHLCV volume (+OI optional) | yes | `READY` |
| F — Volatility expansion | OHLCV | yes | `READY` |
| G — Alt timeframe / universe | OHLCV resampling | yes | `READY` |
| H — Hybrid | depends on chosen components | mostly yes (avoid A, avoid liquidations) | `READY_IF_COMPONENTS_AVOID_BLOCKED` |

## Data-Layer Implications for Selection

1. **Microstructure (A) cannot be selected for immediate execution.** Its inclusion would require a full data-capture buildout first (the 0-9ZA-recommended `0-9ZB-MARKET-MICROSTRUCTURE-DATA-CAPTURE-SHADOW`).
2. **Funding/OI (B) is partially blocked** — liquidation-cluster sub-features are unavailable, but the funding-rate and OI-delta cores are usable.
3. **Regime (C), Cross-sectional (D), Liquidity (E), Volatility (F)** are all OHLCV-derivable and immediately testable.
4. **Hybrid (H)** is data-ready only if components avoid microstructure and liquidations.

## Deliverable

`03_data_availability_matrix.md` — frozen.
