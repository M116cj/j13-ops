"""Tests for T8 live layer: risk_manager, stale_breaker, journal, monitor, main_loop."""
from __future__ import annotations

import json
import time
import tempfile
from collections import deque
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import polars as pl
import pytest

from zangetsu_v3.live.risk_manager import Position, RiskLimits, RiskManager
from zangetsu_v3.live.stale_breaker import StaleBreaker, StaleFeedError
from zangetsu_v3.live.journal import LiveJournal, TradeRecord
from zangetsu_v3.live.monitor import LiveMonitor
from zangetsu_v3.live.main_loop import (
    BarResult,
    LiveState,
    build_live_state,
    on_new_bar,
)
from zangetsu_v3.regime.predictor import OnlineRegimePredictor


# ------------------------------------------------------------------ #
# Fixtures                                                             #
# ------------------------------------------------------------------ #

def _pos(symbol="BTC/USDT", regime_id=0, side="long", qty=0.05, price=50000.0):
    return Position(symbol=symbol, regime_id=regime_id, side=side, quantity=qty, entry_price=price)


def _make_bar_df(close=50000.0, ts="2026-01-01T00:00:00"):
    return pl.DataFrame({
        "timestamp": [ts],
        "open": [close * 0.999],
        "high": [close * 1.001],
        "low": [close * 0.998],
        "close": [close],
        "volume": [100.0],
        "rolling_return": [0.001],
        "realized_vol": [0.01],
        "volume_zscore": [0.5],
        "range_zscore": [0.3],
    })


def _make_live_state(tmp_path, lookback=2):
    """Minimal LiveState with mocked labeler returning regime 0."""
    labeler = MagicMock()
    labeler.label.return_value = np.array([0] * lookback)

    from zangetsu_v3.factors.normalizer import RobustNormalizer
    normalizer = RobustNormalizer()

    predictor = OnlineRegimePredictor()

    from zangetsu_v3.live.risk_manager import RiskLimits, RiskManager
    from zangetsu_v3.live.stale_breaker import StaleBreaker

    card = {
        "version": "3.0",
        "params": {"entry_threshold": 0.5, "exit_threshold": 0.2, "position_frac": 0.1},
        "cost_model": {"trading_bps": 3, "funding_rate_avg": 0.0001},
    }
    weights = np.array([0.5, 0.3, 0.1, 0.1])
    buf = deque(maxlen=lookback)

    return LiveState(
        card=card,
        weights=weights,
        normalizer=normalizer,
        labeler=labeler,
        predictor=predictor,
        risk_manager=RiskManager(limits=RiskLimits()),
        stale_breaker=StaleBreaker(max_stale_seconds=60),
        card_version="3.0",
        entry_threshold=0.5,
        exit_threshold=0.2,
        cost_bps=3.0,
        funding_rate=0.0001,
        position_frac=0.1,
        lookback=lookback,
        bar_buffer=buf,
    )


# ================================================================== #
# RiskManager                                                          #
# ================================================================== #

class TestRiskManager:
    def test_allow_first_position(self):
        rm = RiskManager()
        allowed, reason = rm.check_new_position(_pos(), {})
        assert allowed
        assert reason == "OK"

    def test_block_max_concurrent(self):
        rm = RiskManager(limits=RiskLimits(max_concurrent_positions=1))
        existing = {"BTC/USDT": _pos("BTC/USDT")}
        allowed, reason = rm.check_new_position(_pos("ETH/USDT"), existing)
        assert not allowed
        assert "max_concurrent" in reason

    def test_block_gross_exposure(self):
        # Two 0.25 positions already → gross=0.50 → adding 0.05 pushes to 0.55
        # Set net high enough not to trigger first; per_regime high too
        rm = RiskManager(limits=RiskLimits(
            max_gross_exposure=0.50, max_net_exposure=0.80,
            max_per_regime_exposure=1.0, max_per_symbol_net=1.0,
        ))
        existing = {
            "BTC/USDT": _pos("BTC/USDT", qty=0.25),
            "ETH/USDT": _pos("ETH/USDT", qty=0.25),
        }
        allowed, reason = rm.check_new_position(_pos("SOL/USDT", qty=0.05), existing)
        assert not allowed
        assert "gross_exposure" in reason

    def test_block_net_exposure(self):
        rm = RiskManager(limits=RiskLimits(
            max_net_exposure=0.20, max_per_regime_exposure=1.0,
        ))
        existing = {"BTC/USDT": _pos("BTC/USDT", qty=0.20)}
        allowed, reason = rm.check_new_position(_pos("ETH/USDT", qty=0.05), existing)
        assert not allowed
        assert "net_exposure" in reason

    def test_block_per_symbol_net(self):
        # Candidate alone exceeds per_symbol limit
        rm = RiskManager(limits=RiskLimits(
            max_per_symbol_net=0.10, max_per_regime_exposure=1.0,
        ))
        allowed, reason = rm.check_new_position(_pos("BTC/USDT", qty=0.20), {})
        assert not allowed
        assert "BTC/USDT" in reason

    def test_block_regime_exposure(self):
        rm = RiskManager(limits=RiskLimits(
            max_per_regime_exposure=0.05, max_per_symbol_net=1.0,
        ))
        existing = {"BTC/USDT": _pos("BTC/USDT", regime_id=1, qty=0.05)}
        candidate = _pos("ETH/USDT", regime_id=1, qty=0.01)
        allowed, reason = rm.check_new_position(candidate, existing)
        assert not allowed
        assert "regime_1" in reason

    def test_short_position_reduces_net(self):
        # Use permissive regime/symbol limits so only net is checked
        rm = RiskManager(limits=RiskLimits(
            max_net_exposure=0.25, max_per_regime_exposure=1.0, max_per_symbol_net=1.0,
        ))
        existing = {"BTC/USDT": _pos("BTC/USDT", side="long", qty=0.20)}
        short = _pos("ETH/USDT", side="short", qty=0.10)
        allowed, reason = rm.check_new_position(short, existing)
        assert allowed  # net = 0.20 - 0.10 = 0.10

    def test_portfolio_stats(self):
        rm = RiskManager()
        stats = rm.portfolio_stats({"A": _pos(qty=0.10), "B": _pos(qty=0.05, side="short")})
        assert stats["n_positions"] == 2
        assert abs(stats["net_exposure"] - 0.05) < 1e-9
        assert abs(stats["gross_exposure"] - 0.15) < 1e-9


# ================================================================== #
# StaleBreaker                                                         #
# ================================================================== #

class TestStaleBreaker:
    def test_raises_if_never_received(self):
        sb = StaleBreaker(max_stale_seconds=60)
        with pytest.raises(StaleFeedError, match="ever received"):
            sb.check("BTC")

    def test_passes_after_record(self):
        sb = StaleBreaker(max_stale_seconds=60)
        sb.record_bar("BTC")
        sb.check("BTC")  # should not raise

    def test_raises_when_stale(self):
        sb = StaleBreaker(max_stale_seconds=0)
        sb.record_bar("BTC")
        time.sleep(0.01)
        with pytest.raises(StaleFeedError, match="threshold 0s"):
            sb.check("BTC")

    def test_age_seconds_inf_if_unknown(self):
        sb = StaleBreaker()
        assert sb.age_seconds("UNKNOWN") == float("inf")

    def test_check_all_raises_on_first_stale(self):
        sb = StaleBreaker(max_stale_seconds=60)
        sb.record_bar("BTC")
        with pytest.raises(StaleFeedError):
            sb.check_all(["BTC", "ETH"])  # ETH never received


# ================================================================== #
# LiveJournal                                                          #
# ================================================================== #

def _make_record(**kwargs):
    defaults = dict(
        timestamp="2026-01-01T00:00:00",
        symbol="BTC/USDT",
        side="long",
        quantity=0.1,
        entry_price=50000.0,
        exit_price=51000.0,
        pnl=0.002,
        pnl_pct=0.02,
        max_drawdown=0.0,
        regime_id=0,
        card_version="3.0",
        slippage_bps=3.0,
        funding=0.00001,
    )
    defaults.update(kwargs)
    return TradeRecord(**defaults)


class TestLiveJournal:
    def test_creates_empty_parquet(self, tmp_path):
        j = LiveJournal(tmp_path / "journal.parquet")
        df = j.read()
        assert len(df) == 0
        assert "pnl" in df.columns

    def test_append_one(self, tmp_path):
        j = LiveJournal(tmp_path / "journal.parquet")
        j.append(_make_record())
        assert len(j.read()) == 1

    def test_append_many(self, tmp_path):
        j = LiveJournal(tmp_path / "journal.parquet")
        j.append_many([_make_record(), _make_record(symbol="ETH/USDT")])
        assert len(j.read()) == 2

    def test_atomic_append_survives_re_open(self, tmp_path):
        p = tmp_path / "journal.parquet"
        j1 = LiveJournal(p)
        j1.append(_make_record())
        j2 = LiveJournal(p)  # re-open
        j2.append(_make_record(symbol="ETH/USDT"))
        assert len(j2.read()) == 2

    def test_stats(self, tmp_path):
        j = LiveJournal(tmp_path / "journal.parquet")
        j.append(_make_record(pnl=0.01))
        j.append(_make_record(pnl=-0.005))
        s = j.stats()
        assert s["n_trades"] == 2
        assert abs(s["total_pnl"] - 0.005) < 1e-9
        assert abs(s["win_rate"] - 0.5) < 1e-9

    def test_stats_empty(self, tmp_path):
        j = LiveJournal(tmp_path / "journal.parquet")
        s = j.stats()
        assert s == {"n_trades": 0, "total_pnl": 0.0, "win_rate": 0.0}


# ================================================================== #
# LiveMonitor                                                          #
# ================================================================== #

class TestLiveMonitor:
    def test_emits_json_lines(self, tmp_path, capsys):
        m = LiveMonitor(log_path=tmp_path / "monitor.log")
        m.bar_processed("BTC", "2026-01-01", 0, 1.2, 5.0)
        m.close()
        out = capsys.readouterr().out
        record = json.loads(out.strip())
        assert record["event"] == "bar_processed"
        assert record["symbol"] == "BTC"

    def test_writes_log_file(self, tmp_path):
        log = tmp_path / "m.log"
        m = LiveMonitor(log_path=log)
        m.risk_blocked("ETH", "max_concurrent")
        m.close()
        lines = log.read_text().strip().split("\n")
        assert len(lines) == 1
        assert json.loads(lines[0])["event"] == "risk_blocked"

    def test_error_includes_exception(self, tmp_path, capsys):
        m = LiveMonitor()
        m.error("boom", exc=ValueError("bad value"))
        out = capsys.readouterr().out
        record = json.loads(out.strip())
        assert "ValueError" in record["exception"]


# ================================================================== #
# on_new_bar (main_loop)                                               #
# ================================================================== #

class TestOnNewBar:
    def _setup(self, tmp_path, lookback=2):
        state = _make_live_state(tmp_path, lookback=lookback)
        journal = LiveJournal(tmp_path / "journal.parquet")
        monitor = LiveMonitor()
        return state, journal, monitor

    def _factor_row(self, signal_value=0.0, n=4):
        """Produce factor_row such that weights@row = signal_value (weights=[0.5,0.3,0.1,0.1])."""
        row = np.zeros(n)
        row[0] = signal_value / 0.5
        return row

    def test_warming_up_while_buffer_filling(self, tmp_path, capsys):
        state, journal, monitor = self._setup(tmp_path, lookback=3)
        open_positions = {}
        bar = _make_bar_df()
        factor_row = self._factor_row(1.0)
        # Only send 2 bars with lookback=3 → warming_up
        open_positions, result = on_new_bar("BTC", bar, factor_row, state, open_positions, journal, monitor)
        assert result.action == "warming_up"

    def test_hold_when_signal_below_threshold(self, tmp_path, capsys):
        state, journal, monitor = self._setup(tmp_path, lookback=2)
        open_positions = {}
        bar = _make_bar_df()
        factor_row = self._factor_row(0.1)  # below entry_threshold=0.5
        # Fill buffer
        on_new_bar("BTC", bar, factor_row, state, open_positions, journal, monitor)
        open_positions, result = on_new_bar("BTC", bar, factor_row, state, open_positions, journal, monitor)
        assert result.action == "hold"

    def test_entry_long_on_strong_signal(self, tmp_path, capsys):
        state, journal, monitor = self._setup(tmp_path, lookback=2)
        open_positions = {}
        bar = _make_bar_df()
        factor_row = self._factor_row(1.0)  # above threshold 0.5
        on_new_bar("BTC", bar, factor_row, state, open_positions, journal, monitor)
        open_positions, result = on_new_bar("BTC", bar, factor_row, state, open_positions, journal, monitor)
        assert result.action == "entry_long"
        assert "BTC" in open_positions

    def test_entry_short_on_negative_signal(self, tmp_path, capsys):
        state, journal, monitor = self._setup(tmp_path, lookback=2)
        open_positions = {}
        bar = _make_bar_df()
        factor_row = self._factor_row(-1.0)
        on_new_bar("BTC", bar, factor_row, state, open_positions, journal, monitor)
        open_positions, result = on_new_bar("BTC", bar, factor_row, state, open_positions, journal, monitor)
        assert result.action == "entry_short"

    def test_exit_on_weak_signal(self, tmp_path, capsys):
        state, journal, monitor = self._setup(tmp_path, lookback=2)
        open_positions = {"BTC": _pos("BTC", regime_id=0)}
        bar = _make_bar_df()
        factor_row = self._factor_row(0.1)  # below exit_threshold=0.2? No, 0.1 < 0.2 → exit
        on_new_bar("BTC", bar, factor_row, state, open_positions, journal, monitor)
        open_positions, result = on_new_bar("BTC", bar, factor_row, state, open_positions, journal, monitor)
        assert result.action == "exit"
        assert "BTC" not in open_positions
        assert len(journal.read()) == 1

    def test_exit_on_regime_change(self, tmp_path, capsys):
        state, journal, monitor = self._setup(tmp_path, lookback=2)
        # Position in regime 0, but labeler now returns regime 1 (after debounce)
        state.labeler.label.return_value = np.array([1, 1])
        # Force predictor to be in regime 1 after 5 steps (debounce=5)
        for _ in range(6):
            state.predictor.step(1)
        assert state.predictor.active_regime == 1

        open_positions = {"BTC": _pos("BTC", regime_id=0)}  # pos in regime 0
        bar = _make_bar_df()
        factor_row = self._factor_row(1.0)  # strong signal but regime mismatch
        on_new_bar("BTC", bar, factor_row, state, open_positions, journal, monitor)
        open_positions, result = on_new_bar("BTC", bar, factor_row, state, open_positions, journal, monitor)
        assert result.action == "exit"

    def test_risk_blocked(self, tmp_path, capsys):
        state, journal, monitor = self._setup(tmp_path, lookback=2)
        state.risk_manager.limits.max_concurrent_positions = 0
        open_positions = {}
        bar = _make_bar_df()
        factor_row = self._factor_row(1.0)
        on_new_bar("BTC", bar, factor_row, state, open_positions, journal, monitor)
        open_positions, result = on_new_bar("BTC", bar, factor_row, state, open_positions, journal, monitor)
        assert result.action == "risk_blocked"
        assert "BTC" not in open_positions

    def test_stale_feed(self, tmp_path, capsys):
        state, journal, monitor = self._setup(tmp_path, lookback=2)
        state.stale_breaker._state["BTC"] = MagicMock()
        state.stale_breaker._state["BTC"].last_bar_time = time.monotonic() - 9999
        open_positions = {}
        bar = _make_bar_df()
        factor_row = self._factor_row(1.0)
        open_positions, result = on_new_bar("BTC", bar, factor_row, state, open_positions, journal, monitor)
        # After record_bar, stale_breaker resets — so stale won't trigger here
        # Test the path directly: use max_stale_seconds=0
        state.stale_breaker.max_stale_seconds = 0
        time.sleep(0.01)
        open_positions, result = on_new_bar("BTC", bar, factor_row, state, open_positions, journal, monitor)
        assert result.action == "stale"

    def test_latency_under_50ms(self, tmp_path, capsys):
        state, journal, monitor = self._setup(tmp_path, lookback=2)
        open_positions = {}
        bar = _make_bar_df()
        factor_row = self._factor_row(0.0)
        # warm buffer
        on_new_bar("BTC", bar, factor_row, state, open_positions, journal, monitor)
        open_positions, result = on_new_bar("BTC", bar, factor_row, state, open_positions, journal, monitor)
        assert result.latency_ms < 50.0, f"latency {result.latency_ms:.1f}ms > 50ms"
