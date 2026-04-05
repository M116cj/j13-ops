"""
Calcifer — Zangetsu V3.1 Telegram monitoring & self-healing bot.
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

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TG_TOKEN = os.getenv("CALCIFER_TG_TOKEN", "")
CHAT_ID = os.getenv("CALCIFER_CHAT_ID", "5252897787")

STRATEGIES_DIR = Path(os.getenv("ZV3_STRATEGIES_DIR", "strategies"))
STATUS_FILE = Path(os.getenv("ZV3_STATUS_FILE", "status.json"))
ARENA_LOG_DIR = Path(os.getenv("ZV3_ARENA_LOG_DIR", "logs/arena"))
TMUX_SESSION = os.getenv("ZV3_TMUX_SESSION", "zangetsu")

HEARTBEAT_INTERVAL = 3600       # 1 hour
DAILY_SUMMARY_HOUR_UTC = 0      # 00:00 UTC
WATCHDOG_INTERVAL = 60          # check every 60s

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Calcifer] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("calcifer")

SYSTEM_PROMPT = (
    "You are Calcifer, the butler of Zangetsu V3.1 trading system. "
    "Report format: concise, state 'handled' or 'need decision' first. "
    "Use \U0001f527 for self-handled, \u26a0\ufe0f for need-decision, "
    "\U0001f534 for urgent, \U0001f493 for heartbeat, \U0001f4ca for daily summary."
)

# ---------------------------------------------------------------------------
# Telegram helpers
# ---------------------------------------------------------------------------

_http: Optional[httpx.AsyncClient] = None


async def _client() -> httpx.AsyncClient:
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(timeout=30.0)
    return _http


async def send_message(text: str, parse_mode: str = "HTML") -> bool:
    """Send a Telegram message. Returns True on success."""
    if not TG_TOKEN:
        log.warning("CALCIFER_TG_TOKEN not set — message suppressed")
        return False
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
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
# Data readers (same as dashboard — independent, no imports)
# ---------------------------------------------------------------------------


def _read_status() -> dict:
    if not STATUS_FILE.exists():
        return {}
    try:
        return json.loads(STATUS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _discover_card_dirs() -> list[Path]:
    if not STRATEGIES_DIR.exists():
        return []
    return sorted(
        d for d in STRATEGIES_DIR.iterdir()
        if d.is_dir() and (d / "card.json").exists()
    )


def _load_card_json(card_dir: Path) -> Optional[dict]:
    try:
        return json.loads((card_dir / "card.json").read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _read_journal(card_dir: Path) -> pl.DataFrame:
    journal_path = card_dir / "live_journal.parquet"
    if not journal_path.exists():
        return pl.DataFrame()
    try:
        return pl.read_parquet(journal_path)
    except Exception:
        return pl.DataFrame()


def _today_utc_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


# ---------------------------------------------------------------------------
# Heartbeat — every hour
# ---------------------------------------------------------------------------


async def heartbeat() -> None:
    """Compact system status summary sent hourly."""
    status = _read_status()
    regime = status.get("regime", "UNKNOWN")
    confidence = status.get("confidence", 0.0)
    active = status.get("active_card_id", "–")
    stale = status.get("stale_status", "?")
    last_bar = status.get("last_bar_time", "–")

    # Aggregate PnL
    today_start = _today_utc_start()
    today_pnl = 0.0
    cum_pnl = 0.0
    today_trades = 0
    card_count = 0

    for card_dir in _discover_card_dirs():
        card_count += 1
        df = _read_journal(card_dir)
        if df.is_empty() or "pnl_pct" not in df.columns:
            continue
        pnl_col = df["pnl_pct"].drop_nulls()
        cum_pnl += pnl_col.sum() if len(pnl_col) > 0 else 0.0
        if "timestamp" in df.columns:
            try:
                today_df = df.filter(pl.col("timestamp") >= today_start)
                today_pnl += today_df["pnl_pct"].drop_nulls().sum() if len(today_df) > 0 else 0.0
                today_trades += len(today_df)
            except Exception:
                pass

    net_exp = status.get("net_exposure", 0.0)
    gross_exp = status.get("gross_exposure", 0.0)
    open_pos = status.get("open_positions", 0)

    msg = (
        f"\U0001f493 <b>Zangetsu V3.1 Heartbeat</b>\n"
        f"<code>"
        f"Regime:   {regime} ({confidence:.0%})\n"
        f"Active:   {active}\n"
        f"Data:     {stale} | bar {last_bar[-8:] if len(last_bar) > 8 else last_bar}\n"
        f"Today:    {today_pnl:+.4f} ({today_trades} trades)\n"
        f"Cum PnL:  {cum_pnl:+.4f}\n"
        f"Exposure: net {net_exp:.2f} / gross {gross_exp:.2f}\n"
        f"Cards:    {card_count} | Positions: {open_pos}"
        f"</code>"
    )
    await send_message(msg)
    log.info("Heartbeat sent")


# ---------------------------------------------------------------------------
# Daily summary — 00:00 UTC
# ---------------------------------------------------------------------------


async def daily_summary() -> None:
    """End-of-day summary across all cards."""
    today_start = _today_utc_start()
    status = _read_status()

    total_pnl = 0.0
    total_trades = 0
    card_lines = []
    regime_seconds: dict[str, float] = {}

    for card_dir in _discover_card_dirs():
        card = _load_card_json(card_dir)
        card_id = card["id"] if card else card_dir.name
        df = _read_journal(card_dir)

        if df.is_empty() or "pnl_pct" not in df.columns:
            card_lines.append(f"  {card_id}: no data")
            continue

        pnl_col = df["pnl_pct"].drop_nulls()
        card_pnl = float(pnl_col.sum()) if len(pnl_col) > 0 else 0.0
        card_trades = len(df)
        total_pnl += card_pnl
        total_trades += card_trades
        card_lines.append(f"  {card_id}: {card_pnl:+.4f} ({card_trades}t)")

        # Regime time distribution from journal entries
        if "regime_at_entry" in df.columns:
            for regime_val in df["regime_at_entry"].drop_nulls().to_list():
                regime_seconds[regime_val] = regime_seconds.get(regime_val, 0) + 1

    # Regime distribution as percentages
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
# Alerts
# ---------------------------------------------------------------------------


async def alert(event_type: str, details: str = "") -> None:
    """Send a typed alert to Telegram."""
    icons = {
        "STALE_DATA": "\U0001f534",
        "CARD_DEGRADED": "\u26a0\ufe0f",
        "PROCESS_CRASH": "\U0001f527",
        "SEARCH_COMPLETE": "\U0001f4ca",
        "HIGH_RAM": "\u26a0\ufe0f",
        "CARD_EXPIRED": "\u26a0\ufe0f",
    }
    icon = icons.get(event_type, "\u2753")

    messages = {
        "STALE_DATA": f"{icon} <b>Data stale >60s</b>\n{details}",
        "CARD_DEGRADED": f"{icon} <b>Card degraded</b>\n{details}",
        "PROCESS_CRASH": f"{icon} <b>Process crashed — restarting</b>\n{details}",
        "SEARCH_COMPLETE": f"{icon} <b>Arena search complete</b>\n{details}",
        "HIGH_RAM": f"{icon} <b>High RAM usage</b>\n{details}",
        "CARD_EXPIRED": f"{icon} <b>Card expired</b>\n{details}",
    }
    msg = messages.get(event_type, f"{icon} <b>{event_type}</b>\n{details}")
    await send_message(msg)
    log.info("Alert sent: %s", event_type)


# ---------------------------------------------------------------------------
# Self-healing
# ---------------------------------------------------------------------------


def _run_shell(cmd: str) -> tuple[int, str]:
    """Run a shell command, return (returncode, output)."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return -1, "timeout"
    except Exception as e:
        return -1, str(e)


async def self_heal(event_type: str) -> bool:
    """
    Attempt automated recovery. Returns True if handled.
    """
    if event_type == "PROCESS_CRASH":
        # Restart main_loop in tmux
        code, out = _run_shell(
            f"tmux has-session -t {TMUX_SESSION} 2>/dev/null && "
            f"tmux send-keys -t {TMUX_SESSION} C-c Enter 'python main.py' Enter || "
            f"tmux new-session -d -s {TMUX_SESSION} 'cd {STRATEGIES_DIR.parent} && python main.py'"
        )
        handled = code == 0
        await alert("PROCESS_CRASH", f"{'handled' if handled else 'need decision'}: rc={code}\n{out[:200]}")
        return handled

    elif event_type == "HIGH_RAM":
        # Clear expression cache files
        cache_dir = STRATEGIES_DIR.parent / "cache"
        if cache_dir.exists():
            cleared = 0
            for f in cache_dir.glob("expr_cache_*"):
                try:
                    f.unlink()
                    cleared += 1
                except OSError:
                    pass
            await alert("HIGH_RAM", f"\U0001f527 handled: cleared {cleared} cache files")
            return True
        await alert("HIGH_RAM", "\u26a0\ufe0f need decision: no cache dir found")
        return False

    elif event_type == "CARD_EXPIRED":
        # Load replacement from archive if available
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
                    await alert("CARD_EXPIRED", f"\U0001f527 handled: loaded {src.name} from archive")
                    return True
        await alert("CARD_EXPIRED", "\u26a0\ufe0f need decision: no archive replacement available")
        return False

    log.warning("Unknown self-heal event: %s", event_type)
    return False


# ---------------------------------------------------------------------------
# Watchdog — runs every WATCHDOG_INTERVAL seconds
# ---------------------------------------------------------------------------


async def watchdog() -> None:
    """Check for issues and trigger self-healing."""
    status = _read_status()

    # Stale data check
    last_bar = status.get("last_bar_time", "")
    if last_bar:
        try:
            ts = datetime.fromisoformat(last_bar.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - ts).total_seconds()
            if age > 60:
                await alert("STALE_DATA", f"Last bar: {last_bar} ({age:.0f}s ago)")
        except (ValueError, TypeError):
            pass

    # RAM check
    try:
        import psutil
        mem = psutil.virtual_memory()
        if mem.percent > 90:
            await self_heal("HIGH_RAM")
    except ImportError:
        pass

    # Process liveness: check if main_loop tmux session has a running python process
    code, out = _run_shell(f"tmux has-session -t {TMUX_SESSION} 2>/dev/null")
    if code != 0 and status:
        # Status file exists (system was running) but tmux session gone
        await self_heal("PROCESS_CRASH")


# ---------------------------------------------------------------------------
# Scheduler loop
# ---------------------------------------------------------------------------


async def scheduler() -> None:
    """Main async event loop with time-based scheduling."""
    log.info("Calcifer starting — chat_id=%s", CHAT_ID)
    if not TG_TOKEN:
        log.error("CALCIFER_TG_TOKEN not set! Messages will be suppressed.")

    await send_message("\U0001f527 <b>Calcifer online</b> — Zangetsu V3.1 monitoring active")

    last_heartbeat = 0.0
    last_daily = -1  # hour tracker to fire once at 00 UTC

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

        # Daily summary at 00:xx UTC (fire once per day)
        if utc_now.hour == DAILY_SUMMARY_HOUR_UTC and last_daily != utc_now.day:
            try:
                await daily_summary()
            except Exception as e:
                log.error("Daily summary error: %s", e)
            last_daily = utc_now.day

        await asyncio.sleep(WATCHDOG_INTERVAL)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    asyncio.run(scheduler())


if __name__ == "__main__":
    main()
