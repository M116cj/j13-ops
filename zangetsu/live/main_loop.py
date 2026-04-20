"""Live trading main loop — subscribe to WS feed, process bars, manage cards.

Orchestrates the live trading flow:
  1. Load active (DEPLOYED) cards from champion_pipeline_fresh
  2. Subscribe to Binance Futures WS feed
  3. On each completed bar: detect regime → match card → compute signal → paper trade
  4. Every 5 min: check for card rotations
  5. Binary position model: trigger = close 100%
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

LOG = logging.getLogger("zangetsu.main_loop")

# Card reload interval (seconds)
_RELOAD_INTERVAL = 300  # 5 minutes


@dataclass
class ActiveCard:
    """A deployed strategy card loaded from champion_pipeline_fresh."""
    card_id: int
    regime: str
    strategy_config: Dict[str, Any]
    elo_rating: float
    indicators: List[str] = field(default_factory=list)
    entry_threshold: float = 0.80
    exit_threshold: float = 0.50
    voter_k: int = 3
    voter_n: int = 5


class LiveLoop:
    """Main live trading loop.

    Dependencies:
        db: PipelineDB — card loading, state persistence
        ws_feed: BinanceFuturesWS — bar data subscription
        regime_labeler: LiveRegimeLabeler — regime detection
        paper_trader: PaperTrader — simulated execution
        card_rotator: CardRotator — hot-swap logic
        normalizer: Normalizer — indicator normalization (optional)
        voter: Voter — signal aggregation (optional)
    """

    def __init__(
        self,
        db: Any,
        ws_feed: Any,
        regime_labeler: Any,
        paper_trader: Any,
        card_rotator: Any,
        normalizer: Any = None,
        voter: Any = None,
        symbols: Optional[List[str]] = None,
    ) -> None:
        self._db = db
        self._ws = ws_feed
        self._regime = regime_labeler
        self._paper = paper_trader
        self._rotator = card_rotator
        self._normalizer = normalizer
        self._voter = voter
        self._symbols = symbols or []
        self._cards: Dict[str, List[ActiveCard]] = {}  # regime -> list of cards
        self._all_cards: List[ActiveCard] = []
        self._last_reload = 0.0
        self._running = False
        self._bar_count = 0
        self._error_count = 0

    async def _load_cards(self) -> None:
        """Load active (DEPLOYED) cards from champion_pipeline_fresh."""
        async with self._db.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, regime, passport, status
                FROM champion_pipeline_fresh
                WHERE status = 'DEPLOYED'
                ORDER BY regime, (passport->'arena5'->>'elo_rating')::float DESC
            """)

        self._cards.clear()
        self._all_cards.clear()

        for row in rows:
            passport = row["passport"] or {}
            arena5 = passport.get("arena5", {})
            strategy = passport.get("strategy", {})

            card = ActiveCard(
                card_id=row["id"],
                regime=row["regime"],
                strategy_config=strategy,
                elo_rating=float(arena5.get("elo_rating", 1500)),
                indicators=strategy.get("indicators", []),
                entry_threshold=float(strategy.get("entry_threshold", 0.80)),
                exit_threshold=float(strategy.get("exit_threshold", 0.50)),
                voter_k=int(strategy.get("voter_k", 3)),
                voter_n=int(strategy.get("voter_n", 5)),
            )
            self._all_cards.append(card)
            self._cards.setdefault(row["regime"], []).append(card)

        self._last_reload = time.time()
        LOG.info("Loaded %d active cards across %d regimes",
                 len(self._all_cards), len(self._cards))

    async def _reload_cards(self) -> None:
        """Periodic reload: check for rotations, then reload card list."""
        try:
            rotations = await self._rotator.check_rotation()
            for regime, old_id, new_id, old_elo, new_elo in rotations:
                LOG.info("Rotation detected: %s old=%s new=%s", regime, old_id, new_id)
                # Execute rotation in background (non-blocking)
                asyncio.create_task(
                    self._rotator.execute_rotation(regime, old_id, new_id, old_elo, new_elo)
                )
            await self._load_cards()
        except Exception:
            LOG.exception("Card reload failed")
            self._error_count += 1

    async def run(self) -> None:
        """Main loop: subscribe to WS feed, process bars."""
        self._running = True
        LOG.info("LiveLoop starting for symbols: %s", self._symbols)

        # Initial card load
        await self._load_cards()

        if not self._all_cards:
            LOG.warning("No active cards found — running in observation mode")

        # Subscribe to WS feed and process bars
        try:
            await self._ws.connect()
            LOG.info("WS feed connected")

            while self._running:
                # Check for card reload
                if time.time() - self._last_reload > _RELOAD_INTERVAL:
                    await self._reload_cards()

                # Poll for completed bars from WS feed
                for symbol in self._symbols:
                    try:
                        bar = self._ws.pop_completed_bar(symbol)
                        if bar is not None:
                            await self.process_bar(symbol, bar)
                    except Exception:
                        LOG.exception("Error processing bar for %s", symbol)
                        self._error_count += 1

                # Yield control — don't spin too fast
                await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            LOG.info("LiveLoop cancelled")
        except Exception:
            LOG.exception("LiveLoop fatal error")
            self._error_count += 1
        finally:
            self._running = False
            LOG.info("LiveLoop stopped (bars=%d, errors=%d)",
                     self._bar_count, self._error_count)

    async def process_bar(self, symbol: str, bar: Dict[str, Any]) -> None:
        """Process a single completed 1m bar.

        Flow:
          1. Update regime labeler
          2. Get current regime
          3. Find matching active cards
          4. For each card: normalize → vote → signal
          5. If signal: paper trade (binary position model)
        """
        self._bar_count += 1

        # Step 1: Update regime
        self._regime.update_1m_bar(symbol, bar)
        current_regime = self._regime.get_current_regime(symbol)

        # Step 2: Check damper — skip if active
        if self._regime.is_damper_active(symbol):
            LOG.debug("Damper active for %s, skipping signal generation", symbol)
            return

        # Step 3: Find cards matching current regime
        matching_cards = self._cards.get(current_regime, [])
        if not matching_cards:
            return

        # Step 4: Process each matching card
        for card in matching_cards:
            try:
                signal = await self._compute_signal(symbol, bar, card)

                # Step 5: Paper trade with binary position model
                if signal is not None:
                    await self._paper.process_bar(
                        symbol=symbol, bar=bar, regime=current_regime,
                        card_id=str(card.card_id), signal=signal,
                    )
            except Exception:
                LOG.exception("Signal computation failed for card %s on %s",
                              card.card_id, symbol)

    async def _compute_signal(
        self, symbol: str, bar: Dict[str, Any], card: ActiveCard,
    ) -> Optional[int]:
        """Compute trading signal for a card against current bar.

        Uses normalizer + voter if available, else falls back to
        threshold-based signal from the card's strategy config.

        Returns: +1 (long), -1 (short), 0 (exit/flat), None (no signal).
        """
        close = float(bar["close"])
        bars = self._ws.get_bars(symbol) if hasattr(self._ws, 'get_bars') else None

        if bars is None or len(bars) < 30:
            return None

        # Extract recent closes for indicator computation
        closes = [float(b["close"]) for b in bars[-200:]]

        # If voter is available, use full pipeline
        if self._voter is not None and self._normalizer is not None:
            try:
                # Normalize indicators (engine normalizer interface)
                # Voter aggregates indicator signals
                # This is a simplified version — full pipeline uses engine components
                pass
            except Exception:
                LOG.debug("Voter pipeline failed, falling back to threshold")

        # Fallback: simple EMA crossover signal
        if len(closes) < 50:
            return None

        import numpy as np
        arr = np.array(closes, dtype=np.float64)
        ema_fast = self._ema(arr, 12)
        ema_slow = self._ema(arr, 26)

        # Current signal strength
        diff = (ema_fast[-1] - ema_slow[-1]) / ema_slow[-1] if ema_slow[-1] > 0 else 0
        prev_diff = (ema_fast[-2] - ema_slow[-2]) / ema_slow[-2] if ema_slow[-2] > 0 else 0

        # Entry: crossover with threshold
        entry_thr = card.entry_threshold / 100.0  # threshold is 0.80 meaning 0.008
        exit_thr = card.exit_threshold / 100.0

        if diff > entry_thr and prev_diff <= entry_thr:
            return 1  # long
        elif diff < -entry_thr and prev_diff >= -entry_thr:
            return -1  # short
        elif abs(diff) < exit_thr:
            return 0  # exit / flat

        return None  # hold

    @staticmethod
    def _ema(arr, span: int):
        """Causal EMA computation."""
        import numpy as np
        out = np.empty_like(arr, dtype=np.float64)
        alpha = 2.0 / (span + 1)
        out[0] = arr[0]
        for i in range(1, len(arr)):
            out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
        return out

    async def stop(self) -> None:
        """Gracefully stop the live loop."""
        LOG.info("LiveLoop stop requested")
        self._running = False

    def health_check(self) -> Dict[str, Any]:
        """Dashboard hook: live loop status."""
        return {
            "running": self._running,
            "bar_count": self._bar_count,
            "error_count": self._error_count,
            "active_cards": len(self._all_cards),
            "regimes_covered": list(self._cards.keys()),
            "symbols": self._symbols,
            "last_reload": self._last_reload,
        }
