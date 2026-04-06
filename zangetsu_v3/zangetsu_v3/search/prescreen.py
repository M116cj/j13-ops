"""Analytical prescreen (Rung -1) based on mean/covariance.

V3.2: adds vectorized_prescreen() for batch operation on N candidates
in a single numpy call — no Python loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple

import numpy as np

__all__ = ["AnalyticalPrescreen", "vectorized_prescreen"]


def vectorized_prescreen(
    weights_batch: np.ndarray,
    factor_mu: np.ndarray,
    factor_cov: np.ndarray,
    threshold: float = 0.0,
) -> np.ndarray:
    """Vectorized Rung -1 prescreen (V3.2 Step 4).

    Parameters
    ----------
    weights_batch : np.ndarray
        Shape (N_candidates, N_factors).
    factor_mu : np.ndarray
        Shape (N_factors,). Mean return per factor.
    factor_cov : np.ndarray
        Shape (N_factors, N_factors). Covariance matrix.
    threshold : float
        Minimum predicted Sharpe to survive (default 0.0).

    Returns
    -------
    np.ndarray
        Boolean mask of shape (N_candidates,). True = survived.
    """
    # numerator = weights_batch @ factor_mu  → (N,)
    numerator = weights_batch @ factor_mu

    # denominator = sqrt(sum((weights_batch @ factor_cov) * weights_batch, axis=1))  → (N,)
    # This computes w @ cov @ w.T for each row without an explicit loop
    cov_product = weights_batch @ factor_cov  # (N, K)
    variance = np.sum(cov_product * weights_batch, axis=1)  # (N,)
    # Clamp negative variance (numerical noise) to 0
    variance = np.maximum(variance, 0.0)
    denominator = np.sqrt(variance) + 1e-8

    predicted_sharpe = numerator / denominator

    return predicted_sharpe > threshold


@dataclass
class AnalyticalPrescreen:
    """Single-candidate prescreen (retained for backward compatibility)."""
    threshold: float = 0.0
    min_factors: int = 5

    def predicted_sharpe(self, weights: np.ndarray, mu: np.ndarray, cov: np.ndarray) -> float:
        denom = float(weights @ cov @ weights.T)
        if denom <= 0:
            return -np.inf
        return float(weights @ mu) / np.sqrt(denom)

    def filter(
        self, candidates: Iterable[np.ndarray], mu: np.ndarray, cov: np.ndarray
    ) -> List[Tuple[np.ndarray, float]]:
        passed: List[Tuple[np.ndarray, float]] = []
        for w in candidates:
            if w.shape[0] < self.min_factors:
                continue
            ps = self.predicted_sharpe(w, mu, cov)
            if ps > self.threshold:
                passed.append((w, ps))
        return passed
