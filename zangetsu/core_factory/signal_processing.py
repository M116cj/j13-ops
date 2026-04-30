"""Signal-processing helpers for 0-9AC Round 2.

Two additions over the 0-9AB pipeline:
1. p99 absolute-magnitude value clipping (used for axis H).
2. Band-crossing trigger (used for axis D, replacing pure sign-flip).

Both are pure-function, shadow-only, and produce metadata that the runner
serialises into shadow_outputs alongside per-candidate results.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

import numpy as np


@dataclass
class ClipMetadata:
    enabled: bool
    method: str
    threshold: float
    pre_clip_min: float
    pre_clip_max: float
    pre_clip_p99_abs: float
    post_clip_min: float
    post_clip_max: float
    pre_variance: float
    post_variance: float

    def to_dict(self) -> dict:
        return asdict(self)


def apply_p99_abs_clip(signal: np.ndarray) -> tuple[np.ndarray, ClipMetadata]:
    """Clip |signal| at the 99th percentile of finite |signal|.

    Replaces inf/-inf with finite p99 magnitude. NaN remains NaN (callers
    must mask). Returns (clipped, metadata).
    """
    if signal.size == 0:
        meta = ClipMetadata(False, 'p99_abs', 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        return signal, meta
    finite = np.isfinite(signal)
    finite_vals = signal[finite]
    if finite_vals.size == 0:
        meta = ClipMetadata(False, 'p99_abs', 0.0, float('nan'), float('nan'),
                            float('nan'), float('nan'), float('nan'), 0.0, 0.0)
        return signal.copy(), meta
    pre_min = float(np.min(finite_vals))
    pre_max = float(np.max(finite_vals))
    pre_var = float(np.var(finite_vals))
    abs_vals = np.abs(finite_vals)
    threshold = float(np.percentile(abs_vals, 99.0))
    if threshold <= 0:
        # Degenerate — all values zero. Nothing to clip.
        meta = ClipMetadata(True, 'p99_abs', threshold, pre_min, pre_max,
                            threshold, pre_min, pre_max, pre_var, pre_var)
        return signal.copy(), meta
    out = np.where(np.isfinite(signal), np.clip(signal, -threshold, threshold), signal)
    out = out.astype(signal.dtype, copy=False)
    finite_post = out[np.isfinite(out)]
    post_min = float(np.min(finite_post)) if finite_post.size else float('nan')
    post_max = float(np.max(finite_post)) if finite_post.size else float('nan')
    post_var = float(np.var(finite_post)) if finite_post.size else 0.0
    meta = ClipMetadata(True, 'p99_abs', threshold, pre_min, pre_max,
                        threshold, post_min, post_max, pre_var, post_var)
    return out, meta


def signal_to_trades_sign_flip(
    signal: np.ndarray, close: np.ndarray, intended_side_mode: str,
) -> tuple[list[float], int, int]:
    """Original 0-9AB trigger: open on sign change, close on next sign change."""
    if len(signal) < 3 or len(close) != len(signal):
        return [], 0, 0
    sgn = np.sign(signal)
    returns: list[float] = []
    n_long = 0
    n_short = 0
    pos = 0
    entry_px = 0.0
    for i in range(1, len(sgn)):
        s_now = sgn[i]
        if pos == 0:
            if s_now > 0 and intended_side_mode in {'LONG', 'BOTH'}:
                pos = 1; entry_px = float(close[i]); n_long += 1
            elif s_now < 0 and intended_side_mode in {'SHORT', 'BOTH'}:
                pos = -1; entry_px = float(close[i]); n_short += 1
            continue
        if (pos == 1 and s_now <= 0) or (pos == -1 and s_now >= 0):
            exit_px = float(close[i])
            if entry_px > 0:
                if pos == 1:
                    returns.append((exit_px - entry_px) / entry_px * 10_000.0)
                else:
                    returns.append((entry_px - exit_px) / entry_px * 10_000.0)
            pos = 0
            if s_now > 0 and intended_side_mode in {'LONG', 'BOTH'}:
                pos = 1; entry_px = float(close[i]); n_long += 1
            elif s_now < 0 and intended_side_mode in {'SHORT', 'BOTH'}:
                pos = -1; entry_px = float(close[i]); n_short += 1
    return returns, n_long, n_short


def signal_to_trades_band_crossing(
    signal: np.ndarray, close: np.ndarray, intended_side_mode: str,
    *, band_k: float, rolling_sigma_window: int,
) -> tuple[list[float], int, int]:
    """Round 2 trigger for D: open when signal crosses ±k * rolling_sigma.

    LONG: open when signal crosses up through +k*sigma; close when crosses
    back below 0 or down through -k*sigma.
    SHORT: open when signal crosses down through -k*sigma; close when crosses
    back above 0 or up through +k*sigma.
    """
    n = len(signal)
    if n < max(rolling_sigma_window + 2, 3) or len(close) != n:
        return [], 0, 0
    # Rolling sigma (causal, NaN-safe). Replace inf with 0 for sigma stability.
    sig = np.where(np.isfinite(signal), signal, 0.0).astype(np.float64)
    # Compute rolling std using cumulative sums.
    csum = np.cumsum(sig)
    csum2 = np.cumsum(sig * sig)
    w = rolling_sigma_window
    rolling_std = np.zeros(n, dtype=np.float64)
    for i in range(n):
        if i < w:
            rolling_std[i] = 0.0
            continue
        s = csum[i] - csum[i - w]
        s2 = csum2[i] - csum2[i - w]
        mean = s / w
        var = max(0.0, s2 / w - mean * mean)
        rolling_std[i] = np.sqrt(var)
    upper = band_k * rolling_std
    lower = -band_k * rolling_std
    returns: list[float] = []
    n_long = 0
    n_short = 0
    pos = 0
    entry_px = 0.0
    for i in range(1, n):
        prev = sig[i - 1]; cur = sig[i]
        u_now = upper[i]; l_now = lower[i]
        if rolling_std[i] <= 0:
            continue  # band undefined
        if pos == 0:
            if cur > u_now and prev <= upper[i - 1] and intended_side_mode in {'LONG', 'BOTH'}:
                pos = 1; entry_px = float(close[i]); n_long += 1
            elif cur < l_now and prev >= lower[i - 1] and intended_side_mode in {'SHORT', 'BOTH'}:
                pos = -1; entry_px = float(close[i]); n_short += 1
            continue
        # exit conditions
        if pos == 1 and (cur <= 0 or cur < l_now):
            exit_px = float(close[i])
            if entry_px > 0:
                returns.append((exit_px - entry_px) / entry_px * 10_000.0)
            pos = 0
            # potential immediate flip to short
            if cur < l_now and intended_side_mode in {'SHORT', 'BOTH'}:
                pos = -1; entry_px = float(close[i]); n_short += 1
        elif pos == -1 and (cur >= 0 or cur > u_now):
            exit_px = float(close[i])
            if entry_px > 0:
                returns.append((entry_px - exit_px) / entry_px * 10_000.0)
            pos = 0
            if cur > u_now and intended_side_mode in {'LONG', 'BOTH'}:
                pos = 1; entry_px = float(close[i]); n_long += 1
    return returns, n_long, n_short
