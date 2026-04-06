#!/usr/bin/env python3
"""Zangetsu V3.2 Telegram Bot — NOTIFY ONLY. Zero actions. Reads DB -> Telegram.

Features:
  - Heartbeat every 1h: regime, cards, pnl, trades, exposure
  - Daily summary 00:00 UTC
  - Alerts: search complete, gate results, card deployed, anomalies

MUST NEVER modify DB or restart processes (Q17).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import psycopg2

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ZangetsuBot] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("zangetsu_bot")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def _default_dsn() -> str:
    """Build DSN from config/config.yaml if no env override."""
    try:
        from zangetsu_v3.core.config import load_config
        cfg = load_config(_PROJECT_ROOT / "config" / "config.yaml")
        db = cfg.database
        return f"dbname={db.dbname} user={db.user} password={db.password} host={db.host} port={db.port}"
    except Exception:
        return "dbname=zangetsu user=zangetsu host=127.0.0.1 port=5432"

DB_DSN = os.environ.get("ZV3_DB_DSN") or _default_dsn()
TG_TOKEN = os.environ.get("ZANGETSU_BOT_TOKEN", os.environ.get("CALCIFER_TG_TOKEN", ""))
CHAT_ID = os.environ.get("ZANGETSU_CHAT_ID", "5252897787")

HEARTBEAT_INTERVAL = 3600  # 1 hour
DAILY_SUMMARY_HOUR_UTC = 0
ALERT_POLL_INTERVAL = 60  # check for new events every 60s

# ---------------------------------------------------------------------------
# Telegram send helper (raw httpx)
# ---------------------------------------------------------------------------
_http_client = None


async def _get_client():
    global _http_client
    try:
        import httpx
    except ImportError:
        log.error("httpx not installed, falling back to urllib")
        return None
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=30.0)
    return _http_client


async def send_tg(text: str, parse_mode: str = "HTML") -> bool:
    """Send a Telegram message. Returns True on success."""
    if not TG_TOKEN:
        log.warning("No TG token set — message suppressed: %s", text[:80])
        return False

    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text[:4096],
        "parse_mode": parse_mode,
    }

    try:
        client = await _get_client()
        if client is not None:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                log.error("TG send failed: %s %s", resp.status_code, resp.text[:200])
                return False
            return True
        else:
            # urllib fallback
            import urllib.request
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status == 200
    except Exception as e:
        log.error("TG send error: %s", e)
        return False


# ---------------------------------------------------------------------------
# DB read helpers (READ-ONLY — no writes anywhere in this file)
# ---------------------------------------------------------------------------
def _get_conn():
    return psycopg2.connect(DB_DSN)


def db_query(sql: str, params: tuple = ()) -> list[tuple]:
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def db_scalar(sql: str, params: tuple = ()):
    rows = db_query(sql, params)
    return rows[0][0] if rows else None


def db_row(sql: str, params: tuple = ()) -> Optional[tuple]:
    rows = db_query(sql, params)
    return rows[0] if rows else None


# ---------------------------------------------------------------------------
# Data readers
# ---------------------------------------------------------------------------
def read_runtime_status() -> dict[str, Any]:
    """Read singleton runtime_status (id=1)."""
    row = db_row(
        "SELECT regime, confidence, active_card_id, today_pnl, cumulative_pnl, "
        "today_trades, net_exposure, gross_exposure, open_positions, "
        "last_bar_time, stale_status, updated_at "
        "FROM runtime_status WHERE id = 1"
    )
    if not row:
        return {}
    return {
        "regime": row[0],
        "confidence": row[1],
        "active_card_id": row[2],
        "today_pnl": row[3],
        "cumulative_pnl": row[4],
        "today_trades": row[5],
        "net_exposure": row[6],
        "gross_exposure": row[7],
        "open_positions": row[8],
        "last_bar_time": row[9],
        "stale_status": row[10],
        "updated_at": row[11],
    }


def read_orchestrator_state() -> dict[str, Any]:
    """Read orchestrator_state singleton."""
    row = db_row("SELECT state, details_json, updated_at FROM orchestrator_state WHERE id = 1")
    if not row:
        return {"state": "UNKNOWN", "details": {}, "updated_at": None}
    return {
        "state": row[0],
        "details": row[1] if row[1] else {},
        "updated_at": row[2],
    }


def read_active_cards() -> list[dict]:
    """Read active strategy champions."""
    rows = db_query(
        "SELECT strategy_id, genome->>'regime' AS regime, wf_sharpe, wf_win_rate, "
        "fitness_score, created_at "
        "FROM strategy_champions WHERE status = 'active' "
        "ORDER BY fitness_score DESC NULLS LAST"
    )
    return [
        {
            "strategy_id": r[0],
            "regime": r[1],
            "wf_sharpe": r[2],
            "wf_win_rate": r[3],
            "fitness_score": r[4],
            "created_at": r[5],
        }
        for r in rows
    ]


def read_recent_events(since_minutes: int = 65) -> list[dict]:
    """Read orchestrator_events from the last N minutes."""
    rows = db_query(
        "SELECT event_type, regime, details_json, created_at "
        "FROM orchestrator_events "
        "WHERE created_at > NOW() - INTERVAL '%s minutes' "
        "ORDER BY created_at DESC",
        (since_minutes,),
    )
    return [
        {
            "event_type": r[0],
            "regime": r[1],
            "details": r[2] if r[2] else {},
            "created_at": r[3],
        }
        for r in rows
    ]


def read_daily_stats(date_str: Optional[str] = None) -> list[dict]:
    """Read card_daily_stats for a given date (default: yesterday)."""
    if date_str is None:
        date_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    rows = db_query(
        "SELECT card_id, daily_pnl, trade_count, win_rate, avg_slippage "
        "FROM card_daily_stats WHERE date = %s ORDER BY card_id",
        (date_str,),
    )
    return [
        {
            "card_id": r[0],
            "daily_pnl": r[1],
            "trade_count": r[2],
            "win_rate": r[3],
            "avg_slippage": r[4],
        }
        for r in rows
    ]


def read_trade_summary(hours: int = 24) -> dict:
    """Summarize trade_journal for the last N hours."""
    rows = db_query(
        "SELECT COUNT(*), "
        "COALESCE(SUM(pnl_pct), 0), "
        "COALESCE(AVG(pnl_pct), 0), "
        "COALESCE(AVG(CASE WHEN pnl_pct > 0 THEN 1.0 ELSE 0.0 END), 0) "
        "FROM trade_journal "
        "WHERE created_at > NOW() - INTERVAL '%s hours'",
        (hours,),
    )
    if not rows or rows[0][0] == 0:
        return {"trades": 0, "total_pnl_pct": 0, "avg_pnl_pct": 0, "win_rate": 0}
    r = rows[0]
    return {
        "trades": r[0],
        "total_pnl_pct": float(r[1] or 0),
        "avg_pnl_pct": float(r[2] or 0),
        "win_rate": float(r[3] or 0),
    }


# ---------------------------------------------------------------------------
# Message formatters
# ---------------------------------------------------------------------------
def fmt_heartbeat() -> str:
    """Format the hourly heartbeat message."""
    status = read_runtime_status()
    orch = read_orchestrator_state()
    cards = read_active_cards()
    trade_sum = read_trade_summary(hours=1)

    if not status:
        return "<b>Zangetsu Heartbeat</b>\nruntime_status: OFFLINE"

    lines = [
        f"<b>Zangetsu Heartbeat</b> {datetime.now(timezone.utc).strftime('%H:%M UTC')}",
        "",
        f"<b>Regime:</b> {status.get('regime', 'N/A')} "
        f"(conf={status.get('confidence', 0):.2f})",
        f"<b>Card:</b> {status.get('active_card_id', 'none')}",
        f"<b>PnL:</b> today={status.get('today_pnl', 0):+.4f} "
        f"cum={status.get('cumulative_pnl', 0):+.4f}",
        f"<b>Trades:</b> {status.get('today_trades', 0)} today, "
        f"{trade_sum['trades']} last 1h",
        f"<b>Exposure:</b> net={status.get('net_exposure', 0):.3f} "
        f"gross={status.get('gross_exposure', 0):.3f}",
        f"<b>Stale:</b> {status.get('stale_status', 'N/A')}",
        "",
        f"<b>Orchestrator:</b> {orch['state']}",
        f"<b>Active cards:</b> {len(cards)}",
    ]

    # Positions
    positions = status.get("open_positions", [])
    if positions and isinstance(positions, list) and len(positions) > 0:
        lines.append(f"<b>Positions:</b> {len(positions)}")
        for pos in positions[:5]:
            if isinstance(pos, dict):
                lines.append(
                    f"  {pos.get('symbol', '?')} {pos.get('side', '?')} "
                    f"qty={pos.get('quantity', '?')}"
                )

    return "\n".join(lines)


def fmt_daily_summary() -> str:
    """Format the 00:00 UTC daily summary."""
    status = read_runtime_status()
    orch = read_orchestrator_state()
    cards = read_active_cards()
    stats = read_daily_stats()
    trade_sum = read_trade_summary(hours=24)

    lines = [
        f"<b>Zangetsu Daily Summary</b> "
        f"{(datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')}",
        "",
    ]

    # Trade summary
    lines.append(f"<b>24h Trades:</b> {trade_sum['trades']}")
    lines.append(f"<b>24h PnL:</b> {trade_sum['total_pnl_pct']:+.4f}%")
    lines.append(f"<b>24h Win Rate:</b> {trade_sum['win_rate']:.1%}")
    lines.append(f"<b>24h Avg PnL:</b> {trade_sum['avg_pnl_pct']:+.6f}%")
    lines.append("")

    # Per-card stats
    if stats:
        lines.append("<b>Card Stats:</b>")
        for s in stats:
            lines.append(
                f"  #{s['card_id']}: pnl={s['daily_pnl']:+.4f} "
                f"trades={s['trade_count']} "
                f"wr={s['win_rate']:.1%} "
                f"slip={s['avg_slippage']:.1f}bps"
            )
        lines.append("")

    # Cumulative
    lines.append(f"<b>Cumulative PnL:</b> {status.get('cumulative_pnl', 0):+.4f}")
    lines.append(f"<b>Active Cards:</b> {len(cards)}")
    lines.append(f"<b>Orchestrator:</b> {orch['state']}")

    # Card list
    if cards:
        lines.append("")
        lines.append("<b>Champions:</b>")
        for c in cards[:10]:
            lines.append(
                f"  {c['strategy_id']}: {c['regime']} "
                f"sharpe={c['wf_sharpe']:.2f} "
                f"wr={c['wf_win_rate']:.1%}" if c['wf_sharpe'] and c['wf_win_rate'] else
                f"  {c['strategy_id']}: {c['regime']}"
            )

    return "\n".join(lines)


def fmt_alert(event: dict) -> Optional[str]:
    """Format an alert message for a specific event. Returns None to skip."""
    etype = event["event_type"]
    regime = event.get("regime", "")
    details = event.get("details", {})

    # Map event types to alert messages
    alert_map = {
        "arena1_complete": "Arena 1 factor search complete",
        "arena2_complete": "Arena 2 compression complete",
        "arena3_complete": "Arena 3 QD search complete",
        "arena3_regime_complete": f"Arena 3 search complete for {regime}",
        "gating_complete": "Gating complete",
        "deploying_complete": "Card deployment complete",
        "monitoring_triggered": "Monitoring trigger fired",
        "orchestrator_error": "Orchestrator error",
        "card_deployed": f"Card deployed: {regime}",
        "pysr_background_complete": "PySR background search complete",
    }

    label = alert_map.get(etype)
    if label is None:
        return None

    lines = [f"<b>Alert:</b> {label}"]
    if regime:
        lines.append(f"<b>Regime:</b> {regime}")

    # Add key details
    if etype == "gating_complete":
        lines.append(f"Passed: {details.get('passed', '?')}/{details.get('total_gated', '?')}")
    elif etype == "deploying_complete":
        deployed = details.get('deployed', [])
        lines.append(f"Deployed: {len(deployed) if isinstance(deployed, list) else deployed}")
    elif etype == "monitoring_triggered":
        triggers = details.get('triggers', [])
        for t in triggers:
            lines.append(f"  - {t}")
    elif etype == "orchestrator_error":
        lines.append(f"State: {details.get('state', '?')}")
        lines.append(f"Error: {str(details.get('error', '?'))[:200]}")
    elif etype == "card_deployed":
        lines.append(f"Fitness: {details.get('fitness', '?')}")
        lines.append(f"Sharpe: {details.get('wf_sharpe', '?')}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Anomaly detection (read-only)
# ---------------------------------------------------------------------------
def check_anomalies() -> list[str]:
    """Check for anomalies that warrant an alert. Returns list of alert texts."""
    alerts = []

    # 1. Runtime status stale > 5 minutes
    status = read_runtime_status()
    if status:
        updated = status.get("updated_at")
        if updated and (datetime.now(timezone.utc) - updated).total_seconds() > 300:
            minutes = int((datetime.now(timezone.utc) - updated).total_seconds() / 60)
            alerts.append(
                f"<b>Anomaly:</b> runtime_status stale ({minutes}m since update)"
            )

        # 2. Stale data feed
        if status.get("stale_status") not in (None, "OK", "ok", ""):
            alerts.append(
                f"<b>Anomaly:</b> stale data feed — {status.get('stale_status')}"
            )

        # 3. High exposure
        gross = status.get("gross_exposure", 0) or 0
        if gross > 0.45:
            alerts.append(
                f"<b>Anomaly:</b> high gross exposure {gross:.3f} (limit 0.50)"
            )

    # 4. Orchestrator stuck (same state for > 6h with no events)
    orch = read_orchestrator_state()
    orch_updated = orch.get("updated_at")
    if orch_updated and orch["state"] not in ("IDLE", "MONITORING"):
        hours_stuck = (datetime.now(timezone.utc) - orch_updated).total_seconds() / 3600
        if hours_stuck > 6:
            alerts.append(
                f"<b>Anomaly:</b> orchestrator stuck in {orch['state']} "
                f"for {hours_stuck:.1f}h"
            )

    return alerts


# ---------------------------------------------------------------------------
# Async tasks
# ---------------------------------------------------------------------------
_last_event_id: int = 0


async def heartbeat_loop() -> None:
    """Send heartbeat every HEARTBEAT_INTERVAL seconds."""
    while True:
        try:
            msg = fmt_heartbeat()
            await send_tg(msg)
            log.info("Heartbeat sent")
        except Exception as e:
            log.error("Heartbeat error: %s", e)
        await asyncio.sleep(HEARTBEAT_INTERVAL)


async def daily_summary_loop() -> None:
    """Send daily summary at 00:00 UTC."""
    while True:
        now = datetime.now(timezone.utc)
        # Calculate seconds until next 00:00 UTC
        tomorrow = (now + timedelta(days=1)).replace(
            hour=DAILY_SUMMARY_HOUR_UTC, minute=0, second=0, microsecond=0
        )
        wait_s = (tomorrow - now).total_seconds()
        log.info("Daily summary scheduled in %.0f seconds", wait_s)
        await asyncio.sleep(wait_s)

        try:
            msg = fmt_daily_summary()
            await send_tg(msg)
            log.info("Daily summary sent")
        except Exception as e:
            log.error("Daily summary error: %s", e)


async def alert_loop() -> None:
    """Poll orchestrator_events and anomalies for alerts."""
    global _last_event_id

    # Initialize: get max event id
    max_id = db_scalar("SELECT MAX(id) FROM orchestrator_events")
    _last_event_id = max_id or 0
    log.info("Alert loop starting from event_id=%d", _last_event_id)

    while True:
        try:
            # Check for new orchestrator events
            events = read_recent_events(since_minutes=2)
            for ev in events:
                # Only process events we haven't seen
                # (use created_at comparison since we poll by time window)
                alert_text = fmt_alert(ev)
                if alert_text:
                    await send_tg(alert_text)
                    log.info("Alert sent: %s", ev["event_type"])

            # Check for anomalies
            anomalies = check_anomalies()
            for anomaly_text in anomalies:
                await send_tg(anomaly_text)
                log.info("Anomaly alert sent")

        except Exception as e:
            log.error("Alert loop error: %s\n%s", e, traceback.format_exc())

        await asyncio.sleep(ALERT_POLL_INTERVAL)


# ---------------------------------------------------------------------------
# Alert deduplication
# ---------------------------------------------------------------------------
class AlertDedup:
    """Prevent sending the same alert repeatedly within a cooldown window."""

    def __init__(self, cooldown_s: int = 3600):
        self.cooldown_s = cooldown_s
        self._sent: dict[str, datetime] = {}

    def should_send(self, key: str) -> bool:
        now = datetime.now(timezone.utc)
        last = self._sent.get(key)
        if last and (now - last).total_seconds() < self.cooldown_s:
            return False
        self._sent[key] = now
        return True

    def cleanup(self) -> None:
        """Remove expired entries."""
        now = datetime.now(timezone.utc)
        expired = [k for k, v in self._sent.items()
                    if (now - v).total_seconds() > self.cooldown_s * 2]
        for k in expired:
            del self._sent[k]


_dedup = AlertDedup(cooldown_s=3600)


async def alert_loop_deduped() -> None:
    """Alert loop with deduplication."""
    global _last_event_id

    max_id = db_scalar("SELECT MAX(id) FROM orchestrator_events")
    _last_event_id = max_id or 0
    log.info("Alert loop (deduped) starting from event_id=%d", _last_event_id)

    while True:
        try:
            # New events since last check
            rows = db_query(
                "SELECT id, event_type, regime, details_json, created_at "
                "FROM orchestrator_events "
                "WHERE id > %s ORDER BY id",
                (_last_event_id,),
            )
            for row in rows:
                eid, etype, regime, det, created = row
                _last_event_id = max(_last_event_id, eid)

                ev = {
                    "event_type": etype,
                    "regime": regime,
                    "details": det if det else {},
                    "created_at": created,
                }
                alert_text = fmt_alert(ev)
                if alert_text and _dedup.should_send(f"event:{etype}:{regime}"):
                    await send_tg(alert_text)
                    log.info("Alert sent: %s (id=%d)", etype, eid)

            # Anomaly checks (with dedup)
            anomalies = check_anomalies()
            for atext in anomalies:
                # Use first 50 chars as dedup key
                key = f"anomaly:{atext[:50]}"
                if _dedup.should_send(key):
                    await send_tg(atext)

            # Periodic cleanup
            _dedup.cleanup()

        except Exception as e:
            log.error("Alert loop error: %s", e)

        await asyncio.sleep(ALERT_POLL_INTERVAL)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def async_main() -> None:
    log.info("=" * 60)
    log.info("Zangetsu V3.2 Bot starting (NOTIFY ONLY)")
    log.info("Chat ID: %s", CHAT_ID)
    log.info("Token: %s...%s", TG_TOKEN[:5], TG_TOKEN[-4:]) if len(TG_TOKEN) > 10 else log.info("Token: (not set)")
    log.info("=" * 60)

    # Send startup message
    orch = read_orchestrator_state()
    await send_tg(
        f"<b>Zangetsu V3.2 Bot started</b>\n"
        f"Orchestrator: {orch.get('state', 'N/A')}\n"
        f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )

    # Run all loops concurrently
    await asyncio.gather(
        heartbeat_loop(),
        daily_summary_loop(),
        alert_loop_deduped(),
    )


def main() -> None:
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        log.info("Shutting down")


if __name__ == "__main__":
    main()
