"""P-value computation against random baseline distribution.

Computes the probability that a champion's win rate (or other metric)
could have been produced by random signals — i.e., the null hypothesis.

Uses z-score against the empirical random baseline stored in
config/random_baseline.json.

Bonferroni correction available for multiple testing (N = total champions tested).
"""
import json
import os
from math import erfc, sqrt
from typing import Optional


_BASELINE_CACHE: Optional[dict] = None
_BASELINE_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', 'config', 'random_baseline.json'
)


def load_baseline(path: Optional[str] = None) -> dict:
    """Load random baseline statistics. Cached after first load."""
    global _BASELINE_CACHE
    if _BASELINE_CACHE is not None:
        return _BASELINE_CACHE
    p = path or _BASELINE_PATH
    with open(p) as f:
        _BASELINE_CACHE = json.load(f)
    return _BASELINE_CACHE


def compute_p_value(
    win_rate: float,
    n_trades: int,
    baseline: Optional[dict] = None,
) -> float:
    """Compute one-sided p-value for win rate against random baseline.

    P-value = probability of observing this WR or better by pure chance.
    Uses z-score against the empirical distribution of random signal WRs.

    Args:
        win_rate: Champion's win rate (0-1).
        n_trades: Number of trades (low trade count -> conservative).
        baseline: Random baseline dict. Loaded from file if None.

    Returns:
        p-value in [0, 1]. Lower = more likely to be a real edge.
    """
    if n_trades < 5:
        return 1.0

    if baseline is None:
        baseline = load_baseline()

    wr_mean = baseline['wr_mean']
    wr_std = max(baseline['wr_std'], 1e-12)

    # Adjust std for trade count: fewer trades -> wider distribution
    # Standard error of WR ~ sqrt(p*(1-p)/n), scale baseline std accordingly
    baseline_n = baseline.get('trades_mean', 500)
    se_adjustment = sqrt(baseline_n / max(n_trades, 1))
    adjusted_std = wr_std * se_adjustment

    z = (win_rate - wr_mean) / adjusted_std

    # One-sided p-value from normal distribution (right tail)
    p = 0.5 * erfc(z / sqrt(2))
    return max(min(p, 1.0), 0.0)


def compute_pnl_p_value(
    net_pnl: float,
    baseline: Optional[dict] = None,
) -> float:
    """Compute one-sided p-value for PnL against random baseline."""
    if baseline is None:
        baseline = load_baseline()

    pnl_mean = baseline['pnl_mean']
    pnl_std = max(baseline['pnl_std'], 1e-12)

    z = (net_pnl - pnl_mean) / pnl_std
    p = 0.5 * erfc(z / sqrt(2))
    return max(min(p, 1.0), 0.0)


def bonferroni_threshold(n_tests: int, alpha: float = 0.05) -> float:
    """Return the Bonferroni-corrected significance threshold."""
    if n_tests <= 0:
        return alpha
    return alpha / n_tests


def is_significant(
    p_value: float,
    n_tests: int = 1,
    alpha: float = 0.05,
) -> bool:
    """Is this p-value significant after Bonferroni correction?"""
    return p_value < bonferroni_threshold(n_tests, alpha)
