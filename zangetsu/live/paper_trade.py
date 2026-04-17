"""Paper trading — simulate fills against live feed without real execution.

Tracks simulated positions and PnL in the paper_trades table.
Uses the same risk_manager and journal interfaces as real trading would.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

LOG = logging.getLogger("zangetsu.paper_trade")


@dataclass
class TradeRecord:
    """Immutable record of a simulated trade."""
    trade_id: str
    symbol: str
    side: str           # "long" or "short"
    entry_price: float
    entry_ts: float
    size_usd: float
    regime: str
    card_id: str
    exit_price: Optional[float] = None
    exit_ts: Optional[float] = None
    pnl: Optional[float] = None


@dataclass
class PaperState:
    """Per-symbol position state for paper trading."""
    position: Optional[TradeRecord] = None
    equity: float = 10_000.0
    peak_equity: float = 10_000.0
    trade_count: int = 0
    win_count: int = 0
    total_pnl: float = 0.0


class PaperTrader:
    """Simulates trade execution against live bar data.

    Dependencies:
        ws_feed: BinanceFuturesWS — provides bar data
        risk_manager: check_new_position() for pre-trade validation
        journal: TradeJournal — for logging trades
        db: PipelineDB — for paper_trades table persistence
    """

    def __init__(
        self,
        db: Any,
        risk_manager: Any = None,
        journal: Any = None,
        initial_equity: float = 10_000.0,
        default_size_pct: float = 0.02,
    ) -> None:
        self._db = db
        self._risk_manager = risk_manager
        self._journal = journal
        self._initial_equity = initial_equity
        self._default_size_pct = default_size_pct
        self._states: Dict[str, PaperState] = {}

    async def ensure_table(self) -> None:
        """Create paper_trades table if not exists."""
        async with self._db.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS paper_trades (
                    id          SERIAL PRIMARY KEY,
                    ts          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    trade_id    TEXT UNIQUE NOT NULL,
                    symbol      TEXT NOT NULL,
                    side        TEXT NOT NULL,
                    entry_price DOUBLE PRECISION NOT NULL,
                    exit_price  DOUBLE PRECISION,
                    size_usd    DOUBLE PRECISION NOT NULL,
                    pnl         DOUBLE PRECISION,
                    regime      TEXT,
                    card_id     TEXT,
                    entry_ts    DOUBLE PRECISION,
                    exit_ts     DOUBLE PRECISION
                )
            """)

    def _get_state(self, symbol: str) -> PaperState:
        if symbol not in self._states:
            self._states[symbol] = PaperState(equity=self._initial_equity,
                                               peak_equity=self._initial_equity)
        return self._states[symbol]

    async def process_bar(
        self,
        symbol: str,
        bar: Dict[str, Any],
        regime: str,
        card_id: str,
        signal: Optional[int],
    ) -> Optional[TradeRecord]:
        """Process a completed bar for paper trading.

        Args:
            symbol: trading pair (e.g. BTCUSDT)
            bar: dict with keys: open, high, low, close, volume, ts
            regime: current regime label from regime_labeler
            card_id: active card/strategy ID
            signal: +1 (long), -1 (short), 0 (flat/exit), None (no signal)

        Returns:
            TradeRecord if a trade was opened or closed, else None.
        """
        state = self._get_state(symbol)
        close = float(bar["close"])

        # Binary position model: if we have a position and signal is 0 or opposite, close
        if state.position is not None:
            pos = state.position
            should_close = (
                signal == 0
                or signal is None
                or (signal == 1 and pos.side == "short")
                or (signal == -1 and pos.side == "long")
            )
            if should_close:
                record = await self._simulate_exit(symbol, close)
                # If signal is opposite direction, open new position after close
                if signal in (1, -1) and record is not None:
                    await self._simulate_entry(symbol, close, signal, regime, card_id)
                return record

        # No position — check for entry signal
        if signal in (1, -1) and state.position is None:
            return await self._simulate_entry(symbol, close, signal, regime, card_id)

        return None

    async def _simulate_entry(
        self,
        symbol: str,
        price: float,
        signal: int,
        regime: str,
        card_id: str,
    ) -> Optional[TradeRecord]:
        """Open a new simulated position."""
        state = self._get_state(symbol)
        side = "long" if signal == 1 else "short"
        size_usd = state.equity * self._default_size_pct

        # Risk check (if risk_manager available)
        if self._risk_manager is not None:
            from .risk_manager import ProposedTrade, Position, check_new_position
            proposed = ProposedTrade(
                symbol=symbol, side=side, size_usd=size_usd,
                quant_class="sharpe", regime=0,
            )
            ok, reason = check_new_position([], proposed, state.equity)
            if not ok:
                LOG.debug("Risk rejected %s %s: %s", symbol, side, reason)
                return None

        trade_id = f"paper-{uuid.uuid4().hex[:12]}"
        record = TradeRecord(
            trade_id=trade_id, symbol=symbol, side=side,
            entry_price=price, entry_ts=time.time(),
            size_usd=size_usd, regime=regime, card_id=card_id,
        )
        state.position = record
        state.trade_count += 1
        LOG.info("Paper ENTRY: %s %s @ %.2f (size=$%.0f, card=%s)",
                 symbol, side, price, size_usd, card_id)

        # Persist to DB
        await self._persist_entry(record)
        return record

    async def _simulate_exit(
        self, symbol: str, price: float,
    ) -> Optional[TradeRecord]:
        """Close the current simulated position."""
        state = self._get_state(symbol)
        if state.position is None:
            return None

        pos = state.position
        pos.exit_price = price
        pos.exit_ts = time.time()

        # Calculate PnL
        if pos.side == "long":
            pos.pnl = (price - pos.entry_price) / pos.entry_price * pos.size_usd
        else:
            pos.pnl = (pos.entry_price - price) / pos.entry_price * pos.size_usd

        state.equity += pos.pnl
        state.total_pnl += pos.pnl
        state.peak_equity = max(state.peak_equity, state.equity)
        if pos.pnl > 0:
            state.win_count += 1

        LOG.info("Paper EXIT: %s %s @ %.2f pnl=%.2f equity=%.2f",
                 symbol, pos.side, price, pos.pnl, state.equity)

        # Persist exit to DB
        await self._persist_exit(pos)

        # Log to journal if available
        if self._journal is not None:
            try:
                await self._journal.append_trade({
                    "symbol": symbol, "side": pos.side,
                    "size_usd": pos.size_usd,
                    "entry_price": pos.entry_price,
                    "exit_price": price, "pnl": pos.pnl,
                    "regime": 0, "strategy_id": pos.card_id,
                    "quant_class": "paper",
                })
            except Exception:
                LOG.exception("Failed to log to journal")

        state.position = None
        return pos

    async def _persist_entry(self, record: TradeRecord) -> None:
        """Insert new trade row (exit fields NULL)."""
        try:
            async with self._db.acquire() as conn:
                await conn.execute("""
                    INSERT INTO paper_trades
                        (trade_id, symbol, side, entry_price, size_usd, regime, card_id, entry_ts)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """, record.trade_id, record.symbol, record.side,
                    record.entry_price, record.size_usd, record.regime,
                    record.card_id, record.entry_ts)
        except Exception:
            LOG.exception("Failed to persist entry %s", record.trade_id)

    async def _persist_exit(self, record: TradeRecord) -> None:
        """Update trade row with exit data."""
        try:
            async with self._db.acquire() as conn:
                await conn.execute("""
                    UPDATE paper_trades
                    SET exit_price=$1, pnl=$2, exit_ts=$3
                    WHERE trade_id=$4
                """, record.exit_price, record.pnl, record.exit_ts, record.trade_id)
        except Exception:
            LOG.exception("Failed to persist exit %s", record.trade_id)

    def get_state(self, symbol: str) -> Dict[str, Any]:
        """Return current paper state for a symbol."""
        s = self._get_state(symbol)
        return {
            "equity": s.equity, "peak_equity": s.peak_equity,
            "total_pnl": s.total_pnl, "trade_count": s.trade_count,
            "win_count": s.win_count,
            "win_rate": s.win_count / max(s.trade_count, 1),
            "has_position": s.position is not None,
            "position_side": s.position.side if s.position else None,
        }

    def health_check(self) -> Dict[str, Any]:
        """Dashboard hook: paper trading status."""
        return {
            sym: self.get_state(sym) for sym in self._states
        }
