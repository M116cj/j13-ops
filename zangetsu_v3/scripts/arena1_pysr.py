#!/usr/bin/env python3
"""Arena 1: PySR symbolic regression search for predictive OHLCV expressions.

Input:  per-regime TRAIN segments (1m OHLCV)
Target: next_N_bar_return (N=3,5,10)
Output: top 50 candidate expressions per regime as JSON AST

Constraint: expression max lookback ≤ 10 bars (HFT)
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import os
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import polars as pl
import psycopg2
from pysr import PySRRegressor

from zangetsu_v3.regime.rule_labeler import label_symbol, Regime, REGIME_NAMES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("arena1")


_env_end = os.environ.get("ZV3_TRAINING_END")
TRAINING_END = datetime.fromisoformat(_env_end) if _env_end else datetime.now(timezone.utc) - timedelta(hours=1)

DB_DSN = os.environ.get("ZV3_DB_DSN", "dbname=zangetsu user=zangetsu host=127.0.0.1 port=5432")
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
TRAINING_MONTHS = 18
MIN_SEGMENT_BARS = 1440
OUTPUT_DIR = Path("arena1_results")


def load_ohlcv(symbol: str) -> pl.DataFrame:
    end_ms = int(TRAINING_END.timestamp() * 1000)
    start_ms = int((TRAINING_END - timedelta(days=30 * TRAINING_MONTHS)).timestamp() * 1000)
    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT timestamp, open, high, low, close, volume FROM ohlcv_1m "
                "WHERE symbol = %s AND timestamp >= %s AND timestamp <= %s ORDER BY timestamp",
                (symbol, start_ms, end_ms),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    df = pl.DataFrame(rows, schema=["ts_ms", "open", "high", "low", "close", "volume"], orient="row")
    return df.with_columns(
        pl.from_epoch(pl.col("ts_ms"), time_unit="ms").alias("timestamp"),
        pl.col("open").cast(pl.Float64), pl.col("high").cast(pl.Float64),
        pl.col("low").cast(pl.Float64), pl.col("close").cast(pl.Float64),
        pl.col("volume").cast(pl.Float64),
    ).drop("ts_ms").sort("timestamp")


def build_features_and_target(segments: list[np.ndarray], target_horizon: int = 5) -> tuple[np.ndarray, np.ndarray]:
    """Build feature matrix (lookback ≤ 10 bars) and target from segments.

    Features per bar (all lookback ≤ 10):
      - ret_1..ret_10: past N-bar returns
      - range_1..range_5: (high-low)/close for past N bars
      - vol_ratio_1..vol_5: volume / rolling_mean(volume, 5)
      - hl_pos: (close - low) / (high - low)  intrabar position
      - body: (close - open) / (high - low + 1e-12)  candle body ratio

    Target: future N-bar return (close[i+N] - close[i]) / close[i]
    """
    all_X = []
    all_y = []

    for seg_ohlcv in segments:
        o = seg_ohlcv[:, 0]  # open
        h = seg_ohlcv[:, 1]  # high
        l = seg_ohlcv[:, 2]  # low
        c = seg_ohlcv[:, 3]  # close
        v = seg_ohlcv[:, 4]  # volume
        n = len(c)

        if n < 20 + target_horizon:
            continue

        # Pre-compute rolling features
        features = []
        names = []

        # Past returns (1-10 bars)
        for lag in range(1, 11):
            ret = np.zeros(n)
            ret[lag:] = (c[lag:] - c[:-lag]) / (c[:-lag] + 1e-12)
            features.append(ret)
            names.append(f"ret_{lag}")

        # Range (1-5 bars)
        for lag in range(1, 6):
            rng = np.zeros(n)
            for i in range(lag, n):
                rng[i] = (np.max(h[i - lag:i + 1]) - np.min(l[i - lag:i + 1])) / (c[i] + 1e-12)
            features.append(rng)
            names.append(f"range_{lag}")

        # Volume ratio (vs 5-bar MA)
        vol_ma5 = np.convolve(v, np.ones(5) / 5, mode='same')
        vol_ratio = v / (vol_ma5 + 1e-12)
        features.append(vol_ratio)
        names.append("vol_ratio")

        # Intrabar position
        hl_pos = (c - l) / (h - l + 1e-12)
        features.append(hl_pos)
        names.append("hl_pos")

        # Candle body
        body = (c - o) / (h - l + 1e-12)
        features.append(body)
        names.append("body")

        X = np.column_stack(features)

        # Target: future return
        y = np.zeros(n)
        y[:-target_horizon] = (c[target_horizon:] - c[:-target_horizon]) / (c[:-target_horizon] + 1e-12)

        # Only use bars where all features are valid (skip first 10)
        valid_start = 10
        valid_end = n - target_horizon
        if valid_end <= valid_start:
            continue

        all_X.append(X[valid_start:valid_end])
        all_y.append(y[valid_start:valid_end])

    if not all_X:
        return np.empty((0, 0)), np.empty(0)

    return np.vstack(all_X), np.concatenate(all_y)


def extract_regime_segments(regime_id: int) -> list[np.ndarray]:
    """Extract OHLCV segments for a regime across all symbols."""
    segments = []
    for sym in SYMBOLS:
        raw = load_ohlcv(sym)
        labels_1m, _, _ = label_symbol(raw)

        # Find continuous runs of this regime
        mask = (labels_1m == regime_id)
        diffs = np.diff(mask.astype(int))
        starts = list(np.where(diffs == 1)[0] + 1)
        ends = list(np.where(diffs == -1)[0] + 1)
        if mask[0]:
            starts = [0] + starts
        if mask[-1]:
            ends = ends + [len(labels_1m)]

        ohlcv_np = raw.select(["open", "high", "low", "close", "volume"]).to_numpy()

        for s, e in zip(starts, ends):
            if e - s >= MIN_SEGMENT_BARS:
                # Normalize price to relative scale (divide by first close)
                seg = ohlcv_np[s:e].copy().astype(np.float64)
                base_price = seg[0, 3]  # first close
                seg[:, :4] /= base_price  # normalize OHLC
                seg[:, 4] /= (np.mean(seg[:, 4]) + 1e-12)  # normalize volume
                segments.append(seg)

    return segments


def run_pysr(X: np.ndarray, y: np.ndarray, regime_name: str, max_expressions: int = 50) -> PySRRegressor:
    """Run PySR symbolic regression."""
    log.info(f"  PySR: X={X.shape}, y={y.shape}")

    # Subsample if too large (PySR gets slow beyond ~50K rows)
    max_rows = 50000
    if len(X) > max_rows:
        rng = np.random.default_rng(42)
        idx = rng.choice(len(X), max_rows, replace=False)
        X = X[idx]
        y = y[idx]
        log.info(f"  Subsampled to {max_rows} rows")

    feature_names = (
        [f"ret_{i}" for i in range(1, 11)] +
        [f"range_{i}" for i in range(1, 6)] +
        ["vol_ratio", "hl_pos", "body"]
    )

    model = PySRRegressor(
        niterations=200,
        binary_operators=["+", "-", "*", "/"],
        unary_operators=["abs", "square"],
        extra_sympy_mappings={"square": lambda x: x**2},
        maxsize=15,
        maxdepth=5,
        populations=30,
        population_size=50,
        ncycles_per_iteration=300,
        parsimony=0.003,
        weight_mutate_constant=0.1,
        weight_mutate_operator=0.5,
        weight_add_node=0.3,
        weight_delete_node=0.3,
        deterministic=False,
        procs=4,
        multithreading=True,
        progress=False,
        verbosity=0,
        temp_equation_file=True,
    )

    model.fit(X, y, variable_names=feature_names)
    return model


def extract_results(model: PySRRegressor, regime_name: str) -> list[dict]:
    """Extract top expressions from PySR results."""
    results = []
    equations = model.equations_
    if equations is None or len(equations) == 0:
        return results

    for _, row in equations.iterrows():
        results.append({
            "expression": str(row.get("equation", row.get("sympy_format", "?"))),
            "complexity": int(row.get("complexity", 0)),
            "loss": float(row.get("loss", 0)),
            "score": float(row.get("score", 0)),
        })

    # Sort by score (higher = better improvement per complexity)
    results.sort(key=lambda x: -x["score"])
    return results[:50]


def main():
    log.info("Arena 1 — PySR Symbolic Regression Search")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Pilot: BULL_TREND only
    regime_id = Regime.BULL_TREND
    regime_name = REGIME_NAMES[regime_id]
    log.info(f"\nRegime: {regime_name}")

    # Extract segments
    t0 = time.monotonic()
    segments = extract_regime_segments(regime_id)
    log.info(f"  Extracted {len(segments)} segments")

    # Build features + target for multiple horizons
    for horizon in [5]:  # Start with 5-bar
        log.info(f"\n  Target: next_{horizon}_bar_return")
        X, y = build_features_and_target(segments, target_horizon=horizon)
        if len(X) == 0:
            log.warning(f"  No valid data for horizon={horizon}")
            continue

        log.info(f"  Data: {X.shape[0]} samples, {X.shape[1]} features")
        log.info(f"  Target stats: mean={y.mean():.6f}, std={y.std():.6f}")

        # Run PySR
        t1 = time.monotonic()
        model = run_pysr(X, y, regime_name)
        search_time = time.monotonic() - t1
        log.info(f"  PySR completed in {search_time:.0f}s")

        # Extract results
        top_exprs = extract_results(model, regime_name)
        log.info(f"  Top {len(top_exprs)} expressions:")
        for i, expr in enumerate(top_exprs[:10]):
            log.info(f"    #{i+1}: score={expr['score']:.6f} loss={expr['loss']:.8f} "
                     f"complexity={expr['complexity']} | {expr['expression']}")

        # Save
        out_file = OUTPUT_DIR / f"{regime_name}_h{horizon}.json"
        with out_file.open("w") as f:
            json.dump({
                "regime": regime_name,
                "horizon": horizon,
                "n_segments": len(segments),
                "n_samples": len(X),
                "search_time_s": search_time,
                "expressions": top_exprs,
            }, f, indent=2)
        log.info(f"  Saved: {out_file}")

    total = time.monotonic() - t0
    log.info(f"\nTotal time: {total:.0f}s")


if __name__ == "__main__":
    main()
