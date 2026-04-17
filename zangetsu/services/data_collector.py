"""Data Collector — Funding Rate + Open Interest downloader via ccxt.

Downloads from Binance Futures, saves as parquet, merges with OHLCV.
All operations are idempotent (append-only, dedup by timestamp).

Usage:
    python -m zangetsu.services.data_collector          # all symbols
    python -m zangetsu.services.data_collector BTCUSDT  # single symbol
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import logging
from pathlib import Path
from typing import List, Optional

import numpy as np
import polars as pl

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("data_collector")

DATA_DIR = Path("/home/j13/j13-ops/zangetsu/data")
OHLCV_DIR = DATA_DIR / "ohlcv"
FUNDING_DIR = DATA_DIR / "funding"
OI_DIR = DATA_DIR / "oi"

DEFAULT_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT",
    "XRPUSDT", "DOGEUSDT", "LINKUSDT", "AAVEUSDT",
    "AVAXUSDT", "DOTUSDT", "FILUSDT",
    "1000PEPEUSDT", "1000SHIBUSDT", "GALAUSDT",
]


def _init_exchange():
    """Initialize ccxt Binance futures (no API key needed for public data)."""
    import ccxt
    return ccxt.binanceusdm({
        "enableRateLimit": True,
        "options": {"defaultType": "future"},
    })


async def fetch_funding_rate(symbol: str, since_ms: Optional[int] = None) -> pl.DataFrame:
    """Fetch all funding rate history for symbol. Returns DataFrame with
    columns: [timestamp, fundingRate, fundingTime]."""
    exchange = _init_exchange()
    all_rows = []
    # Default: start from 2020-01-01
    since = since_ms or int(time.mktime(time.strptime("2020-01-01", "%Y-%m-%d")) * 1000)
    limit = 1000

    while True:
        try:
            # ccxt unified: fetchFundingRateHistory
            rates = exchange.fetch_funding_rate_history(symbol, since=since, limit=limit)
        except Exception as e:
            log.warning(f"  Funding API error for {symbol}: {e}")
            break

        if not rates:
            break

        for r in rates:
            all_rows.append({
                "timestamp": int(r["timestamp"]),
                "fundingRate": float(r["fundingRate"]),
                "fundingTime": int(r["timestamp"]),
            })

        last_ts = rates[-1]["timestamp"]
        if last_ts <= since:
            break
        since = last_ts + 1

        if len(rates) < limit:
            break

        time.sleep(0.1)  # rate limit courtesy

    if not all_rows:
        return pl.DataFrame({"timestamp": [], "fundingRate": [], "fundingTime": []}).cast(
            {"timestamp": pl.Int64, "fundingRate": pl.Float64, "fundingTime": pl.Int64}
        )

    return pl.DataFrame(all_rows).unique(subset=["timestamp"]).sort("timestamp")


async def fetch_open_interest(symbol: str, since_ms: Optional[int] = None) -> pl.DataFrame:
    """Fetch OI history via ccxt unified fetch_open_interest_history (5min intervals)."""
    exchange = _init_exchange()
    all_rows = []
    # OI history API only keeps ~30 days; don't pass ancient startTime
    since = since_ms  # None = let Binance return most recent
    limit = 500

    # ccxt unified symbol format
    ccxt_symbol = symbol.replace("USDT", "/USDT:USDT")

    while True:
        try:
            kwargs = {"timeframe": "5m", "limit": limit}
            if since is not None:
                kwargs["since"] = since
            records = exchange.fetch_open_interest_history(
                ccxt_symbol, **kwargs
            )
        except Exception as e:
            log.warning(f"  OI API error for {symbol}: {e}")
            break

        if not records:
            break

        for r in records:
            all_rows.append({
                "timestamp": int(r["timestamp"]),
                "sumOpenInterest": float(r["openInterestAmount"]),
                "sumOpenInterestValue": float(r["openInterestValue"]),
            })

        last_ts = records[-1]["timestamp"]
        if since is not None and last_ts <= since:
            break
        since = last_ts + 1

        if len(records) < limit:
            break

        time.sleep(0.2)  # rate limit courtesy

    if not all_rows:
        return pl.DataFrame({
            "timestamp": [], "sumOpenInterest": [], "sumOpenInterestValue": []
        }).cast({
            "timestamp": pl.Int64,
            "sumOpenInterest": pl.Float64,
            "sumOpenInterestValue": pl.Float64,
        })

    return pl.DataFrame(all_rows).unique(subset=["timestamp"]).sort("timestamp")


def _load_existing(path: Path, schema_cols: list) -> pl.DataFrame:
    """Load existing parquet if it exists, return empty DataFrame otherwise."""
    if path.exists():
        try:
            return pl.read_parquet(path)
        except Exception:
            pass
    return None


def _save_merged(new_df: pl.DataFrame, path: Path, key: str = "timestamp") -> int:
    """Merge new data with existing parquet (append + dedup). Returns total rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _load_existing(path, new_df.columns)
    if existing is not None and len(existing) > 0:
        combined = pl.concat([existing, new_df]).unique(subset=[key]).sort(key)
    else:
        combined = new_df.unique(subset=[key]).sort(key)
    combined.write_parquet(path)
    return len(combined)


def _normalize_ts_col(df):
    if 'timestamp' not in df.columns and 'open_time' in df.columns:
        df = df.rename({'open_time': 'timestamp'})
    return df


def merge_funding_to_1m(ohlcv_path: Path, funding_path: Path) -> Optional[np.ndarray]:
    """Forward-fill 8h funding rates to 1m OHLCV timestamps.
    Returns numpy array aligned to OHLCV timestamps."""
    if not funding_path.exists():
        return None

    ohlcv = _normalize_ts_col(pl.read_parquet(ohlcv_path))
    funding = pl.read_parquet(funding_path)

    if len(funding) == 0:
        return None

    # Use asof join to forward-fill funding to 1m bars
    ohlcv_ts = ohlcv.select("timestamp").sort("timestamp")
    funding_sel = funding.select([
        pl.col("timestamp"),
        pl.col("fundingRate"),
    ]).sort("timestamp")

    joined = ohlcv_ts.join_asof(funding_sel, on="timestamp", strategy="backward")
    result = joined["fundingRate"].fill_null(0.0).to_numpy().astype(np.float64)
    return result


def merge_oi_to_1m(ohlcv_path: Path, oi_path: Path) -> Optional[np.ndarray]:
    """Forward-fill 5min OI to 1m OHLCV timestamps.
    Returns numpy array aligned to OHLCV timestamps."""
    if not oi_path.exists():
        return None

    ohlcv = _normalize_ts_col(pl.read_parquet(ohlcv_path))
    oi = pl.read_parquet(oi_path)

    if len(oi) == 0:
        return None

    ohlcv_ts = ohlcv.select("timestamp").sort("timestamp")
    oi_sel = oi.select([
        pl.col("timestamp"),
        pl.col("sumOpenInterest").alias("oi"),
    ]).sort("timestamp")

    joined = ohlcv_ts.join_asof(oi_sel, on="timestamp", strategy="backward")
    result = joined["oi"].fill_null(0.0).to_numpy().astype(np.float64)
    return result


async def collect_symbol(symbol: str) -> dict:
    """Download funding + OI for a single symbol. Returns stats dict."""
    log.info(f"Collecting {symbol}...")

    # Check existing data to set start time
    funding_path = FUNDING_DIR / f"{symbol}.parquet"
    oi_path = OI_DIR / f"{symbol}.parquet"

    # Funding rate
    funding_since = None
    if funding_path.exists():
        existing = pl.read_parquet(funding_path)
        if len(existing) > 0:
            funding_since = int(existing["timestamp"].max()) + 1

    funding_df = await fetch_funding_rate(symbol, funding_since)
    funding_total = 0
    if len(funding_df) > 0:
        funding_total = _save_merged(funding_df, funding_path)
    elif funding_path.exists():
        funding_total = len(pl.read_parquet(funding_path))
    log.info(f"  {symbol} funding: {len(funding_df)} new, {funding_total} total")

    # Open Interest
    oi_since = None
    if oi_path.exists():
        existing = pl.read_parquet(oi_path)
        if len(existing) > 0:
            oi_since = int(existing["timestamp"].max()) + 1

    oi_df = await fetch_open_interest(symbol, oi_since)
    oi_total = 0
    if len(oi_df) > 0:
        oi_total = _save_merged(oi_df, oi_path)
    elif oi_path.exists():
        oi_total = len(pl.read_parquet(oi_path))
    log.info(f"  {symbol} OI: {len(oi_df)} new, {oi_total} total")

    return {
        "symbol": symbol,
        "funding_new": len(funding_df),
        "funding_total": funding_total,
        "oi_new": len(oi_df),
        "oi_total": oi_total,
    }


async def collect_all(symbols: Optional[List[str]] = None):
    """Collect funding + OI for all symbols sequentially (API rate limits)."""
    symbols = symbols or DEFAULT_SYMBOLS
    results = []
    for sym in symbols:
        try:
            r = await collect_symbol(sym)
            results.append(r)
        except Exception as e:
            log.error(f"Failed {sym}: {e}")
            results.append({"symbol": sym, "error": str(e)})
    return results


if __name__ == "__main__":
    symbols = sys.argv[1:] if len(sys.argv) > 1 else None
    results = asyncio.run(collect_all(symbols))
    for r in results:
        log.info(f"Result: {r}")
