#!/bin/bash
# Zangetsu V5 — Daily data collection (OHLCV + Funding + OI)
# Run via cron every 6 hours to accumulate OI history
cd /home/j13/j13-ops/zangetsu_v5
VENV=.venv/bin/python3
LOG=/tmp/daily_data_collect.log
ALLSYMS="BTCUSDT ETHUSDT SOLUSDT BNBUSDT XRPUSDT DOGEUSDT LINKUSDT AAVEUSDT AVAXUSDT DOTUSDT FILUSDT 1000PEPEUSDT 1000SHIBUSDT GALAUSDT"

echo "[$(date)] Starting daily data collection" >> $LOG

# OHLCV incremental update
$VENV scripts/backfill_ohlcv.py >> $LOG 2>&1

# Funding rate (7-day lookback) + OI (30-day window, merge with existing)
$VENV scripts/fetch_funding_oi.py --symbols $ALLSYMS --days 7 >> $LOG 2>&1

# OI dedicated pass — merge-append to accumulate history
$VENV -c "
from scripts.fetch_funding_oi import fetch_open_interest
from pathlib import Path
import polars as pl
OI_DIR = Path('data/oi')
for s in '$ALLSYMS'.split():
    try:
        df = fetch_open_interest(s, days=30)
        out = OI_DIR / f'{s}.parquet'
        if out.exists():
            old = pl.read_parquet(str(out))
            df = pl.concat([old, df]).unique(subset=['timestamp']).sort('timestamp')
        df.write_parquet(str(out))
        print(f'{s}: {len(df)} recs')
    except Exception as e:
        print(f'{s}: FAIL {e}')
" >> $LOG 2>&1

echo "[$(date)] Done" >> $LOG
