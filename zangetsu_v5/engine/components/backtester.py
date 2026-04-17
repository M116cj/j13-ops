"""Backtester — Numba JIT CPU vectorized with future GPU offload path."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    from numba import njit, prange
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False
    def njit(*args, **kwargs):
        def wrapper(fn):
            return fn
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return wrapper
    prange = range


@dataclass
class BacktestResult:
    symbol: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    gross_pnl: float
    net_pnl: float
    max_drawdown: float
    sharpe_ratio: float
    avg_hold_bars: float
    pnl_per_trade: float
    equity_curve: np.ndarray
    trade_log: np.ndarray
    dynamic_strength: float = 0.0


@njit(cache=True)
def _vectorized_backtest(
    signals: np.ndarray,
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    cost_per_trade: float,
    max_hold_bars: int,
    atr_stop_mult: float,
    atr: np.ndarray,
    sizes: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Core vectorized backtest with dual binary exit (vote decay + ATR stop)."""
    n = len(signals)
    pnl = np.zeros(n, dtype=np.float64)
    entries = np.empty(n, dtype=np.int64)
    exits = np.empty(n, dtype=np.int64)
    exit_reasons = np.empty(n, dtype=np.int8)  # 0=signal, 1=atr_stop, 2=max_hold
    trade_count = 0

    position = 0
    entry_price = 0.0
    hold_count = 0

    for i in range(1, n):
        if position == 0:
            if signals[i] != 0:
                position = signals[i]
                entry_price = close[i]
                hold_count = 0
                entries[trade_count] = i
        else:
            hold_count += 1
            reason = -1

            # ATR hard stop (intra-bar H/L check)
            if atr_stop_mult > 0 and atr[i] > 0:
                if position == 1 and low[i] <= entry_price - atr_stop_mult * atr[i]:
                    reason = 1
                elif position == -1 and high[i] >= entry_price + atr_stop_mult * atr[i]:
                    reason = 1

            # Vote decay exit (signal == 0 or flip)
            if reason < 0 and (signals[i] == -position or signals[i] == 0):
                reason = 0

            # Max hold
            if reason < 0 and hold_count >= max_hold_bars:
                reason = 2

            if reason >= 0:
                exit_price = close[i]
                raw_return = (exit_price - entry_price) / entry_price * position
                # V7.1: scale by position size from continuous signal strength
                size = sizes[i] if sizes[i] > 0.0 else 1.0
                cost = cost_per_trade
                pnl[i] = (raw_return - cost) * size
                exits[trade_count] = i
                exit_reasons[trade_count] = reason
                trade_count += 1
                position = 0

    return pnl, entries[:trade_count], exits[:trade_count], exit_reasons[:trade_count]


class Backtester:
    """Backtest engine with Numba JIT acceleration and dual binary exit.

    Integration:
        - CONSOLE_HOOK: backtest_chunk_size, backtest_gpu_enabled, backtest_gpu_batch_size
        - DASHBOARD_HOOK: backtest_throughput, total_backtests, avg_time_ms
    """

    def __init__(self, config) -> None:
        self._chunk_size: int = config.backtest_chunk_size
        self._gpu_enabled: bool = config.backtest_gpu_enabled
        self._gpu_batch: int = config.backtest_gpu_batch_size
        self._total_runs: int = 0
        self._total_time_ms: float = 0.0
        self._bars_per_year: int = 525_600  # 1m bars default

    def run(
        self,
        signals: np.ndarray,
        close: np.ndarray,
        symbol: str,
        cost_bps: float,
        max_hold_bars: int = 48,
        high: Optional[np.ndarray] = None,
        low: Optional[np.ndarray] = None,
        atr: Optional[np.ndarray] = None,
        atr_stop_mult: float = 0.0,
        bars_per_year: Optional[int] = None,
        sizes: Optional[np.ndarray] = None,
    ) -> BacktestResult:
        t0 = time.monotonic()
        self._total_runs += 1

        cost_frac = cost_bps / 10000.0
        _high = high if high is not None else close
        _low = low if low is not None else close
        _atr = atr if atr is not None else np.zeros_like(close)
        _sizes = sizes if sizes is not None else np.ones_like(close)
        bpy = bars_per_year or self._bars_per_year

        pnl_array, entries, exits, exit_reasons = _vectorized_backtest(
            signals.astype(np.int8),
            close.astype(np.float64),
            _high.astype(np.float64),
            _low.astype(np.float64),
            cost_frac,
            max_hold_bars,
            atr_stop_mult,
            _atr.astype(np.float64),
            _sizes.astype(np.float64),
        )

        total_trades = len(entries)
        trade_pnls = pnl_array[pnl_array != 0.0]
        winning = int(np.sum(trade_pnls > 0))
        losing = int(np.sum(trade_pnls < 0))
        gross_pnl = float(np.sum(trade_pnls[trade_pnls > 0])) if winning > 0 else 0.0
        net_pnl = float(np.sum(trade_pnls))

        equity = np.cumsum(pnl_array)
        running_max = np.maximum.accumulate(equity)
        drawdowns = running_max - equity
        max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

        # Per-trade Sharpe (not per-bar) for meaningful risk-adjusted metric
        if len(trade_pnls) > 1 and np.std(trade_pnls) > 1e-12:
            sharpe = float(np.mean(trade_pnls) / np.std(trade_pnls) * np.sqrt(min(total_trades, 252)))
        else:
            sharpe = 0.0

        if total_trades > 0:
            hold_durations = exits - entries
            avg_hold = float(np.mean(hold_durations))
            pnl_per_trade = net_pnl / total_trades
        else:
            avg_hold = 0.0
            pnl_per_trade = 0.0

        trade_log = np.column_stack([entries, exits, exit_reasons]) if total_trades > 0 else np.empty((0, 3))

        elapsed = (time.monotonic() - t0) * 1000
        self._total_time_ms += elapsed

        return BacktestResult(
            symbol=symbol,
            total_trades=total_trades,
            winning_trades=winning,
            losing_trades=losing,
            win_rate=winning / total_trades if total_trades > 0 else 0.0,
            gross_pnl=gross_pnl,
            net_pnl=net_pnl,
            max_drawdown=max_dd,
            sharpe_ratio=sharpe,
            avg_hold_bars=avg_hold,
            pnl_per_trade=pnl_per_trade,
            equity_curve=equity,
            trade_log=trade_log,
        )

    def run_batch(
        self,
        signal_matrix: np.ndarray,
        close: np.ndarray,
        symbol: str,
        cost_bps: float,
        max_hold_bars: int = 48,
        **kwargs,
    ) -> List[BacktestResult]:
        results = []
        for i in range(signal_matrix.shape[0]):
            results.append(self.run(signal_matrix[i], close, symbol, cost_bps, max_hold_bars, **kwargs))
        return results

    def health_check(self) -> Dict:
        return {
            "numba_available": HAS_NUMBA,
            "gpu_enabled": self._gpu_enabled,
            "total_runs": self._total_runs,
            "avg_time_ms": (
                round(self._total_time_ms / self._total_runs, 2)
                if self._total_runs > 0 else 0.0
            ),
            "chunk_size": self._chunk_size,
            "bars_per_year": self._bars_per_year,
        }
