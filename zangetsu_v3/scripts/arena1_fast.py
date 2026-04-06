#!/usr/bin/env python3
"""Arena 1 Fast: Random Expression Generator for Zangetsu V3.2 §7 Lane A.

Generates 10,000 random AST expressions per regime (5k from 34 cols, 5k from 5 OHLCV),
screens via Pearson correlation, inserts survivors into factor_candidates.

All 11 regimes run in parallel via ProcessPoolExecutor.
Target runtime: ~15 minutes.
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hashlib
import io
import json
import logging
import os
import random
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from enum import IntEnum
from typing import Any

import numpy as np
import psycopg2
import polars as pl
from scipy.stats import pearsonr

from zangetsu_v3.regime.rule_labeler import label_symbol, Regime, REGIME_NAMES

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("arena1_fast")

_env_end = os.environ.get("ZV3_TRAINING_END")
TRAINING_END = (
    datetime.fromisoformat(_env_end)
    if _env_end
    else datetime.now(timezone.utc) - timedelta(hours=1)
)

DB_DSN = os.environ.get(
    "ZV3_DB_DSN",
    "dbname=zangetsu user=zangetsu password=9c424966bebb05a42966186bb22d7480 host=127.0.0.1 port=5432",
)
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
TRAINING_MONTHS = 18
MIN_SEGMENT_BARS = 1440

SEARCH_REGIMES = [
    Regime.BULL_TREND, Regime.BEAR_TREND, Regime.BULL_PULLBACK, Regime.BEAR_RALLY,
    Regime.TOPPING, Regime.BOTTOMING, Regime.CONSOLIDATION, Regime.SQUEEZE,
    Regime.CHOPPY_VOLATILE, Regime.DISTRIBUTION, Regime.ACCUMULATION,
]

BATCH_SIZE_FULL = 5000      # ASTs from 34 columns
BATCH_SIZE_OHLCV = 5000     # ASTs from 5 OHLCV only
TREE_DEPTH_MIN = 2
TREE_DEPTH_MAX = 5
LOOKBACK_POOL = [1, 2, 3, 5, 7, 10]
QUICK_TOP_K = 500
FULL_CORR_THRESHOLD = 0.01
FULL_MIN_TARGETS = 3
EVAL_BARS = 1000
NAN_INF_THRESHOLD = 0.10
TARGET_HORIZONS = [1, 5, 10, 30]

# 5 OHLCV base columns
OHLCV_COLS = ["open", "high", "low", "close", "volume"]

# ---------------------------------------------------------------------------
# AST Node types
# ---------------------------------------------------------------------------

class NodeType(IntEnum):
    CONST = 0
    COL = 1
    BINARY = 2
    UNARY = 3
    ROLLING = 4


# Operators
BINARY_OPS = ["add", "sub", "mul", "div"]
UNARY_OPS = ["abs", "neg", "square", "sqrt", "log1p"]
ROLLING_OPS = ["ts_delta", "ts_std", "ts_mean", "ts_max", "ts_min", "ts_rank"]
ROLLING_OPS_2COL = ["ts_corr"]  # needs 2 columns


def _protected_div(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    mask = np.abs(b) < 1e-8
    out = np.zeros_like(a)
    out[~mask] = a[~mask] / b[~mask]
    return out


def _protected_sqrt(x: np.ndarray) -> np.ndarray:
    return np.sqrt(np.abs(x))


def _log1p_safe(x: np.ndarray) -> np.ndarray:
    return np.log1p(np.abs(x))


# ---------------------------------------------------------------------------
# AST representation and evaluation
# ---------------------------------------------------------------------------

def make_ast(depth: int, col_names: list[str], rng: random.Random) -> dict:
    """Recursively generate a random AST node."""
    # Leaf node conditions
    if depth <= 0 or (depth == 1 and rng.random() < 0.5):
        if rng.random() < 0.15:
            return {"t": "const", "v": round(rng.uniform(-2, 2), 3)}
        else:
            return {"t": "col", "v": rng.choice(col_names)}

    kind = rng.random()
    if kind < 0.35:
        # Binary op
        op = rng.choice(BINARY_OPS)
        return {
            "t": "bin", "op": op,
            "l": make_ast(depth - 1, col_names, rng),
            "r": make_ast(depth - 1, col_names, rng),
        }
    elif kind < 0.55:
        # Unary op
        op = rng.choice(UNARY_OPS)
        return {"t": "un", "op": op, "c": make_ast(depth - 1, col_names, rng)}
    elif kind < 0.85:
        # Rolling op (single column)
        op = rng.choice(ROLLING_OPS)
        n = rng.choice(LOOKBACK_POOL)
        return {
            "t": "roll", "op": op, "n": n,
            "c": make_ast(depth - 1, col_names, rng),
        }
    else:
        # Rolling op with 2 columns (ts_corr)
        n = rng.choice(LOOKBACK_POOL)
        return {
            "t": "roll2", "op": "ts_corr", "n": n,
            "l": make_ast(depth - 1, col_names, rng),
            "r": make_ast(depth - 1, col_names, rng),
        }


def ast_to_str(node: dict) -> str:
    """Convert AST to human-readable string."""
    t = node["t"]
    if t == "const":
        return str(node["v"])
    if t == "col":
        return node["v"]
    if t == "bin":
        return f"({ast_to_str(node['l'])} {node['op']} {ast_to_str(node['r'])})"
    if t == "un":
        return f"{node['op']}({ast_to_str(node['c'])})"
    if t == "roll":
        return f"{node['op']}({ast_to_str(node['c'])}, {node['n']})"
    if t == "roll2":
        return f"{node['op']}({ast_to_str(node['l'])}, {ast_to_str(node['r'])}, {node['n']})"
    return "?"


def ast_hash(node: dict) -> str:
    """Structural hash for dedup."""
    return hashlib.md5(json.dumps(node, sort_keys=True).encode()).hexdigest()


def _rolling_op(op: str, arr: np.ndarray, n: int) -> np.ndarray:
    """Compute a single-input rolling operation."""
    length = len(arr)
    out = np.full(length, np.nan)
    if n < 1 or n > length:
        return out

    if op == "ts_delta":
        out[n:] = arr[n:] - arr[:-n]
    elif op == "ts_mean":
        cs = np.cumsum(arr)
        cs = np.insert(cs, 0, 0.0)
        out[n - 1:] = (cs[n:] - cs[:-n]) / n
    elif op == "ts_std":
        # Welford-style via cumsum trick
        cs = np.cumsum(arr)
        cs2 = np.cumsum(arr ** 2)
        cs = np.insert(cs, 0, 0.0)
        cs2 = np.insert(cs2, 0, 0.0)
        mean = (cs[n:] - cs[:-n]) / n
        var = (cs2[n:] - cs2[:-n]) / n - mean ** 2
        var = np.maximum(var, 0.0)
        out[n - 1:] = np.sqrt(var)
    elif op == "ts_max":
        # Strided view for small windows
        if n <= 50:
            from numpy.lib.stride_tricks import sliding_window_view
            w = sliding_window_view(arr, n)
            out[n - 1:] = np.max(w, axis=1)
        else:
            for i in range(n - 1, length):
                out[i] = np.max(arr[i - n + 1:i + 1])
    elif op == "ts_min":
        if n <= 50:
            from numpy.lib.stride_tricks import sliding_window_view
            w = sliding_window_view(arr, n)
            out[n - 1:] = np.min(w, axis=1)
        else:
            for i in range(n - 1, length):
                out[i] = np.min(arr[i - n + 1:i + 1])
    elif op == "ts_rank":
        # Percentile rank within window
        if n <= 50:
            from numpy.lib.stride_tricks import sliding_window_view
            w = sliding_window_view(arr, n)
            out[n - 1:] = np.sum(w <= arr[n - 1:, None], axis=1) / n
        else:
            for i in range(n - 1, length):
                window = arr[i - n + 1:i + 1]
                out[i] = np.sum(window <= arr[i]) / n
    return out


def _rolling_corr(a: np.ndarray, b: np.ndarray, n: int) -> np.ndarray:
    """Rolling Pearson correlation between two arrays."""
    length = len(a)
    out = np.full(length, np.nan)
    if n < 3 or n > length:
        return out

    cs_a = np.insert(np.cumsum(a), 0, 0.0)
    cs_b = np.insert(np.cumsum(b), 0, 0.0)
    cs_a2 = np.insert(np.cumsum(a ** 2), 0, 0.0)
    cs_b2 = np.insert(np.cumsum(b ** 2), 0, 0.0)
    cs_ab = np.insert(np.cumsum(a * b), 0, 0.0)

    sum_a = cs_a[n:] - cs_a[:-n]
    sum_b = cs_b[n:] - cs_b[:-n]
    sum_a2 = cs_a2[n:] - cs_a2[:-n]
    sum_b2 = cs_b2[n:] - cs_b2[:-n]
    sum_ab = cs_ab[n:] - cs_ab[:-n]

    numer = n * sum_ab - sum_a * sum_b
    denom = np.sqrt((n * sum_a2 - sum_a ** 2) * (n * sum_b2 - sum_b ** 2))
    mask = np.abs(denom) < 1e-12
    result = np.zeros(len(numer))
    result[~mask] = numer[~mask] / denom[~mask]
    out[n - 1:] = result
    return out


def eval_ast(node: dict, data: dict[str, np.ndarray]) -> np.ndarray:
    """Evaluate AST against data dict. Returns array of same length."""
    t = node["t"]
    if t == "const":
        return np.full(next(iter(data.values())).shape[0], node["v"], dtype=np.float64)
    if t == "col":
        col = node["v"]
        if col in data:
            return data[col].copy()
        return np.zeros(next(iter(data.values())).shape[0])
    if t == "bin":
        l = eval_ast(node["l"], data)
        r = eval_ast(node["r"], data)
        op = node["op"]
        if op == "add":
            return l + r
        elif op == "sub":
            return l - r
        elif op == "mul":
            return l * r
        elif op == "div":
            return _protected_div(l, r)
    if t == "un":
        c = eval_ast(node["c"], data)
        op = node["op"]
        if op == "abs":
            return np.abs(c)
        elif op == "neg":
            return -c
        elif op == "square":
            return c ** 2
        elif op == "sqrt":
            return _protected_sqrt(c)
        elif op == "log1p":
            return _log1p_safe(c)
    if t == "roll":
        c = eval_ast(node["c"], data)
        return _rolling_op(node["op"], c, node["n"])
    if t == "roll2":
        l = eval_ast(node["l"], data)
        r = eval_ast(node["r"], data)
        return _rolling_corr(l, r, node["n"])
    return np.zeros(next(iter(data.values())).shape[0])


# ---------------------------------------------------------------------------
# Scale filter Q13: discard raw price not in ratio structure
# ---------------------------------------------------------------------------

def _uses_raw_price_unsafe(node: dict) -> bool:
    """Return True if expression uses raw OHLCV price columns outside a ratio structure.

    The spec says: discard expressions with raw price not in ratio structure.
    Volume must also be in ratio form.

    We check recursively: if a leaf is open/high/low/close/volume and it is NOT
    inside a division, it's unsafe.
    """
    return _check_scale(node, in_ratio=False)


def _check_scale(node: dict, in_ratio: bool) -> bool:
    """Returns True if BAD (raw price used outside ratio)."""
    t = node["t"]
    raw_cols = {"open", "high", "low", "close", "volume"}

    if t == "const":
        return False
    if t == "col":
        # Derived features (ret_*, range_*, vratio_*, body, etc.) are already ratios.
        # Only OHLCV raw cols are problematic outside a ratio.
        if node["v"] in raw_cols and not in_ratio:
            return True
        return False
    if t == "bin":
        # Division creates a ratio context for both children
        if node["op"] == "div":
            return _check_scale(node["l"], in_ratio=True) or _check_scale(node["r"], in_ratio=True)
        elif node["op"] == "sub":
            # (price - price) is okay if both are raw → difference is scale-dependent
            # But (price - price) / price is fine. We conservatively allow sub.
            return _check_scale(node["l"], in_ratio) or _check_scale(node["r"], in_ratio)
        else:
            return _check_scale(node["l"], in_ratio) or _check_scale(node["r"], in_ratio)
    if t == "un":
        return _check_scale(node["c"], in_ratio)
    if t == "roll":
        # Rolling on a column inherits ratio context
        return _check_scale(node["c"], in_ratio)
    if t == "roll2":
        # ts_corr is dimensionless → children are safe
        return False
    return False


# ---------------------------------------------------------------------------
# Feature computation (from arena1_full.py build_features_and_target)
# ---------------------------------------------------------------------------

# Feature names produced by build_features (34 total: 29 derived + 5 OHLCV)
DERIVED_FEATURE_NAMES: list[str] = []
ALL_FEATURE_NAMES: list[str] = []  # 34 = 29 derived + 5 OHLCV


def _compute_features_for_segment(seg: np.ndarray) -> dict[str, np.ndarray]:
    """Compute 29 derived features + 5 OHLCV for a single segment.

    seg columns: open, high, low, close, volume (already normalized).
    Returns dict col_name -> array.
    """
    o, h, l, c, v = seg[:, 0], seg[:, 1], seg[:, 2], seg[:, 3], seg[:, 4]
    n = len(c)
    data: dict[str, np.ndarray] = {}

    # OHLCV (normalized)
    data["open"] = o.copy()
    data["high"] = h.copy()
    data["low"] = l.copy()
    data["close"] = c.copy()
    data["volume"] = v.copy()

    # Returns at multiple lags
    for lag in [1, 2, 3, 5, 7, 10, 20, 30, 50]:
        ret = np.zeros(n)
        ret[lag:] = (c[lag:] - c[:-lag]) / (c[:-lag] + 1e-12)
        data[f"ret_{lag}"] = ret

    # Ranges at multiple windows
    for w in [1, 3, 5, 10, 20, 50]:
        rng = np.zeros(n)
        for i in range(w, n):
            rng[i] = (np.max(h[i - w + 1:i + 1]) - np.min(l[i - w + 1:i + 1])) / (c[i] + 1e-12)
        data[f"range_{w}"] = rng

    # Volume ratios
    for w in [3, 5, 10, 20]:
        vm = np.convolve(v, np.ones(w) / w, mode="same")
        data[f"vratio_{w}"] = v / (vm + 1e-12)

    # Candle structure
    hl = h - l + 1e-8
    data["body"] = (c - o) / hl
    data["upper_wick"] = (h - np.maximum(o, c)) / hl
    data["lower_wick"] = (np.minimum(o, c) - l) / hl
    data["hl_pos"] = (c - l) / hl

    # Range position
    for w in [10, 20, 50]:
        hi = np.zeros(n)
        lo = np.zeros(n)
        for i in range(w, n):
            hi[i] = np.max(h[i - w + 1:i + 1])
            lo[i] = np.min(l[i - w + 1:i + 1])
        data[f"range_pos_{w}"] = (c - lo) / (hi - lo + 1e-12)

    # Volatility
    for w in [5, 10, 20]:
        vol = np.zeros(n)
        for i in range(w, n):
            vol[i] = np.std(c[i - w + 1:i + 1] / c[i - w] - 1)
        data[f"vol_{w}"] = vol

    return data


def _build_feature_name_lists():
    """Initialize global feature name lists."""
    global DERIVED_FEATURE_NAMES, ALL_FEATURE_NAMES
    names = []
    for lag in [1, 2, 3, 5, 7, 10, 20, 30, 50]:
        names.append(f"ret_{lag}")
    for w in [1, 3, 5, 10, 20, 50]:
        names.append(f"range_{w}")
    for w in [3, 5, 10, 20]:
        names.append(f"vratio_{w}")
    names.extend(["body", "upper_wick", "lower_wick", "hl_pos"])
    for w in [10, 20, 50]:
        names.append(f"range_pos_{w}")
    for w in [5, 10, 20]:
        names.append(f"vol_{w}")
    DERIVED_FEATURE_NAMES = names  # 29
    ALL_FEATURE_NAMES = OHLCV_COLS + names  # 34


_build_feature_name_lists()


# ---------------------------------------------------------------------------
# Data loading (same as arena1_full.py)
# ---------------------------------------------------------------------------

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
    df = pl.DataFrame(
        rows,
        schema=["ts_ms", "open", "high", "low", "close", "volume"],
        orient="row",
    )
    return (
        df.with_columns(
            pl.from_epoch(pl.col("ts_ms"), time_unit="ms").alias("timestamp"),
            pl.col("open").cast(pl.Float64),
            pl.col("high").cast(pl.Float64),
            pl.col("low").cast(pl.Float64),
            pl.col("close").cast(pl.Float64),
            pl.col("volume").cast(pl.Float64),
        )
        .drop("ts_ms")
        .sort("timestamp")
    )


def extract_regime_segments(
    regime_id: int, all_data: dict
) -> list[np.ndarray]:
    """Extract OHLCV segments for a regime. Normalize by first close price."""
    segments = []
    for sym, (raw, labels_1m) in all_data.items():
        mask = labels_1m == regime_id
        diffs = np.diff(mask.astype(int))
        starts = list(np.where(diffs == 1)[0] + 1)
        ends = list(np.where(diffs == -1)[0] + 1)
        if mask[0]:
            starts = [0] + starts
        if mask[-1]:
            ends = ends + [len(labels_1m)]
        ohlcv_np = (
            raw.select(["open", "high", "low", "close", "volume"])
            .to_numpy()
            .astype(np.float64)
        )
        for s, e in zip(starts, ends):
            if e - s >= MIN_SEGMENT_BARS:
                seg = ohlcv_np[s:e].copy()
                bp = seg[0, 3]
                if bp > 0:
                    seg[:, :4] /= bp
                vm = np.mean(seg[:, 4])
                if vm > 0:
                    seg[:, 4] /= vm
                segments.append(seg)
    return segments


# ---------------------------------------------------------------------------
# AST generation batches
# ---------------------------------------------------------------------------

def generate_batch(
    count: int, col_names: list[str], seed: int
) -> list[tuple[dict, str, str]]:
    """Generate `count` ASTs. Returns list of (ast_dict, ast_str, hash)."""
    rng = random.Random(seed)
    results = []
    seen_hashes: set[str] = set()
    attempts = 0
    max_attempts = count * 3  # allow some duplication headroom
    while len(results) < count and attempts < max_attempts:
        attempts += 1
        depth = rng.randint(TREE_DEPTH_MIN, TREE_DEPTH_MAX)
        ast = make_ast(depth, col_names, rng)
        h = ast_hash(ast)
        if h in seen_hashes:
            continue
        seen_hashes.add(h)
        results.append((ast, ast_to_str(ast), h))
    return results


# ---------------------------------------------------------------------------
# Validity check
# ---------------------------------------------------------------------------

def check_validity(
    ast_node: dict, data: dict[str, np.ndarray], n_bars: int
) -> bool:
    """Evaluate AST on data, check NaN/Inf ratio <= threshold."""
    try:
        vals = eval_ast(ast_node, data)
    except Exception:
        return False
    if len(vals) < n_bars:
        return False
    sample = vals[:n_bars]
    bad = np.isnan(sample) | np.isinf(sample)
    return np.sum(bad) / n_bars <= NAN_INF_THRESHOLD


# ---------------------------------------------------------------------------
# Correlation helpers
# ---------------------------------------------------------------------------

def compute_corr(signal: np.ndarray, target: np.ndarray) -> float:
    """Pearson correlation, ignoring NaN positions."""
    mask = np.isfinite(signal) & np.isfinite(target)
    if np.sum(mask) < 100:
        return 0.0
    s = signal[mask]
    t = target[mask]
    if np.std(s) < 1e-12 or np.std(t) < 1e-12:
        return 0.0
    r, _ = pearsonr(s, t)
    return float(r) if np.isfinite(r) else 0.0


def make_return_target(close: np.ndarray, horizon: int) -> np.ndarray:
    """Next-N-bar return."""
    n = len(close)
    y = np.full(n, np.nan)
    y[:-horizon] = (close[horizon:] - close[:-horizon]) / (close[:-horizon] + 1e-12)
    return y


# ---------------------------------------------------------------------------
# Per-regime pipeline (runs in subprocess)
# ---------------------------------------------------------------------------

def run_regime(
    regime_id: int,
    all_data_serialized: dict,
    run_id: str,
) -> list[dict]:
    """Full pipeline for one regime. Returns list of candidate dicts for DB insert."""
    regime_name = REGIME_NAMES[regime_id]
    log.info(f"[{regime_name}] Starting")
    t0 = time.monotonic()

    # Reconstruct all_data from serialized form
    all_data = {}
    for sym, (raw_bytes, labels_bytes) in all_data_serialized.items():
        raw = pl.read_ipc(raw_bytes)  # type: ignore
        labels = np.frombuffer(labels_bytes, dtype=np.int64)
        all_data[sym] = (raw, labels)

    segments = extract_regime_segments(regime_id, all_data)
    if len(segments) < 1:
        log.warning(f"[{regime_name}] No segments >= {MIN_SEGMENT_BARS} bars, skip")
        return []

    log.info(f"[{regime_name}] {len(segments)} segments")

    # ---- Step 1: Generate ASTs ----
    seed_base = regime_id * 100_000
    batch1 = generate_batch(BATCH_SIZE_FULL, ALL_FEATURE_NAMES, seed_base)
    batch2 = generate_batch(BATCH_SIZE_OHLCV, OHLCV_COLS, seed_base + 50_000)

    # Dedup across batches
    seen: set[str] = set()
    all_asts: list[tuple[dict, str]] = []
    for ast, expr_str, h in batch1 + batch2:
        if h not in seen:
            seen.add(h)
            all_asts.append((ast, expr_str))

    log.info(f"[{regime_name}] Generated {len(all_asts)} unique ASTs")

    # ---- Step 2: Validity filter on 1000 bars ----
    # Use first segment for validity check
    eval_seg = segments[0]
    eval_data = _compute_features_for_segment(eval_seg)
    n_eval = min(EVAL_BARS, len(eval_seg))

    valid_asts: list[tuple[dict, str]] = []
    for ast, expr_str in all_asts:
        if _uses_raw_price_unsafe(ast):
            continue
        if check_validity(ast, eval_data, n_eval):
            valid_asts.append((ast, expr_str))

    log.info(f"[{regime_name}] {len(valid_asts)} valid after NaN/Scale filter")

    if not valid_asts:
        return []

    # ---- Step 3: Quick screen on longest TRAIN segment ----
    # Pick the longest segment
    longest_idx = max(range(len(segments)), key=lambda i: len(segments[i]))
    longest_seg = segments[longest_idx]
    longest_data = _compute_features_for_segment(longest_seg)
    target_5 = make_return_target(longest_seg[:, 3], 5)  # next_5_bar_return

    scored: list[tuple[float, int]] = []
    for idx, (ast, expr_str) in enumerate(valid_asts):
        try:
            vals = eval_ast(ast, longest_data)
            r = compute_corr(vals, target_5)
            scored.append((abs(r), idx))
        except Exception:
            continue

    scored.sort(reverse=True)
    top_indices = [idx for _, idx in scored[:QUICK_TOP_K]]
    quick_survivors = [valid_asts[i] for i in top_indices]

    log.info(f"[{regime_name}] {len(quick_survivors)} pass quick screen")

    if not quick_survivors:
        return []

    # ---- Step 4: Full validation on ALL TRAIN segments ----
    # Compute features and targets for all segments
    seg_data_list: list[tuple[dict[str, np.ndarray], dict[int, np.ndarray]]] = []
    for seg in segments:
        sd = _compute_features_for_segment(seg)
        targets = {}
        close = seg[:, 3]
        for h in TARGET_HORIZONS:
            targets[h] = make_return_target(close, h)
        seg_data_list.append((sd, targets))

    candidates: list[dict] = []

    for ast, expr_str in quick_survivors:
        corrs: dict[int, list[float]] = {h: [] for h in TARGET_HORIZONS}

        for sd, targets in seg_data_list:
            try:
                vals = eval_ast(ast, sd)
            except Exception:
                continue
            for h in TARGET_HORIZONS:
                r = compute_corr(vals, targets[h])
                corrs[h].append(r)

        # Average correlation across segments
        avg_corr = {}
        for h in TARGET_HORIZONS:
            if corrs[h]:
                avg_corr[h] = float(np.mean(corrs[h]))
            else:
                avg_corr[h] = 0.0

        # Keep if abs(corr) > 0.01 on >= 3 targets
        pass_count = sum(1 for h in TARGET_HORIZONS if abs(avg_corr[h]) > FULL_CORR_THRESHOLD)
        if pass_count >= FULL_MIN_TARGETS:
            candidates.append({
                "source": "random",
                "regime": regime_name,
                "horizon": "multi",
                "raw_expression": expr_str,
                "ast_json": ast,
                "corr_h1": avg_corr.get(1, 0.0),
                "corr_h5": avg_corr.get(5, 0.0),
                "corr_h10": avg_corr.get(10, 0.0),
                "corr_h30": avg_corr.get(30, 0.0),
                "run_id": run_id,
            })

    elapsed = time.monotonic() - t0
    log.info(
        f"[{regime_name}] Done: {len(candidates)} candidates in {elapsed:.0f}s"
    )
    return candidates


# ---------------------------------------------------------------------------
# DB insert
# ---------------------------------------------------------------------------

def insert_candidates(candidates: list[dict]) -> int:
    """Insert candidates into factor_candidates table. Returns count inserted."""
    if not candidates:
        return 0
    conn = psycopg2.connect(DB_DSN)
    inserted = 0
    try:
        with conn.cursor() as cur:
            for c in candidates:
                cur.execute(
                    """INSERT INTO factor_candidates
                    (source, regime, horizon, raw_expression, ast_json,
                     corr_h1, corr_h5, corr_h10, corr_h30, run_id, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())""",
                    (
                        c["source"],
                        c["regime"],
                        c["horizon"],
                        c["raw_expression"],
                        json.dumps(c["ast_json"]),
                        c["corr_h1"],
                        c["corr_h5"],
                        c["corr_h10"],
                        c["corr_h30"],
                        c["run_id"],
                    ),
                )
                inserted += 1
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.error(f"DB insert failed: {e}")
        raise
    finally:
        conn.close()
    return inserted


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    log.info("Arena 1 Fast — Random Expression Generator (V3.2 §7 Lane A)")
    log.info(f"Training end: {TRAINING_END.isoformat()}")
    log.info(f"Symbols: {SYMBOLS}")
    log.info(f"Regimes: {len(SEARCH_REGIMES)}")
    log.info(f"Batch sizes: {BATCH_SIZE_FULL} (34-col) + {BATCH_SIZE_OHLCV} (OHLCV)")

    t_global = time.monotonic()
    run_id = f"rnd_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    log.info(f"Run ID: {run_id}")

    # ---- Load all OHLCV + label ----
    log.info("Loading OHLCV and labeling regimes...")
    all_data_raw: dict[str, tuple[pl.DataFrame, np.ndarray]] = {}
    for sym in SYMBOLS:
        raw = load_ohlcv(sym)
        labels_1m, _, _ = label_symbol(raw)
        all_data_raw[sym] = (raw, labels_1m)
        log.info(f"  {sym}: {len(raw)} bars")

    # Serialize for subprocess transfer (IPC bytes for polars, raw bytes for numpy)
    all_data_ser: dict[str, tuple[bytes, bytes]] = {}
    for sym, (raw, labels) in all_data_raw.items():
        ipc_buf = io.BytesIO()
        raw.write_ipc(ipc_buf)
        labels_int = labels.astype(np.int64)
        all_data_ser[sym] = (ipc_buf.getvalue(), labels_int.tobytes())

    # ---- Run all regimes in parallel ----
    log.info(f"Launching {len(SEARCH_REGIMES)} regime workers...")
    all_candidates: list[dict] = []

    with ProcessPoolExecutor(max_workers=len(SEARCH_REGIMES)) as executor:
        futures = {}
        for regime in SEARCH_REGIMES:
            f = executor.submit(run_regime, regime.value, all_data_ser, run_id)
            futures[f] = REGIME_NAMES[regime.value]

        for f in as_completed(futures):
            regime_name = futures[f]
            try:
                cands = f.result()
                all_candidates.extend(cands)
                log.info(f"  {regime_name}: {len(cands)} candidates")
            except Exception as e:
                log.error(f"  {regime_name} FAILED: {e}")

    # ---- Insert into DB ----
    log.info(f"Total candidates: {len(all_candidates)}")
    if all_candidates:
        inserted = insert_candidates(all_candidates)
        log.info(f"Inserted {inserted} rows into factor_candidates")
    else:
        log.warning("No candidates to insert")

    elapsed = time.monotonic() - t_global
    log.info(f"Arena 1 Fast complete in {elapsed / 60:.1f} min")

    # ---- Summary per regime ----
    from collections import Counter
    regime_counts = Counter(c["regime"] for c in all_candidates)
    for rname in sorted(regime_counts):
        log.info(f"  {rname}: {regime_counts[rname]}")


if __name__ == "__main__":
    main()
