"""V9 Alpha Discovery — parallel service using GP to discover new alpha formulas.

Runs independently of A1 main loop. Every N minutes, samples a symbol/regime,
runs GP evolution for M generations, stores discovered alphas in DB with
engine_hash='zv5_v10_alpha', card_status='DISCOVERED'.

These discovered alphas are:
- NOT used by A1 random sampling (they're formulas, not indicator combos)
- NOT entered into ELO rotation (card_status filter)
- Available for future integration into signal generation
"""
from __future__ import annotations

import sys
sys.path.insert(0, '/home/j13/j13-ops')

import asyncio
import json
import logging
import os
import random
from pathlib import Path

import asyncpg
import numpy as np
import polars as pl

from zangetsu.engine.components.alpha_engine import AlphaEngine, AlphaResult

log = logging.getLogger(__name__)

DSN = os.environ.get(
    "ZV5_DSN",
    "postgresql://zangetsu:9c424966bebb05a42966186bb22d7480@127.0.0.1:5432/zangetsu",
)
DATA_DIR = Path("/home/j13/j13-ops/zangetsu/data/ohlcv")
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]

# Quality gate — alphas below this |IC| are dropped before DB insert.
MIN_IC_THRESHOLD = 0.02


async def discover_alphas_for_symbol(
    sym: str,
    n_gen: int = 20,
    pop_size: int = 100,
    top_k: int = 3,
) -> int:
    """Run GP evolution for one symbol, store top-k alphas.

    Returns the number of alphas inserted. Returns 0 gracefully on any
    recoverable failure (missing parquet, empty data, DB/engine error).
    """
    path = DATA_DIR / f"{sym}.parquet"
    if not path.exists():
        log.warning(f"Data file missing for {sym}: {path}")
        return 0

    try:
        df = pl.read_parquet(str(path))
    except Exception as e:
        log.warning(f"Failed to read parquet for {sym}: {e}")
        return 0

    if df is None or len(df) < 1000:
        log.warning(f"Insufficient data for {sym}: rows={0 if df is None else len(df)}")
        return 0

    n = min(50000, len(df))
    try:
        close = df['close'].to_numpy()[-n:].astype(np.float32)
        high = df['high'].to_numpy()[-n:].astype(np.float32)
        low = df['low'].to_numpy()[-n:].astype(np.float32)
        volume = df['volume'].to_numpy()[-n:].astype(np.float32)
    except Exception as e:
        log.warning(f"Column extraction failed for {sym}: {e}")
        return 0

    returns = np.zeros_like(close)
    returns[1:] = (close[1:] - close[:-1]) / np.maximum(close[:-1], 1e-10)

    try:
        engine = AlphaEngine()
    except ImportError as e:
        log.error(f"AlphaEngine unavailable (DEAP missing?): {e}")
        return 0
    except Exception as e:
        log.error(f"AlphaEngine init failed: {e}")
        return 0

    log.info(f"Starting GP evolution for {sym}: {n_gen} gen, pop={pop_size}")
    try:
        results = engine.evolve(
            close, high, low, volume, returns,
            n_gen=n_gen, pop_size=pop_size, top_k=top_k,
        )
    except Exception as e:
        log.error(f"GP evolution crashed for {sym}: {e}")
        return 0

    if not results:
        log.info(f"No GP results for {sym}")
        return 0

    try:
        conn = await asyncpg.connect(DSN)
    except Exception as e:
        log.error(f"DB connect failed: {e}")
        return 0

    inserted = 0
    try:
        for alpha in results:
            if abs(alpha.ic) < MIN_IC_THRESHOLD:
                continue
            passport = {
                "alpha_expression": alpha.to_passport(),
                "discovery": {
                    "method": "gp_evolution",
                    "generation": n_gen,
                    "population": pop_size,
                    "symbol": sym,
                },
            }
            indicator_hash = f"alpha_{alpha.hash}_{sym}"
            try:
                await conn.execute(
                    """
                    INSERT INTO champion_pipeline (
                        regime, indicator_hash, alpha_hash, status, n_indicators,
                        arena1_score, arena1_win_rate, arena1_pnl, arena1_n_trades,
                        card_status, passport, engine_hash, evolution_operator,
                        created_at, updated_at
                    ) VALUES (
                        'DISCOVERED', $1, $4, 'ARENA1_READY', 1,
                        $2, 0.5, 0.0, 0,
                        'DISCOVERED', $3::jsonb, 'zv5_v10_alpha', 'gp_evolution',
                        NOW(), NOW()
                    )
                    
                    """,
                    indicator_hash,
                    float(abs(alpha.ic)),
                    json.dumps(passport),
                    alpha.hash,
                )
                inserted += 1
            except Exception as e:
                log.warning(f"Insert alpha failed ({indicator_hash}): {e}")
    finally:
        try:
            await conn.close()
        except Exception as e:
            log.debug(f"DB close failed: {e}")

    log.info(f"Inserted {inserted} alphas for {sym}")
    return inserted


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
    )
    sym = random.choice(SYMBOLS)
    try:
        total = await discover_alphas_for_symbol(sym, n_gen=15, pop_size=80, top_k=3)
    except Exception as e:
        log.error(f"Alpha discovery cycle crashed: {e}")
        total = 0
    print(f"Alpha discovery cycle complete: {total} new alphas for {sym}")


if __name__ == "__main__":
    asyncio.run(main())
