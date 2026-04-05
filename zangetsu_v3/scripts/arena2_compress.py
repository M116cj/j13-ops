"""Arena 2 — compress Arena 1's raw PySR signal pool into 10-20 orthogonal factors.

Reads:  arena1_results/all_candidates.json
Writes: arena2_output/factor_pool.json

Dedup logic:
  1. Evaluate each candidate expression on OHLCV data to get factor time series.
  2. Remove weak factors (abs(corr with target) < 0.01 across all segments).
  3. Remove redundant pairs: if abs(pairwise corr) > threshold, keep lower PySR loss.
  4. If remaining > 20: keep top 20 by loss.
  5. If remaining < 10: relax threshold from 0.7 → 0.8 and repeat.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import polars as pl

# Allow importing from project root and inner package
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "zangetsu_v3"))

from zangetsu_v3.factors.expr_eval import ExprEval
from zangetsu_v3.factors.hft_factors import compute_hft_factors

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DB_DSN = "dbname=zangetsu user=zangetsu password=9c424966bebb05a42966186bb22d7480 host=127.0.0.1 port=5432"
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]

INPUT_PATH = Path("arena1_results/all_candidates.json")
OUTPUT_DIR = Path("arena2_output")

MIN_FACTORS = 10
MAX_FACTORS = 20
DEDUP_THRESHOLD_TIGHT = 0.7
DEDUP_THRESHOLD_RELAXED = 0.8
WEAK_CORR_THRESHOLD = 0.01

HORIZON_MAP = {
    1: "next_1_bar_return",
    3: "next_3_bar_return",
    5: "next_5_bar_return",
    10: "next_10_bar_return",
    20: "next_20_bar_return",
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_ohlcv_from_db(symbol: str, limit: int = 50_000) -> pl.DataFrame:
    """Load OHLCV bars from PostgreSQL ohlcv_1m table."""
    try:
        import psycopg2
    except ImportError:
        raise ImportError("psycopg2 required for DB access — pip install psycopg2-binary")

    conn = psycopg2.connect(DB_DSN)
    try:
        query = (
            "SELECT timestamp, open, high, low, close, volume "
            "FROM ohlcv_1m "
            "WHERE symbol = %s "
            "ORDER BY timestamp ASC "
            "LIMIT %s"
        )
        cur = conn.cursor()
        cur.execute(query, (symbol, limit))
        rows = cur.fetchall()
        cur.close()
    finally:
        conn.close()

    if not rows:
        raise ValueError(f"No OHLCV data for {symbol}")

    df = pl.DataFrame(
        {
            "timestamp": [r[0] for r in rows],
            "open": [float(r[1]) for r in rows],
            "high": [float(r[2]) for r in rows],
            "low": [float(r[3]) for r in rows],
            "close": [float(r[4]) for r in rows],
            "volume": [float(r[5]) for r in rows],
        }
    )
    return df


def prepare_factor_df(ohlcv: pl.DataFrame) -> pl.DataFrame:
    """Compute HFT factor columns and forward returns on OHLCV data.

    Returns a DataFrame containing both the HFT factor columns (ret_1, ret_3,
    range_3, etc.) and OHLCV columns — suitable for ExprEval namespace.
    """
    hft = compute_hft_factors(ohlcv)
    # Merge OHLCV + HFT factors side-by-side
    combined = pl.concat([ohlcv, hft], how="horizontal")

    # Add forward return columns for target correlation
    close = combined["close"].to_numpy().astype(np.float64)
    n = len(close)
    for horizon in [1, 3, 5, 10, 20]:
        fwd = np.full(n, np.nan)
        if horizon < n:
            fwd[:-horizon] = (close[horizon:] - close[:-horizon]) / (close[:-horizon] + 1e-12)
        col_name = HORIZON_MAP.get(horizon, f"next_{horizon}_bar_return")
        combined = combined.with_columns(pl.Series(col_name, fwd))

    return combined


# ---------------------------------------------------------------------------
# Expression evaluation
# ---------------------------------------------------------------------------
def evaluate_expression(
    expr_str: str,
    df: pl.DataFrame,
    evaluator: ExprEval,
) -> Optional[np.ndarray]:
    """Evaluate a PySR expression string against the factor DataFrame.

    Returns the factor time series as a numpy array, or None on failure.
    """
    try:
        result = evaluator.eval(expr_str, df)
        if not isinstance(result, np.ndarray):
            result = np.asarray(result, dtype=np.float64)
        return result
    except Exception as e:
        logger.warning("Failed to evaluate expression %r: %s", expr_str, e)
        return None


# ---------------------------------------------------------------------------
# Compression logic
# ---------------------------------------------------------------------------
def _pearson_corr(a: np.ndarray, b: np.ndarray) -> float:
    """Pearson correlation between two arrays, ignoring NaN positions."""
    mask = np.isfinite(a) & np.isfinite(b)
    if mask.sum() < 30:
        return 0.0
    a_clean = a[mask]
    b_clean = b[mask]
    std_a = np.std(a_clean)
    std_b = np.std(b_clean)
    if std_a < 1e-12 or std_b < 1e-12:
        return 0.0
    return float(np.corrcoef(a_clean, b_clean)[0, 1])


def _target_col_for_horizon(horizon: int) -> str:
    return HORIZON_MAP.get(horizon, f"next_{horizon}_bar_return")


def remove_weak_candidates(
    candidates: List[Dict[str, Any]],
    series_map: Dict[int, np.ndarray],
    target_series: Dict[int, np.ndarray],
    threshold: float = WEAK_CORR_THRESHOLD,
) -> List[Dict[str, Any]]:
    """Remove factors whose abs(corr) with target < threshold across ALL segments."""
    kept = []
    for i, cand in enumerate(candidates):
        if i not in series_map:
            continue
        factor_ts = series_map[i]
        # Check correlation with the candidate's own target horizon
        horizon = cand.get("horizon", 5)
        target_col = _target_col_for_horizon(horizon)
        if horizon in target_series:
            corr = abs(_pearson_corr(factor_ts, target_series[horizon]))
            if corr >= threshold:
                kept.append(cand)
                continue
        # If no matching horizon target, check all available
        any_pass = False
        for h, tgt in target_series.items():
            if abs(_pearson_corr(factor_ts, tgt)) >= threshold:
                any_pass = True
                break
        if any_pass:
            kept.append(cand)
        else:
            logger.info("Removed weak candidate: %s (max target corr < %.4f)", cand["expression"], threshold)
    return kept


def deduplicate(
    candidates: List[Dict[str, Any]],
    series_map: Dict[int, np.ndarray],
    threshold: float,
) -> List[Dict[str, Any]]:
    """Remove redundant factors by pairwise correlation.

    For each pair with abs(corr) > threshold, remove the one with higher PySR loss.
    """
    # Build index mapping from original candidate list position to series_map key
    # We need to track which candidates have valid series
    valid = [(i, c) for i, c in enumerate(candidates) if i in series_map]
    if not valid:
        return []

    # Sort by loss ascending — lower loss = better, processed first
    valid.sort(key=lambda x: x[1].get("loss", float("inf")))

    kept_indices: List[int] = []
    kept_series: List[np.ndarray] = []

    for idx, cand in valid:
        ts = series_map[idx]
        is_redundant = False
        for existing_ts in kept_series:
            if abs(_pearson_corr(ts, existing_ts)) > threshold:
                is_redundant = True
                break
        if not is_redundant:
            kept_indices.append(idx)
            kept_series.append(ts)

    return [candidates[i] for i in kept_indices]


def compress(
    candidates: List[Dict[str, Any]],
    dfs: Dict[str, pl.DataFrame],
    evaluator: ExprEval,
) -> List[Dict[str, Any]]:
    """Main compression pipeline: evaluate → remove weak → dedup → cap/relax.

    Parameters
    ----------
    candidates : list of candidate dicts from Arena 1
    dfs : dict mapping symbol → prepared factor DataFrame
    evaluator : ExprEval instance

    Returns
    -------
    list of 10-20 compressed factor dicts
    """
    if not candidates:
        logger.warning("No candidates provided")
        return []

    # Pick the first available symbol for evaluation (multi-symbol averaging is future work)
    primary_symbol = next(iter(dfs))
    df = dfs[primary_symbol]

    # --- Step 1: Evaluate all expressions ---
    series_map: Dict[int, np.ndarray] = {}
    for i, cand in enumerate(candidates):
        expr = cand.get("raw_expression") or cand.get("expression", "")
        ts = evaluate_expression(expr, df, evaluator)
        if ts is not None and np.isfinite(ts).sum() > 30:
            series_map[i] = ts
        else:
            logger.info("Skipping candidate %d (%s): evaluation failed or too few finite values", i, expr)

    logger.info("Evaluated %d / %d candidates successfully", len(series_map), len(candidates))

    # --- Step 2: Build target return series ---
    target_series: Dict[int, np.ndarray] = {}
    for horizon in [1, 3, 5, 10, 20]:
        col = _target_col_for_horizon(horizon)
        if col in df.columns:
            target_series[horizon] = df[col].to_numpy().astype(np.float64)

    # --- Step 3: Remove weak candidates ---
    filtered = remove_weak_candidates(candidates, series_map, target_series)
    # Rebuild series_map indices for filtered list
    old_to_new: Dict[int, int] = {}
    filtered_series: Dict[int, np.ndarray] = {}
    j = 0
    for i, cand in enumerate(candidates):
        if cand in filtered:
            if i in series_map:
                filtered_series[j] = series_map[i]
            old_to_new[i] = j
            j += 1

    logger.info("After weak removal: %d candidates", len(filtered))

    # --- Step 4: Deduplicate at tight threshold ---
    result = deduplicate(filtered, filtered_series, DEDUP_THRESHOLD_TIGHT)

    # --- Step 5: Cap at MAX_FACTORS ---
    if len(result) > MAX_FACTORS:
        result.sort(key=lambda c: c.get("loss", float("inf")))
        result = result[:MAX_FACTORS]

    # --- Step 6: If < MIN_FACTORS, relax threshold and retry ---
    if len(result) < MIN_FACTORS:
        logger.info("Only %d factors after tight dedup; relaxing to %.2f", len(result), DEDUP_THRESHOLD_RELAXED)
        result = deduplicate(filtered, filtered_series, DEDUP_THRESHOLD_RELAXED)
        if len(result) > MAX_FACTORS:
            result.sort(key=lambda c: c.get("loss", float("inf")))
            result = result[:MAX_FACTORS]

    logger.info("Final factor count: %d", len(result))
    return result


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------
def format_output(factors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert compressed candidates into the arena2 output schema."""
    output = []
    for i, cand in enumerate(factors):
        horizon = cand.get("horizon", 5)
        output.append({
            "index": i,
            "name": f"factor_{i + 1:03d}",
            "expression": cand.get("expression", ""),
            "raw_expression": cand.get("raw_expression", cand.get("expression", "")),
            "pysr_loss": cand.get("loss", 0.0),
            "pysr_score": cand.get("score", 0.0),
            "lookback": horizon,
            "source_regime": cand.get("regime", "UNKNOWN"),
            "source_target": _target_col_for_horizon(horizon),
        })
    return output


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Load candidates
    if not INPUT_PATH.exists():
        logger.error("Input file not found: %s", INPUT_PATH)
        sys.exit(1)

    with open(INPUT_PATH) as f:
        candidates: List[Dict[str, Any]] = json.load(f)

    logger.info("Loaded %d candidates from %s", len(candidates), INPUT_PATH)

    if not candidates:
        logger.error("No candidates to process")
        sys.exit(1)

    # Load OHLCV and prepare factor DataFrames
    evaluator = ExprEval()
    dfs: Dict[str, pl.DataFrame] = {}

    for symbol in SYMBOLS:
        try:
            ohlcv = load_ohlcv_from_db(symbol)
            dfs[symbol] = prepare_factor_df(ohlcv)
            logger.info("Loaded %d bars for %s", len(ohlcv), symbol)
        except Exception as e:
            logger.warning("Failed to load %s: %s", symbol, e)

    if not dfs:
        logger.error("No OHLCV data loaded for any symbol")
        sys.exit(1)

    # Compress
    compressed = compress(candidates, dfs, evaluator)

    if not compressed:
        logger.error("Compression produced zero factors")
        sys.exit(1)

    # Write output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = format_output(compressed)
    output_path = OUTPUT_DIR / "factor_pool.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    logger.info("Wrote %d factors to %s", len(output), output_path)


if __name__ == "__main__":
    main()
