"""Per-quant-class risk management with kill switches and position limits.

Enforces drawdown limits per quant class, max position sizing,
and correlated position caps before any new trade is placed.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple


class QuantClass(str, Enum):
    SHARPE = "sharpe"
    EXPECTANCY = "expectancy"
    PNL = "pnl"


# Per-class max drawdown before kill switch triggers
_CLASS_DD_LIMIT: Dict[QuantClass, float] = {
    QuantClass.SHARPE: 0.03,       # 3% DD
    QuantClass.EXPECTANCY: 0.05,   # 5% DD
    QuantClass.PNL: 0.07,          # 7% DD
}

# Default limits
_DEFAULT_MAX_POSITION_PCT: float = 0.02   # 2% of equity per position
_DEFAULT_MAX_CORRELATED: int = 3          # max positions in same regime


@dataclass
class Position:
    symbol: str
    side: str            # "long" or "short"
    size_usd: float
    quant_class: str     # maps to QuantClass value
    regime: int          # regime label from regime_labeler
    entry_equity: float  # equity at entry
    peak_equity: float   # peak equity since entry
    current_equity: float


@dataclass
class ProposedTrade:
    symbol: str
    side: str
    size_usd: float
    quant_class: str
    regime: int


def _current_drawdown(pos: Position) -> float:
    """Drawdown from peak equity, as a positive fraction."""
    if pos.peak_equity <= 0:
        return 0.0
    return max(0.0, (pos.peak_equity - pos.current_equity) / pos.peak_equity)


def _check_kill_switch(
    positions: List[Position],
) -> Tuple[bool, Optional[str]]:
    """Check if any quant class has breached its drawdown limit.

    Returns (killed, reason). If killed is True, no new positions allowed.
    """
    # Aggregate max drawdown per quant class
    class_dd: Dict[str, float] = {}
    for pos in positions:
        dd = _current_drawdown(pos)
        key = pos.quant_class
        if key not in class_dd or dd > class_dd[key]:
            class_dd[key] = dd

    for cls_name, dd in class_dd.items():
        try:
            qc = QuantClass(cls_name)
        except ValueError:
            continue
        limit = _CLASS_DD_LIMIT.get(qc, 0.05)
        if dd >= limit:
            return True, (
                f"Kill switch: {qc.value} class drawdown {dd:.1%} >= {limit:.1%}"
            )
    return False, None


def _check_position_size(
    proposed: ProposedTrade,
    equity: float,
    max_pct: float = _DEFAULT_MAX_POSITION_PCT,
) -> Tuple[bool, Optional[str]]:
    """Reject if proposed size exceeds max % of equity."""
    if equity <= 0:
        return False, "Equity <= 0, cannot open position"
    ratio = proposed.size_usd / equity
    if ratio > max_pct:
        return False, (
            f"Position size {ratio:.2%} of equity exceeds limit {max_pct:.2%}"
        )
    return True, None


def _check_correlated_positions(
    positions: List[Position],
    proposed: ProposedTrade,
    max_correlated: int = _DEFAULT_MAX_CORRELATED,
) -> Tuple[bool, Optional[str]]:
    """Reject if too many open positions share the same regime."""
    same_regime = sum(1 for p in positions if p.regime == proposed.regime)
    if same_regime >= max_correlated:
        return False, (
            f"Already {same_regime} positions in regime {proposed.regime} "
            f"(limit {max_correlated})"
        )
    return True, None


def check_new_position(
    positions: List[Position],
    proposed: ProposedTrade,
    equity: float,
    max_position_pct: float = _DEFAULT_MAX_POSITION_PCT,
    max_correlated: int = _DEFAULT_MAX_CORRELATED,
) -> Tuple[bool, str]:
    """Main entry point: validate a proposed trade against all risk rules.

    Returns:
        (approved, reason): True + "OK" if approved, False + reason if rejected.
    """
    # 1. Kill switch -- any class in drawdown?
    killed, reason = _check_kill_switch(positions)
    if killed:
        return False, reason  # type: ignore[return-value]

    # 2. Position size check
    ok, reason = _check_position_size(proposed, equity, max_position_pct)
    if not ok:
        return False, reason  # type: ignore[return-value]

    # 3. Correlated positions check
    ok, reason = _check_correlated_positions(positions, proposed, max_correlated)
    if not ok:
        return False, reason  # type: ignore[return-value]

    return True, "OK"
