"""Live monitor: structured metrics emission for observability (C29).

Emits structured JSON lines to stdout (and optionally to a log file).
Downstream can tail the log file or pipe to a collector.

Metrics emitted per bar:
  - bar_processed: symbol, timestamp, regime_id, signal, latency_ms
  - position_opened / position_closed: trade details
  - risk_blocked: reason why a position was blocked
  - regime_switch: old → new regime
  - stale_feed: symbol, age_seconds
  - portfolio_snapshot: exposure stats
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, TextIO


@dataclass
class LiveMonitor:
    log_path: Optional[str | Path] = None
    _file: Optional[TextIO] = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.log_path is not None:
            p = Path(self.log_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            self._file = p.open("a", encoding="utf-8")

    # ------------------------------------------------------------------ #
    # Emit helpers                                                         #
    # ------------------------------------------------------------------ #

    def bar_processed(
        self,
        symbol: str,
        bar_timestamp: str,
        regime_id: int,
        signal: float,
        latency_ms: float,
    ) -> None:
        self._emit(
            "bar_processed",
            symbol=symbol,
            bar_timestamp=bar_timestamp,
            regime_id=regime_id,
            signal=signal,
            latency_ms=latency_ms,
        )

    def position_opened(self, symbol: str, side: str, quantity: float, price: float, regime_id: int) -> None:
        self._emit(
            "position_opened",
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            regime_id=regime_id,
        )

    def position_closed(
        self,
        symbol: str,
        pnl: float,
        pnl_pct: float,
        slippage_bps: float,
        funding: float,
    ) -> None:
        self._emit(
            "position_closed",
            symbol=symbol,
            pnl=pnl,
            pnl_pct=pnl_pct,
            slippage_bps=slippage_bps,
            funding=funding,
        )

    def risk_blocked(self, symbol: str, reason: str) -> None:
        self._emit("risk_blocked", symbol=symbol, reason=reason)

    def regime_switch(self, symbol: str, old_regime: int, new_regime: int, confidence: float) -> None:
        self._emit(
            "regime_switch",
            symbol=symbol,
            old_regime=old_regime,
            new_regime=new_regime,
            confidence=confidence,
        )

    def stale_feed(self, symbol: str, age_seconds: float) -> None:
        self._emit("stale_feed", symbol=symbol, age_seconds=age_seconds)

    def portfolio_snapshot(self, stats: Dict[str, Any]) -> None:
        self._emit("portfolio_snapshot", **stats)

    def error(self, message: str, exc: Optional[Exception] = None) -> None:
        kwargs: Dict[str, Any] = {"message": message}
        if exc is not None:
            kwargs["exception"] = repr(exc)
        self._emit("error", **kwargs)

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _emit(self, event: str, **kwargs: Any) -> None:
        record = {"ts": time.time(), "event": event, **kwargs}
        line = json.dumps(record, separators=(",", ":"))
        print(line, flush=True)
        if self._file is not None:
            self._file.write(line + "\n")
            self._file.flush()

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None

    def __del__(self) -> None:
        self.close()


__all__ = ["LiveMonitor"]
