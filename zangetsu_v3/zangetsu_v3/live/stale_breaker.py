"""Stale-data circuit breaker (C28).

Tracks the wall-clock age of the most recent bar received per symbol.
Raises StaleFeedError when age exceeds max_stale_seconds to prevent
the live loop from trading on stale data.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict


class StaleFeedError(RuntimeError):
    """Raised when a symbol's last bar is older than max_stale_seconds."""


@dataclass
class StaleBreakerState:
    last_bar_time: float = field(default_factory=time.monotonic)  # wall clock seconds


@dataclass
class StaleBreaker:
    max_stale_seconds: int = 60

    _state: Dict[str, StaleBreakerState] = field(default_factory=dict, repr=False)

    def record_bar(self, symbol: str) -> None:
        """Call this every time a new bar arrives for symbol."""
        self._state[symbol] = StaleBreakerState(last_bar_time=time.monotonic())

    def check(self, symbol: str) -> None:
        """Raise StaleFeedError if symbol data is stale.

        If no bar has ever been received, the symbol is considered stale
        immediately (never-seen = infinitely old).
        """
        if symbol not in self._state:
            raise StaleFeedError(
                f"{symbol}: no bar ever received (feed never started)"
            )
        age = time.monotonic() - self._state[symbol].last_bar_time
        if age > self.max_stale_seconds:
            raise StaleFeedError(
                f"{symbol}: last bar {age:.1f}s ago, "
                f"threshold {self.max_stale_seconds}s"
            )

    def check_all(self, symbols: list[str]) -> None:
        """Check all symbols; raises on the first stale one found."""
        for sym in symbols:
            self.check(sym)

    def age_seconds(self, symbol: str) -> float:
        """Return seconds since last bar, or inf if never received."""
        if symbol not in self._state:
            return float("inf")
        return time.monotonic() - self._state[symbol].last_bar_time


__all__ = ["StaleBreaker", "StaleFeedError"]
