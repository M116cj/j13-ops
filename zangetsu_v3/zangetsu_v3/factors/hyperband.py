"""Hyperband-style pipeline: Rung-1 prescreen → Rung0 parallel → natural gap → Rung1 cross-symbol → tell-all."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

import numpy as np
from joblib import Parallel, delayed

from .scheduler import RegimeScheduler


# C04 fix: concrete evaluator builder that applies signal = factor_matrix @ weights
def make_evaluator(
    factor_matrix: np.ndarray,
    close: np.ndarray,
    regime_labels: np.ndarray,
    target_regime_id: int,
    cost_bps: float,
    funding_rate: float,
    engine,  # BacktestEngine Protocol
    n_weights: int,
) -> Callable[[np.ndarray], Tuple[float, np.ndarray]]:
    """
    Returns a closure that:
      1. Splits solution into weights (first n_weights) + params (remaining 5)
      2. Computes signal = factor_matrix @ weights  (C04 — one matmul)
      3. Runs backtest
      4. Returns (fitness, measures)
    """
    def evaluator(solution: np.ndarray) -> Tuple[float, np.ndarray]:
        weights = solution[:n_weights]
        params = {
            "entry_thr":  float(solution[n_weights]),
            "exit_thr":   float(solution[n_weights + 1]),
            "stop_mult":  float(solution[n_weights + 2]),
            "pos_frac":   float(solution[n_weights + 3]),
            "hold_max":   int(solution[n_weights + 4]),
        }
        # C04: signal = factor_matrix @ weights (one matmul at deploy time)
        signal = factor_matrix @ weights
        result = engine.evaluate(
            signal, close, params, regime_labels, target_regime_id, cost_bps, funding_rate
        )
        fitness = float(result.sharpe)
        measures = np.array([result.sharpe, result.max_drawdown], dtype=float)
        return fitness, measures

    return evaluator


def _natural_gap_cutoff(scores: np.ndarray, min_cutoff: int = 3) -> np.ndarray:
    """C14: promote top candidates above natural gap in sorted fitness."""
    if len(scores) <= min_cutoff:
        return np.ones(len(scores), dtype=bool)
    order = np.argsort(scores)[::-1]
    sorted_s = scores[order]
    gaps = np.diff(sorted_s)  # negative values (scores descending)
    gap_idx = int(np.argmin(gaps))  # largest drop
    cutoff = max(gap_idx + 1, min_cutoff)
    mask = np.zeros(len(scores), dtype=bool)
    mask[order[:cutoff]] = True
    return mask


@dataclass
class HyperbandPipeline:
    scheduler: RegimeScheduler
    n_jobs: int = 4          # C11: parallel jobs for Rung0
    qd_history: List[float] = field(default_factory=list)

    def tell_all(self, objectives: List[float], measures: List[np.ndarray]) -> None:
        """Tell ALL candidates back to scheduler (C14 — including eliminated ones)."""
        self.scheduler.tell(objectives, measures)
        stats = self.scheduler.result_archive.stats
        self.qd_history.append(float(stats["qd_score"]))

    def run(self, generations: int, evaluator: Callable[[np.ndarray], Tuple[float, np.ndarray]]) -> None:
        """C11: parallel evaluation via joblib. C14: tell all results back."""
        for _ in range(generations):
            sols = self.scheduler.ask()

            # C11: parallel evaluation
            results: List[Tuple[float, np.ndarray]] = Parallel(n_jobs=self.n_jobs, backend="loky")(
                delayed(evaluator)(s) for s in sols
            )

            objs = [r[0] for r in results]
            meas = [r[1] for r in results]
            self.tell_all(objs, meas)


__all__ = ["HyperbandPipeline", "make_evaluator", "_natural_gap_cutoff"]
