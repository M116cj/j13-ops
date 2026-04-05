"""Adaptive bounds for CMA‑MAE search (C15)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np


HARD_BOUNDS = {
    "weights": (-5.0, 5.0),
    "entry": (0.5, 5.0),
    "exit": (0.05, 2.0),
    "stop": (0.5, 10.0),
    "pos_frac": (0.01, 0.25),
    "hold": (5.0, 500.0),
}


@dataclass
class AdaptiveBounds:
    min_elites: int = 30

    def hard(self, factor_count: int) -> Tuple[np.ndarray, np.ndarray]:
        low = [HARD_BOUNDS["weights"][0]] * factor_count
        high = [HARD_BOUNDS["weights"][1]] * factor_count
        low += [HARD_BOUNDS["entry"][0], HARD_BOUNDS["exit"][0], HARD_BOUNDS["stop"][0], HARD_BOUNDS["pos_frac"][0], HARD_BOUNDS["hold"][0]]
        high += [HARD_BOUNDS["entry"][1], HARD_BOUNDS["exit"][1], HARD_BOUNDS["stop"][1], HARD_BOUNDS["pos_frac"][1], HARD_BOUNDS["hold"][1]]
        return np.array(low, dtype=float), np.array(high, dtype=float)

    def soft(self, elites: np.ndarray, factor_count: int) -> Tuple[np.ndarray, np.ndarray]:
        hard_low, hard_high = self.hard(factor_count)
        if elites.shape[0] < self.min_elites:
            return hard_low, hard_high

        p5 = np.percentile(elites, 5, axis=0)
        p95 = np.percentile(elites, 95, axis=0)
        iqr = np.subtract(*np.percentile(elites, [75, 25], axis=0))
        low = np.maximum(hard_low, p5 - iqr)
        high = np.minimum(hard_high, p95 + iqr)

        # ensure bounds are not collapsed; keep at least 20% of hard range
        width_floor = 0.2 * (hard_high - hard_low)
        width = high - low
        too_small = width < width_floor
        high[too_small] = low[too_small] + width_floor[too_small]

        # enforce exit <= entry*0.8
        idx_exit = factor_count + 1
        idx_entry = factor_count
        high[idx_exit] = min(high[idx_exit], high[idx_entry] * 0.8)
        low[idx_exit] = min(low[idx_exit], high[idx_exit])
        return low, high


__all__ = ["AdaptiveBounds", "HARD_BOUNDS"]

