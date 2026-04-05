"""Regime-specific pyribs Scheduler wrapper (C03, C11)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from ribs.archives import GridArchive
from ribs.emitters import EvolutionStrategyEmitter
from ribs.schedulers import Scheduler

# Fallback bounds (used when signal scale is not provided)
DEFAULT_PARAM_BOUNDS = np.array([
    [0.1, 5.0],     # entry_thr
    [0.05, 2.0],    # exit_thr
    [0.5, 5.0],     # stop_mult
    [0.01, 0.25],   # pos_frac (Fix1: hard cap 0.25)
    [10, 480],       # hold_max
], dtype=float)


@dataclass
class RegimeScheduler:
    solution_dim: int
    n_weights: int = 15
    measure_bounds: Tuple[Tuple[float, float], Tuple[float, float]] = ((-5.0, 5.0), (0.0, 0.5))
    learning_rate: float = 0.15
    param_bounds: Optional[np.ndarray] = None
    median_signal_std: float = 1.0

    def __post_init__(self):
        self._param_bounds = self.param_bounds if self.param_bounds is not None else DEFAULT_PARAM_BOUNDS

        self.archive = GridArchive(
            solution_dim=self.solution_dim,
            dims=(20, 20),
            ranges=self.measure_bounds,
            learning_rate=self.learning_rate,
            threshold_min=-1e9,
        )

        # Fix4: x0 weights=0, params at normalized center (0.5)
        x0 = np.zeros(self.solution_dim)
        n_params = self.solution_dim - self.n_weights
        x0[self.n_weights:self.n_weights + n_params] = 0.5

        # Fix4: sigma0 scales with signal std
        # Weights sigma: if signal_std is small, weights need smaller perturbations
        sigma0 = min(0.5, self.median_signal_std * 0.3) if self.median_signal_std < 1.0 else 0.5

        emitter = EvolutionStrategyEmitter(
            self.archive,
            x0=x0,
            sigma0=sigma0,
            ranker="imp",
        )
        self.scheduler = Scheduler(self.archive, [emitter])

    def denormalize_params(self, solution: np.ndarray) -> dict:
        """Convert normalized [0,1] params back to real values with Fix1 hard clamp."""
        pb = self._param_bounds
        raw = solution[self.n_weights:]
        entry = float(pb[0, 0] + np.clip(raw[0], 0, 1) * (pb[0, 1] - pb[0, 0]))
        exit_ = float(pb[1, 0] + np.clip(raw[1], 0, 1) * (pb[1, 1] - pb[1, 0]))
        exit_ = float(np.clip(exit_, pb[1, 0], min(entry * 0.8, pb[1, 1])))
        return {
            "entry_thr":  entry,
            "exit_thr":   exit_,
            "stop_mult":  float(np.clip(pb[2, 0] + np.clip(raw[2], 0, 1) * (pb[2, 1] - pb[2, 0]), 0.5, 5.0)),
            "pos_frac":   float(np.clip(pb[3, 0] + np.clip(raw[3], 0, 1) * (pb[3, 1] - pb[3, 0]), 0.01, 0.25)),
            "hold_max":   int(np.clip(pb[4, 0] + np.clip(raw[4], 0, 1) * (pb[4, 1] - pb[4, 0]), 3, 30)),
        }

    def ask(self) -> List[np.ndarray]:
        return self.scheduler.ask()

    def tell(self, objectives: List[float], measures: List[np.ndarray]) -> None:
        self.scheduler.tell(objectives, measures)

    @property
    def result_archive(self):
        return self.archive


__all__ = ["RegimeScheduler", "DEFAULT_PARAM_BOUNDS"]
