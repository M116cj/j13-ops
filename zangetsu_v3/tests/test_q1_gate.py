"""
Q1 Gate Tests for compute_trade_level_metrics fitness gate logic.

Gate rule (in WORKER's compute_trade_fitness):
    if expectancy <= 0 or n_trades < 80: return -999.0
    else: fitness = trade_level_sharpe * win_rate * log1p(tpd)

These tests verify the metrics that feed the gate, not the gate function itself.
"""

import sys
import os

sys.path.insert(0, os.path.expanduser("~/j13-ops/zangetsu_v3"))

import numpy as np
import pytest
from backtest_regime import compute_trade_level_metrics


def _make_trades(returns):
    """Build trade dicts from a list of PnL values."""
    return [
        {"pnl": r, "cost": 0.0, "funding": 0.0, "position_size": 1.0}
        for r in returns
    ]


class TestQ1Gate:
    """Tests for the fitness gate conditions."""

    def test_asymmetric_passes_gate(self):
        """30% win@0.05, 70% lose@0.01 over 100 trades -> passes gate."""
        rng = np.random.default_rng(42)
        n = 100
        wins = rng.choice([True, False], size=n, p=[0.30, 0.70])
        returns = np.where(wins, 0.05, -0.01)
        trades = _make_trades(returns.tolist())

        m = compute_trade_level_metrics(trades, years_of_data=1.0)

        # Gate condition 1: positive expectancy
        assert m["expectancy"] > 0, (
            f"Expected positive expectancy, got {m['expectancy']}"
        )
        # Gate condition 2: sufficient trades
        assert m["n_trades"] >= 80, (
            f"Expected n_trades >= 80, got {m['n_trades']}"
        )

        # Compute fitness as the worker would
        tpd = m["trades_per_year"] / 365.0
        fitness = m["trade_level_sharpe"] * m["win_rate"] * np.log1p(tpd)

        assert fitness != -999.0, "Fitness should not be gated to -999"
        assert fitness > 0, f"Expected positive fitness, got {fitness}"

    def test_low_trades_fails_gate(self):
        """50 trades with positive expectancy -> gated out (n_trades < 80)."""
        rng = np.random.default_rng(42)
        n = 50
        wins = rng.choice([True, False], size=n, p=[0.30, 0.70])
        returns = np.where(wins, 0.05, -0.01)
        trades = _make_trades(returns.tolist())

        m = compute_trade_level_metrics(trades, years_of_data=1.0)

        # Expectancy should still be positive with this distribution
        assert m["expectancy"] > 0, (
            f"Expected positive expectancy, got {m['expectancy']}"
        )
        # But trade count is below gate threshold
        assert m["n_trades"] < 80, (
            f"Expected n_trades < 80, got {m['n_trades']}"
        )

    def test_negative_expectancy_fails(self):
        """WR=0.55 but avg_win=0.005 vs avg_loss=0.01 -> negative expectancy."""
        rng = np.random.default_rng(42)
        n = 200
        wins = rng.choice([True, False], size=n, p=[0.55, 0.45])
        returns = np.where(wins, 0.005, -0.01)
        trades = _make_trades(returns.tolist())

        m = compute_trade_level_metrics(trades, years_of_data=1.0)

        # Expectancy should be negative: 0.55*0.005 - 0.45*0.01 = -0.00175
        assert m["expectancy"] < 0, (
            f"Expected negative expectancy, got {m['expectancy']}"
        )
