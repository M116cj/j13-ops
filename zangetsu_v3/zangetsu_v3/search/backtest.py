"""Backtesting engine for V3.1 HFT (Tier 4). No regime filter — data is per-regime segments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
from numba import njit

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "HFTBacktest",
    "backtest_hft",
    "hft_fitness",
]


@njit
def backtest_hft(
    signal,        # float64 array
    close,         # float64 array
    entry_thr,     # float - signal threshold to enter
    exit_thr,      # float - signal threshold to exit
    stop_mult,     # float - ATR multiplier for stop
    pos_frac,      # float - position fraction
    hold_max,      # int - max bars to hold (3-30 for HFT)
    cost_bps,      # float - trading cost in bps (per-symbol)
    funding_rate,  # float - funding rate constant
):
    """Pure signal->trade->PnL backtest. No regime filter.

    Entry: signal > entry_thr -> long, signal < -entry_thr -> short
    Exit: abs(signal) < exit_thr OR hold >= hold_max OR stop hit
    Cost: entry and exit each incur cost_bps
    Funding: every 480 bars deduct funding_rate * pos_frac

    Returns: pnl array, positions array, hold_bars array
    """
    n = len(signal)
    pnl = np.zeros(n)
    pos = np.zeros(n, dtype=np.int8)    # -1/0/+1
    holds = np.zeros(n, dtype=np.int32)  # how many bars held
    entry_px = 0.0
    hold = 0

    for i in range(1, n):
        p = pos[i - 1]
        if p != 0:
            # In position
            ret = float(p) * (close[i] - close[i - 1]) / close[i - 1] * pos_frac
            pnl[i] = ret
            if i % 480 == 0:
                pnl[i] -= abs(funding_rate) * pos_frac
            hold += 1
            holds[i] = hold

            # Exit conditions
            atr = abs(close[i] - close[i - 1]) * 14
            stop = (
                (close[i] < entry_px - stop_mult * atr)
                if p > 0
                else (close[i] > entry_px + stop_mult * atr)
            )
            if stop or abs(signal[i]) < exit_thr or hold >= hold_max:
                pnl[i] -= cost_bps / 10000 * pos_frac  # exit cost
                hold = 0
                pos[i] = 0
                continue
            pos[i] = p
            continue

        # Not in position — check entry
        if signal[i] > entry_thr:
            pos[i] = 1
            entry_px = close[i]
            hold = 0
            pnl[i] -= cost_bps / 10000 * pos_frac  # entry cost
        elif signal[i] < -entry_thr:
            pos[i] = -1
            entry_px = close[i]
            hold = 0
            pnl[i] -= cost_bps / 10000 * pos_frac

    return pnl, pos, holds


def _active_time_sharpe(pnl: np.ndarray, min_active: int = 30) -> float:
    """Sharpe using only active (pnl!=0) bars.

    Split into 5 segments. If >1 segment has <min_active bars, return -999.
    Annualize by active frequency, not calendar.
    """
    active_mask = pnl != 0
    active_pnl = pnl[active_mask]
    n_active = len(active_pnl)
    if n_active < min_active:
        return -999.0

    n_segments = 5
    seg_size = n_active // n_segments
    if seg_size < min_active:
        seg_size = min_active
        n_segments = max(1, n_active // seg_size)

    zero_count = 0
    for s in range(n_segments):
        start = s * seg_size
        end = start + seg_size if s < n_segments - 1 else n_active
        seg = active_pnl[start:end]
        if len(seg) < min_active:
            zero_count += 1
            continue
        seg_std = np.std(seg)
        if seg_std < 1e-15:
            zero_count += 1

    if zero_count > 1:
        return -999.0

    mean = float(np.mean(active_pnl))
    std = float(np.std(active_pnl))
    if std < 1e-15:
        return 0.0

    # Annualize by active bar frequency
    # active_bars / total_bars gives the duty cycle
    # annualization = sqrt(active_bars_per_year)
    # active_bars_per_year = n_active / (len(pnl) / (1440 * 365))
    bars_per_year = 1440.0 * 365.0
    active_per_year = n_active / (len(pnl) / bars_per_year) if len(pnl) > 0 else n_active
    annualization = np.sqrt(active_per_year)

    return float(mean / std * annualization)


def hft_fitness(pnl: np.ndarray, total_bars: int, min_tpd: float = 100.0) -> float:
    """C10: HFT fitness = sharpe_active * win_rate * log1p(trades_per_day).

    Returns -999.0 if any gate fails:
    - win_rate < 0.52
    - trades_per_day < min_tpd
    - sharpe <= 0
    """
    active_pnl = pnl[pnl != 0]
    n_active = len(active_pnl)
    if n_active < 30:
        return -999.0

    # Count trades (position entries = transitions from 0 to non-0)
    active_mask = (pnl != 0).astype(np.int8)
    entries = int(np.sum(np.diff(active_mask) == 1))
    if pnl[0] != 0:
        entries += 1  # started in position

    n_days = max(total_bars / 1440.0, 1e-6)
    tpd = entries / n_days

    win_rate = float(np.mean(active_pnl > 0))
    sharpe = _active_time_sharpe(pnl)

    if win_rate < 0.52:
        return -999.0
    if tpd < min_tpd:
        return -999.0
    if sharpe <= 0:
        return -999.0

    return float(sharpe * win_rate * np.log1p(tpd))


@dataclass
class BacktestResult:
    pnl: np.ndarray
    total_return: float
    sharpe: float            # active-time sharpe
    hft_fitness: float       # sharpe * win_rate * log1p(tpd)
    max_drawdown: float
    trades_per_day: float
    win_rate: float
    n_trades: int
    n_active_bars: int
    hold_bars_avg: float     # average bars held per trade (HFT: should be 3-30)
    return_skewness: float
    return_kurtosis: float


class BacktestEngine(Protocol):
    def evaluate(
        self,
        signal: np.ndarray,
        close: np.ndarray,
        params: dict,
        cost_bps: float,
        funding_rate: float,
    ) -> BacktestResult:
        ...


class HFTBacktest:
    """V3.1 HFT backtest engine. No regime filter."""

    def evaluate(
        self,
        signal: np.ndarray,
        close: np.ndarray,
        params: dict,
        cost_bps: float,
        funding_rate: float = 0.0,
    ) -> BacktestResult:
        pnl, pos, holds = backtest_hft(
            signal,
            close,
            float(params.get("entry_thr", 1.0)),
            float(params.get("exit_thr", 0.5)),
            float(params.get("stop_mult", 2.0)),
            float(params.get("pos_frac", 0.1)),
            int(params.get("hold_max", 15)),
            float(cost_bps),
            float(funding_rate),
        )

        total_bars = len(pnl)
        sharpe = _active_time_sharpe(pnl)
        fitness = hft_fitness(pnl, total_bars)

        # Stats
        active_pnl = pnl[pnl != 0]
        n_active = len(active_pnl)
        total_ret = float(np.nansum(pnl))

        # Max drawdown
        cum = np.nancumsum(pnl)
        running_max = np.maximum.accumulate(cum)
        dd = running_max - cum
        max_dd = float(np.nanmax(dd)) if dd.size else 0.0

        # Trade count
        active_mask = (pnl != 0).astype(np.int8)
        entries = int(np.sum(np.diff(active_mask) == 1))
        if pnl[0] != 0:
            entries += 1
        n_days = max(total_bars / 1440.0, 1e-6)
        tpd = entries / n_days

        win_rate = float(np.mean(active_pnl > 0)) if n_active > 0 else 0.0

        # Average hold bars — use hold value at position exits
        exits = np.where(np.diff(active_mask) == -1)[0]
        avg_hold = float(np.mean(holds[exits])) if len(exits) > 0 else 0.0

        # Skew/kurt
        skew = kurt = 0.0
        if n_active > 2:
            std = float(np.std(active_pnl) + 1e-12)
            centered = (active_pnl - active_pnl.mean()) / std
            skew = float(np.nan_to_num(np.mean(centered**3)))
            kurt = float(np.nan_to_num(np.mean(centered**4) - 3))

        return BacktestResult(
            pnl=pnl,
            total_return=total_ret,
            sharpe=sharpe,
            hft_fitness=fitness,
            max_drawdown=max_dd,
            trades_per_day=tpd,
            win_rate=win_rate,
            n_trades=entries,
            n_active_bars=n_active,
            hold_bars_avg=avg_hold,
            return_skewness=skew,
            return_kurtosis=kurt,
        )
