"""Simple Telegram bot for Zangetsu V5 monitoring.

Commands: /status, /positions, /equity
Push alerts via alert(message).
Uses aiohttp directly -- no python-telegram-bot dependency.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Callable, Coroutine, Dict, List, Optional

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

logger = logging.getLogger("zangetsu_v5.bot")

_TG_API = "https://api.telegram.org/bot{token}"
_POLL_TIMEOUT = 30  # long-poll timeout seconds


class ZangetsuBot:
    """Telegram bot for live system monitoring.

    Usage:
        bot = ZangetsuBot(token="...", chat_id=123456)
        bot.register_status_callback(my_status_fn)
        bot.register_positions_callback(my_positions_fn)
        bot.register_equity_callback(my_equity_fn)
        await bot.start()
    """

    def __init__(
        self,
        token: Optional[str] = None,
        chat_id: Optional[int] = None,
    ) -> None:
        if not HAS_AIOHTTP:
            raise RuntimeError("aiohttp not installed -- pip install aiohttp")
        self._token = token or os.getenv("ZV5_TG_BOT_TOKEN", "")
        self._chat_id = chat_id or int(os.getenv("ZV5_TG_CHAT_ID", "0"))
        if not self._token:
            raise ValueError("Telegram bot token required (ZV5_TG_BOT_TOKEN)")
        self._base = _TG_API.format(token=self._token)
        self._session: Optional[aiohttp.ClientSession] = None
        self._running = False
        self._offset = 0
        self._task: Optional[asyncio.Task] = None

        # Callbacks for commands -- return str to send as reply
        self._on_status: Optional[Callable[[], Coroutine[Any, Any, str]]] = None
        self._on_positions: Optional[Callable[[], Coroutine[Any, Any, str]]] = None
        self._on_equity: Optional[Callable[[], Coroutine[Any, Any, str]]] = None

    # -- Callback registration ----------------------------------------

    def register_status_callback(
        self, fn: Callable[[], Coroutine[Any, Any, str]]
    ) -> None:
        self._on_status = fn

    def register_positions_callback(
        self, fn: Callable[[], Coroutine[Any, Any, str]]
    ) -> None:
        self._on_positions = fn

    def register_equity_callback(
        self, fn: Callable[[], Coroutine[Any, Any, str]]
    ) -> None:
        self._on_equity = fn

    # -- Lifecycle ----------------------------------------------------

    async def start(self) -> None:
        """Start polling for updates."""
        self._session = aiohttp.ClientSession()
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Telegram bot started")

    async def stop(self) -> None:
        """Stop the bot gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._session and not self._session.closed:
            await self._session.close()
        logger.info("Telegram bot stopped")

    # -- Push alerts --------------------------------------------------

    async def alert(self, message: str) -> bool:
        """Send a push notification to the configured chat.

        Returns True on success, False on failure.
        """
        return await self._send_message(self._chat_id, message)

    # -- Internal: polling --------------------------------------------

    async def _poll_loop(self) -> None:
        """Long-poll for Telegram updates."""
        while self._running:
            try:
                updates = await self._get_updates()
                for update in updates:
                    await self._handle_update(update)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Poll error: {e}")
                await asyncio.sleep(2)

    async def _get_updates(self) -> List[Dict]:
        """Fetch updates via getUpdates."""
        url = f"{self._base}/getUpdates"
        params = {"offset": self._offset, "timeout": _POLL_TIMEOUT}
        try:
            async with self._session.get(  # type: ignore[union-attr]
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=_POLL_TIMEOUT + 5),
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                results = data.get("result", [])
                if results:
                    self._offset = results[-1]["update_id"] + 1
                return results
        except Exception:
            return []

    async def _handle_update(self, update: Dict) -> None:
        """Route commands to registered callbacks."""
        msg = update.get("message", {})
        text = msg.get("text", "").strip()
        chat_id = msg.get("chat", {}).get("id")

        if not text or not chat_id:
            return

        # Only respond in authorized chat
        if self._chat_id and chat_id != self._chat_id:
            return

        reply: Optional[str] = None

        if text == "/status":
            if self._on_status:
                try:
                    reply = await self._on_status()
                except Exception as e:
                    reply = f"Error: {e}"
            else:
                reply = "Status callback not registered"

        elif text == "/positions":
            if self._on_positions:
                try:
                    reply = await self._on_positions()
                except Exception as e:
                    reply = f"Error: {e}"
            else:
                reply = "Positions callback not registered"

        elif text == "/equity":
            if self._on_equity:
                try:
                    reply = await self._on_equity()
                except Exception as e:
                    reply = f"Error: {e}"
            else:
                reply = "Equity callback not registered"

        if reply:
            await self._send_message(chat_id, reply)

    async def _send_message(self, chat_id: int, text: str) -> bool:
        """Send a message via Telegram API."""
        url = f"{self._base}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        try:
            async with self._session.post(  # type: ignore[union-attr]
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning(f"Send message failed: {e}")
            return False


# -- Module-level convenience -----------------------------------------

async def alert(
    message: str,
    token: Optional[str] = None,
    chat_id: Optional[int] = None,
) -> bool:
    """One-shot alert: send a single message without starting the bot loop.

    Usage:
        await alert("Position opened: BTCUSDT LONG 1000 USD")
    """
    if not HAS_AIOHTTP:
        logger.error("aiohttp not installed")
        return False

    tok = token or os.getenv("ZV5_TG_BOT_TOKEN", "")
    cid = chat_id or int(os.getenv("ZV5_TG_CHAT_ID", "0"))
    if not tok or not cid:
        logger.error("Missing TG token or chat_id for alert")
        return False

    base = _TG_API.format(token=tok)
    url = f"{base}/sendMessage"
    payload = {"chat_id": cid, "text": message, "parse_mode": "HTML"}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning(f"Alert send failed: {e}")
            return False
