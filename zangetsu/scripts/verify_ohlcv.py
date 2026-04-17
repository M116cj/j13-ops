#!/usr/bin/env python3
"""Verify OHLCV backfill results."""
import polars as pl
import os
from datetime import datetime

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "DOGEUSDT",
    "LINKUSDT", "AAVEUSDT", "AVAXUSDT", "DOTUSDT", "FILUSDT",
    "1000PEPEUSDT", "1000SHIBUSDT", "GALAUSDT",
]

ohlcv_dir = '/home/j13/j13-ops/zangetsu/data/ohlcv'
required = {'timestamp', 'open', 'high', 'low', 'close', 'volume'}

print("=" * 80)
print("ZANGETSU V5 — OHLCV Verification")
print("=" * 80)
print(f"{'Symbol':<16} {'Bars':>12} {'Start':>12} {'End':>12} {'Size MB':>8} {'Schema':>8}")
print("-" * 80)

total_bars = 0
total_size = 0
all_ok = True

for sym in SYMBOLS:
    fpath = os.path.join(ohlcv_dir, f"{sym}.parquet")
    if not os.path.exists(fpath):
        print(f"{sym:<16} {'MISSING':>12}")
        all_ok = False
        continue
    
    df = pl.read_parquet(fpath)
    cols = set(df.columns)
    schema_ok = cols == required
    size_mb = os.path.getsize(fpath) / 1024 / 1024
    
    first = datetime.fromtimestamp(df['timestamp'][0] / 1000)
    last = datetime.fromtimestamp(df['timestamp'][-1] / 1000)
    
    total_bars += len(df)
    total_size += size_mb
    
    status = "OK" if schema_ok else "FAIL"
    if not schema_ok:
        all_ok = False
    
    print(f"{sym:<16} {len(df):>12,} {str(first.date()):>12} {str(last.date()):>12} {size_mb:>7.1f} {status:>8}")

print("-" * 80)
print(f"{'TOTAL':<16} {total_bars:>12,} {'':>12} {'':>12} {total_size:>7.1f}")
print(f"\nAll schemas OK: {all_ok}")
print(f"Files present: {sum(1 for s in SYMBOLS if os.path.exists(os.path.join(ohlcv_dir, f'{s}.parquet')))}/{len(SYMBOLS)}")
