"""Per-symbol cost model: taker fees, funding rates, slippage estimates.

Costs vary by exchange, symbol, and account tier. This module provides
a lookup table consumed by Arena 3 (PnL training) and the backtester.

V5 Architecture: 14 symbols across 3 tiers (Stable / Diversified / High-Vol).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass(frozen=True)
class SymbolCost:
    """Cost parameters for a single trading pair."""
    symbol: str
    taker_bps: float           # taker fee in basis points
    maker_bps: float           # maker fee (rebate if negative)
    funding_8h_avg_bps: float  # average 8-hour funding rate
    slippage_bps: float        # estimated market-order slippage
    min_notional_usd: float    # minimum order size

    @property
    def total_round_trip_bps(self) -> float:
        """Total cost for entry + exit (taker both sides) + avg funding."""
        return (self.taker_bps * 2) + self.slippage_bps + self.funding_8h_avg_bps


# ── Tier definitions ─────────────────────────────────────────────
# Stable:       maker=2.0  taker=5.0   slippage=0.5
# Diversified:  maker=2.5  taker=6.25  slippage=1.0
# High-Vol:     maker=4.0  taker=10.0  slippage=2.0
# Funding rate: 1.0 bps per 8h for all symbols.

# ── Default cost table ───────────────────────────────────────────
# Based on Binance Futures tiered model, V5 architecture spec.
# CONSOLE_HOOK: cost_table (entire table replaceable)
DEFAULT_COST_TABLE: Dict[str, SymbolCost] = {
    # ── Stable tier (6 symbols) ──────────────────────────────────
    "BTCUSDT":  SymbolCost("BTCUSDT",  taker_bps=5.0,  maker_bps=2.0, funding_8h_avg_bps=1.0, slippage_bps=0.5, min_notional_usd=5.0),
    "ETHUSDT":  SymbolCost("ETHUSDT",  taker_bps=5.0,  maker_bps=2.0, funding_8h_avg_bps=1.0, slippage_bps=0.5, min_notional_usd=5.0),
    "BNBUSDT":  SymbolCost("BNBUSDT",  taker_bps=5.0,  maker_bps=2.0, funding_8h_avg_bps=1.0, slippage_bps=0.5, min_notional_usd=5.0),
    "SOLUSDT":  SymbolCost("SOLUSDT",  taker_bps=5.0,  maker_bps=2.0, funding_8h_avg_bps=1.0, slippage_bps=0.5, min_notional_usd=5.0),
    "XRPUSDT":  SymbolCost("XRPUSDT",  taker_bps=5.0,  maker_bps=2.0, funding_8h_avg_bps=1.0, slippage_bps=0.5, min_notional_usd=5.0),
    "DOGEUSDT": SymbolCost("DOGEUSDT", taker_bps=5.0,  maker_bps=2.0, funding_8h_avg_bps=1.0, slippage_bps=0.5, min_notional_usd=5.0),
    # ── Diversified tier (5 symbols) ─────────────────────────────
    "LINKUSDT": SymbolCost("LINKUSDT", taker_bps=6.25, maker_bps=2.5, funding_8h_avg_bps=1.0, slippage_bps=1.0, min_notional_usd=5.0),
    "AAVEUSDT": SymbolCost("AAVEUSDT", taker_bps=6.25, maker_bps=2.5, funding_8h_avg_bps=1.0, slippage_bps=1.0, min_notional_usd=5.0),
    "AVAXUSDT": SymbolCost("AVAXUSDT", taker_bps=6.25, maker_bps=2.5, funding_8h_avg_bps=1.0, slippage_bps=1.0, min_notional_usd=5.0),
    "DOTUSDT":  SymbolCost("DOTUSDT",  taker_bps=6.25, maker_bps=2.5, funding_8h_avg_bps=1.0, slippage_bps=1.0, min_notional_usd=5.0),
    "FILUSDT":  SymbolCost("FILUSDT",  taker_bps=6.25, maker_bps=2.5, funding_8h_avg_bps=1.0, slippage_bps=1.0, min_notional_usd=5.0),
    # ── High-Vol tier (3 symbols) ────────────────────────────────
    "1000PEPEUSDT": SymbolCost("1000PEPEUSDT", taker_bps=10.0, maker_bps=4.0, funding_8h_avg_bps=1.0, slippage_bps=2.0, min_notional_usd=5.0),
    "1000SHIBUSDT": SymbolCost("1000SHIBUSDT", taker_bps=10.0, maker_bps=4.0, funding_8h_avg_bps=1.0, slippage_bps=2.0, min_notional_usd=5.0),
    "GALAUSDT":     SymbolCost("GALAUSDT",     taker_bps=10.0, maker_bps=4.0, funding_8h_avg_bps=1.0, slippage_bps=2.0, min_notional_usd=5.0),
}


class CostModel:
    """Runtime cost model. Supports per-symbol overrides from console.

    Usage:
        model = CostModel()
        cost = model.get("BTCUSDT")
        total = cost.total_round_trip_bps
    """

    def __init__(
        self,
        table: Optional[Dict[str, SymbolCost]] = None,
        default_taker_bps: float = 6.25,      # CONSOLE_HOOK: default_taker_bps
        default_slippage_bps: float = 1.5,     # CONSOLE_HOOK: default_slippage_bps
    ) -> None:
        self._table: Dict[str, SymbolCost] = dict(table or DEFAULT_COST_TABLE)
        self._default_taker = default_taker_bps
        self._default_slippage = default_slippage_bps

    def get(self, symbol: str) -> SymbolCost:
        """Return cost for symbol, or a conservative default."""
        if symbol in self._table:
            return self._table[symbol]
        return SymbolCost(
            symbol=symbol,
            taker_bps=self._default_taker,
            maker_bps=2.5,
            funding_8h_avg_bps=1.0,
            slippage_bps=self._default_slippage,
            min_notional_usd=5.0,
        )

    def update_symbol(self, symbol: str, cost: SymbolCost) -> None:
        """Override cost for a symbol at runtime (console API)."""
        self._table[symbol] = cost

    # DASHBOARD_HOOK: cost_table_snapshot
    def snapshot(self) -> Dict[str, Dict[str, float]]:
        """Return serializable snapshot of all costs."""
        return {
            sym: {
                "taker_bps": c.taker_bps,
                "maker_bps": c.maker_bps,
                "funding_8h_avg_bps": c.funding_8h_avg_bps,
                "slippage_bps": c.slippage_bps,
                "total_round_trip_bps": c.total_round_trip_bps,
            }
            for sym, c in self._table.items()
        }
