"""Threshold invariants — A2_MIN_TRADES and Arena gates remain unchanged.

This is the explicit test for STOP-9 (A2_MIN_TRADES change) and STOP-8
(Arena threshold weakened) under 0-9AB.
"""

from zangetsu.services import arena_gates
from zangetsu.config import settings as zs


def test_arena_gates_a2_min_trades_25():
    assert arena_gates.A2_MIN_TRADES == 25


def test_settings_arena2_min_trades_25():
    assert zs.ARENA2_MIN_TRADES == 25
    assert zs.Settings().arena2_min_trades == 25


def test_arena2_pass_rejects_below_25_trades():
    from zangetsu.services.arena_gates import Trade, arena2_pass
    trades = [Trade(pnl=10.0, entry_idx=i, exit_idx=i+1) for i in range(24)]
    res = arena2_pass(trades)
    assert res.passed is False
    assert res.reason == 'too_few_trades'
