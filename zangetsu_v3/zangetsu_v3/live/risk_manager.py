"""Live risk manager: position-level exposure checks (C28).

All checks are synchronous and stateless given the portfolio snapshot.
Returns (allowed: bool, reason: str) for every gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class Position:
    symbol: str
    regime_id: int
    side: str          # "long" | "short"
    quantity: float    # absolute notional fraction of equity
    entry_price: float


@dataclass
class RiskLimits:
    max_net_exposure: float = 0.25
    max_gross_exposure: float = 0.50
    max_per_regime_exposure: float = 0.15
    max_per_symbol_net: float = 0.15
    max_concurrent_positions: int = 8


@dataclass
class RiskManager:
    limits: RiskLimits = field(default_factory=RiskLimits)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def check_new_position(
        self,
        candidate: Position,
        open_positions: Dict[str, Position],
    ) -> tuple[bool, str]:
        """Return (True, "OK") if candidate can be opened, else (False, reason)."""

        if len(open_positions) >= self.limits.max_concurrent_positions:
            return False, (
                f"max_concurrent_positions reached "
                f"({self.limits.max_concurrent_positions})"
            )

        # Build prospective portfolio
        prospective = dict(open_positions)
        prospective[candidate.symbol] = candidate

        net = self._net_exposure(prospective)
        gross = self._gross_exposure(prospective)
        regime_exp = self._regime_exposure(prospective, candidate.regime_id)
        symbol_net = self._symbol_net(prospective, candidate.symbol)

        if abs(net) > self.limits.max_net_exposure:
            return False, f"net_exposure {net:.3f} > {self.limits.max_net_exposure}"
        if gross > self.limits.max_gross_exposure:
            return False, f"gross_exposure {gross:.3f} > {self.limits.max_gross_exposure}"
        if regime_exp > self.limits.max_per_regime_exposure:
            return False, (
                f"regime_{candidate.regime_id} exposure {regime_exp:.3f} "
                f"> {self.limits.max_per_regime_exposure}"
            )
        if abs(symbol_net) > self.limits.max_per_symbol_net:
            return False, (
                f"{candidate.symbol} net {symbol_net:.3f} "
                f"> {self.limits.max_per_symbol_net}"
            )

        return True, "OK"

    def portfolio_stats(self, open_positions: Dict[str, Position]) -> dict:
        """Snapshot of current exposure metrics for monitoring."""
        return {
            "n_positions": len(open_positions),
            "net_exposure": self._net_exposure(open_positions),
            "gross_exposure": self._gross_exposure(open_positions),
        }

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _signed(pos: Position) -> float:
        return pos.quantity if pos.side == "long" else -pos.quantity

    def _net_exposure(self, positions: Dict[str, Position]) -> float:
        return sum(self._signed(p) for p in positions.values())

    def _gross_exposure(self, positions: Dict[str, Position]) -> float:
        return sum(abs(p.quantity) for p in positions.values())

    def _regime_exposure(self, positions: Dict[str, Position], regime_id: int) -> float:
        return sum(
            abs(p.quantity) for p in positions.values() if p.regime_id == regime_id
        )

    def _symbol_net(self, positions: Dict[str, Position], symbol: str) -> float:
        return sum(
            self._signed(p) for p in positions.values() if p.symbol == symbol
        )


__all__ = ["RiskManager", "RiskLimits", "Position"]
