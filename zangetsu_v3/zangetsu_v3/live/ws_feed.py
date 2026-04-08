"""Binance Futures WebSocket feed — live 1m kline bars for Zangetsu V5.

Single combined-stream connection with REST prefill, auto-reconnect,
watchdog, and thread-safe buffer reads.
"""
from __future__ import annotations

import asyncio
import logging
import random
import threading
import time
from collections import deque
from typing import Any

import aiohttp

logger = logging.getLogger("zangetsu.ws_feed")

_BASE_WS = "wss://fstream.binance.com/stream?streams="
_BASE_REST = "https://fapi.binance.com/fapi/v1/klines"

_RECONNECT_BASE = 1.0
_RECONNECT_MAX = 60.0
_RECONNECT_JITTER = 0.20
_WATCHDOG_TIMEOUT = 90.0
_HEALTH_WINDOW = 120.0


def _parse_rest_bar(raw: list) -> dict:
    """Convert REST kline array to bar dict."""
    return {
        "timestamp": float(raw[0]),
        "open": float(raw[1]),
        "high": float(raw[2]),
        "low": float(raw[3]),
        "close": float(raw[4]),
        "volume": float(raw[5]),
    }


def _parse_ws_bar(k: dict) -> dict:
    """Convert WS kline payload to bar dict."""
    return {
        "timestamp": float(k["t"]),
        "open": float(k["o"]),
        "high": float(k["h"]),
        "low": float(k["l"]),
        "close": float(k["c"]),
        "volume": float(k["v"]),
    }


class BinanceFuturesWS:
    """Combined-stream WebSocket client for Binance USDⓈ-M Futures klines."""

    def __init__(self, symbols: list[str], buffer_size: int = 500) -> None:
        self._symbols = [s.upper() for s in symbols]
        self._buffer_size = buffer_size

        # Per-symbol 1m bar buffer — deque is thread-safe for append/iter
        self._bars: dict[str, deque[dict]] = {
            s: deque(maxlen=buffer_size) for s in self._symbols
        }
        # Per-symbol 4h bar buffer — for indicator computation
        self._bars_4h: dict[str, deque[dict]] = {
            s: deque(maxlen=250) for s in self._symbols
        }
        # Last bar timestamp per symbol (epoch ms)
        self._last_bar_ts: dict[str, float] = {s: 0.0 for s in self._symbols}
        self._lock = threading.Lock()

        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._running = False
        self._connected = False
        self._last_msg_time: float = 0.0
        self._tasks: list[asyncio.Task] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start REST prefill then WS loop. Blocks until stop() is called."""
        self._running = True
        self._session = aiohttp.ClientSession()
        try:
            await self._prefill()
            self._tasks.append(asyncio.ensure_future(self._ws_loop()))
            self._tasks.append(asyncio.ensure_future(self._watchdog()))
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            pass
        finally:
            await self._cleanup()

    async def stop(self) -> None:
        """Clean shutdown — cancel tasks, close WS and session."""
        self._running = False
        for t in self._tasks:
            t.cancel()
        # Allow cancellation to propagate
        await asyncio.sleep(0.1)
        await self._cleanup()

    def get_bars(self, symbol: str, n: int = 500) -> list[dict]:
        """Return last *n* closed bars. Thread-safe."""
        sym = symbol.upper()
        with self._lock:
            buf = self._bars.get(sym)
            if buf is None:
                return []
            items = list(buf)
        return items[-n:]

    def get_4h_bars(self, symbol: str, n: int = 200) -> list[dict]:
        """Return last *n* 4h bars. Thread-safe."""
        sym = symbol.upper()
        with self._lock:
            buf = self._bars_4h.get(sym)
            if buf is None:
                return []
            items = list(buf)
        return items[-n:]

    def latest_bar(self, symbol: str) -> dict | None:
        """Most recent closed bar, or None."""
        sym = symbol.upper()
        with self._lock:
            buf = self._bars.get(sym)
            if not buf:
                return None
            return buf[-1]

    def is_healthy(self) -> bool:
        """True if every symbol received a bar within the last 120 s."""
        now = time.time()
        with self._lock:
            return all(
                (now - ts / 1000.0) < _HEALTH_WINDOW
                for ts in self._last_bar_ts.values()
            )

    def health_detail(self) -> dict:
        """Per-symbol health snapshot."""
        now = time.time()
        detail: dict[str, Any] = {}
        with self._lock:
            for s in self._symbols:
                ts = self._last_bar_ts[s]
                detail[s] = {
                    "last_bar_time": ts,
                    "age_s": round(now - ts / 1000.0, 1) if ts else None,
                    "bars_count": len(self._bars[s]),
                    "connected": self._connected,
                }
        return detail

    # ------------------------------------------------------------------
    # REST prefill
    # ------------------------------------------------------------------

    async def _prefill(self) -> None:
        """Fetch last 500 bars per symbol via REST."""
        assert self._session is not None
        for sym in self._symbols:
            url = _BASE_REST
            params = {"symbol": sym, "interval": "1m", "limit": self._buffer_size}
            try:
                async with self._session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        logger.error("REST prefill %s HTTP %d", sym, resp.status)
                        continue
                    data = await resp.json()
                # Drop the last (potentially open) bar
                closed = data[:-1] if data else []
                with self._lock:
                    buf = self._bars[sym]
                    for raw in closed:
                        buf.append(_parse_rest_bar(raw))
                    if buf:
                        self._last_bar_ts[sym] = buf[-1]["timestamp"]
                logger.info("Prefilled %s: %d 1m bars", sym, len(closed))
            except Exception:
                logger.exception("REST prefill failed for %s", sym)

        # 4h bar prefill
        for sym in self._symbols:
            url = _BASE_REST
            params = {"symbol": sym, "interval": "4h", "limit": 250}
            try:
                async with self._session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        logger.error("REST prefill 4h %s HTTP %d", sym, resp.status)
                        continue
                    data = await resp.json()
                closed = data[:-1] if data else []
                with self._lock:
                    buf = self._bars_4h[sym]
                    for raw in closed:
                        buf.append(_parse_rest_bar(raw))
                logger.info("Prefilled %s: %d 4h bars", sym, len(closed))
            except Exception:
                logger.exception("REST prefill 4h failed for %s", sym)

    # ------------------------------------------------------------------
    # WebSocket loop
    # ------------------------------------------------------------------

    def _build_url(self) -> str:
        streams = "/".join(f"{s.lower()}@kline_1m" for s in self._symbols)
        return _BASE_WS + streams

    async def _ws_loop(self) -> None:
        backoff = _RECONNECT_BASE
        while self._running:
            try:
                await self._connect_and_listen()
                # Clean disconnect — reset backoff
                backoff = _RECONNECT_BASE
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("WS error, reconnecting in %.1fs", backoff)
            finally:
                self._connected = False

            if not self._running:
                break

            # Exponential backoff with jitter
            jitter = backoff * random.uniform(-_RECONNECT_JITTER, _RECONNECT_JITTER)
            await asyncio.sleep(backoff + jitter)
            backoff = min(backoff * 2, _RECONNECT_MAX)

    async def _connect_and_listen(self) -> None:
        assert self._session is not None
        url = self._build_url()
        logger.info("Connecting to %s", url[:80] + "...")
        async with self._session.ws_connect(url, heartbeat=30) as ws:
            self._ws = ws
            self._connected = True
            self._last_msg_time = time.monotonic()
            logger.info("WS connected")

            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    self._last_msg_time = time.monotonic()
                    self._handle_message(msg.json())
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error("WS error: %s", ws.exception())
                    break
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING):
                    break

            self._ws = None

    def _handle_message(self, payload: dict) -> None:
        """Process a combined-stream message."""
        data = payload.get("data")
        if not data or data.get("e") != "kline":
            return
        k = data["k"]
        if not k.get("x"):
            return  # Not a closed bar

        sym = k["s"].upper()
        bar = _parse_ws_bar(k)

        with self._lock:
            buf = self._bars.get(sym)
            if buf is not None:
                buf.append(bar)
                self._last_bar_ts[sym] = bar["timestamp"]

            # Live 4h bar aggregation: check if this 1m bar completes a 4h boundary
            # 4h boundaries: timestamp_ms % (4*3600*1000) == (4*3600*1000 - 60*1000)
            # i.e., the 1m bar closing at XX:00, XX:04, XX:08, ... (UTC 4h aligned)
            bar_close_ms = bar["timestamp"] + 60_000  # close time = open + 1min
            if bar_close_ms % (4 * 3600 * 1000) == 0:
                # Aggregate last 240 1m bars into a synthetic 4h bar
                bars_1m = list(self._bars.get(sym, []))
                if len(bars_1m) >= 240:
                    last_240 = bars_1m[-240:]
                    bar_4h = {
                        "timestamp": last_240[0]["timestamp"],
                        "open": last_240[0]["open"],
                        "high": max(b["high"] for b in last_240),
                        "low": min(b["low"] for b in last_240),
                        "close": last_240[-1]["close"],
                        "volume": sum(b["volume"] for b in last_240),
                    }
                    buf_4h = self._bars_4h.get(sym)
                    if buf_4h is not None:
                        buf_4h.append(bar_4h)
                    logger.info("4h bar aggregated: %s @ %.0f", sym, bar_4h["timestamp"])

        logger.debug("Bar closed: %s @ %.0f", sym, bar["timestamp"])

    # ------------------------------------------------------------------
    # Watchdog
    # ------------------------------------------------------------------

    async def _watchdog(self) -> None:
        """Force reconnect if no message for _WATCHDOG_TIMEOUT seconds."""
        while self._running:
            await asyncio.sleep(10)
            if not self._connected:
                continue
            elapsed = time.monotonic() - self._last_msg_time
            if elapsed > _WATCHDOG_TIMEOUT:
                logger.warning("Watchdog: no message for %.0fs, forcing reconnect", elapsed)
                if self._ws is not None:
                    await self._ws.close()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def _cleanup(self) -> None:
        self._connected = False
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
            self._ws = None
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None
