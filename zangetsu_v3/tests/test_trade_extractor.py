import sys, os
sys.path.insert(0, os.path.expanduser("~/j13-ops/zangetsu_v3"))
from backtest_regime import extract_trades_from_backtest, backtest_regime_conditional, compute_regime_fitness
import numpy as np
import pytest


def test_1_no_trades():
    pnl = np.zeros(100)
    pos = np.zeros(100, dtype=np.int8)
    close = np.ones(100) * 50000.0
    result = extract_trades_from_backtest(pnl, pos, close, 0.05, 4.0, 10.0)
    assert result == []


def test_2_single_long():
    pos = np.array([0, 0, 1, 1, 1, 0, 0], dtype=np.int8)
    pnl = np.zeros(7)
    close = np.array([100, 100, 100, 101, 102, 103, 103], dtype=np.float64)
    pos_frac = 0.05
    maker_bps = 4.0
    # entry at i=2: pnl[2] = -maker_bps/10000 * pos_frac
    pnl[2] = -4.0 / 10000.0 * 0.05
    # hold at i=3: pnl[3] = 1 * (101-100)/100 * 0.05
    pnl[3] = (101 - 100) / 100 * 0.05
    # hold at i=4: pnl[4] = 1 * (102-101)/101 * 0.05
    pnl[4] = (102 - 101) / 101 * 0.05
    # exit at i=5: pnl[5] = 1*(103-102)/102*0.05 - maker_bps/10000*0.05
    pnl[5] = (103 - 102) / 102 * 0.05 - 4.0 / 10000.0 * 0.05

    result = extract_trades_from_backtest(pnl, pos, close, pos_frac, maker_bps, 10.0)
    assert len(result) == 1
    t = result[0]
    assert t['direction'] == 1
    assert t['hold_bars'] == 3  # i=5 - i=2
    assert t['entry_idx'] == 2
    assert t['exit_idx'] == 5


def test_3_reverse():
    pos = np.array([0, 1, 1, -1, -1, 0], dtype=np.int8)
    pnl = np.zeros(6)
    close = np.array([100, 100, 101, 102, 101, 100], dtype=np.float64)
    pos_frac = 0.05
    # entry long at i=1
    pnl[1] = -4.0 / 10000.0 * 0.05
    # hold at i=2
    pnl[2] = (101 - 100) / 100 * 0.05
    # reverse at i=3: close long + open short
    pnl[3] = 1 * (102 - 101) / 101 * 0.05 - 4.0 / 10000.0 * 0.05
    # hold short at i=4
    pnl[4] = -1 * (101 - 102) / 102 * 0.05  # short profits when price drops
    # exit short at i=5
    pnl[5] = -1 * (100 - 101) / 101 * 0.05 - 4.0 / 10000.0 * 0.05

    result = extract_trades_from_backtest(pnl, pos, close, pos_frac, 4.0, 10.0)
    assert len(result) == 2
    assert result[0]['direction'] == 1   # long
    assert result[1]['direction'] == -1  # short


def test_4_count_match():
    # Run an actual backtest and verify trade count matches compute_regime_fitness
    np.random.seed(42)
    n = 10000
    signal = np.random.randn(n) * 0.5
    close = 50000 + np.cumsum(np.random.randn(n) * 10)
    close = np.maximum(close, 1000)  # prevent negative prices
    regime_labels = np.zeros(n, dtype=np.int8)  # all regime 0

    pnl, pos, exit_type = backtest_regime_conditional(
        signal, close.astype(np.float64), regime_labels, np.int8(0),
        0.7, 0.3, 2.0, 0.05, 480, 6,
        4.0, 10.0, 0.0001
    )

    trades = extract_trades_from_backtest(pnl, pos, close, 0.05, 4.0, 10.0, exit_type)

    # Count entries from compute_regime_fitness
    regime_pnl = pnl[regime_labels == 0]
    entries_fitness = int(np.sum(np.diff((regime_pnl != 0).astype(np.int8)) == 1))

    # Extractor trade count should match (possibly ±1 for unclosed position)
    assert abs(len(trades) - entries_fitness) <= 1, \
        f"Extractor found {len(trades)} trades, fitness counter found {entries_fitness}"
