"""
Calcifer — Zangetsu V3.1 Telegram monitoring & self-healing bot.

Two modes:
  1. Interactive: Telegram bot with /status, /cards, /arena, /health commands
  2. Push: scheduled heartbeats, daily summaries, watchdog alerts, self-healing

Runs as a standalone daemon. No zangetsu_v3 imports.
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
import polars as pl

from calcifer_brain import (
    AlertTracker,
    CalciferBrain,
    Status,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TG_TOKEN = os.getenv("CALCIFER_TOKEN", os.getenv("CALCIFER_TG_TOKEN", ""))
CHAT_ID = os.getenv("CALCIFER_CHAT_ID", "5252897787")

STRATEGIES_DIR = Path(os.getenv("ZV3_STRATEGIES_DIR", "strategies"))
STATUS_FILE = Path(os.getenv("ZV3_STATUS_FILE", "status.json"))
ARENA_LOG_DIR = Path(os.getenv("ZV3_ARENA_LOG_DIR", "logs/arena"))
TMUX_SESSION = os.getenv("ZV3_TMUX_SESSION", "zangetsu")

HEARTBEAT_INTERVAL = int(os.getenv("CALCIFER_HEARTBEAT_S", "3600"))  # 1h default
DAILY_SUMMARY_HOUR_UTC = 0
WATCHDOG_INTERVAL = 60

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Calcifer] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("calcifer")

# ---------------------------------------------------------------------------
# Brain & alert tracker instances
# ---------------------------------------------------------------------------

brain = CalciferBrain(
    status_file=STATUS_FILE,
    strategies_dir=STRATEGIES_DIR,
    arena_log_dir=ARENA_LOG_DIR,
)
alert_tracker = AlertTracker(cooldown_seconds=300)

# ---------------------------------------------------------------------------
# Telegram send helper (raw httpx — used by both push and fallback)
# ---------------------------------------------------------------------------

_http: Optional[httpx.AsyncClient] = None


async def _client() -> httpx.AsyncClient:
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(timeout=30.0)
    return _http


async def send_message(
    text: str,
    chat_id: str = "",
    parse_mode: str = "HTML",
) -> bool:
    """Send a Telegram message via raw API. Returns True on success."""
    if not TG_TOKEN:
        log.warning("CALCIFER_TOKEN not set — message suppressed")
        return False
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id or CHAT_ID,
        "text": text[:4096],
        "parse_mode": parse_mode,
    }
    try:
        client = await _client()
        resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            log.error("Telegram send failed: %s %s", resp.status_code, resp.text[:200])
            return False
        return True
    except Exception as e:
        log.error("Telegram send error: %s", e)
        return False


# ---------------------------------------------------------------------------
# Telegram command handlers (python-telegram-bot)
# ---------------------------------------------------------------------------

try:
    from telegram import Update
    from telegram.ext import (
        Application,
        CommandHandler,
        ContextTypes,
    )
    HAS_PTB = True
except ImportError:
    HAS_PTB = False
    log.warning("python-telegram-bot not installed — interactive commands disabled, push-only mode")


if HAS_PTB:
    async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler for /status — current system snapshot."""
        try:
            text = brain.status_text()
        except Exception as e:
            log.error("status command error: %s", e)
            text = f"\U0001f534 Error reading status: {e}"
        await update.message.reply_text(text, parse_mode="HTML")

    async def cmd_cards(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler for /cards — strategy cards summary."""
        try:
            text = brain.cards_summary()
        except Exception as e:
            log.error("cards command error: %s", e)
            text = f"\U0001f534 Error reading cards: {e}"
        await update.message.reply_text(text, parse_mode="HTML")

    async def cmd_arena(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler for /arena — arena search progress."""
        try:
            text = brain.arena_summary()
        except Exception as e:
            log.error("arena command error: %s", e)
            text = f"\U0001f534 Error reading arena: {e}"
        await update.message.reply_text(text, parse_mode="HTML")

    async def cmd_health(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler for /health — full health assessment with per-dimension checks."""
        try:
            assessment = brain.assess_health(tmux_session=TMUX_SESSION)
            text = assessment.summary_text()
        except Exception as e:
            log.error("health command error: %s", e)
            text = f"\U0001f534 Error running health check: {e}"
        await update.message.reply_text(text, parse_mode="HTML")

    async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler for /start — welcome message."""
        await update.message.reply_text(
            "\U0001f527 <b>Calcifer online</b>\n\n"
            "Commands:\n"
            "  /status — current system status\n"
            "  /cards — strategy cards summary\n"
            "  /arena — arena search progress\n"
            "  /health — full health check\n",
            parse_mode="HTML",
        )


# ---------------------------------------------------------------------------
# Self-healing (kept from original)
# ---------------------------------------------------------------------------


def _run_shell(cmd: str) -> tuple[int, str]:
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30,
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return -1, "timeout"
    except Exception as e:
        return -1, str(e)


async def self_heal(event_type: str) -> bool:
    """Attempt automated recovery. Returns True if handled."""
    if event_type == "PROCESS_CRASH":
        code, out = _run_shell(
            f"tmux has-session -t {TMUX_SESSION} 2>/dev/null && "
            f"tmux send-keys -t {TMUX_SESSION} C-c Enter 'python main.py' Enter || "
            f"tmux new-session -d -s {TMUX_SESSION} 'cd {STRATEGIES_DIR.parent} && python main.py'"
        )
        handled = code == 0
        icon = "\U0001f527" if handled else "\u26a0\ufe0f"
        await send_message(
            f"{icon} <b>Process crashed — {'handled' if handled else 'need decision'}</b>\n"
            f"<code>rc={code}\n{out[:200]}</code>"
        )
        return handled

    elif event_type == "HIGH_RAM":
        cache_dir = STRATEGIES_DIR.parent / "cache"
        if cache_dir.exists():
            cleared = 0
            for f in cache_dir.glob("expr_cache_*"):
                try:
                    f.unlink()
                    cleared += 1
                except OSError:
                    pass
            await send_message(f"\U0001f527 <b>High RAM — handled</b>: cleared {cleared} cache files")
            return True
        await send_message("\u26a0\ufe0f <b>High RAM — need decision</b>: no cache dir found")
        return False

    elif event_type == "CARD_EXPIRED":
        archive_dir = STRATEGIES_DIR.parent / "archive"
        if archive_dir.exists():
            candidates = sorted(
                (d for d in archive_dir.iterdir() if d.is_dir() and (d / "card.json").exists()),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if candidates:
                src = candidates[0]
                dst = STRATEGIES_DIR / src.name
                if not dst.exists():
                    shutil.copytree(str(src), str(dst))
                    await send_message(f"\U0001f527 <b>Card expired — handled</b>: loaded {src.name} from archive")
                    return True
        await send_message("\u26a0\ufe0f <b>Card expired — need decision</b>: no archive replacement")
        return False

    log.warning("Unknown self-heal event: %s", event_type)
    return False


# ---------------------------------------------------------------------------
# Watchdog — runs every WATCHDOG_INTERVAL seconds
# ---------------------------------------------------------------------------


async def watchdog() -> None:
    """Check health via brain and fire alerts / self-healing as needed."""
    try:
        assessment = brain.assess_health(tmux_session=TMUX_SESSION)
    except Exception as e:
        log.error("Brain assess_health error: %s", e)
        return

    # Fire alerts based on brain assessment
    decisions = alert_tracker.evaluate_assessment(assessment)
    for d in decisions:
        await send_message(d.message)
        alert_tracker.record(d.event_type)
        log.info("Alert fired: %s", d.event_type)

    # Self-healing for critical process issues
    for f in assessment.findings:
        if f.category == "process" and f.status == Status.CRITICAL:
            await self_heal("PROCESS_CRASH")

    # RAM check (psutil optional)
    try:
        import psutil
        mem = psutil.virtual_memory()
        if mem.percent > 90:
            await self_heal("HIGH_RAM")
    except ImportError:
        pass


# ---------------------------------------------------------------------------
# Heartbeat — periodic system snapshot
# ---------------------------------------------------------------------------


async def heartbeat() -> None:
    """Compact system status summary sent periodically."""
    text = brain.status_text()
    # Prefix with heartbeat icon
    text = text.replace("<b>Zangetsu V3.1 Status</b>", "\U0001f493 <b>Zangetsu V3.1 Heartbeat</b>")
    await send_message(text)
    log.info("Heartbeat sent")


# ---------------------------------------------------------------------------
# Daily summary
# ---------------------------------------------------------------------------


async def daily_summary() -> None:
    """End-of-day summary across all cards."""
    today_start = brain._today_utc_start()
    total_pnl = 0.0
    total_trades = 0
    card_lines = []
    regime_seconds: dict[str, float] = {}

    for card_dir in brain._discover_card_dirs():
        card = brain._load_card(card_dir)
        card_id = card["id"] if card else card_dir.name
        df = brain._read_journal(card_dir)

        if df.is_empty() or "pnl_pct" not in df.columns:
            card_lines.append(f"  {card_id}: no data")
            continue

        pnl_col = df["pnl_pct"].drop_nulls()
        card_pnl = float(pnl_col.sum()) if len(pnl_col) > 0 else 0.0
        card_trades = len(df)
        total_pnl += card_pnl
        total_trades += card_trades
        card_lines.append(f"  {card_id}: {card_pnl:+.4f} ({card_trades}t)")

        if "regime_at_entry" in df.columns:
            for rv in df["regime_at_entry"].drop_nulls().to_list():
                regime_seconds[rv] = regime_seconds.get(rv, 0) + 1

    regime_total = sum(regime_seconds.values()) or 1
    regime_lines = [
        f"  {r}: {(c / regime_total):.0%}"
        for r, c in sorted(regime_seconds.items(), key=lambda x: -x[1])
    ]

    msg = (
        f"\U0001f4ca <b>Zangetsu V3.1 Daily Summary</b>\n"
        f"<code>"
        f"Total PnL:  {total_pnl:+.6f}\n"
        f"Trades:     {total_trades}\n"
        f"\nPer-card:\n"
        + "\n".join(card_lines[:15]) + "\n"
        f"\nRegime distribution:\n"
        + ("\n".join(regime_lines[:8]) if regime_lines else "  no data") + "\n"
        f"</code>"
    )
    await send_message(msg)
    log.info("Daily summary sent")


# ---------------------------------------------------------------------------
# Push scheduler (background task — runs alongside the bot polling)
# ---------------------------------------------------------------------------


async def push_scheduler() -> None:
    """Background loop for heartbeats, daily summaries, and watchdog checks."""
    log.info("Push scheduler starting")
    await send_message("\U0001f527 <b>Calcifer online</b> — Zangetsu V3.1 monitoring active")

    last_heartbeat = 0.0
    last_daily = -1

    while True:
        now = time.time()
        utc_now = datetime.now(timezone.utc)

        # Watchdog
        try:
            await watchdog()
        except Exception as e:
            log.error("Watchdog error: %s", e)

        # Heartbeat
        if now - last_heartbeat >= HEARTBEAT_INTERVAL:
            try:
                await heartbeat()
            except Exception as e:
                log.error("Heartbeat error: %s", e)
            last_heartbeat = now

        # Daily summary at 00:xx UTC
        if utc_now.hour == DAILY_SUMMARY_HOUR_UTC and last_daily != utc_now.day:
            try:
                await daily_summary()
            except Exception as e:
                log.error("Daily summary error: %s", e)
            last_daily = utc_now.day

        await asyncio.sleep(WATCHDOG_INTERVAL)


# ---------------------------------------------------------------------------
# Main — two modes depending on python-telegram-bot availability
# ---------------------------------------------------------------------------


def main() -> None:
    if not TG_TOKEN:
        log.error("CALCIFER_TOKEN (or CALCIFER_TG_TOKEN) not set. Set it and restart.")
        return

    if HAS_PTB:
        # Full mode: interactive commands + push scheduler
        log.info("Starting in full mode (interactive + push)")
        app = Application.builder().token(TG_TOKEN).build()

        # Register command handlers
        app.add_handler(CommandHandler("start", cmd_start))
        app.add_handler(CommandHandler("status", cmd_status))
        app.add_handler(CommandHandler("cards", cmd_cards))
        app.add_handler(CommandHandler("arena", cmd_arena))
        app.add_handler(CommandHandler("health", cmd_health))

        # Schedule push_scheduler as a background task after bot starts
        async def post_init(application: Application) -> None:
            application.create_task(push_scheduler())

        app.post_init = post_init

        # run_polling handles the asyncio event loop
        app.run_polling(drop_pending_updates=True)
    else:
        # Push-only mode (no python-telegram-bot)
        log.info("Starting in push-only mode (no interactive commands)")
        asyncio.run(push_scheduler())


if __name__ == "__main__":
    main()
