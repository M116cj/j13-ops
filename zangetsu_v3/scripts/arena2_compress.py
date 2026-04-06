"""Arena 2 — compress Arena 1's raw PySR signal pool into 10-20 orthogonal factors.

V3.2 DB-backed:
  Reads:  SELECT * FROM factor_candidates WHERE regime=$1
  Writes: INSERT INTO factor_pool (regime, name, ast_json, raw_expression,
          lookback, score, pool_version, pairwise_max_corr, avg_corr_with_target)

Dedup logic (per regime):
  1. Evaluate each candidate expression on OHLCV data to get factor time series.
  2. Remove weak factors (abs(corr with target) < 0.01 across all segments).
  3. Greedy dedup: sort by score desc, add one-by-one, skip if pairwise corr > 0.7.
  4. If remaining > 20: keep top 20 by score.
  5. If remaining < 10: relax threshold from 0.7 → 0.8 and repeat.
  6. pool_version = current timestamp (same for all factors in one run).
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
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
DB_DSN = os.environ.get(
    "ZV3_DB_DSN",
    "dbname=zangetsu user=zangetsu password=9c424966bebb05a42966186bb22d7480 host=127.0.0.1 port=5432",
)
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]

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
    30: "next_30_bar_return",
}


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
def _get_conn():
    """Create a new psycopg2 connection."""
    try:
        import psycopg2
    except ImportError:
        raise ImportError("psycopg2 required — pip install psycopg2-binary")
    return psycopg2.connect(DB_DSN)


def load_candidates_from_db(regime: str) -> List[Dict[str, Any]]:
    """SELECT * FROM factor_candidates WHERE regime=$1, return as list of dicts."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, source, regime, horizon, ast_json, raw_expression, "
            "loss, score, corr_h1, corr_h5, corr_h10, corr_h30, lookback, run_id "
            "FROM factor_candidates WHERE regime = %s",
            (regime,),
        )
        cols = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        cur.close()
    finally:
        conn.close()

    candidates = []
    for row in rows:
        d = dict(zip(cols, row))
        # Normalise: ast_json may already be dict from psycopg2 jsonb handling
        if isinstance(d.get("ast_json"), str):
            try:
                d["ast_json"] = json.loads(d["ast_json"])
            except (json.JSONDecodeError, TypeError):
                pass
        # Ensure expression field exists (used by compression logic)
        if not d.get("raw_expression"):
            d["raw_expression"] = ""
        d["expression"] = d["raw_expression"]
        candidates.append(d)

    return candidates


def get_all_regimes() -> List[str]:
    """Return distinct regimes from factor_candidates."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT regime FROM factor_candidates ORDER BY regime")
        regimes = [row[0] for row in cur.fetchall()]
        cur.close()
    finally:
        conn.close()
    return regimes


def insert_factor_pool(
    factors: List[Dict[str, Any]],
    regime: str,
    pool_version: datetime,
) -> int:
    """INSERT compressed factors into factor_pool. Returns count inserted."""
    if not factors:
        return 0

    conn = _get_conn()
    try:
        cur = conn.cursor()
        inserted = 0
        for f in factors:
            ast_json = f.get("ast_json")
            if ast_json is not None and not isinstance(ast_json, str):
                ast_json = json.dumps(ast_json)

            cur.execute(
                "INSERT INTO factor_pool "
                "(regime, name, ast_json, raw_expression, lookback, score, "
                " pool_version, pairwise_max_corr, avg_corr_with_target) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    regime,
                    f.get("name", ""),
                    ast_json,
                    f.get("raw_expression", ""),
                    f.get("lookback"),
                    f.get("score"),
                    pool_version,
                    f.get("pairwise_max_corr"),
                    f.get("avg_corr_with_target"),
                ),
            )
            inserted += 1

        conn.commit()
        cur.close()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return inserted


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_ohlcv_from_db(symbol: str, limit: int = 50_000) -> pl.DataFrame:
    """Load OHLCV bars from PostgreSQL ohlcv_1m table."""
    conn = _get_conn()
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
    """Compute HFT factor columns and forward returns on OHLCV data."""
    hft = compute_hft_factors(ohlcv)
    combined = pl.concat([ohlcv, hft], how="horizontal")

    close = combined["close"].to_numpy().astype(np.float64)
    n = len(close)
    for horizon in [1, 3, 5, 10, 20, 30]:
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
    """Evaluate a PySR expression string against the factor DataFrame."""
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
) -> Tuple[List[Dict[str, Any]], Dict[int, float]]:
    """Remove factors whose abs(corr) with target < threshold across ALL targets.

    Returns (kept_candidates, avg_corr_map) where avg_corr_map[new_index] = avg abs corr with targets.
    """
    kept = []
    avg_corr_map: Dict[int, float] = {}
    for i, cand in enumerate(candidates):
        if i not in series_map:
            continue
        factor_ts = series_map[i]
        # Compute correlations with all target horizons
        corrs = []
        for h, tgt in target_series.items():
            corrs.append(abs(_pearson_corr(factor_ts, tgt)))

        if not corrs:
            continue

        max_corr = max(corrs)
        if max_corr >= threshold:
            avg_corr_map[len(kept)] = float(np.mean(corrs))
            kept.append(cand)
        else:
            logger.info(
                "Removed weak candidate: %s (max target corr %.6f < %.4f)",
                cand.get("raw_expression", "?"), max_corr, threshold,
            )
    return kept, avg_corr_map


def deduplicate(
    candidates: List[Dict[str, Any]],
    series_map: Dict[int, np.ndarray],
    threshold: float,
) -> Tuple[List[Dict[str, Any]], Dict[int, float]]:
    """Greedy dedup: sort by score desc, add one-by-one, skip if pairwise corr > threshold.

    Returns (kept_candidates, pairwise_max_corr_map) where
    pairwise_max_corr_map[new_index] = max abs corr with any other kept factor.
    """
    valid = [(i, c) for i, c in enumerate(candidates) if i in series_map]
    if not valid:
        return [], {}

    # Sort by score descending (higher = better)
    valid.sort(key=lambda x: x[1].get("score", 0.0), reverse=True)

    kept_indices: List[int] = []
    kept_series: List[np.ndarray] = []
    pairwise_max_map: Dict[int, float] = {}  # keyed by position in result list

    for idx, cand in valid:
        ts = series_map[idx]
        max_corr_with_kept = 0.0
        is_redundant = False
        for existing_ts in kept_series:
            c = abs(_pearson_corr(ts, existing_ts))
            if c > max_corr_with_kept:
                max_corr_with_kept = c
            if c > threshold:
                is_redundant = True
                break
        if not is_redundant:
            pairwise_max_map[len(kept_indices)] = max_corr_with_kept
            kept_indices.append(idx)
            kept_series.append(ts)

    return [candidates[i] for i in kept_indices], pairwise_max_map


def compress_regime(
    candidates: List[Dict[str, Any]],
    dfs: Dict[str, pl.DataFrame],
    evaluator: ExprEval,
    regime: str,
) -> List[Dict[str, Any]]:
    """Compression pipeline for a single regime.

    Returns list of 10-20 compressed factor dicts with metadata fields:
    name, raw_expression, ast_json, lookback, score, pairwise_max_corr, avg_corr_with_target.
    """
    if not candidates:
        logger.warning("[%s] No candidates provided", regime)
        return []

    symbol_list = list(dfs.keys())
    primary_symbol = symbol_list[0]
    df = dfs[primary_symbol]

    # --- Step 1: Evaluate all expressions across all symbols ---
    series_map: Dict[int, np.ndarray] = {}
    for i, cand in enumerate(candidates):
        expr = cand.get("raw_expression") or cand.get("expression", "")
        if not expr:
            continue
        symbol_series = []
        for sym, sym_df in dfs.items():
            ts = evaluate_expression(expr, sym_df, evaluator)
            if ts is not None and np.isfinite(ts).sum() > 30:
                symbol_series.append(ts)
        if symbol_series:
            min_len = min(len(s) for s in symbol_series)
            truncated = [s[:min_len] for s in symbol_series]
            avg_ts = np.nanmean(truncated, axis=0)
            if np.isfinite(avg_ts).sum() > 30:
                series_map[i] = avg_ts

    logger.info("[%s] Evaluated %d / %d candidates (across %d symbols)",
                regime, len(series_map), len(candidates), len(symbol_list))

    if not series_map:
        logger.warning("[%s] No candidates evaluated successfully", regime)
        return []

    # --- Step 2: Build target return series (primary symbol) ---
    target_series: Dict[int, np.ndarray] = {}
    for horizon in [1, 3, 5, 10, 20, 30]:
        col = _target_col_for_horizon(horizon)
        if col in df.columns:
            target_series[horizon] = df[col].to_numpy().astype(np.float64)

    # --- Step 3: Remove weak candidates ---
    filtered, avg_corr_map = remove_weak_candidates(candidates, series_map, target_series)

    # Rebuild series_map for filtered list
    filtered_ids = {id(c) for c in filtered}
    filtered_series: Dict[int, np.ndarray] = {}
    j = 0
    for i, cand in enumerate(candidates):
        if id(cand) in filtered_ids:
            if i in series_map:
                filtered_series[j] = series_map[i]
            j += 1

    logger.info("[%s] After weak removal: %d candidates", regime, len(filtered))

    # --- Step 4: Greedy dedup at tight threshold ---
    result, pairwise_map = deduplicate(filtered, filtered_series, DEDUP_THRESHOLD_TIGHT)

    # --- Step 5: Cap at MAX_FACTORS ---
    if len(result) > MAX_FACTORS:
        result.sort(key=lambda c: c.get("score", 0.0), reverse=True)
        result = result[:MAX_FACTORS]

    # --- Step 6: If < MIN_FACTORS, relax threshold and retry ---
    if len(result) < MIN_FACTORS:
        logger.info("[%s] Only %d factors after tight dedup; relaxing to %.2f",
                     regime, len(result), DEDUP_THRESHOLD_RELAXED)
        result, pairwise_map = deduplicate(filtered, filtered_series, DEDUP_THRESHOLD_RELAXED)
        if len(result) > MAX_FACTORS:
            result.sort(key=lambda c: c.get("score", 0.0), reverse=True)
            result = result[:MAX_FACTORS]

    logger.info("[%s] Final factor count: %d", regime, len(result))

    # --- Step 7: Build output dicts with DB-ready fields ---
    # Rebuild avg_corr for final result using filtered avg_corr_map
    # We need to match result items back to their filtered index
    filtered_id_to_idx = {id(c): idx for idx, c in enumerate(filtered)}
    output = []
    for i, cand in enumerate(result):
        filt_idx = filtered_id_to_idx.get(id(cand))
        avg_corr = avg_corr_map.get(filt_idx) if filt_idx is not None else None
        pw_max = pairwise_map.get(i)

        horizon = cand.get("lookback") or cand.get("horizon", 5)
        try:
            horizon = int(horizon)
        except (ValueError, TypeError):
            horizon = 5

        output.append({
            "name": f"factor_{i + 1:03d}",
            "raw_expression": cand.get("raw_expression", ""),
            "ast_json": cand.get("ast_json"),
            "lookback": horizon,
            "score": cand.get("score", 0.0),
            "pairwise_max_corr": pw_max,
            "avg_corr_with_target": avg_corr,
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

    # Determine pool_version — one timestamp for the entire run
    pool_version = datetime.now(timezone.utc)
    logger.info("Pool version (run timestamp): %s", pool_version.isoformat())

    # Discover regimes from DB
    regimes = get_all_regimes()
    if not regimes:
        logger.error("No regimes found in factor_candidates — nothing to compress")
        sys.exit(1)

    logger.info("Found %d regimes: %s", len(regimes), regimes)

    # Load OHLCV and prepare factor DataFrames (shared across regimes)
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

    # Process each regime independently
    total_inserted = 0
    for regime in regimes:
        logger.info("--- Processing regime: %s ---", regime)
        candidates = load_candidates_from_db(regime)
        if not candidates:
            logger.warning("[%s] No candidates in DB — skipping", regime)
            continue

        logger.info("[%s] Loaded %d candidates from factor_candidates", regime, len(candidates))
        compressed = compress_regime(candidates, dfs, evaluator, regime)

        if not compressed:
            logger.warning("[%s] Compression produced zero factors", regime)
            continue

        count = insert_factor_pool(compressed, regime, pool_version)
        total_inserted += count
        logger.info("[%s] Inserted %d factors into factor_pool", regime, count)

    logger.info("=== Arena 2 complete: %d total factors inserted across %d regimes ===",
                total_inserted, len(regimes))

    if total_inserted == 0:
        logger.error("No factors were inserted — check factor_candidates data")
        sys.exit(1)


if __name__ == "__main__":
    main()


# Compatibility shim for tests (V3.2: output goes to DB, not JSON)
def format_output(factors):
    result = []
    for i, f in enumerate(factors):
        entry = {"index": i, **f}
        if "name" not in entry:
            entry["name"] = f"factor_{i + 1:03d}"
        if "expression" not in entry and "raw_expression" in entry:
            entry["expression"] = entry["raw_expression"]
        if "raw_expression" not in entry and "expression" in entry:
            entry["raw_expression"] = entry["expression"]
        if "target" not in entry:
            horizon = entry.get("horizon", entry.get("lookback", 5))
            entry["target"] = f"next_{horizon}_bar_return"
        if "regime" not in entry:
            entry["regime"] = entry.get("source_regime", "UNKNOWN")
        if "source_regime" not in entry:
            entry["source_regime"] = entry.get("regime", "UNKNOWN")
        if "source_target" not in entry:
            entry["source_target"] = entry.get("target", "")
        if "pysr_loss" not in entry:
            entry["pysr_loss"] = float(entry.get("loss", 0.0))
        if "pysr_score" not in entry:
            entry["pysr_score"] = float(entry.get("score", 0.0))
        if "lookback" not in entry:
            entry["lookback"] = int(entry.get("horizon", 5))
        if "loss" not in entry:
            entry["loss"] = entry.get("pysr_loss", 0.0)
        entry["loss"] = float(entry["loss"])
        result.append(entry)
    return result
