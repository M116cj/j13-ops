#!/usr/bin/env python3
"""Arena 1: Full PySR signal pool search. 11 regimes × 5 targets. No lookback limit.

PySR searches directly on OHLCV-derived features. It decides the best
mathematical expressions and lookback periods automatically.

Output: arena1_results/all_candidates.json (de-duplicated signal pool)
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import logging
import time
from datetime import datetime, timedelta, timezone

import numpy as np
import polars as pl
import psycopg2
from pysr import PySRRegressor

from zangetsu_v3.regime.rule_labeler import label_symbol, Regime, REGIME_NAMES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("arena1")

DB_DSN = "dbname=zangetsu user=zangetsu password=9c424966bebb05a42966186bb22d7480 host=127.0.0.1 port=5432"
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
TRAINING_MONTHS = 18
MIN_SEGMENT_BARS = 1440
OUTPUT_DIR = Path("arena1_results")

SEARCH_REGIMES = [
    Regime.BULL_TREND, Regime.BEAR_TREND, Regime.BULL_PULLBACK, Regime.BEAR_RALLY,
    Regime.TOPPING, Regime.BOTTOMING, Regime.CONSOLIDATION, Regime.SQUEEZE,
    Regime.CHOPPY_VOLATILE, Regime.DISTRIBUTION, Regime.ACCUMULATION,
]
TARGETS = [1, 3, 5, 10, 30]  # next_N_bar_return


def load_ohlcv(symbol: str) -> pl.DataFrame:
    end_ms = int(datetime(2026, 3, 29, tzinfo=timezone.utc).timestamp() * 1000)
    start_ms = int((datetime(2026, 3, 29, tzinfo=timezone.utc) - timedelta(days=30 * TRAINING_MONTHS)).timestamp() * 1000)
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


def extract_regime_segments(regime_id: int, all_data: dict) -> list[np.ndarray]:
    segments = []
    for sym, (raw, labels_1m) in all_data.items():
        mask = labels_1m == regime_id
        diffs = np.diff(mask.astype(int))
        starts = list(np.where(diffs == 1)[0] + 1)
        ends = list(np.where(diffs == -1)[0] + 1)
        if mask[0]: starts = [0] + starts
        if mask[-1]: ends = ends + [len(labels_1m)]
        ohlcv_np = raw.select(["open", "high", "low", "close", "volume"]).to_numpy().astype(np.float64)
        for s, e in zip(starts, ends):
            if e - s >= MIN_SEGMENT_BARS:
                seg = ohlcv_np[s:e].copy()
                bp = seg[0, 3]
                if bp > 0: seg[:, :4] /= bp
                vm = np.mean(seg[:, 4])
                if vm > 0: seg[:, 4] /= vm
                segments.append(seg)
    return segments


def build_features_and_target(segments: list[np.ndarray], target_horizon: int) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Build raw OHLCV-derived features with multiple lookbacks. No artificial limit."""
    all_X, all_y = [], []

    for seg in segments:
        o, h, l, c, v = seg[:, 0], seg[:, 1], seg[:, 2], seg[:, 3], seg[:, 4]
        n = len(c)
        if n < 60 + target_horizon:
            continue

        features, names = [], []

        # Returns at multiple scales (no limit — let PySR pick what works)
        for lag in [1, 2, 3, 5, 7, 10, 20, 30, 50]:
            ret = np.zeros(n); ret[lag:] = (c[lag:] - c[:-lag]) / (c[:-lag] + 1e-12)
            features.append(ret); names.append(f"ret_{lag}")

        # Ranges at multiple scales
        for w in [1, 3, 5, 10, 20, 50]:
            rng = np.zeros(n)
            for i in range(w, n):
                rng[i] = (np.max(h[i - w + 1:i + 1]) - np.min(l[i - w + 1:i + 1])) / (c[i] + 1e-12)
            features.append(rng); names.append(f"range_{w}")

        # Volume ratios
        for w in [3, 5, 10, 20]:
            vm = np.convolve(v, np.ones(w) / w, mode='same')
            features.append(v / (vm + 1e-12)); names.append(f"vratio_{w}")

        # Candle structure
        hl = h - l + 1e-8
        features.append((c - o) / hl); names.append("body")
        features.append((h - np.maximum(o, c)) / hl); names.append("upper_wick")
        features.append((np.minimum(o, c) - l) / hl); names.append("lower_wick")
        features.append((c - l) / hl); names.append("hl_pos")

        # Close relative to range extremes
        for w in [10, 20, 50]:
            hi = np.zeros(n); lo = np.zeros(n)
            for i in range(w, n):
                hi[i] = np.max(h[i - w + 1:i + 1]); lo[i] = np.min(l[i - w + 1:i + 1])
            features.append((c - lo) / (hi - lo + 1e-12)); names.append(f"range_pos_{w}")

        # Volatility (std of returns)
        for w in [5, 10, 20]:
            vol = np.zeros(n)
            for i in range(w, n):
                vol[i] = np.std(c[i - w + 1:i + 1] / c[i - w] - 1)
            features.append(vol); names.append(f"vol_{w}")

        X = np.column_stack(features)
        y = np.zeros(n)
        y[:-target_horizon] = (c[target_horizon:] - c[:-target_horizon]) / (c[:-target_horizon] + 1e-12)

        valid_start = 50
        valid_end = n - target_horizon
        if valid_end <= valid_start: continue
        all_X.append(X[valid_start:valid_end])
        all_y.append(y[valid_start:valid_end])

    if not all_X:
        return np.empty((0, 0)), np.empty(0), []
    return np.vstack(all_X), np.concatenate(all_y), names


def run_pysr(X: np.ndarray, y: np.ndarray, feature_names: list[str]) -> PySRRegressor:
    max_rows = 15000
    if len(X) > max_rows:
        rng = np.random.default_rng(42)
        idx = rng.choice(len(X), max_rows, replace=False)
        X, y = X[idx], y[idx]

    model = PySRRegressor(
        niterations=400,
        binary_operators=["+", "-", "*", "/"],
        unary_operators=["abs", "square"],
        extra_sympy_mappings={"square": lambda x: x**2},
        maxsize=25,
        maxdepth=7,
        populations=50,
        population_size=60,
        ncycles_per_iteration=500,
        parsimony=0.0015,
        deterministic=False,
        procs=4,
        parallelism="multiprocessing",
        progress=False,
        verbosity=0,
        temp_equation_file=True,
    )
    model.fit(X, y, variable_names=feature_names)
    return model


def extract_results(model: PySRRegressor) -> list[dict]:
    results = []
    equations = model.equations_
    if equations is None or len(equations) == 0:
        return results
    for _, row in equations.iterrows():
        # raw_expression: human-readable string via sympy
        raw_expr = str(row.get("equation", ""))
        try:
            sympy_expr = model.sympy(row.get("complexity", 0))
            raw_expr = str(sympy_expr)
        except Exception:
            pass
        results.append({
            "expression": str(row.get("equation", "")),
            "raw_expression": raw_expr,
            "complexity": int(row.get("complexity", 0)),
            "loss": float(row.get("loss", 0)),
            "score": float(row.get("score", 0)),
        })
    results.sort(key=lambda x: x["loss"])
    return results[:20]


def main():
    log.info("Arena 1 — Full PySR Signal Pool (11 regimes × 5 targets)")
    log.info(f"Targets: next_{TARGETS}_bar_return")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    t_global = time.monotonic()

    log.info("Loading all OHLCV + labeling...")
    all_data = {}
    for sym in SYMBOLS:
        raw = load_ohlcv(sym)
        labels_1m, _, _ = label_symbol(raw)
        all_data[sym] = (raw, labels_1m)
        log.info(f"  {sym}: {len(raw)} bars")

    all_candidates = []
    run_count = 0
    total_runs = len(SEARCH_REGIMES) * len(TARGETS)

    for regime_id in SEARCH_REGIMES:
        regime_name = REGIME_NAMES[regime_id]
        segments = extract_regime_segments(regime_id, all_data)

        if len(segments) < 3:
            log.warning(f"SKIP {regime_name}: only {len(segments)} segments")
            for h in TARGETS:
                run_count += 1
            continue

        log.info(f"\n{'='*60}")
        log.info(f"REGIME: {regime_name} ({len(segments)} segments)")

        for horizon in TARGETS:
            run_count += 1

            # Resume: skip already-completed runs
            out_path = OUTPUT_DIR / f"{regime_name}_h{horizon}.json"
            if out_path.exists():
                log.info(f"  SKIP {regime_name}_h{horizon} — already complete")
                continue

            log.info(f"\n  [{run_count}/{total_runs}] target=next_{horizon}_bar_return")

            X, y, feature_names = build_features_and_target(segments, horizon)
            if len(X) < 500:
                log.warning(f"    Too few samples ({len(X)}), skip")
                continue

            log.info(f"    X={X.shape}, y_std={y.std():.6f}")

            t1 = time.monotonic()
            try:
                model = run_pysr(X, y, feature_names)
                dt = time.monotonic() - t1
                top_exprs = extract_results(model)
                log.info(f"    PySR done in {dt:.0f}s, {len(top_exprs)} expressions")

                for i, e in enumerate(top_exprs[:3]):
                    log.info(f"      #{i+1}: loss={e['loss']:.8f} score={e['score']:.6f} | {e['expression']}")

                for e in top_exprs:
                    e["regime"] = regime_name
                    e["horizon"] = horizon
                all_candidates.extend(top_exprs); log.info("DRY RUN: first run complete, exiting"); import sys; sys.exit(0)

                out = OUTPUT_DIR / f"{regime_name}_h{horizon}.json"
                with out.open("w") as f:
                    json.dump(top_exprs, f, indent=2)
            except Exception as ex:
                log.error(f"    PySR failed: {ex}")

    # De-duplicate
    seen = set()
    unique = []
    for c in all_candidates:
        expr = c["expression"]
        if expr not in seen:
            seen.add(expr)
            unique.append(c)

    elapsed = time.monotonic() - t_global
    log.info(f"\n{'='*60}")
    log.info(f"ARENA 1 COMPLETE")
    log.info(f"  Total candidates: {len(all_candidates)}")
    log.info(f"  Unique expressions: {len(unique)}")
    log.info(f"  Time: {elapsed / 3600:.1f}h")

    with (OUTPUT_DIR / "all_candidates.json").open("w") as f:
        json.dump(unique, f, indent=2)
    log.info(f"  Saved: {OUTPUT_DIR}/all_candidates.json")


if __name__ == "__main__":
    main()
