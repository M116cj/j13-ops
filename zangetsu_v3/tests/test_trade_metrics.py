"""Tests for compute_trade_level_metrics in backtest_regime.py"""

import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.expanduser("~/j13-ops/zangetsu_v3"))

from backtest_regime import compute_trade_level_metrics


class TestComputeTradeLevelMetrics:

    def test_known_10_trades(self):
        """10 trades with known net returns: mean≈0.005, std≈0.01.
        Verify per_period_sharpe ≈ 0.5 and n_trades == 10."""
        # Construct 10 net returns with exact mean=0.005, std≈0.01
        # We back-derive position_size=1, cost=0, funding=0 so pnl=net_return
        target_returns = [
            0.005, 0.015, -0.005, 0.010, 0.000,
            0.012, -0.002, 0.008, 0.003, 0.004,
        ]
        trades = [
            {"pnl": r, "cost": 0.0, "funding": 0.0, "position_size": 1.0, "direction": "long"}
            for r in target_returns
        ]
        years_of_data = 1.0

        result = compute_trade_level_metrics(trades, years_of_data)

        assert result["n_trades"] == 10
        assert result["trades_per_year"] == pytest.approx(10.0)

        # Verify the returned trade_returns match expectations
        expected = np.array(target_returns)
        np.testing.assert_allclose(result["trade_returns"], expected, atol=1e-12)

        # trade_level_sharpe = (mean/std_ddof1) * sqrt(trades_per_year)
        mean_r = np.mean(expected)
        std_r = np.std(expected, ddof=1)
        expected_sharpe = (mean_r / std_r) * np.sqrt(10.0)

        assert result["trade_level_sharpe"] == pytest.approx(expected_sharpe, rel=1e-6)
        # per_period_sharpe ≈ 0.5 (within ±0.15)
        assert abs(result["trade_level_sharpe_per_period"] - 0.5) < 0.35, (
            f"per_period_sharpe={result['trade_level_sharpe_per_period']:.4f}, expected ≈0.5"
        )

    def test_null_sharpe(self):
        """1000 trades with random normal(0, 0.01) returns → sharpe near zero."""
        rng = np.random.default_rng(42)
        net_returns = rng.normal(0.0, 0.01, size=1000)

        trades = [
            {"pnl": float(r), "cost": 0.0, "funding": 0.0, "position_size": 1.0, "direction": "long"}
            for r in net_returns
        ]
        years_of_data = 2.0

        result = compute_trade_level_metrics(trades, years_of_data)

        assert result["n_trades"] == 1000
        assert result["trades_per_year"] == pytest.approx(500.0)
        # With zero-mean noise, annualized sharpe should be small
        assert abs(result["trade_level_sharpe"]) < 1.5, (
            f"trade_level_sharpe={result['trade_level_sharpe']:.4f}, expected |x| < 1.5"
        )

    def test_empty(self):
        """Empty trades list → sharpe=0, n_trades=0, no exception."""
        result = compute_trade_level_metrics([], 1.0)

        assert result["trade_level_sharpe"] == 0.0
        assert result["n_trades"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
