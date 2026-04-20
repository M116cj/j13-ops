"""Market-regime tagger for the A4 gate.

Uses BTC 20-bar momentum and 20-bar realised volatility to label every
bar as `bull`, `bear`, or `chop`. The A4 gate requires an alpha to
maintain win-rate > 0.40 in its training regime AND in at least one
other regime — measured on the last third of the holdout, which is
independent of A2 and A3 data.

Thresholds are parameters of the pipeline; defaults tuned to 1-minute
BTC bars. Override via settings if bar-resolution changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np


class Regime(str, Enum):
    BULL = "bull"
    BEAR = "bear"
    CHOP = "chop"


@dataclass(frozen=True)
class RegimeParams:
    window: int = 20
    momentum_threshold: float = 0.002  # 0.2% over the window
    vol_threshold: float = 0.0015  # 0.15% stdev of returns


def tag_regime(close: np.ndarray, params: RegimeParams | None = None) -> np.ndarray:
    """Return per-bar regime labels aligned with `close`.

    The first `window` bars are labelled CHOP because there is not
    enough history to compute the rolling statistics. Downstream
    callers should either skip these bars or tolerate the CHOP label.
    """
    p = params or RegimeParams()
    close = np.asarray(close, dtype=np.float64)
    n = close.size
    if n <= p.window:
        return np.full(n, Regime.CHOP.value, dtype=object)

    # 20-bar return
    ret = np.zeros(n, dtype=np.float64)
    ret[p.window :] = (close[p.window :] - close[: -p.window]) / np.maximum(
        close[: -p.window], 1e-10
    )

    # rolling stdev of 1-bar log returns as a volatility proxy
    logret = np.zeros(n, dtype=np.float64)
    logret[1:] = np.log(close[1:] / np.maximum(close[:-1], 1e-10))
    vol = np.zeros(n, dtype=np.float64)
    for i in range(p.window, n):
        vol[i] = float(np.std(logret[i - p.window + 1 : i + 1]))

    labels = np.full(n, Regime.CHOP.value, dtype=object)
    for i in range(p.window, n):
        if vol[i] > p.vol_threshold:
            labels[i] = Regime.CHOP.value
        elif ret[i] > p.momentum_threshold:
            labels[i] = Regime.BULL.value
        elif ret[i] < -p.momentum_threshold:
            labels[i] = Regime.BEAR.value
        else:
            labels[i] = Regime.CHOP.value
    return labels


def dominant_regime(labels: np.ndarray) -> str:
    """Return the most common regime label in a sequence."""
    unique, counts = np.unique(labels, return_counts=True)
    if len(unique) == 0:
        return Regime.CHOP.value
    return str(unique[counts.argmax()])
