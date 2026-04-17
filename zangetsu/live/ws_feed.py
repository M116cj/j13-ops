"""Binance Futures WebSocket feed with 1m bar buffering and REST prefill.

Connects to Binance Futures combined stream for configurable symbols,
buffers 1-minute klines in memory, prefills history via REST on startup,
and auto-reconnects with exponential backoff.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Tuple

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

logger = logging.getLogger("zangetsu.ws_feed")

# -- Constants --------------------------------------------------------

_WS_BASE = "wss://fstream.binance.com/stream?streams="
_REST_BASE = "https://fapi.binance.com"
_MAX_BARS = 1500          # max 1m bars kept per symbol
_PREFILL_BARS = 500       # bars to fetch via REST on startup
_RECONNECT_BASE = 1.0     # initial reconnect delay (seconds)
_RECONNECT_MAX = 60.0     # max reconnect delay
_RECONNECT_MULT = 2.0     # exponential backoff multiplier


def _kline_to_bar(k: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Binance kline payload to a standardized bar dict."""
    return {
        "ts": int(k["t"]),
        "open": float(k["o"]),
        "high": float(k["h"]),
        "low": float(k["l"]),
        "close": float(k["c"]),
        "volume": float(k["v"]),
        "closed": bool(k["x"]),
    }


class BinanceFuturesWS:
    """WebSocket client for Binance USDM Futures kline streams.

    Usage:
        feed = BinanceFuturesWS(["BTCUSDT", "ETHUSDT"])
        await feed.start()      # prefill + connect
        bars = feed.get_bars("BTCUSDT", 100)
        ...
        await feed.stop()
    """

    def __init__(
        self,
        symbols: List[str],
        interval: str = "1m",
        max_bars: int = _MAX_BARS,
    ) -> None:
        if not HAS_AIOHTTP:
            raise RuntimeError("aiohttp not installed -- pip install aiohttp")
        self._symbols = [s.upper() for s in symbols]
        self._interval = interval
        self._max_bars = max_bars
        self._buffers: Dict[str, Deque[Dict[str, Any]]] = {
            s: deque(maxlen=max_bars) for s in self._symbols
        }
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._reconnect_delay = _RECONNECT_BASE

    # -- Public API ---------------------------------------------------

    async def start(self) -> None:
        """Prefill bars via REST, then start WebSocket listener."""
        self._session = aiohttp.ClientSession()
        await self._prefill_all()
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("WS feed started", extra={"symbols": self._symbols})

    async def stop(self) -> None:
        """Gracefully shut down."""
        self._running = False
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._session and not self._session.closed:
            await self._session.close()
        logger.info("WS feed stopped")

    def get_bars(self, symbol: str, n: int) -> List[Dict[str, Any]]:
        """Return the last N closed bars for a symbol.

        Returns newest-last ordering (chronological).
        """
        symbol = symbol.upper()
        buf = self._buffers.get(symbol)
        if buf is None:
            return []
        # Filter closed bars only
        closed = [b for b in buf if b.get("closed", True)]
        return list(closed)[-n:]

    @property
    def symbols(self) -> List[str]:
        return list(self._symbols)

    @property
    def connected(self) -> bool:
        return self._ws is not None and not self._ws.closed

    def buffer_sizes(self) -> Dict[str, int]:
        return {s: len(b) for s, b in self._buffers.items()}

    # -- REST prefill -------------------------------------------------

    async def _prefill_all(self) -> None:
        """Fetch recent klines via REST for all symbols."""
        tasks = [self._prefill_symbol(s) for s in self._symbols]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _prefill_symbol(self, symbol: str) -> None:
        """Fetch klines for one symbol via REST."""
        url = f"{_REST_BASE}/fapi/v1/klines"
        params = {
            "symbol": symbol,
            "interval": self._interval,
            "limit": _PREFILL_BARS,
        }
        try:
            async with self._session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:  # type: ignore[union-attr]
                if resp.status != 200:
                    logger.warning(f"REST prefill failed for {symbol}: HTTP {resp.status}")
                    return
                data = await resp.json()
        except Exception as e:
            logger.warning(f"REST prefill error for {symbol}: {e}")
            return

        buf = self._buffers[symbol]
        for row in data:
            bar = {
                "ts": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
                "closed": True,  # REST klines are all closed
            }
            buf.append(bar)
        logger.info(f"Prefilled {len(data)} bars for {symbol}")

    # -- WebSocket loop -----------------------------------------------

    def _build_ws_url(self) -> str:
        """Build combined stream URL."""
        streams = "/".join(
            f"{s.lower()}@kline_{self._interval}" for s in self._symbols
        )
        return f"{_WS_BASE}{streams}"

    async def _run_loop(self) -> None:
        """Main reconnect loop."""
        while self._running:
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                break
            except Exception as e:
                if not self._running:
                    break
                logger.warning(
                    f"WS disconnected: {e}. Reconnecting in {self._reconnect_delay:.1f}s"
                )
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(
                    self._reconnect_delay * _RECONNECT_MULT, _RECONNECT_MAX
                )

    async def _connect_and_listen(self) -> None:
        """Connect to WS and process messages until disconnect."""
        url = self._build_ws_url()
        logger.info(f"Connecting to {url[:80]}...")

        async with self._session.ws_connect(url, heartbeat=20) as ws:  # type: ignore[union-attr]
            self._ws = ws
            self._reconnect_delay = _RECONNECT_BASE  # reset on success
            logger.info("WS connected")

            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    self._handle_message(msg.data)
                elif msg.type in (
                    aiohttp.WSMsgType.ERROR,
                    aiohttp.WSMsgType.CLOSED,
                ):
                    break

        self._ws = None

    def _handle_message(self, raw: str) -> None:
        """Parse and buffer a kline message."""
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return

        data = payload.get("data", {})
        if data.get("e") != "kline":
            return

        k = data.get("k", {})
        symbol = data.get("s", "").upper()
        if symbol not in self._buffers:
            return

        bar = _kline_to_bar(k)
        buf = self._buffers[symbol]

        # Update in-place if same timestamp, otherwise append
        if buf and buf[-1]["ts"] == bar["ts"]:
            buf[-1] = bar
        else:
            buf.append(bar)
