"""Test: Measure look-ahead bias impact on champion WR.

Compares:
1. Full-sample normalization (old, biased)
2. Causal half-split normalization (new, unbiased)

For N random champions from DB, recomputes WR both ways and reports difference.
"""
import sys, os, json, asyncio, random
sys.path.insert(0, '/home/j13/j13-ops')
sys.path.insert(0, '/home/j13/j13-ops/zangetsu/indicator_engine/target/release')
os.chdir('/home/j13/j13-ops')

import numpy as np
import polars as pl
import asyncpg

try:
    import zangetsu_indicators as zi
    RUST = True
except ImportError:
    RUST = False
    print("WARN: Rust engine not available, using zeros")

from zangetsu.config.settings import Settings
from zangetsu.config.cost_model import CostModel
from zangetsu.engine.components.backtester import Backtester, BacktestResult
from zangetsu.engine.components.signal_utils import generate_threshold_signals


def extract_symbol(indicator_hash: str) -> str:
    SYMBOLS = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","DOGEUSDT",
               "LINKUSDT","AAVEUSDT","AVAXUSDT","DOTUSDT","FILUSDT",
               "1000PEPEUSDT","1000SHIBUSDT","GALAUSDT"]
    for sym in SYMBOLS:
        if indicator_hash.endswith(sym):
            return sym
    parts = indicator_hash.split("_")
    return parts[-1] if parts else indicator_hash


def compute_signals(configs, close, high, low, volume, medians, mads):
    """Compute normalized matrix and generate signals."""
    arrays = []
    for cfg in configs:
        name = cfg["name"]
        period = cfg.get("period", 14)
        try:
            if RUST:
                vals = zi.compute(name, {"period": period}, close, high, low, volume)
            else:
                vals = np.zeros(len(close))
            arrays.append(np.asarray(vals, dtype=np.float64))
        except Exception:
            arrays.append(np.zeros(len(close), dtype=np.float64))

    if not arrays:
        return None, None

    matrix = np.column_stack(arrays)
    med = np.array(medians, dtype=np.float64)
    mad = np.array(mads, dtype=np.float64)
    if med.shape[0] != matrix.shape[1]:
        return None, None
    mad[mad == 0] = 1e-12
    norm = np.clip((matrix - med) / mad, -5, 5)

    names = [cfg["name"] for cfg in configs]
    ind_arrays = [norm[:, j] for j in range(norm.shape[1])]
    signals, agreements = generate_threshold_signals(
        names, ind_arrays, 0.60, 0.30, 60, 60
    )
    return signals, agreements


async def main():
    settings = Settings()
    cost_model = CostModel()

    class C:
        backtest_chunk_size=10000; backtest_gpu_enabled=False; backtest_gpu_batch_size=64
    backtester = Backtester(C())

    db = await asyncpg.connect(
        host=settings.db_host, port=settings.db_port,
        database='zangetsu', user=settings.db_user,
        password=settings.db_password,
    )

    # Load data
    data_cache = {}
    for sym in settings.symbols:
        try:
            df = pl.read_parquet(f"/home/j13/j13-ops/zangetsu/data/ohlcv/{sym}.parquet")
            w = min(200000, len(df))
            data_cache[sym] = {
                "close": df["close"].to_numpy()[-w:].astype(np.float64),
                "high": df["high"].to_numpy()[-w:].astype(np.float64),
                "low": df["low"].to_numpy()[-w:].astype(np.float64),
                "volume": df["volume"].to_numpy()[-w:].astype(np.float64),
            }
        except Exception as e:
            print(f"Skip {sym}: {e}")

    # Pick 20 random champions from DB
    rows = await db.fetch("""
        SELECT id, indicator_hash, passport, arena1_win_rate
        FROM champion_pipeline
        WHERE status IN ('ARENA1_COMPLETE','ARENA2_REJECTED','ARENA4_ELIMINATED','DEPLOYABLE','EVOLVED')
        ORDER BY RANDOM()
        LIMIT 20
    """)

    print(f"\n{'='*80}")
    print(f"LOOK-AHEAD BIAS TEST — {len(rows)} champions")
    print(f"{'='*80}")
    print(f"{'ID':>6} | {'Symbol':>14} | {'Full WR':>8} | {'Causal WR':>10} | {'Delta':>7} | {'Full Trades':>11} | {'Causal Trades':>13}")
    print(f"{'-'*6}-+-{'-'*14}-+-{'-'*8}-+-{'-'*10}-+-{'-'*7}-+-{'-'*11}-+-{'-'*13}")

    full_wrs = []
    causal_wrs = []
    deltas = []

    for row in rows:
        cid = row["id"]
        ihash = row["indicator_hash"]
        passport = json.loads(row["passport"]) if isinstance(row["passport"], str) else row["passport"]
        a1 = passport.get("arena1", {})
        configs = a1.get("configs", [])

        symbol = extract_symbol(ihash)
        if symbol not in data_cache or not configs:
            continue

        d = data_cache[symbol]
        close, high, low, volume = d["close"], d["high"], d["low"], d["volume"]
        cost_bps = cost_model.get(symbol).total_round_trip_bps

        # Recompute raw indicator arrays
        arrays = []
        for cfg in configs:
            name = cfg["name"]
            period = cfg.get("period", 14)
            try:
                if RUST:
                    vals = zi.compute(name, {"period": period}, close, high, low, volume)
                else:
                    vals = np.zeros(len(close))
                arrays.append(np.asarray(vals, dtype=np.float64))
            except Exception:
                arrays.append(np.zeros(len(close), dtype=np.float64))

        if len(arrays) < 2:
            continue

        matrix = np.column_stack(arrays)

        # Method 1: Full-sample (biased)
        full_med = np.median(matrix, axis=0)
        full_mad = np.median(np.abs(matrix - full_med), axis=0) * 1.4826
        full_mad[full_mad == 0] = 1e-12

        signals_full, _ = compute_signals(configs, close, high, low, volume,
                                          full_med.tolist(), full_mad.tolist())
        if signals_full is None:
            continue
        bt_full = backtester.run(signals_full, close, symbol, cost_bps, 480, high=high, low=low)

        # Method 2: Causal half-split (unbiased)
        half = max(1, len(matrix) // 2)
        train = matrix[:half]
        causal_med = np.median(train, axis=0)
        causal_mad = np.median(np.abs(train - causal_med), axis=0) * 1.4826
        causal_mad[causal_mad == 0] = 1e-12

        signals_causal, _ = compute_signals(configs, close, high, low, volume,
                                            causal_med.tolist(), causal_mad.tolist())
        if signals_causal is None:
            continue
        bt_causal = backtester.run(signals_causal, close, symbol, cost_bps, 480, high=high, low=low)

        full_wr = bt_full.win_rate
        causal_wr = bt_causal.win_rate
        delta = causal_wr - full_wr

        full_wrs.append(full_wr)
        causal_wrs.append(causal_wr)
        deltas.append(delta)

        print(f"{cid:>6} | {symbol:>14} | {full_wr:>8.4f} | {causal_wr:>10.4f} | {delta:>+7.4f} | {bt_full.total_trades:>11} | {bt_causal.total_trades:>13}")

    if deltas:
        print(f"\n{'='*80}")
        print(f"SUMMARY ({len(deltas)} champions tested)")
        print(f"{'='*80}")
        print(f"  Mean full-sample WR:  {np.mean(full_wrs):.4f}")
        print(f"  Mean causal WR:       {np.mean(causal_wrs):.4f}")
        print(f"  Mean delta:           {np.mean(deltas):+.4f}")
        print(f"  Median delta:         {np.median(deltas):+.4f}")
        print(f"  Max degradation:      {min(deltas):+.4f}")
        print(f"  Max improvement:      {max(deltas):+.4f}")
        print(f"  Champions degraded:   {sum(1 for d in deltas if d < -0.001)}/{len(deltas)}")
        print(f"  Champions improved:   {sum(1 for d in deltas if d > 0.001)}/{len(deltas)}")
        print(f"  Champions unchanged:  {sum(1 for d in deltas if abs(d) <= 0.001)}/{len(deltas)}")
        
        if np.mean(deltas) > -0.02:
            print(f"\n  VERDICT: Look-ahead bias impact is SMALL (mean delta {np.mean(deltas):+.4f})")
            print(f"  Causal normalization is safe to deploy.")
        else:
            print(f"\n  VERDICT: Look-ahead bias impact is SIGNIFICANT (mean delta {np.mean(deltas):+.4f})")
            print(f"  Many existing champions may have inflated WR from look-ahead.")
    else:
        print("\nNo valid champions found for testing.")

    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
