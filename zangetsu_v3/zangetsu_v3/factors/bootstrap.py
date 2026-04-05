"""Bootstrap factor definitions and computation helpers (Tier 2)."""

from __future__ import annotations

from typing import Dict, List, Tuple

import polars as pl

from .expr_eval import ExprEval


# Exact AST strings per requirement
BOOTSTRAP_FACTORS: List[Tuple[str, str]] = [
    ("momentum_5", "ts_delta(close,5)"),
    ("momentum_10", "ts_delta(close,10)"),
    ("momentum_20", "ts_delta(close,20)"),
    ("ts_rank_20", "ts_rank(close,20)"),
    ("vol_10", "ts_std(close,10)"),
    ("vol_50", "ts_std(close,50)"),
    ("vol_ratio", "ts_std(close,10)/ts_std(close,50)"),
    ("bar_range", "(high-low)/close"),
    ("vol_rank_20", "ts_rank(volume,20)"),
    ("vol_ratio_50", "volume/ts_mean(volume,50)"),
    ("mean_rev_20", "close/ts_mean(close,20)-1"),
    ("mean_rev_50", "close/ts_mean(close,50)-1"),
    ("corr_cv_30", "ts_corr(close,volume,30)"),
    ("ret_skew_20", "ts_skew(ts_delta(close,1),20)"),
    ("high_low_ma", "(ts_max(high,20)-ts_min(low,20))/ts_mean(close,20)"),
]


def compute_factor_matrix(df: pl.DataFrame, expr: ExprEval | None = None) -> pl.DataFrame:
    """Compute all bootstrap factors for the provided OHLCV frame.

    Parameters
    ----------
    df : pl.DataFrame
        Input frame must contain columns ``close``, ``high``, ``low``,
        and ``volume``.
    expr : ExprEval, optional
        Reusable evaluator; if omitted a fresh instance is used.
    """

    evaluator = expr or ExprEval()
    factor_cols: Dict[str, pl.Series] = {}
    for name, expression in BOOTSTRAP_FACTORS:
        values = evaluator.eval(expression, df)
        factor_cols[name] = pl.Series(name, values)

    return pl.DataFrame(factor_cols)


__all__ = ["BOOTSTRAP_FACTORS", "compute_factor_matrix"]

