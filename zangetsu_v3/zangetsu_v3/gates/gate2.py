"""Gate 2: Deflated Sharpe Ratio > 0.95 (Bailey–LdP 2014)."""

from __future__ import annotations

import numpy as np
from scipy.stats import norm

from zangetsu_v3.search.backtest import BacktestResult


def deflated_sharpe_ratio(sharpe: float, n: int, trials: int = 1) -> float:
    if n <= 2 or trials < 1:
        return 0.0
    # Expected maximum SR under multiple testing (Bailey & López de Prado 2014)
    # E[max SR] ≈ (1 - γ) * Φ^{-1}(1 - 1/trials) + γ * Φ^{-1}(1 - 1/(trials*e))
    # where γ = Euler–Mascheroni constant ≈ 0.5772
    gamma = 0.5772156649
    expected_max = (1 - gamma) * norm.ppf(1 - 1.0 / trials) + gamma * norm.ppf(
        1 - 1.0 / (trials * np.e)
    ) if trials > 1 else 0.0

    sr_std = np.sqrt((1 + 0.5 * sharpe ** 2) / max(n - 1, 1))
    z = (sharpe - expected_max) / max(sr_std, 1e-12)
    return float(norm.cdf(z))


class DeflatedSharpeGate:
    """Gate 2: DSR > threshold.

    n_trials accumulates across all evaluated candidates (RISK-4 fix).
    Call increment_trials(n) after each generation's evaluations.
    trials= init param preserved for backwards compatibility (treated as initial count).
    """

    def __init__(self, threshold: float = 0.95, trials: int = 0):
        self.threshold = threshold
        self._total_trials: int = trials  # seed with explicit count if provided
        self.last_dsr: float = 0.0

    def increment_trials(self, n: int = 1) -> None:
        """Accumulate evaluated candidate count. Call once per batch of evaluations."""
        self._total_trials += n

    @property
    def total_trials(self) -> int:
        return self._total_trials

    def gate(
        self,
        observed_sharpe: float,
        n_observations: int,
        skewness: float = 0.0,
        kurtosis: float = 0.0,
        n_trials: int | None = None,
        threshold: float | None = None,
    ) -> bool:
        """Returns True if DSR > threshold.

        n_trials: override accumulated count (for testing). Default = self._total_trials.
        """
        trials = n_trials if n_trials is not None else max(self._total_trials, 1)
        thr = threshold if threshold is not None else self.threshold
        dsr = deflated_sharpe_ratio(observed_sharpe, n_observations, trials)
        self.last_dsr = dsr
        return dsr > thr

    # backwards-compat alias used by tests
    def evaluate(self, result: BacktestResult) -> bool:
        pnl = result.pnl[np.isfinite(result.pnl)]
        return self.gate(result.sharpe, len(pnl))


__all__ = ["DeflatedSharpeGate", "deflated_sharpe_ratio"]
