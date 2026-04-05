"""Tests for Gate1, Gate2 (DeflatedSharpeGate), and Gate3 (HoldoutGate).

No DB required — synthetic BacktestResult objects only.
"""

from __future__ import annotations

import numpy as np
import pytest

from zangetsu_v3.search.backtest import BacktestResult
from zangetsu_v3.gates.gate1 import Gate1
from zangetsu_v3.gates.gate2 import DeflatedSharpeGate, deflated_sharpe_ratio
from zangetsu_v3.gates.gate3 import HoldoutGate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_result(
    sharpe: float = 1.0,
    hft_fitness: float = 1.0,
    max_drawdown: float = 0.05,
    trades_per_day: float = 10.0,
    win_rate: float = 0.55,
    n_pnl: int = 1440,
    positive_pnl: bool = True,
) -> BacktestResult:
    """Construct a synthetic BacktestResult with controlled properties."""
    np.random.seed(0)
    if positive_pnl:
        pnl = np.abs(np.random.randn(n_pnl) * 0.001) + 0.0001
    else:
        pnl = np.random.randn(n_pnl) * 0.001 - 0.0001
    return BacktestResult(
        pnl=pnl,
        total_return=float(np.nansum(pnl)),
        sharpe=sharpe,
        hft_fitness=hft_fitness,
        max_drawdown=max_drawdown,
        trades_per_day=trades_per_day,
        win_rate=win_rate,
        n_trades=int(trades_per_day * (n_pnl / 1440.0)),
        n_active_bars=n_pnl // 2,
        hold_bars_avg=10.0,
        return_skewness=0.1,
        return_kurtosis=0.2,
    )


# ---------------------------------------------------------------------------
# Gate1 tests
# ---------------------------------------------------------------------------

class TestGate1:
    def test_pass_positive_pnl_above_sos_threshold(self):
        gate = Gate1(sos_threshold=0.001)
        result = make_result(positive_pnl=True, n_pnl=1440)
        assert gate.evaluate(result) is True

    def test_fail_negative_pnl_trimmed_min_below_zero(self):
        gate = Gate1(sos_threshold=0.001)
        pnl = np.zeros(1440)
        pnl[:800] = -0.01  # first portion is very negative
        result = BacktestResult(
            pnl=pnl,
            total_return=float(np.sum(pnl)),
            sharpe=-1.0,
            hft_fitness=-999.0,
            max_drawdown=0.5,
            trades_per_day=5.0,
            win_rate=0.3,
            n_trades=5,
            n_active_bars=800,
            hold_bars_avg=10.0,
            return_skewness=0.0,
            return_kurtosis=0.0,
        )
        assert gate.evaluate(result) is False

    def test_fail_sos_below_threshold(self):
        gate = Gate1(sos_threshold=1000.0)  # very high threshold
        result = make_result(positive_pnl=True, n_pnl=100)
        assert gate.evaluate(result) is False

    def test_last_trimmed_min_and_sos_set_after_evaluate(self):
        gate = Gate1(sos_threshold=0.001)
        result = make_result(positive_pnl=True)
        gate.evaluate(result)
        assert hasattr(gate, "last_trimmed_min")
        assert hasattr(gate, "last_sos")
        assert isinstance(gate.last_trimmed_min, float)
        assert isinstance(gate.last_sos, float)
        assert gate.last_sos > 0

    def test_empty_pnl_fails(self):
        gate = Gate1(sos_threshold=0.001)
        result = BacktestResult(
            pnl=np.array([]),
            total_return=0.0,
            sharpe=0.0,
            hft_fitness=-999.0,
            max_drawdown=0.0,
            trades_per_day=0.0,
            win_rate=0.0,
            n_trades=0,
            n_active_bars=0,
            hold_bars_avg=0.0,
            return_skewness=0.0,
            return_kurtosis=0.0,
        )
        assert gate.evaluate(result) is False

    def test_all_zero_pnl_fails(self):
        gate = Gate1(sos_threshold=0.001)
        result = BacktestResult(
            pnl=np.zeros(500),
            total_return=0.0,
            sharpe=0.0,
            hft_fitness=-999.0,
            max_drawdown=0.0,
            trades_per_day=0.0,
            win_rate=0.0,
            n_trades=0,
            n_active_bars=0,
            hold_bars_avg=0.0,
            return_skewness=0.0,
            return_kurtosis=0.0,
        )
        assert gate.evaluate(result) is False

    def test_custom_sos_threshold(self):
        gate = Gate1(sos_threshold=0.0)  # threshold=0 → any positive SOS passes
        pnl = np.ones(100) * 0.001
        result = BacktestResult(
            pnl=pnl, total_return=0.1, sharpe=2.0, hft_fitness=2.0,
            max_drawdown=0.01, trades_per_day=10.0, win_rate=0.6,
            n_trades=10, n_active_bars=100, hold_bars_avg=10.0,
            return_skewness=0.0, return_kurtosis=0.0,
        )
        assert gate.evaluate(result) is True


# ---------------------------------------------------------------------------
# Gate2 (DeflatedSharpeGate) tests
# ---------------------------------------------------------------------------

class TestDeflatedSharpeGate:
    def test_high_sharpe_low_trials_passes(self):
        gate = DeflatedSharpeGate(threshold=0.95, trials=1)
        pnl = np.random.randn(10000) * 0.001 + 0.002
        result = BacktestResult(
            pnl=pnl,
            total_return=float(np.sum(pnl)),
            sharpe=3.0,
            hft_fitness=3.0,
            max_drawdown=0.02,
            trades_per_day=100.0,
            win_rate=0.6,
            n_trades=100,
            n_active_bars=5000,
            hold_bars_avg=10.0,
            return_skewness=0.0,
            return_kurtosis=0.0,
        )
        assert gate.evaluate(result) is True

    def test_high_n_trials_marginal_sharpe_fails(self):
        gate = DeflatedSharpeGate(threshold=0.95, trials=1000)
        pnl = np.random.randn(500) * 0.001 + 0.0005
        result = BacktestResult(
            pnl=pnl,
            total_return=float(np.sum(pnl)),
            sharpe=0.5,
            hft_fitness=0.5,
            max_drawdown=0.05,
            trades_per_day=10.0,
            win_rate=0.5,
            n_trades=10,
            n_active_bars=250,
            hold_bars_avg=10.0,
            return_skewness=0.0,
            return_kurtosis=0.0,
        )
        assert gate.evaluate(result) is False

    def test_dsr_value_in_zero_one_range(self):
        gate = DeflatedSharpeGate(threshold=0.95, trials=10)
        pnl = np.random.randn(500) * 0.001
        result = BacktestResult(
            pnl=pnl,
            total_return=float(np.sum(pnl)),
            sharpe=1.0,
            hft_fitness=1.0,
            max_drawdown=0.05,
            trades_per_day=10.0,
            win_rate=0.5,
            n_trades=10,
            n_active_bars=250,
            hold_bars_avg=10.0,
            return_skewness=0.0,
            return_kurtosis=0.0,
        )
        gate.evaluate(result)
        assert hasattr(gate, "last_dsr")
        assert 0.0 <= gate.last_dsr <= 1.0

    def test_deflated_sharpe_ratio_function_low_trials(self):
        dsr = deflated_sharpe_ratio(sharpe=2.0, n=1000, trials=1)
        assert 0.0 <= dsr <= 1.0
        assert dsr > 0.95

    def test_deflated_sharpe_ratio_function_high_trials(self):
        dsr = deflated_sharpe_ratio(sharpe=0.5, n=200, trials=500)
        assert 0.0 <= dsr <= 1.0
        assert dsr < 0.95

    def test_deflated_sharpe_ratio_too_few_observations(self):
        dsr = deflated_sharpe_ratio(sharpe=2.0, n=2, trials=1)
        assert dsr == 0.0

    def test_last_dsr_attribute_set(self):
        gate = DeflatedSharpeGate(threshold=0.95, trials=5)
        pnl = np.ones(1000) * 0.001
        result = BacktestResult(
            pnl=pnl, total_return=1.0, sharpe=2.0, hft_fitness=2.0,
            max_drawdown=0.01, trades_per_day=10.0, win_rate=0.6,
            n_trades=10, n_active_bars=500, hold_bars_avg=10.0,
            return_skewness=0.0, return_kurtosis=0.0,
        )
        gate.evaluate(result)
        assert hasattr(gate, "last_dsr")


# ---------------------------------------------------------------------------
# Gate3 (HoldoutGate) tests — CRITICAL permanent failure logic
# ---------------------------------------------------------------------------

class TestHoldoutGate:
    def _passing_result(
        self,
        hft_fitness: float = 1.5,
        win_rate: float = 0.55,
        trades_per_day: float = 150.0,
        max_drawdown: float = 0.05,
        sharpe: float = 1.5,
    ) -> BacktestResult:
        return BacktestResult(
            pnl=np.random.randn(1440) * 0.001,
            total_return=0.1,
            sharpe=sharpe,
            hft_fitness=hft_fitness,
            max_drawdown=max_drawdown,
            trades_per_day=trades_per_day,
            win_rate=win_rate,
            n_trades=int(trades_per_day),
            n_active_bars=500,
            hold_bars_avg=10.0,
            return_skewness=0.1,
            return_kurtosis=0.2,
        )

    def test_pass_all_conditions_met(self):
        """hft_fitness>0, win_rate>=0.52, tpd>=100 → PASSED."""
        gate = HoldoutGate()
        result = self._passing_result(hft_fitness=1.5, win_rate=0.55, trades_per_day=150.0)
        passed, reason = gate.gate(holdout_result=result)
        assert passed is True
        assert reason == "PASSED"

    def test_fail_hft_fitness_below_zero(self):
        """hft_fitness <= 0 → fail."""
        gate = HoldoutGate()
        result = self._passing_result(hft_fitness=-1.0, win_rate=0.55, trades_per_day=150.0)
        passed, reason = gate.gate(holdout_result=result)
        assert passed is False
        assert "hft_fitness" in reason

    def test_fail_win_rate_below_threshold(self):
        """win_rate < 0.52 → fail."""
        gate = HoldoutGate()
        result = self._passing_result(hft_fitness=1.0, win_rate=0.40, trades_per_day=150.0)
        passed, reason = gate.gate(holdout_result=result)
        assert passed is False
        assert "win_rate" in reason

    def test_fail_tpd_below_100(self):
        """trades_per_day < 100 → fail."""
        gate = HoldoutGate()
        result = self._passing_result(hft_fitness=1.0, win_rate=0.55, trades_per_day=50.0)
        passed, reason = gate.gate(holdout_result=result)
        assert passed is False
        assert "tpd" in reason

    def test_permanent_failure_after_fail(self):
        """Once gate() returns False due to condition failure, _failed=True permanently."""
        gate = HoldoutGate()

        # First call — should fail (low hft_fitness)
        bad_result = self._passing_result(hft_fitness=-1.0, win_rate=0.55, trades_per_day=150.0)
        passed, _ = gate.gate(holdout_result=bad_result)
        assert passed is False
        assert gate._failed is True

        # Second call — passing result, but gate is permanently failed
        good_result = self._passing_result(hft_fitness=2.0, win_rate=0.60, trades_per_day=200.0)
        passed2, reason2 = gate.gate(holdout_result=good_result)
        assert passed2 is False
        assert reason2 == "FAILED_HOLDOUT_PERMANENT"

    def test_already_tested_always_returns_permanent_failure(self):
        gate = HoldoutGate()
        good_result = self._passing_result(hft_fitness=2.0, win_rate=0.60, trades_per_day=200.0)
        passed, reason = gate.gate(
            holdout_result=good_result,
            already_tested=True,
        )
        assert passed is False
        assert reason == "FAILED_HOLDOUT_PERMANENT"

    def test_already_tested_does_not_set_failed_flag(self):
        """already_tested=True short-circuits before setting _failed."""
        gate = HoldoutGate()
        good_result = self._passing_result(hft_fitness=2.0, win_rate=0.60, trades_per_day=200.0)
        gate.gate(
            holdout_result=good_result,
            already_tested=True,
        )
        # _failed should NOT be set by already_tested path
        assert gate._failed is False

    def test_exactly_at_win_rate_threshold_fails(self):
        """win_rate exactly 0.52 is >= 0.52, so it should pass (not <0.52)."""
        gate = HoldoutGate()
        result = self._passing_result(hft_fitness=1.0, win_rate=0.52, trades_per_day=150.0)
        passed, _ = gate.gate(holdout_result=result)
        assert passed is True

    def test_multiple_conditions_can_fail_simultaneously(self):
        """When hft_fitness and win_rate both fail, both appear in reason."""
        gate = HoldoutGate()
        result = self._passing_result(hft_fitness=-1.0, win_rate=0.40, trades_per_day=50.0)
        passed, reason = gate.gate(holdout_result=result)
        assert passed is False
        assert "hft_fitness" in reason
        assert "win_rate" in reason
        assert "tpd" in reason
