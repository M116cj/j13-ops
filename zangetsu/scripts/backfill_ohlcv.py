#!/usr/bin/env python3
"""Backfill historical 1m OHLCV from Binance Futures REST API to Parquet.
Uses weight-aware rate limiting: 2400 weight/min limit, each kline request = 5 weight.
Conservative: stay under 1200 weight/min = 240 requests/min = 4 req/sec.
"""

import asyncio
import aiohttp
import polars as pl
import time
import os
from pathlib import Path
from datetime import datetime

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "DOGEUSDT",
    "LINKUSDT", "AAVEUSDT", "AVAXUSDT", "DOTUSDT", "FILUSDT",
    "1000PEPEUSDT", "1000SHIBUSDT", "GALAUSDT", "XRPUSDT",
]

OUTPUT_DIR = Path("/home/j13/j13-ops/zangetsu/data/ohlcv")
BINANCE_URL = "https://fapi.binance.com/fapi/v1/klines"
INTERVAL = "1m"
LIMIT = 1500
RATE_LIMIT_DELAY = 0.3  # 300ms = ~200 req/min = ~1000 weight/min (safe)

SYMBOL_START = {
    "BTCUSDT":      1568764800000,
    "ETHUSDT":      1568764800000,
    "BNBUSDT":      1580515200000,
    "SOLUSDT":      1599696000000,
    "DOGEUSDT":     1594252800000,
    "LINKUSDT":     1578528000000,
    "AAVEUSDT":     1602806400000,
    "AVAXUSDT":     1601510400000,
    "DOTUSDT":      1597881600000,
    "FILUSDT":      1602806400000,
    "1000PEPEUSDT": 1683590400000,
    "1000SHIBUSDT": 1620691200000,
    "GALAUSDT":     1637625600000,
    "XRPUSDT":      1568764800000,
}

async def fetch_klines(session, symbol, start_time, retries=3):
    params = {"symbol": symbol, "interval": INTERVAL, "limit": LIMIT, "startTime": start_time}
    
    for attempt in range(retries):
        try:
            async with session.get(BINANCE_URL, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", "60"))
                    print(f"  429 rate limited, sleeping {retry_after}s...")
                    await asyncio.sleep(retry_after)
                    continue
                if resp.status == 418:
                    print(f"  418 IP ban, sleeping 120s...")
                    await asyncio.sleep(120)
                    continue
                data = await resp.json()
                if isinstance(data, dict) and "code" in data:
                    print(f"  API error: {data}")
                    if data.get("code") == -1003:  # rate limit
                        await asyncio.sleep(60)
                        continue
                    return []
                return data
        except Exception as e:
            if attempt < retries - 1:
                await asyncio.sleep(5)
            else:
                print(f"  Failed after {retries} retries: {e}")
                return []
    return []

async def backfill_symbol(session, symbol):
    print(f"\n[{symbol}] Starting backfill...")
    
    # Check if existing file has data we can resume from
    output_path = OUTPUT_DIR / f"{symbol}.parquet"
    existing_bars = 0
    start_time = SYMBOL_START.get(symbol, 1568764800000)
    
    if output_path.exists():
        try:
            existing = pl.read_parquet(str(output_path))
            if len(existing) > 1500:  # has real historical data
                last_ts = existing["timestamp"].max()
                start_time = last_ts + 60000
                existing_bars = len(existing)
                dt = datetime.fromtimestamp(last_ts / 1000)
                print(f"  [{symbol}] Resuming from {dt.strftime('%Y-%m-%d %H:%M')}, {existing_bars:,} existing bars")
        except:
            pass
    
    all_bars = []
    now_ms = int(time.time() * 1000)
    request_count = 0
    
    while start_time < now_ms:
        bars = await fetch_klines(session, symbol, start_time=start_time)
        if not bars:
            break
        
        all_bars.extend(bars)
        request_count += 1
        
        if request_count % 100 == 0:
            bars_count = len(all_bars)
            latest_ts = bars[-1][0]
            dt = datetime.fromtimestamp(latest_ts / 1000)
            print(f"  [{symbol}] {bars_count:,} new bars, up to {dt.strftime('%Y-%m-%d %H:%M')}, {request_count} reqs")
        
        last_ts = bars[-1][0]
        start_time = last_ts + 60000
        
        if len(bars) < LIMIT:
            break
        
        await asyncio.sleep(RATE_LIMIT_DELAY)
    
    if not all_bars and existing_bars == 0:
        print(f"  [{symbol}] No data available!")
        return 0
    
    # Build new dataframe from fetched bars
    if all_bars:
        new_df = pl.DataFrame({
            "timestamp": [int(b[0]) for b in all_bars],
            "open": [float(b[1]) for b in all_bars],
            "high": [float(b[2]) for b in all_bars],
            "low": [float(b[3]) for b in all_bars],
            "close": [float(b[4]) for b in all_bars],
            "volume": [float(b[5]) for b in all_bars],
        })
        
        # Merge with existing if resuming
        if existing_bars > 0:
            existing = pl.read_parquet(str(output_path))
            df = pl.concat([existing, new_df])
        else:
            df = new_df
    else:
        df = pl.read_parquet(str(output_path))
    
    df = df.unique(subset=["timestamp"]).sort("timestamp")
    df.write_parquet(str(output_path), compression="snappy")
    
    size_mb = output_path.stat().st_size / 1024 / 1024
    first_dt = datetime.fromtimestamp(df["timestamp"][0] / 1000)
    last_dt = datetime.fromtimestamp(df["timestamp"][-1] / 1000)
    
    print(f"  [{symbol}] DONE: {len(df):,} bars, {first_dt.date()} to {last_dt.date()}, {size_mb:.1f} MB, {request_count} reqs")
    return len(df)

async def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("ZANGETSU V5 — OHLCV Backfill (v3 - safe rate limit)")
    print(f"Symbols: {len(SYMBOLS)}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Rate: {1/RATE_LIMIT_DELAY:.0f} req/sec ({1/RATE_LIMIT_DELAY*5:.0f} weight/min)")
    print("=" * 60)
    
    t0 = time.time()
    total_bars = 0
    
    async with aiohttp.ClientSession() as session:
        for symbol in SYMBOLS:
            bars = await backfill_symbol(session, symbol)
            total_bars += bars
    
    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"COMPLETE: {total_bars:,} total bars across {len(SYMBOLS)} symbols")
    print(f"Time: {elapsed/60:.1f} minutes")
    print(f"{'=' * 60}")

if __name__ == "__main__":
    asyncio.run(main())
