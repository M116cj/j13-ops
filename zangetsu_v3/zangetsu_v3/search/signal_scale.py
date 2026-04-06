"""Signal scale estimator for deriving entry/exit threshold bounds.

Samples random weight vectors against a factor matrix to estimate
the typical signal standard deviation, then derives CMA-MAE search
bounds that match the actual signal scale.

Supports both static bootstrap factor matrices and dynamic factor pools
loaded from Arena 2 factor_pool.json.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np

__all__ = ["SignalScaleEstimator"]

logger = logging.getLogger(__name__)


class SignalScaleEstimator:
    """Estimate signal std from factor_matrix using random weight samples.

    Used before CMA-MAE search to derive entry/exit bounds that match
    the actual signal scale. Without this, thresholds can be orders of
    magnitude off from the signal range.

    Works with any number of factors — both the 15 hardcoded bootstrap
    factors and dynamically loaded factor pools from Arena 2.
    """

    def __init__(self, n_samples: int = 1000, seed: int = 0):
        self.n_samples = n_samples
        self.seed = seed
        self.median_std: float = 0.0
        self.n_factors: int = 0
        self.factor_source: str = ""

    def estimate(self, factor_matrix: np.ndarray, factor_source: str = "") -> float:
        """Estimate median std of signal = factor_matrix @ random_weights.

        Uses sigma=0.5 for random weights (matching CMA-ES initial sigma).
        Returns median_std. Stores it in self.median_std.

        Works with any (N, K) factor_matrix regardless of K — adapts
        the weight vector dimension to match the number of columns.

        Parameters
        ----------
        factor_matrix : np.ndarray
            Shape (n_bars, n_factors). May come from bootstrap or factor_pool.
        factor_source : str
            Label for logging (e.g. 'bootstrap', 'factor_pool').
        """
        if factor_matrix.ndim != 2 or factor_matrix.shape[1] == 0:
            logger.warning("Invalid factor_matrix shape %s — using default median_std=1.0", factor_matrix.shape)
            self.median_std = 1.0
            self.n_factors = 0
            return self.median_std

        rng = np.random.default_rng(self.seed)
        n_weights = factor_matrix.shape[1]
        self.n_factors = n_weights
        self.factor_source = factor_source

        stds = np.empty(self.n_samples)
        for i in range(self.n_samples):
            w = rng.standard_normal(n_weights) * 0.5
            sig = factor_matrix @ w
            stds[i] = np.std(sig)
        self.median_std = float(np.median(stds))
        if self.median_std < 1e-12 or not np.isfinite(self.median_std):
            self.median_std = 1.0

        if factor_source:
            logger.info(
                "SignalScaleEstimator: %d factors from %s → median_std=%.6f",
                n_weights, factor_source, self.median_std,
            )
        return self.median_std

    def derive_bounds(self) -> dict:
        """Derive HFT parameter bounds from estimated signal scale.

        C09 HFT bounds:
        - entry: [0.3sigma, 1.5sigma]
        - exit:  [0.05sigma, 0.8sigma]
        - stop_mult: [0.5, 5.0] (signal-independent)
        - pos_frac: [0.01, 0.25]
        - hold_max: [3, 30] (HFT: 3-30 minutes)

        Returns dict with numpy array 'param_bounds' (5x2) and individual ranges.
        """
        s = self.median_std
        bounds = np.array([
            [0.3 * s, 1.5 * s],    # entry_thr
            [0.05 * s, 0.8 * s],   # exit_thr
            [0.5, 5.0],            # stop_mult
            [0.01, 0.25],          # pos_frac
            [3, 30],               # hold_max: HFT 3-30 bars
        ], dtype=np.float64)
        return {
            "param_bounds": bounds,
            "median_signal_std": s,
            "entry_range": (bounds[0, 0], bounds[0, 1]),
            "exit_range": (bounds[1, 0], bounds[1, 1]),
        }
