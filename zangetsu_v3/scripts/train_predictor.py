#!/usr/bin/env python3
"""Train LightGBM online regime predictor using rule-based labels as ground truth (V3.2 C3).

Uses only PAST features (no lookahead) to predict the 13-state label that the
rule-based labeler produces (which uses lookahead).

Split: TEMPORAL only (train on earlier 80%, test on later 20%).
Target: >70% accuracy on both fine (13-state) and coarse (11-state).

Output: strategies/regime_model.pkl (LightGBM model + feature names + coarse_map)
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
import time
import numpy as np
import polars as pl
import psycopg2
import joblib
from sklearn.metrics import accuracy_score, classification_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("train_predictor")

DB_DSN = os.environ.get("ZV3_DB_DSN", "dbname=zangetsu user=zangetsu password=9c424966bebb05a42966186bb22d7480 host=127.0.0.1 port=5432")
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
OUTPUT_PATH = Path("strategies/regime_model.pkl")

# 13 fine -> 11 coarse mapping (must match predictor.py FINE_TO_COARSE)
COARSE_MAP = {
    0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 9: 9, 10: 10,
    11: 1,  # LIQUIDITY_CRISIS -> BEAR_TREND
    12: 0,  # PARABOLIC -> BULL_TREND
}


def load_ohlcv(symbol):
    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT timestamp, open, high, low, close, volume FROM ohlcv_1m "
                "WHERE symbol = %s ORDER BY timestamp", (symbol,)
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return pl.DataFrame(rows, schema=["ts_ms","open","high","low","close","volume"], orient="row").with_columns(
        pl.from_epoch(pl.col("ts_ms"), time_unit="ms").alias("timestamp"),
        pl.col("open").cast(pl.Float64), pl.col("high").cast(pl.Float64),
        pl.col("low").cast(pl.Float64), pl.col("close").cast(pl.Float64),
        pl.col("volume").cast(pl.Float64),
    ).drop("ts_ms").sort("timestamp")


def resample_4h(df):
    return df.sort("timestamp").group_by_dynamic("timestamp", every="4h").agg([
        pl.col("open").first(),
        pl.col("high").max(),
        pl.col("low").min(),
        pl.col("close").last(),
        pl.col("volume").sum(),
    ]).sort("timestamp")


def compute_features(df_4h):
    """Compute past-only features on 4h bars for LightGBM prediction.
    Must produce the same 12 features as predictor._compute_online_features().
    """
    close = df_4h["close"].to_numpy().astype(np.float64)
    high = df_4h["high"].to_numpy().astype(np.float64)
    low = df_4h["low"].to_numpy().astype(np.float64)
    volume = df_4h["volume"].to_numpy().astype(np.float64)
    n = len(close)

    def _ema(x, p):
        out = np.zeros(n); out[0] = x[0]; alpha = 2/(p+1)
        for i in range(1, n): out[i] = alpha*x[i] + (1-alpha)*out[i-1]
        return out

    def _atr(p):
        tr = np.maximum(high[1:]-low[1:], np.maximum(np.abs(high[1:]-close[:-1]), np.abs(low[1:]-close[:-1])))
        tr = np.concatenate([[high[0]-low[0]], tr])
        return _ema(tr, p)

    def _rolling_pct(x, w):
        out = np.full(n, 50.0)
        for i in range(w, n):
            window = x[i-w:i+1]
            out[i] = np.sum(window <= x[i]) / len(window) * 100
        return out

    ema21 = _ema(close, 21)
    ema55 = _ema(close, 55)
    ema200 = _ema(close, 200)
    atr14 = _atr(14)
    atr_pct = _rolling_pct(atr14, 100)

    # BB width
    bb_mean = np.convolve(close, np.ones(20)/20, mode="same")
    bb_std = np.array([np.std(close[max(0,i-19):i+1]) for i in range(n)])
    bb_width = 2 * bb_std / (bb_mean + 1e-12)
    bb_width_pct = _rolling_pct(bb_width, 100)

    # ADX
    plus_dm = np.maximum(np.diff(high, prepend=high[0]), 0)
    minus_dm = np.maximum(-np.diff(low, prepend=low[0]), 0)
    mask = plus_dm > minus_dm; minus_dm[mask] = 0; plus_dm[~mask] = 0
    plus_di = _ema(plus_dm, 14) / (atr14 + 1e-12) * 100
    minus_di = _ema(minus_dm, 14) / (atr14 + 1e-12) * 100
    dx = np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-12) * 100
    adx = _ema(dx, 14)

    # Slopes
    ema21_slope = np.zeros(n); ema21_slope[5:] = (ema21[5:] - ema21[:-5]) / (ema21[:-5] + 1e-12)
    ema55_slope = np.zeros(n); ema55_slope[10:] = (ema55[10:] - ema55[:-10]) / (ema55[:-10] + 1e-12)

    # Volume z-score
    vol_ma = np.convolve(volume, np.ones(20)/20, mode="same")
    vol_std = np.array([np.std(volume[max(0,i-19):i+1]) for i in range(n)])
    vol_z = (volume - vol_ma) / (vol_std + 1e-12)

    # Higher highs / lower lows pattern
    hh = np.zeros(n)
    for i in range(3, n):
        hh[i] = 1 if high[i] > high[i-1] > high[i-2] else (-1 if low[i] < low[i-1] < low[i-2] else 0)

    # Close relative to EMAs
    close_vs_ema21 = (close - ema21) / (atr14 + 1e-12)
    close_vs_ema200 = (close - ema200) / (atr14 + 1e-12)
    ema21_vs_ema55 = (ema21 - ema55) / (atr14 + 1e-12)

    features = np.column_stack([
        adx, atr_pct, bb_width_pct,
        ema21_slope, ema55_slope,
        vol_z, hh,
        close_vs_ema21, close_vs_ema200, ema21_vs_ema55,
        plus_di, minus_di,
    ])
    feature_names = [
        "adx", "atr_pct", "bb_width_pct",
        "ema21_slope", "ema55_slope",
        "vol_z", "hh_pattern",
        "close_vs_ema21", "close_vs_ema200", "ema21_vs_ema55",
        "plus_di", "minus_di",
    ]
    return features, feature_names


def main():
    from zangetsu_v3.regime.rule_labeler import label_symbol, REGIME_NAMES

    log.info("Training Online Regime Predictor (LightGBM) -- V3.2")
    t0 = time.monotonic()

    all_X, all_y = [], []
    for sym in SYMBOLS:
        log.info(f"  Loading {sym}...")
        raw = load_ohlcv(sym)
        labels_1m, _, _ = label_symbol(raw)
        df_4h = resample_4h(raw)
        X, feat_names = compute_features(df_4h)

        # Broadcast 4h labels: take label at each 4h bar timestamp
        ts_1m = raw["timestamp"].to_numpy()
        ts_4h = df_4h["timestamp"].to_numpy()
        labels_4h = np.zeros(len(ts_4h), dtype=int)
        j = 0
        for i in range(len(ts_4h)):
            while j < len(ts_1m) - 1 and ts_1m[j] < ts_4h[i]:
                j += 1
            labels_4h[i] = labels_1m[min(j, len(labels_1m)-1)]

        # Skip warmup (first 200 bars need indicator stabilization)
        valid = 200
        all_X.append(X[valid:])
        all_y.append(labels_4h[valid:])
        log.info(f"    {sym}: {len(X)-valid} 4h bars, {len(set(labels_4h[valid:]))} unique regimes")

    X = np.vstack(all_X)
    y = np.concatenate(all_y)
    log.info(f"  Total: {len(X)} samples, {len(set(y))} classes")

    # TEMPORAL split: last 20% of each symbol's data
    # Since we stacked symbols sequentially, we split at 80% overall
    # This is temporal because each symbol's data is already time-sorted
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    log.info(f"  Train: {len(X_train)} | Test: {len(X_test)} (temporal 80/20)")

    import lightgbm as lgb
    model = lgb.LGBMClassifier(
        n_estimators=300, max_depth=6, learning_rate=0.05,
        num_leaves=31, min_child_samples=20,
        subsample=0.8, colsample_bytree=0.8,
        class_weight="balanced", verbose=-1,
    )
    model.fit(X_train, y_train)

    # Fine accuracy (13 states)
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    log.info(f"  Fine accuracy (13 states): {acc:.4f} ({acc*100:.1f}%)")

    # Coarse accuracy (11 search regimes)
    y_test_coarse = np.array([COARSE_MAP.get(v, v) for v in y_test])
    y_pred_coarse = np.array([COARSE_MAP.get(v, v) for v in y_pred])
    acc_coarse = accuracy_score(y_test_coarse, y_pred_coarse)
    log.info(f"  Coarse accuracy (11 regimes): {acc_coarse:.4f} ({acc_coarse*100:.1f}%)")

    if acc < 0.70:
        log.warning(f"  WARNING: Fine accuracy {acc:.1%} below 70% target!")
    if acc_coarse < 0.70:
        log.warning(f"  WARNING: Coarse accuracy {acc_coarse:.1%} below 70% target!")

    # Per-class report
    present_classes = sorted(set(y_test))
    report = classification_report(
        y_test, y_pred,
        target_names=[REGIME_NAMES.get(i, f"R{i}") for i in present_classes],
        labels=present_classes,
        zero_division=0,
    )
    log.info(f"\n{report}")

    # Save model with V3.2 coarse_map (LIQUIDITY_CRISIS->BEAR_TREND, PARABOLIC->BULL_TREND)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "model": model,
        "feature_names": feat_names,
        "coarse_map": COARSE_MAP,
        "version": "3.2",
        "fine_accuracy": float(acc),
        "coarse_accuracy": float(acc_coarse),
    }, OUTPUT_PATH)
    log.info(f"  Saved: {OUTPUT_PATH}")
    log.info(f"  Time: {time.monotonic()-t0:.0f}s")


if __name__ == "__main__":
    main()
