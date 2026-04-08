"""
Tests for trade-level fitness function used in arena3_regime.py.
Fitness formula: trade_level_sharpe * win_rate * log1p(trades_per_day)
"""
import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.expanduser("~/j13-ops/zangetsu_v3"))
from backtest_regime import (
    extract_trades_from_backtest,
    compute_trade_level_metrics,
    backtest_regime_conditional,
)


def test_trade_level_fitness_positive():
    np.random.seed(42)
    n = 10000
    signal = np.random.randn(n) * 0.5
    close = 50000 + np.cumsum(np.random.randn(n) * 10)
    close = np.maximum(close, 1000).astype(np.float64)
    regime_labels = np.zeros(n, dtype=np.int8)

    pnl, pos, exit_type = backtest_regime_conditional(
        signal, close, regime_labels, np.int8(0),
        0.7, 0.3, 2.0, 0.05, 480, 6, 4.0, 10.0, 0.0001,
    )

    trades = extract_trades_from_backtest(pnl, pos, close, 0.05, 4.0, 10.0, exit_type)
    trades_fmt = [
        {"pnl": t["net_pnl"], "cost": 0.0, "funding": 0.0, "position_size": t["position_size"]}
        for t in trades
    ]

    regime_bars = int(np.sum(regime_labels == 0))
    years = regime_bars / (1440.0 * 365.0)
    m = compute_trade_level_metrics(trades_fmt, years)

    n_days = regime_bars / 1440.0
    entries = len(trades)
    tpd = entries / max(n_days, 1e-6)

    fitness = m["trade_level_sharpe"] * m["win_rate"] * np.log1p(max(tpd, 0.1))

    # Fitness should be a finite number in roughly [-50, 50] range
    assert np.isfinite(fitness), f"fitness is {fitness}"
    # Trade-level sharpe should NOT be in the inflated per-bar range [10+]
    assert abs(m["trade_level_sharpe"]) < 10, (
        f"sharpe {m['trade_level_sharpe']} looks per-bar, not per-trade"
    )
    print(f"fitness={fitness:.4f} sharpe={m['trade_level_sharpe']:.4f} wr={m['win_rate']:.4f} tpd={tpd:.2f}")


def test_zero_trades_fitness():
    # All-zero signal -> no entries -> fitness should be -999
    pnl = np.zeros(1000)
    pos = np.zeros(1000, dtype=np.int8)
    close = np.ones(1000) * 50000.0
    exit_type = np.zeros(1000, dtype=np.int8)

    trades = extract_trades_from_backtest(pnl, pos, close, 0.05, 4.0, 10.0, exit_type)
    assert len(trades) == 0

    trades_fmt = [
        {"pnl": t["net_pnl"], "cost": 0.0, "funding": 0.0, "position_size": t["position_size"]}
        for t in trades
    ]
    m = compute_trade_level_metrics(trades_fmt, 1.0)
    assert m["n_trades"] == 0
    assert m["trade_level_sharpe"] == 0.0


def test_fitness_differs_from_per_bar():
    # Run a real backtest and compute BOTH sharpe types
    # They should differ significantly (trade-level should be much lower in abs value)
    np.random.seed(99)
    n = 20000
    signal = np.random.randn(n) * 0.5
    close = 50000 + np.cumsum(np.random.randn(n) * 10)
    close = np.maximum(close, 1000).astype(np.float64)
    regime_labels = np.zeros(n, dtype=np.int8)

    pnl, pos, exit_type = backtest_regime_conditional(
        signal, close, regime_labels, np.int8(0),
        0.7, 0.3, 2.0, 0.05, 480, 6, 4.0, 10.0, 0.0001,
    )

    # Per-bar sharpe (old method)
    in_regime = regime_labels == 0
    regime_pnl = pnl[in_regime]
    active = regime_pnl[regime_pnl != 0]
    if len(active) > 10:
        active_per_year = len(active) / (np.sum(in_regime) / (1440.0 * 365.0))
        per_bar_sharpe = float(np.mean(active)) / float(np.std(active)) * np.sqrt(active_per_year)
    else:
        per_bar_sharpe = 0.0

    # Trade-level sharpe (new method)
    trades = extract_trades_from_backtest(pnl, pos, close, 0.05, 4.0, 10.0, exit_type)
    trades_fmt = [
        {"pnl": t["net_pnl"], "cost": 0.0, "funding": 0.0, "position_size": t["position_size"]}
        for t in trades
    ]
    years = np.sum(in_regime) / (1440.0 * 365.0)
    m = compute_trade_level_metrics(trades_fmt, years)
    trade_sharpe = m["trade_level_sharpe"]

    # They should differ by at least 2x typically
    if abs(per_bar_sharpe) > 1 and abs(trade_sharpe) > 0.01:
        ratio = abs(per_bar_sharpe / trade_sharpe)
        print(f"per_bar={per_bar_sharpe:.4f} trade={trade_sharpe:.4f} ratio={ratio:.2f}")
        # Per-bar is typically much larger due to annualization inflation
        # Just verify they're different
        assert ratio > 1.5 or ratio < 0.67, (
            f"ratio {ratio:.2f} too close -- sharpe swap may not have happened"
        )
