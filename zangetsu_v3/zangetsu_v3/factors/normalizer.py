"""Robust z-score normalisation (median + MAD * 1.4826).

V3.2: Supports loading factor definitions from DB (factor_pool table)
with fallback to JSON file, then to hardcoded BOOTSTRAP_FACTORS.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import polars as pl


SCALE = 1.4826
EPS = 1e-9

DB_DSN = os.environ.get(
    "ZV3_DB_DSN",
    "dbname=zangetsu user=zangetsu password=REDACTED host=127.0.0.1 port=5432",
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DB-backed factor loading
# ---------------------------------------------------------------------------
def load_factor_pool_from_db(
    regime: str,
    pool_version: Optional[str] = None,
) -> Optional[List[Dict[str, Any]]]:
    """Load factor definitions from factor_pool table for a specific regime.

    If pool_version is None, loads the latest pool_version for the regime.

    Returns list of dicts with keys: name, raw_expression, ast_json, lookback,
    score, pairwise_max_corr, avg_corr_with_target, pool_version.
    Returns None if no data found or DB unavailable.
    """
    try:
        import psycopg2
    except ImportError:
        logger.warning("psycopg2 not installed — cannot load from DB")
        return None

    try:
        conn = psycopg2.connect(DB_DSN)
    except Exception as exc:
        logger.warning("Cannot connect to DB: %s — falling back", exc)
        return None

    try:
        cur = conn.cursor()
        if pool_version is not None:
            cur.execute(
                "SELECT name, raw_expression, ast_json, lookback, score, "
                "pairwise_max_corr, avg_corr_with_target, pool_version "
                "FROM factor_pool "
                "WHERE regime = %s AND pool_version = %s "
                "ORDER BY score DESC",
                (regime, pool_version),
            )
        else:
            # Latest pool_version for this regime
            cur.execute(
                "SELECT name, raw_expression, ast_json, lookback, score, "
                "pairwise_max_corr, avg_corr_with_target, pool_version "
                "FROM factor_pool "
                "WHERE regime = %s "
                "  AND pool_version = ("
                "    SELECT MAX(pool_version) FROM factor_pool WHERE regime = %s"
                "  ) "
                "ORDER BY score DESC",
                (regime, regime),
            )

        cols = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        cur.close()
    except Exception as exc:
        logger.warning("DB query failed: %s — falling back", exc)
        return None
    finally:
        conn.close()

    if not rows:
        logger.info("No factors in factor_pool for regime=%s — falling back", regime)
        return None

    factors = []
    for row in rows:
        d = dict(zip(cols, row))
        # Normalise ast_json
        if isinstance(d.get("ast_json"), str):
            try:
                d["ast_json"] = json.loads(d["ast_json"])
            except (json.JSONDecodeError, TypeError):
                pass
        factors.append(d)

    logger.info("Loaded %d factors from factor_pool for regime=%s (pool_version=%s)",
                len(factors), regime, factors[0].get("pool_version") if factors else "?")
    return factors


# ---------------------------------------------------------------------------
# JSON file-based loading (legacy fallback)
# ---------------------------------------------------------------------------
def load_factor_pool(
    pool_path: str | Path,
) -> Optional[List[Tuple[str, str]]]:
    """Load factor definitions from an Arena 2 factor_pool.json file.

    Returns a list of (name, expression) tuples compatible with
    BOOTSTRAP_FACTORS format, or None if the file does not exist or
    cannot be parsed.
    """
    path = Path(pool_path)
    if not path.exists():
        logger.info("factor_pool.json not found at %s — will use bootstrap factors", path)
        return None

    try:
        with open(path) as f:
            pool = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read factor_pool.json at %s: %s — falling back to bootstrap", path, exc)
        return None

    if not isinstance(pool, list) or len(pool) == 0:
        logger.warning("factor_pool.json is empty or not a list — falling back to bootstrap")
        return None

    factors: List[Tuple[str, str]] = []
    for entry in pool:
        name = entry.get("name", "")
        expression = entry.get("expression", "") or entry.get("raw_expression", "")
        if not name or not expression:
            logger.warning("Skipping factor pool entry with missing name/expression: %s", entry)
            continue
        factors.append((name, expression))

    if not factors:
        logger.warning("No valid factors in factor_pool.json — falling back to bootstrap")
        return None

    logger.info("Loaded %d factors from %s", len(factors), path)
    return factors


# ---------------------------------------------------------------------------
# Unified factor loading
# ---------------------------------------------------------------------------
def get_factors(
    pool_path: Optional[str | Path] = None,
    regime: Optional[str] = None,
    pool_version: Optional[str] = None,
) -> Tuple[List[Tuple[str, str]], str]:
    """Return (factors_list, source_label).

    Priority:
      1. DB (factor_pool table) if regime is provided
      2. JSON file (pool_path) if provided
      3. BOOTSTRAP_FACTORS

    factors_list is a list of (name, expression) tuples.
    source_label is 'factor_pool_db', 'factor_pool_json', or 'bootstrap'.
    """
    from .bootstrap import BOOTSTRAP_FACTORS

    # Try DB first when regime is specified
    if regime is not None:
        db_factors = load_factor_pool_from_db(regime, pool_version=pool_version)
        if db_factors is not None:
            pairs = []
            for f in db_factors:
                name = f.get("name", "")
                expr = f.get("raw_expression", "")
                if name and expr:
                    pairs.append((name, expr))
            if pairs:
                return pairs, "factor_pool_db"

    # Try JSON file
    if pool_path is not None:
        loaded = load_factor_pool(pool_path)
        if loaded is not None:
            return loaded, "factor_pool_json"

    logger.info("Using BOOTSTRAP_FACTORS (%d factors)", len(BOOTSTRAP_FACTORS))
    return list(BOOTSTRAP_FACTORS), "bootstrap"


def get_factors_with_metadata(
    regime: str,
    pool_version: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], str]:
    """Return (factors_with_metadata, source_label) from DB.

    Unlike get_factors(), this returns full dict records with all DB columns.
    Falls back to bootstrap as list of dicts with name/expression only.
    """
    from .bootstrap import BOOTSTRAP_FACTORS

    db_factors = load_factor_pool_from_db(regime, pool_version=pool_version)
    if db_factors is not None and len(db_factors) > 0:
        return db_factors, "factor_pool_db"

    # Fallback to bootstrap — convert to dict format
    bootstrap_dicts = [
        {"name": name, "raw_expression": expr, "lookback": None, "score": None}
        for name, expr in BOOTSTRAP_FACTORS
    ]
    logger.info("Falling back to BOOTSTRAP_FACTORS (%d factors) for regime=%s",
                len(bootstrap_dicts), regime)
    return bootstrap_dicts, "bootstrap"


@dataclass
class RobustNormalizer:
    medians: Dict[str, float] = field(default_factory=dict)
    scales: Dict[str, float] = field(default_factory=dict)

    def fit(self, df: pl.DataFrame) -> None:
        for col in df.columns:
            series = df[col]
            med = float(series.median())
            mad = float((series - med).abs().median())
            scale = max(mad * SCALE, EPS)
            self.medians[col] = med
            self.scales[col] = scale

    def transform(self, df: pl.DataFrame) -> pl.DataFrame:
        # RISK-1 fix: never auto-fit — caller must fit on TRAIN only before calling transform
        if not self.medians:
            raise RuntimeError(
                "RobustNormalizer.transform() called before fit(). "
                "Call fit() on TRAIN data only to prevent lookahead contamination."
            )
        out_cols = []
        for col in df.columns:
            med = self.medians[col]
            scale = self.scales[col]
            out_cols.append(((df[col] - med) / scale).alias(col))
        return pl.DataFrame({c.name: c for c in out_cols})

    def add_factor(self, name: str, series: pl.Series) -> pl.Series:
        med = float(series.median())
        mad = float((series - med).abs().median())
        scale = max(mad * SCALE, EPS)
        self.medians[name] = med
        self.scales[name] = scale
        return (series - med) / scale

    def to_dict(self) -> Dict[str, Any]:
        """Serialize normalization params for card.json."""
        return {
            "medians": dict(self.medians),
            "scales": dict(self.scales),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RobustNormalizer":
        """Deserialize normalization params from card.json."""
        norm = cls()
        norm.medians = dict(data.get("medians", {}))
        norm.scales = dict(data.get("scales", {}))
        return norm


__all__ = [
    "RobustNormalizer",
    "SCALE",
    "load_factor_pool",
    "load_factor_pool_from_db",
    "get_factors",
    "get_factors_with_metadata",
]
