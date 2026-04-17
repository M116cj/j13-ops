"""Fetch Binance Futures funding rate and open interest history → parquet.

Usage:
    python fetch_funding_oi.py [--symbols BTCUSDT ETHUSDT] [--days 365]

Output:
    data/funding/{SYMBOL}.parquet   — columns: timestamp, fundingRate, fundingTime
    data/oi/{SYMBOL}.parquet        — columns: timestamp, sumOpenInterest, sumOpenInterestValue
"""
from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

import numpy as np
import polars as pl
import requests

BASE_DIR = Path("/home/j13/j13-ops/zangetsu_v5/data")
FUNDING_DIR = BASE_DIR / "funding"
OI_DIR = BASE_DIR / "oi"

FUNDING_URL = "https://fapi.binance.com/fapi/v1/fundingRate"
OI_URL = "https://fapi.binance.com/futures/data/openInterestHist"


def fetch_funding_rate(symbol: str, days: int = 365) -> pl.DataFrame:
    """Fetch historical funding rate. Max 1000 per request, paginate forward."""
    all_rows = []
    now_ms = int(time.time() * 1000)
    start_time = now_ms - days * 86400 * 1000

    while start_time < now_ms:
        params = {
            "symbol": symbol,
            "limit": 1000,
            "startTime": start_time,
        }
        resp = requests.get(FUNDING_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break

        all_rows.extend(data)
        latest = max(d["fundingTime"] for d in data)
        if len(data) < 1000:
            break  # no more pages
        start_time = latest + 1
        time.sleep(0.2)  # rate limit courtesy

    if not all_rows:
        return pl.DataFrame({"timestamp": [], "fundingRate": [], "fundingTime": []})

    df = pl.DataFrame(all_rows)
    df = df.select([
        pl.col("fundingTime").alias("timestamp"),
        pl.col("fundingRate").cast(pl.Float64),
        pl.col("fundingTime"),
    ]).sort("timestamp").unique(subset=["timestamp"])

    return df


def fetch_open_interest(symbol: str, days: int = 30) -> pl.DataFrame:
    """Fetch historical open interest (5m period). Max 500 per request.
    Note: Binance OI history API only provides ~30 days of 5m data."""
    all_rows = []
    now_ms = int(time.time() * 1000)
    start_time = now_ms - days * 86400 * 1000
    period = "5m"

    while start_time < now_ms:
        params = {
            "symbol": symbol,
            "period": period,
            "limit": 500,
            "startTime": start_time,
        }
        resp = requests.get(OI_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break

        all_rows.extend(data)
        latest = max(d["timestamp"] for d in data)
        if len(data) < 500:
            break
        start_time = latest + 1
        time.sleep(0.3)

    if not all_rows:
        return pl.DataFrame({
            "timestamp": [], "sumOpenInterest": [], "sumOpenInterestValue": []
        })

    df = pl.DataFrame(all_rows)
    df = df.select([
        pl.col("timestamp").cast(pl.Int64),
        pl.col("sumOpenInterest").cast(pl.Float64),
        pl.col("sumOpenInterestValue").cast(pl.Float64),
    ]).sort("timestamp").unique(subset=["timestamp"])

    return df


def main():
    parser = argparse.ArgumentParser(description="Fetch Binance funding rate and OI")
    parser.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    parser.add_argument("--days", type=int, default=365)
    args = parser.parse_args()

    FUNDING_DIR.mkdir(parents=True, exist_ok=True)
    OI_DIR.mkdir(parents=True, exist_ok=True)

    for sym in args.symbols:
        print(f"[{sym}] Fetching funding rate...")
        try:
            df_fund = fetch_funding_rate(sym, args.days)
            out_path = FUNDING_DIR / f"{sym}.parquet"
            # Merge-append: preserve existing history
            if out_path.exists():
                old = pl.read_parquet(str(out_path))
                df_fund = pl.concat([old, df_fund]).unique(subset=['timestamp']).sort('timestamp')
            df_fund.write_parquet(str(out_path))
            print(f"  → {out_path} ({len(df_fund)} rows)")
        except Exception as e:
            print(f"  ✗ Funding rate failed: {e}")

        print(f"[{sym}] Fetching open interest...")
        try:
            df_oi = fetch_open_interest(sym, args.days)
            out_path = OI_DIR / f"{sym}.parquet"
            # Merge-append: preserve existing history
            if out_path.exists():
                old = pl.read_parquet(str(out_path))
                df_oi = pl.concat([old, df_oi]).unique(subset=['timestamp']).sort('timestamp')
            df_oi.write_parquet(str(out_path))
            print(f"  → {out_path} ({len(df_oi)} rows)")
        except Exception as e:
            print(f"  ✗ Open interest failed: {e}")


if __name__ == "__main__":
    main()
