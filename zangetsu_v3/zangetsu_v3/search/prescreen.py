"""Analytical prescreen (Rung‑1) based on mean/covariance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple

import numpy as np


@dataclass
class AnalyticalPrescreen:
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


__all__ = ["AnalyticalPrescreen"]

