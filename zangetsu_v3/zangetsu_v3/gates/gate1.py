"""Gate 1: trimmed_min + Sum of Squares threshold (C06)."""

from __future__ import annotations

import numpy as np

from zangetsu_v3.search.backtest import BacktestResult


def trimmed_min(pnl: np.ndarray, segments: int = 5) -> float:
    if pnl.size == 0:
        return 0.0
    parts = np.array_split(pnl, segments)
    seg_pnl = [np.nansum(p) for p in parts]
    if len(seg_pnl) <= 1:
        return seg_pnl[0] if seg_pnl else 0.0
    worst_idx = int(np.argmin(seg_pnl))
    remaining = [v for i, v in enumerate(seg_pnl) if i != worst_idx]
    return float(np.min(remaining)) if remaining else 0.0


class Gate1:
    def __init__(self, sos_threshold: float = 1.0):
        self.sos_threshold = sos_threshold

    def evaluate(self, result: BacktestResult) -> bool:
        sos = float(np.nansum(np.square(result.pnl)))
        tmin = trimmed_min(result.pnl)
        self.last_trimmed_min = tmin
        self.last_sos = sos
        return sos > self.sos_threshold and tmin > 0


__all__ = ["Gate1", "trimmed_min"]

