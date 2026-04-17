"""V9 Numba CUDA batch backtest kernel.

Evaluates thousands of (entry_thr, exit_thr, atr_mult, tp_param) parameter
combinations in parallel on the GPU. The CPU fallback uses plain numpy
loops so the pipeline keeps working on machines without CUDA — e.g. the
developer laptop.

Signal convention
    * A position is opened when a pre-computed signal crosses above
      entry_thr (long) or below -entry_thr (short).
    * It closes when |signal| falls back below exit_thr, or on an ATR stop
      (atr_mult * atr[t] away from entry), or on a fixed take-profit
      (tp_param percent) — whichever comes first.
    * Everything is evaluated on close prices; no funding / fees modelled
      here (that's done in backtester.py for the champion only).

Usage
    from engine.components.cuda_backtest import batch_backtest
    pnl = batch_backtest(prices, signal, atr, params_list)

Params layout
    params[i] = [entry_thr, exit_thr, atr_mult, tp_param]

Returns
    np.ndarray of shape (n_combos,) dtype float32 — cumulative PnL per combo.
"""
from __future__ import annotations

import logging
import math
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# Numba import guard — never crash at import time on GPU-less systems
# ─────────────────────────────────────────────────────────────────────

HAS_NUMBA = False
HAS_CUDA = False
cuda = None  # type: ignore

try:
    from numba import cuda as _cuda  # type: ignore
    cuda = _cuda
    HAS_NUMBA = True
    try:
        HAS_CUDA = bool(cuda.is_available())
    except Exception as exc:  # pragma: no cover — driver missing etc.
        log.debug("cuda.is_available() raised: %s", exc)
        HAS_CUDA = False
except Exception as exc:  # pragma: no cover
    log.debug("numba.cuda not importable: %s", exc)
    HAS_NUMBA = False
    HAS_CUDA = False


# ─────────────────────────────────────────────────────────────────────
# CUDA kernel (compiled lazily so import is cheap on CPU-only hosts)
# ─────────────────────────────────────────────────────────────────────

_KERNEL = None


def _build_kernel():
    """Compile and return the CUDA kernel. Cached after first call."""
    global _KERNEL
    if _KERNEL is not None:
        return _KERNEL
    if not HAS_CUDA:
        raise RuntimeError("CUDA kernel requested but CUDA is not available")

    @cuda.jit  # type: ignore[misc]
    def batch_backtest_kernel(prices, signal, atr, params, results, n_bars):
        """One CUDA thread per parameter combo.

        Args:
            prices:  float32[n_bars]             — close prices, read-only
            signal:  float32[n_bars]             — pre-computed directional
                                                    signal in [-1, 1]
            atr:     float32[n_bars]             — ATR series (same length)
            params:  float32[n_combos, 4]        — [entry, exit, atr_mult, tp]
            results: float32[n_combos]           — output cumulative PnL
            n_bars:  int32                       — length of the series
        """
        idx = cuda.grid(1)
        n_combos = params.shape[0]
        if idx >= n_combos:
            return

        entry_thr = params[idx, 0]
        exit_thr = params[idx, 1]
        atr_mult = params[idx, 2]
        tp_param = params[idx, 3]

        position = 0           # -1 short, 0 flat, +1 long
        entry_price = 0.0
        entry_atr = 0.0
        pnl = 0.0

        for t in range(1, n_bars):
            px = prices[t]
            sg = signal[t]
            at = atr[t]

            if position == 0:
                # Entry gating — signal must exceed entry threshold.
                if sg > entry_thr:
                    position = 1
                    entry_price = px
                    entry_atr = at
                elif sg < -entry_thr:
                    position = -1
                    entry_price = px
                    entry_atr = at
            else:
                # Move = signed return since entry.
                if entry_price > 0.0:
                    move = (px - entry_price) / entry_price
                else:
                    move = 0.0
                if position < 0:
                    move = -move

                # ATR stop: hit when price ran atr_mult*entry_atr against us.
                stop_hit = False
                if entry_price > 0.0 and atr_mult > 0.0:
                    stop_dist = atr_mult * entry_atr / entry_price
                    if move <= -stop_dist:
                        stop_hit = True

                # Fixed TP in percent.
                tp_hit = (tp_param > 0.0) and (move >= tp_param)

                # Signal-decay exit.
                if position > 0:
                    decay = sg < exit_thr
                else:
                    decay = sg > -exit_thr

                if stop_hit or tp_hit or decay:
                    if stop_hit:
                        realized = -atr_mult * entry_atr / max(entry_price, 1e-8)
                    elif tp_hit:
                        realized = tp_param
                    else:
                        realized = move
                    pnl += realized
                    position = 0
                    entry_price = 0.0
                    entry_atr = 0.0

        # Mark-to-market any open position on the final bar.
        if position != 0 and entry_price > 0.0:
            final_move = (prices[n_bars - 1] - entry_price) / entry_price
            if position < 0:
                final_move = -final_move
            pnl += final_move

        results[idx] = pnl

    _KERNEL = batch_backtest_kernel
    return _KERNEL


# ─────────────────────────────────────────────────────────────────────
# CPU fallback — same semantics, pure numpy / python
# ─────────────────────────────────────────────────────────────────────

def _cpu_backtest(prices: np.ndarray, signal: np.ndarray, atr: np.ndarray,
                  params: np.ndarray) -> np.ndarray:
    n_combos = params.shape[0]
    n_bars = prices.shape[0]
    out = np.zeros(n_combos, dtype=np.float32)

    # Hoist into locals for speed.
    for idx in range(n_combos):
        entry_thr = float(params[idx, 0])
        exit_thr = float(params[idx, 1])
        atr_mult = float(params[idx, 2])
        tp_param = float(params[idx, 3])

        position = 0
        entry_price = 0.0
        entry_atr = 0.0
        pnl = 0.0

        for t in range(1, n_bars):
            px = float(prices[t])
            sg = float(signal[t])
            at = float(atr[t])

            if position == 0:
                if sg > entry_thr:
                    position = 1
                    entry_price = px
                    entry_atr = at
                elif sg < -entry_thr:
                    position = -1
                    entry_price = px
                    entry_atr = at
                continue

            if entry_price > 0.0:
                move = (px - entry_price) / entry_price
            else:
                move = 0.0
            if position < 0:
                move = -move

            stop_hit = False
            if entry_price > 0.0 and atr_mult > 0.0:
                stop_dist = atr_mult * entry_atr / entry_price
                if move <= -stop_dist:
                    stop_hit = True

            tp_hit = (tp_param > 0.0) and (move >= tp_param)

            if position > 0:
                decay = sg < exit_thr
            else:
                decay = sg > -exit_thr

            if stop_hit or tp_hit or decay:
                if stop_hit:
                    realized = -atr_mult * entry_atr / max(entry_price, 1e-8)
                elif tp_hit:
                    realized = tp_param
                else:
                    realized = move
                pnl += realized
                position = 0
                entry_price = 0.0
                entry_atr = 0.0

        if position != 0 and entry_price > 0.0:
            final_move = (float(prices[-1]) - entry_price) / entry_price
            if position < 0:
                final_move = -final_move
            pnl += final_move

        out[idx] = pnl

    return out


# ─────────────────────────────────────────────────────────────────────
# Public launcher
# ─────────────────────────────────────────────────────────────────────

def is_cuda_available() -> bool:
    """Cheap runtime check used by callers before assembling big batches."""
    return bool(HAS_CUDA)


def _coerce_float32(a: np.ndarray, name: str) -> np.ndarray:
    if a is None:
        raise ValueError(f"{name} is None")
    arr = np.ascontiguousarray(np.asarray(a), dtype=np.float32)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be 1-D, got shape={arr.shape}")
    # Scrub NaN/Inf so kernel math stays well-defined.
    if not np.isfinite(arr).all():
        arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    return arr


def batch_backtest(
    prices: np.ndarray,
    params_list,
    *,
    signal: Optional[np.ndarray] = None,
    atr: Optional[np.ndarray] = None,
    force_cpu: bool = False,
    threads_per_block: int = 128,
) -> np.ndarray:
    """Evaluate a batch of parameter combinations.

    Args:
        prices:      1-D close price series (float-like)
        params_list: list/ndarray of shape (n_combos, 4) — each row is
                     [entry_thr, exit_thr, atr_mult, tp_param]
        signal:      optional directional signal; defaults to normalized
                     one-bar return (useful for smoke tests).
        atr:         optional ATR series; defaults to rolling abs-return * price.
        force_cpu:   bypass CUDA even if available — for A/B testing.
        threads_per_block: CUDA launch geometry knob.

    Returns:
        np.ndarray of shape (n_combos,) dtype float32 — cumulative PnL per combo.
        On any kernel error we automatically fall through to the CPU path.
    """
    prices_a = _coerce_float32(prices, "prices")
    n_bars = prices_a.shape[0]
    if n_bars < 2:
        raise ValueError(f"prices too short: n_bars={n_bars}")

    if signal is None:
        ret = np.zeros(n_bars, dtype=np.float32)
        ret[1:] = (prices_a[1:] - prices_a[:-1]) / np.maximum(prices_a[:-1], 1e-8)
        scale = float(np.nanstd(ret)) or 1.0
        signal = np.clip(ret / (scale * 3.0), -1.0, 1.0)
    signal_a = _coerce_float32(signal, "signal")
    if signal_a.shape[0] != n_bars:
        raise ValueError(
            f"signal length {signal_a.shape[0]} != prices length {n_bars}")

    if atr is None:
        window = 14
        abs_ret = np.abs(np.diff(prices_a, prepend=prices_a[0]))
        atr_calc = np.zeros(n_bars, dtype=np.float32)
        if n_bars >= window:
            cs = np.cumsum(abs_ret)
            atr_calc[window:] = (cs[window:] - cs[:-window]) / window
            atr_calc[:window] = atr_calc[window] if n_bars > window else abs_ret[:window].mean()
        else:
            atr_calc[:] = abs_ret.mean()
        atr = atr_calc
    atr_a = _coerce_float32(atr, "atr")
    if atr_a.shape[0] != n_bars:
        raise ValueError(f"atr length {atr_a.shape[0]} != prices length {n_bars}")

    params_a = np.ascontiguousarray(np.asarray(params_list), dtype=np.float32)
    if params_a.ndim != 2 or params_a.shape[1] != 4:
        raise ValueError(
            f"params_list must be shape (n_combos, 4); got {params_a.shape}")
    n_combos = params_a.shape[0]
    if n_combos == 0:
        return np.zeros(0, dtype=np.float32)

    # ── GPU path ────────────────────────────────────────────────────
    if HAS_CUDA and not force_cpu:
        try:
            kernel = _build_kernel()
            d_prices = cuda.to_device(prices_a)
            d_signal = cuda.to_device(signal_a)
            d_atr = cuda.to_device(atr_a)
            d_params = cuda.to_device(params_a)
            d_results = cuda.device_array(n_combos, dtype=np.float32)

            blocks = int(math.ceil(n_combos / float(threads_per_block)))
            kernel[blocks, threads_per_block](
                d_prices, d_signal, d_atr, d_params, d_results, np.int32(n_bars),
            )
            cuda.synchronize()
            results = d_results.copy_to_host()
            if not np.isfinite(results).all():
                results = np.nan_to_num(results, nan=0.0, posinf=0.0, neginf=0.0)
            return results
        except Exception as exc:
            log.warning("cuda_backtest: GPU path failed (%s); falling back to CPU", exc)

    # ── CPU path ────────────────────────────────────────────────────
    results = _cpu_backtest(prices_a, signal_a, atr_a, params_a)
    if not np.isfinite(results).all():
        results = np.nan_to_num(results, nan=0.0, posinf=0.0, neginf=0.0)
    return results


__all__ = [
    "batch_backtest",
    "is_cuda_available",
    "HAS_CUDA",
    "HAS_NUMBA",
]
