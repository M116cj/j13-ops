# 03 — Orderbook Data Availability

## Sources surveyed

1. **zangetsu repo `data/`**: `ohlcv/`, `funding/`, `oi/` only. **No** orderbook, depth, bid/ask, or trade-print files. Files are parquet per-symbol (e.g. `data/funding/BTCUSDT.parquet`).
2. **Katen** (running, container `katen-collector`, `Up 2 days` at task start): writes to `KATEN_DB_URL = postgresql://zangetsu:***@akasha-postgres:5432/zangetsu` (verified via `docker inspect katen-collector`).
3. **akasha-postgres** (container `akasha-postgres`, port 127.0.0.1:5433 → 5432 internal): hosts katen tables.
4. **deploy-postgres-1** (port 127.0.0.1:5432): hosts zangetsu DB; **no** orderbook tables present.

## Data classification

| Data type | Available? | Source | Resolution | Coverage | Needed for | Blocker? |
|-----------|-----------|--------|-----------:|----------|------------|----------|
| best bid / best ask **price** | **NO** | `katen_raw_ticks` schema exists (`bid_prices double precision[]`, `ask_prices double precision[]`) but **0 rows / 0 partitions** | n/a | n/a | empirical maker-fill simulation | **YES (HARD)** |
| best bid / best ask **size** | **NO** | `katen_raw_ticks.bid_sizes/ask_sizes` empty | n/a | n/a | queue position estimate | **YES (HARD)** |
| spread (aggregated bps) | YES | `katen_tick_features.spread_bps` | 1 s | 2026-04-08 16:54 → 2026-04-30 01:33 (~22 d), 6/14 symbols | conservative spread-cost proxy | partial (coverage) |
| mid price (weighted) | YES | `katen_tick_features.wmid` | 1 s | same as above | adverse-selection post-fill drift proxy | partial (coverage) |
| top-of-book size | NO | aggregated only (`obi`, `depth_ratio`) — no absolute size | n/a | n/a | queue risk | **YES** |
| depth levels (5-10 levels) | NO | `katen_raw_ticks` empty; `katen_tick_features` only stores `depth_ratio` (a derived scalar) | n/a | n/a | partial-fill risk model | **YES** |
| trade prints | NO | not collected by Katen at HEAD (`on_trade` referenced in `katen/src/main.py:161` but no `katen_trades` table observed; only book ticks) | n/a | n/a | fill-probability model (need trades crossing limit) | **YES (HARD)** |
| mark price | NO | not in any zangetsu / katen table | n/a | n/a | adverse-selection benchmark | **YES** |
| funding rate | YES (8h granularity) | zangetsu `data/funding/{SYMBOL}.parquet` | 8 h | full historical (years), all 14 zangetsu symbols | side-funding decomposition | NO |
| timestamp alignment | YES at 1s for katen, 8h for funding, OHLCV per-bar | mixed | mixed | mixed | join sanity | NO (but cross-resolution) |
| symbol universe overlap | **MISMATCH** | Katen: `BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT,DOGEUSDT` (6 symbols, all Stable tier). Zangetsu: 14 symbols (6 Stable + 5 Diversified + 3 High-Vol). | n/a | 0/5 Diversified, 0/3 High-Vol covered by Katen orderbook data | per-symbol maker fill | **YES (PARTIAL)** |
| latency proxy | NO | no client-server timestamp pair stored | n/a | n/a | execution-delay model | **YES** |

## Critical gaps

1. **Raw L1 prices unavailable**: `katen_raw_ticks` is partitioned but has **0 partitions / 0 rows**. The `on_book` callback in `katen/src/main.py` exists, the table exists, but persistence of raw arrays was never enabled (likely cost-controlled — would generate ~50-100M rows/day at 1s × 6 symbols × 10 levels). Without raw bid/ask history, we **cannot** simulate "would my limit at bid have filled at time t" empirically.
2. **No trade prints**: cannot detect when price traded *through* the maker limit, which is the canonical fill-detection signal.
3. **Coverage mismatch on tier**: Katen covers 6/14 symbols, all Stable tier. Diversified (LINK, AAVE, AVAX, DOT, FIL) and High-Vol (1000PEPE, 1000SHIB, GALA) symbols — which dominate zangetsu's higher-cost backtests — have **zero orderbook history**.
4. **Coverage window short**: 22 days is below typical Arena-2 holdout window (~90 days) and far below Arena-3/4 window (~180-360 days). Even if raw L1 were enabled today, building enough history for backtest validation takes months.

## Conservative-proxy possibility

The order text states: "If bid/ask and trade prints are unavailable, classify empirical maker-fill as DATA_BLOCKED **unless a conservative proxy can be justified**." Possible proxies:

| Proxy | What it gives | What it misses | Verdict |
|-------|---------------|----------------|---------|
| OHLCV-derived high/low intersection of limit | Approximate fill flag (did price touch our limit during the bar?) | No queue order, no partial-fill, no adverse-selection measurement, biased optimistic (intra-bar trade prints lost) | **WEAK** — usable only as *upper bound* on fill rate, not as decisive net-bps source |
| `katen_tick_features.spread_bps` (1s aggregated) on Stable tier | Realistic spread cost proxy for 6/14 symbols | Doesn't cover Diversified / High-Vol; doesn't simulate fill | usable for spread-cost lower bound on Stable only |
| Literature adverse-selection band (30-80%) | Conservative net-bps under maker-only, as already used in 0-9Z | Not symbol- or side-specific | **already applied in 0-9Z**; using again here adds zero new signal |

The strongest defensible proxy is **OHLCV-fill-flag × spread-cost-from-katen on Stable tier only**, but it cannot prove *both* sides net-positive simultaneously and cannot speak to Diversified or High-Vol tiers at all. Per the order's per-side rule (no combined-only verdict), this proxy is **insufficient** to upgrade out of `DATA_BLOCKED` status.

## Verdict

**`EMPIRICAL_MAKER_FILL = DATA_BLOCKED`.** Conservative proxy possible only on partial subset (Stable tier, 22-day window) and only as one-sided upper bound; cannot satisfy the order's mandatory LONG / SHORT / COMBINED separability requirement at the empirical level.

