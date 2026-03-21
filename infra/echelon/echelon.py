"""
echelon.py — zangetsu signal relay → Telegram

Polls execution_log in PostgreSQL for new BUY/SELL signals.
Sends formatted Telegram notification to TOPIC_SIGNALS thread.

Architecture:
  deploy-trader-1 → execution_log (PostgreSQL) → echelon → @Alaya13jbot Telegram

High-water mark: stored in echelon_state table (auto-created).
Runs as Docker container on the `deploy` network.
"""

import os
import time
import logging
import json
import psycopg2
import psycopg2.extras
import httpx
from datetime import timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("echelon")

# ── Config ────────────────────────────────────────────────────────────────────
DB_URL         = os.environ["POOL_DATABASE_URL"]
BOT_TOKEN      = os.environ["ALAYA_BOT_TOKEN"]
CHAT_ID        = int(os.environ["GROUP_CHAT_ID"])
TOPIC_SIGNALS  = int(os.environ.get("TOPIC_SIGNALS", "12"))
POLL_INTERVAL  = int(os.environ.get("POLL_INTERVAL_S", "15"))
MIN_CONFIDENCE = float(os.environ.get("MIN_CONFIDENCE", "0.0"))  # 0 = all signals

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ── Database ──────────────────────────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(DB_URL, connect_timeout=10)


def ensure_state_table(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS echelon_state (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        cur.execute("""
            INSERT INTO echelon_state (key, value)
            VALUES ('last_seen_id', '0')
            ON CONFLICT (key) DO NOTHING
        """)
    conn.commit()


def get_last_seen_id(conn) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT value FROM echelon_state WHERE key='last_seen_id'")
        row = cur.fetchone()
        return int(row[0]) if row else 0


def set_last_seen_id(conn, row_id: int):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE echelon_state SET value=%s WHERE key='last_seen_id'",
            (str(row_id),)
        )
    conn.commit()


def fetch_new_signals(conn, last_id: int) -> list[dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT id, symbol, side, entry_price, signal_confidence,
                   regime_at_entry, leverage_used, entry_ts
            FROM execution_log
            WHERE id > %s
              AND signal_confidence >= %s
            ORDER BY id ASC
        """, (last_id, MIN_CONFIDENCE))
        return [dict(r) for r in cur.fetchall()]


# ── Telegram ──────────────────────────────────────────────────────────────────

def format_signal(row: dict) -> str:
    side    = row["side"]
    symbol  = row["symbol"]
    price   = row["entry_price"]
    conf    = row["signal_confidence"]
    regime  = row.get("regime_at_entry") or "unknown"
    lev     = row.get("leverage_used")
    ts      = row["entry_ts"]
    if ts and hasattr(ts, "strftime"):
        ts_str = ts.strftime("%H:%M UTC")
    else:
        ts_str = str(ts)[:16] if ts else "?"

    icon = "🟢" if side == "BUY" else "🔴"
    lev_str = f"  ×{lev:.1f}" if lev else ""

    return (
        f"{icon} <b>zangetsu {side}</b> — {symbol}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 Entry: <code>${price:,.2f}</code>{lev_str}\n"
        f"🎯 Confidence: <code>{conf:.1%}</code>\n"
        f"📊 Regime: <code>{regime}</code>\n"
        f"⏱ {ts_str}  •  paper-trade mode"
    )


def send_telegram(text: str) -> bool:
    try:
        payload = {
            "chat_id": CHAT_ID,
            "text": text[:4096],
            "parse_mode": "HTML",
            "message_thread_id": TOPIC_SIGNALS,
        }
        r = httpx.post(f"{TG_API}/sendMessage", json=payload, timeout=15)
        if r.status_code == 200:
            log.info("Telegram sent OK")
            return True
        log.warning("Telegram error %s: %s", r.status_code, r.text[:200])
        return False
    except Exception as e:
        log.error("Telegram send failed: %s", e)
        return False


# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    log.info("echelon starting — poll=%ds, min_confidence=%.0f%%",
             POLL_INTERVAL, MIN_CONFIDENCE * 100)

    conn = None
    retry_delay = 5

    while True:
        try:
            if conn is None or conn.closed:
                log.info("Connecting to PostgreSQL…")
                conn = get_conn()
                ensure_state_table(conn)
                log.info("Connected. Watching execution_log…")
                retry_delay = 5

            last_id = get_last_seen_id(conn)
            rows = fetch_new_signals(conn, last_id)

            for row in rows:
                log.info("Signal: id=%d %s %s conf=%.2f",
                         row["id"], row["side"], row["symbol"], row["signal_confidence"])
                text = format_signal(row)
                send_telegram(text)
                set_last_seen_id(conn, row["id"])

            time.sleep(POLL_INTERVAL)

        except psycopg2.OperationalError as e:
            log.error("DB connection lost: %s — reconnecting in %ds", e, retry_delay)
            try:
                conn.close()
            except Exception:
                pass
            conn = None
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)

        except Exception as e:
            log.error("Unexpected error: %s", e, exc_info=True)
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
