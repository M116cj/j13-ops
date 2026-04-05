"""
Zangetsu V3.1 Dashboard API Server
Independent FastAPI service — reads JSON/parquet files directly, no zangetsu_v3 imports.
"""

import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import polars as pl
import psutil
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

STRATEGIES_DIR = Path(os.getenv("ZV3_STRATEGIES_DIR", "strategies"))
STATUS_FILE = Path(os.getenv("ZV3_STATUS_FILE", "status.json"))
ARENA_LOG_DIR = Path(os.getenv("ZV3_ARENA_LOG_DIR", "logs/arena"))
PORT = int(os.getenv("ZV3_DASHBOARD_PORT", "8766"))

app = FastAPI(title="Zangetsu V3.1 Dashboard", version="3.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_start_time = time.monotonic()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_status() -> dict:
    """Read status.json written by main_loop every bar."""
    if not STATUS_FILE.exists():
        return {}
    try:
        return json.loads(STATUS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _discover_card_dirs() -> list[Path]:
    """Return all strategy card directories (contain card.json)."""
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
    """Read live_journal.parquet, return empty DataFrame on any failure."""
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
# GET /api/status
# ---------------------------------------------------------------------------


@app.get("/api/status")
def get_status():
    status = _read_status()

    # Compute aggregate PnL from all journals
    today_pnl = 0.0
    cumulative_pnl = 0.0
    today_trades = 0
    open_positions = 0
    net_exposure = 0.0
    gross_exposure = 0.0

    today_start = _today_utc_start()

    for card_dir in _discover_card_dirs():
        df = _read_journal(card_dir)
        if df.is_empty() or "pnl_pct" not in df.columns:
            continue

        pnl_col = df["pnl_pct"].drop_nulls()
        cumulative_pnl += pnl_col.sum() if len(pnl_col) > 0 else 0.0

        if "timestamp" in df.columns:
            try:
                today_df = df.filter(pl.col("timestamp") >= today_start)
                today_pnl_col = today_df["pnl_pct"].drop_nulls()
                today_pnl += today_pnl_col.sum() if len(today_pnl_col) > 0 else 0.0
                today_trades += len(today_df)
            except Exception:
                pass

    # Override with status.json values if present (runtime knows better)
    return {
        "regime": status.get("regime", "UNKNOWN"),
        "confidence": status.get("confidence", 0.0),
        "bars_since_switch": status.get("bars_since_switch", 0),
        "switch_confidence": status.get("switch_confidence", 0.0),
        "active_card_id": status.get("active_card_id", ""),
        "stale_status": status.get("stale_status", "unknown"),
        "last_bar_time": status.get("last_bar_time", ""),
        "today_pnl": status.get("today_pnl", today_pnl),
        "cumulative_pnl": status.get("cumulative_pnl", cumulative_pnl),
        "today_trades": status.get("today_trades", today_trades),
        "open_positions": status.get("open_positions", open_positions),
        "net_exposure": status.get("net_exposure", net_exposure),
        "gross_exposure": status.get("gross_exposure", gross_exposure),
    }


# ---------------------------------------------------------------------------
# GET /api/cards
# ---------------------------------------------------------------------------


@app.get("/api/cards")
def list_cards():
    cards = []
    for card_dir in _discover_card_dirs():
        card = _load_card_json(card_dir)
        if card is None:
            continue

        journal = _read_journal(card_dir)
        trade_count = len(journal) if not journal.is_empty() else 0
        cum_pnl = 0.0
        if not journal.is_empty() and "pnl_pct" in journal.columns:
            cum_pnl = float(journal["pnl_pct"].drop_nulls().sum())

        cards.append({
            "id": card.get("id", card_dir.name),
            "regime": card.get("regime", ""),
            "version": card.get("version", ""),
            "created_at": card.get("created_at", ""),
            "factors_count": len(card.get("factors", [])),
            "params": card.get("params", {}),
            "backtest": card.get("backtest", {}),
            "symbols": card.get("deployment_hints", {}).get("preferred_symbols", []),
            "trade_count": trade_count,
            "cumulative_pnl": cum_pnl,
        })
    return {"cards": cards}


# ---------------------------------------------------------------------------
# GET /api/card/{card_id}/pnl
# ---------------------------------------------------------------------------


@app.get("/api/card/{card_id}/pnl")
def card_pnl(card_id: str):
    card_dir = STRATEGIES_DIR / card_id
    if not card_dir.exists():
        raise HTTPException(status_code=404, detail=f"Card {card_id} not found")

    df = _read_journal(card_dir)
    if df.is_empty() or "pnl_pct" not in df.columns:
        return {"card_id": card_id, "pnl_series": []}

    # Build cumulative PnL time series
    has_ts = "timestamp" in df.columns
    pnl_vals = df["pnl_pct"].fill_null(0.0).to_list()
    cumulative = []
    running = 0.0
    for i, v in enumerate(pnl_vals):
        running += v
        entry = {"index": i, "pnl_pct": v, "cumulative_pnl": running}
        if has_ts:
            try:
                entry["timestamp"] = str(df["timestamp"][i])
            except Exception:
                pass
        cumulative.append(entry)

    return {"card_id": card_id, "pnl_series": cumulative}


# ---------------------------------------------------------------------------
# GET /api/card/{card_id}/trades
# ---------------------------------------------------------------------------


@app.get("/api/card/{card_id}/trades")
def card_trades(card_id: str, limit: int = Query(default=20, ge=1, le=500)):
    card_dir = STRATEGIES_DIR / card_id
    if not card_dir.exists():
        raise HTTPException(status_code=404, detail=f"Card {card_id} not found")

    df = _read_journal(card_dir)
    if df.is_empty():
        return {"card_id": card_id, "trades": [], "total": 0}

    total = len(df)
    recent = df.tail(limit)

    trades = []
    for row in recent.iter_rows(named=True):
        trade = {}
        for k, v in row.items():
            if isinstance(v, datetime):
                trade[k] = v.isoformat()
            elif v is None:
                trade[k] = None
            else:
                trade[k] = v
        trades.append(trade)

    # Reverse so most recent first
    trades.reverse()
    return {"card_id": card_id, "trades": trades, "total": total}


# ---------------------------------------------------------------------------
# GET /api/arena
# ---------------------------------------------------------------------------


@app.get("/api/arena")
def arena_status():
    """Read arena pipeline status from log files and checkpoint files."""
    result = {
        "running": False,
        "current_generation": 0,
        "total_generations": 0,
        "elite_count": 0,
        "best_fitness": 0.0,
        "last_update": "",
        "recent_log_lines": [],
    }

    # Check for arena checkpoint
    checkpoint_candidates = [
        STRATEGIES_DIR.parent / "arena_checkpoint.json",
        Path("arena_checkpoint.json"),
    ]
    for cp_path in checkpoint_candidates:
        if cp_path.exists():
            try:
                cp = json.loads(cp_path.read_text())
                result["running"] = cp.get("running", False)
                result["current_generation"] = cp.get("generation", 0)
                result["total_generations"] = cp.get("total_generations", 0)
                result["elite_count"] = cp.get("elite_count", 0)
                result["best_fitness"] = cp.get("best_fitness", 0.0)
                result["last_update"] = cp.get("timestamp", "")
                break
            except (json.JSONDecodeError, OSError):
                pass

    # Read tail of arena log
    if ARENA_LOG_DIR.exists():
        log_files = sorted(ARENA_LOG_DIR.glob("arena*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        if log_files:
            try:
                lines = log_files[0].read_text().strip().split("\n")
                result["recent_log_lines"] = lines[-20:]
            except OSError:
                pass

    return result


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------


@app.get("/api/health")
def health_check():
    health = {
        "status": "ok",
        "checks": {},
        "uptime_seconds": round(time.monotonic() - _start_time, 1),
    }

    # Postgres ping
    pg_ok = False
    try:
        import psycopg2  # noqa: delayed import — only needed for health check

        conn = psycopg2.connect(
            host=os.getenv("ZV3_DB_HOST", "127.0.0.1"),
            port=int(os.getenv("ZV3_DB_PORT", "5432")),
            user=os.getenv("ZV3_DB_USER", "zangetsu"),
            password=os.getenv("ZV3_DB_PASSWORD", ""),
            dbname=os.getenv("ZV3_DB_NAME", "zangetsu"),
            connect_timeout=3,
        )
        conn.close()
        pg_ok = True
    except Exception as e:
        health["checks"]["postgres"] = f"FAIL: {e}"

    if pg_ok:
        health["checks"]["postgres"] = "ok"

    # Disk usage
    try:
        usage = shutil.disk_usage("/")
        free_gb = usage.free / (1024**3)
        health["checks"]["disk_free_gb"] = round(free_gb, 2)
        if free_gb < 5.0:
            health["status"] = "degraded"
            health["checks"]["disk"] = f"LOW: {free_gb:.1f} GB free"
        else:
            health["checks"]["disk"] = "ok"
    except Exception:
        health["checks"]["disk"] = "unknown"

    # RAM
    try:
        mem = psutil.virtual_memory()
        health["checks"]["ram_used_pct"] = round(mem.percent, 1)
        health["checks"]["ram_available_gb"] = round(mem.available / (1024**3), 2)
        if mem.percent > 90:
            health["status"] = "degraded"
            health["checks"]["ram"] = f"HIGH: {mem.percent}%"
        else:
            health["checks"]["ram"] = "ok"
    except Exception:
        health["checks"]["ram"] = "unknown"

    # Last bar age
    status = _read_status()
    last_bar = status.get("last_bar_time", "")
    if last_bar:
        try:
            ts = datetime.fromisoformat(last_bar.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - ts).total_seconds()
            health["checks"]["last_bar_age_seconds"] = round(age, 1)
            if age > 120:
                health["status"] = "degraded"
                health["checks"]["data_freshness"] = f"STALE: {age:.0f}s"
            else:
                health["checks"]["data_freshness"] = "ok"
        except (ValueError, TypeError):
            health["checks"]["data_freshness"] = "unparseable"
    else:
        health["checks"]["data_freshness"] = "no data"

    return health


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
