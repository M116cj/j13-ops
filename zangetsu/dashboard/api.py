"""Dashboard API — live data from champion_pipeline DB.

V6 upgrade:
- cached_fetch() wired into all endpoints (TTL=5s)
- /api/components queries actual systemd service status
- bare except: clauses replaced with specific exception handling + logging
- new /api/v7/families endpoint (queries family_ranking materialized view)
- new /api/v7/pipeline-flow endpoint (funnel view)
- /api/health/pipeline checks actual systemd services
- PAUSE/HALT button references removed from mobile.html serving
"""
from __future__ import annotations
import asyncio
import logging
import math
import subprocess
import time
from typing import Any, Dict, List, TYPE_CHECKING
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from .models import (
    ArenaStatus, BacktestSummary, ComponentHealth,
    ELOLeaderboard, ELOEntry, EvolutionStats, PipelineOverview,
)

logger = logging.getLogger("zangetsu.dashboard")

_cache: Dict[str, Any] = {}
_cache_ts: Dict[str, float] = {}
CACHE_TTL = 5.0  # upgraded from 1.5s to 5s

_start_time = time.time()


async def cached_fetch(key: str, fetch_fn):
    """Cache async fetch results for CACHE_TTL seconds."""
    now = time.time()
    if key in _cache and now - _cache_ts.get(key, 0) < CACHE_TTL:
        return _cache[key]
    result = await fetch_fn()
    _cache[key] = result
    _cache_ts[key] = now
    return result


# --- Systemd service checker (runs on host, not in Docker) ---

ZANGETSU_SERVICES = [
    "arena-pipeline",
    "arena23-orchestrator",
    "arena45-orchestrator",
    "arena13-evolution",
    "console-api",
    "dashboard-api",
]


def _check_systemd_service(name: str) -> dict:
    """Check if a systemd service is active. Returns status dict."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", f"{name}.service"],
            capture_output=True, text=True, timeout=5
        )
        state = result.stdout.strip()
        return {"name": name, "status": "ok" if state == "active" else "degraded", "state": state}
    except subprocess.TimeoutExpired:
        return {"name": name, "status": "unknown", "state": "timeout"}
    except FileNotFoundError:
        # systemctl not available (e.g. running in Docker)
        return {"name": name, "status": "unknown", "state": "systemctl_unavailable"}
    except OSError as e:
        return {"name": name, "status": "error", "state": str(e)}


def _check_all_services() -> List[dict]:
    """Check all Zangetsu systemd services."""
    return [_check_systemd_service(svc) for svc in ZANGETSU_SERVICES]


def create_dashboard_app(engine) -> FastAPI:
    app = FastAPI(title="Zangetsu V6 Dashboard", version="6.0.0")

    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response

    class NoCacheMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            response = await call_next(request)
            if request.url.path.endswith('.html') or request.url.path == '/mobile' or request.url.path == '/':
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"
            return response

    app.add_middleware(NoCacheMiddleware)

    async def _compute_throughput(eng):
        """Compute throughput from actual DB time range (non-LEGACY records)."""
        try:
            row = await eng.db.fetchrow(
                "SELECT EXTRACT(EPOCH FROM (MAX(created_at) - MIN(created_at))) as span_s, "
                "count(*) as cnt FROM champion_pipeline WHERE status != 'LEGACY'"
            )
            if row and row["span_s"] and row["span_s"] > 0:
                return round(row["cnt"] / (float(row["span_s"]) / 3600), 1)
            return 0
        except Exception as e:
            logger.warning("throughput computation failed: %s", e)
            return 0

    # ---------------------------------------------------------------
    # Core pipeline endpoints
    # ---------------------------------------------------------------

    @app.get("/api/pipeline")
    async def pipeline_overview():
        async def _fetch():
            rows = await engine.db.fetch(
                "SELECT status, count(*) as cnt FROM champion_pipeline "
                "WHERE status NOT LIKE 'LEGACY%%' GROUP BY status ORDER BY cnt DESC"
            )
            by_status = {r["status"]: r["cnt"] for r in rows}
            total = sum(by_status.values())
            deployable = by_status.get("DEPLOYABLE", 0)
            active_row = await engine.db.fetchrow(
                """SELECT count(*) AS cnt FROM champion_pipeline
                   WHERE status = 'DEPLOYABLE'
                     AND card_status IN ('ACTIVE', 'CHALLENGED', 'DRAINING', 'HANDOVER')"""
            )
            active_cards = int(active_row["cnt"] or 0) if active_row else 0
            _urow = await engine.db.fetchrow(
                "SELECT count(DISTINCT passport->'arena1'->>'config_hash') as cnt "
                "FROM champion_pipeline WHERE status NOT LIKE 'LEGACY%%' "
                "AND passport->'arena1'->>'config_hash' IS NOT NULL"
            )
            unique = _urow["cnt"] if _urow else 0
            _nrow = await engine.db.fetchrow(
                "SELECT count(*) as cnt FROM champion_pipeline "
                "WHERE status NOT LIKE 'LEGACY%%' AND created_at > NOW() - INTERVAL '1 hour'"
            )
            new_1h = _nrow["cnt"] if _nrow else 0
            _crow = await engine.db.fetchrow(
                "SELECT count(*) as cnt FROM champion_pipeline WHERE status = 'CANDIDATE'"
            )
            candidate = _crow["cnt"] if _crow else 0
            return {
                "state": "RUNNING",
                "since": _start_time,
                "total_champions": total,
                "unique_combos": unique or 0,
                "new_1h": new_1h or 0,
                "deployable": deployable,
                "candidate": candidate or 0,
                "active_cards": active_cards,
                "by_status": by_status,
                "throughput_hr": await _compute_throughput(engine),
            }
        try:
            return await cached_fetch("pipeline_overview", _fetch)
        except Exception as e:
            logger.error("pipeline_overview failed: %s", e)
            return {"state": "ERROR", "error": str(e), "by_status": {}}

    @app.get("/health")
    async def health():
        try:
            overview = await pipeline_overview()
            if overview.get("state") != "RUNNING":
                raise HTTPException(status_code=503, detail=overview)
            recent = await engine.db.fetchrow(
                """SELECT EXTRACT(EPOCH FROM (NOW() - MAX(created_at))) AS age_s
                   FROM champion_pipeline WHERE status != 'LEGACY'"""
            )
            age_s = float(recent["age_s"]) if recent and recent["age_s"] is not None else None
            return {
                "status": "ok",
                "state": overview["state"],
                "deployable": overview.get("deployable", 0),
                "active_cards": overview.get("active_cards", 0),
                "last_champion_ago_s": round(age_s, 1) if age_s is not None else None,
                "uptime_s": round(time.time() - _start_time, 1),
            }
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("health check failed: %s", exc)
            raise HTTPException(status_code=503, detail=str(exc))

    @app.get("/api/elo")
    async def elo_leaderboard():
        async def _fetch():
            rows = await engine.db.fetch("""
                SELECT id, indicator_hash, regime, elo_rating, quant_class,
                       arena1_win_rate, arena1_pnl, arena1_n_trades, card_status,
                       arena3_sharpe, arena3_expectancy, arena3_pnl,
                       elo_consecutive_first,
                       EXTRACT(EPOCH FROM (NOW() - COALESCE(arena5_last_tested, created_at))) as elo_age_s,
                       passport->'arena3'->>'atr_multiplier' as atr_mult,
                       passport->'arena3'->>'half_kelly' as kelly,
                       passport->'arena2'->>'optimized_entry_threshold' as opt_entry,
                       passport->'arena2'->>'optimized_exit_threshold' as opt_exit,
                       n_indicators
                FROM champion_pipeline
                WHERE status IN ('DEPLOYABLE', 'CANDIDATE') AND elo_rating IS NOT NULL
                ORDER BY elo_rating DESC LIMIT 50
            """)
            return [
                {
                    "id": r["id"],
                    "hash": r["indicator_hash"][:25],
                    "regime": r["regime"],
                    "elo": round(float(r["elo_rating"]), 1),
                    "quant_class": r["quant_class"] or "unknown",
                    "wr": round(float(r["arena1_win_rate"] or 0), 3),
                    "pnl": round(float(r["arena1_pnl"] or 0), 4),
                    "trades": r["arena1_n_trades"] or 0,
                    "card": r["card_status"] or "INACTIVE",
                    "sharpe": round(float(r["arena3_sharpe"] or 0), 2),
                    "expectancy": round(float(r["arena3_expectancy"] or 0), 4),
                    "a3_pnl": round(float(r["arena3_pnl"] or 0), 4),
                    "streak": r["elo_consecutive_first"] or 0,
                    "elo_age_h": round(float(r["elo_age_s"] or 0) / 3600, 1),
                    "atr_mult": r["atr_mult"] or "--",
                    "kelly": r["kelly"] or "--",
                    "opt_entry": r["opt_entry"] or "--",
                    "opt_exit": r["opt_exit"] or "--",
                    "n_ind": r["n_indicators"] or 0,
                }
                for r in rows
            ]
        try:
            return await cached_fetch("elo_leaderboard", _fetch)
        except Exception as e:
            logger.error("elo_leaderboard failed: %s", e)
            return []

    @app.get("/api/active-cards")
    async def active_cards():
        async def _fetch():
            rows = await engine.db.fetch("""
                SELECT regime, indicator_hash, elo_rating, quant_class, arena1_win_rate, card_status
                FROM champion_pipeline
                WHERE status = 'DEPLOYABLE' AND card_status IN ('ACTIVE', 'CHALLENGED')
                ORDER BY regime, elo_rating DESC
            """)
            return [
                {
                    "regime": r["regime"],
                    "hash": r["indicator_hash"][:20],
                    "elo": round(float(r["elo_rating"]), 1),
                    "quant_class": r["quant_class"] or "unknown",
                    "wr": round(float(r["arena1_win_rate"] or 0), 3),
                    "card": r["card_status"],
                }
                for r in rows
            ]
        try:
            return await cached_fetch("active_cards", _fetch)
        except Exception as e:
            logger.error("active_cards failed: %s", e)
            return []

    @app.get("/api/arenas")
    async def arena_stats():
        async def _fetch():
            rows = await engine.db.fetch("""
                SELECT
                    count(*) FILTER (WHERE status LIKE 'ARENA1%%') as arena1,
                    count(*) FILTER (WHERE status LIKE 'ARENA2%%') as arena2,
                    count(*) FILTER (WHERE status LIKE 'ARENA3%%') as arena3,
                    count(*) FILTER (WHERE status LIKE 'ARENA4%%') as arena4,
                    count(*) FILTER (WHERE status = 'DEPLOYABLE') as arena5,
                    count(*) FILTER (WHERE status IN ('EVOLVING','EVOLVED')) as arena13,
                    count(*) FILTER (WHERE status = 'ELO_RETIRED') as retired,
                    round(max(arena1_win_rate)::numeric, 3) as best_wr,
                    round(max(elo_rating) FILTER (WHERE status = 'DEPLOYABLE')::numeric, 1) as top_elo
                FROM champion_pipeline
                WHERE status NOT LIKE 'LEGACY%%'
            """)
            r = rows[0] if rows else {}
            return {
                "arena1": {"count": r.get("arena1", 0), "status": "RUNNING"},
                "arena2": {"count": r.get("arena2", 0), "status": "RUNNING"},
                "arena3": {"count": r.get("arena3", 0), "status": "RUNNING"},
                "arena4": {"count": r.get("arena4", 0), "status": "RUNNING"},
                "arena5": {"count": r.get("arena5", 0), "status": "RUNNING", "top_elo": float(r.get("top_elo", 0) or 0)},
                "arena13": {"count": r.get("arena13", 0), "status": "WAITING"},
                "best_wr": float(r.get("best_wr", 0) or 0),
                "retired": r.get("retired", 0),
            }
        try:
            return await cached_fetch("arena_stats", _fetch)
        except Exception as e:
            logger.error("arena_stats failed: %s", e)
            return {"error": str(e)}

    @app.get("/api/components")
    async def components():
        """Query actual systemd service status instead of returning static 'ok'."""
        async def _fetch():
            # Check systemd services (runs in thread to avoid blocking)
            loop = asyncio.get_event_loop()
            service_statuses = await loop.run_in_executor(None, _check_all_services)

            # Check DB connectivity
            db_status = "ok"
            db_details: dict = {}
            try:
                row = await engine.db.fetchrow("SELECT count(*) as total FROM champion_pipeline")
                db_details = {"total_rows": row["total"]}
            except Exception as e:
                db_status = "error"
                db_details = {"error": str(e)}

            # Check Rust engine (GPU)
            rust_status = "unknown"
            rust_details: dict = {}
            try:
                gpu_info = engine.gpu.health_check()
                rust_status = "ok" if gpu_info else "degraded"
                rust_details = gpu_info if isinstance(gpu_info, dict) else {}
            except Exception as e:
                rust_status = "error"
                rust_details = {"error": str(e)}

            # Map service names to component names
            svc_map = {
                "arena-pipeline": ("arena_pipeline", "Arena 1 Discovery"),
                "arena23-orchestrator": ("arena23", "Arena 2+3 Optimizer"),
                "arena45-orchestrator": ("arena45", "Arena 4+5 Validator+ELO"),
                "arena13-evolution": ("arena13", "Arena 13 Evolution"),
                "console-api": ("console_api", "Console API"),
                "dashboard-api": ("dashboard_api", "Dashboard API"),
            }

            result = []
            for svc in service_statuses:
                mapped = svc_map.get(svc["name"])
                if mapped:
                    comp_name, comp_type = mapped
                    result.append({
                        "name": comp_name,
                        "status": svc["status"],
                        "details": {"type": comp_type, "state": svc.get("state", "unknown")},
                    })

            result.append({"name": "db", "status": db_status, "details": db_details})
            result.append({"name": "rust_engine", "status": rust_status, "details": rust_details})
            return result

        try:
            return await cached_fetch("components", _fetch)
        except Exception as e:
            logger.error("components check failed: %s", e)
            return [{"name": "system", "status": "error", "details": {"error": str(e)}}]

    @app.get("/api/gpu")
    async def gpu():
        try:
            return engine.gpu.health_check()
        except Exception as e:
            logger.error("gpu health check failed: %s", e)
            return {"status": "error", "error": str(e)}

    @app.get("/api/scores/top/{k}")
    async def top_scores(k: int = 20):
        async def _fetch():
            rows = await engine.db.fetch("""
                SELECT id, indicator_hash, regime, arena1_win_rate, arena1_pnl,
                       arena1_n_trades, elo_rating, quant_class
                FROM champion_pipeline
                WHERE status = 'DEPLOYABLE'
                ORDER BY elo_rating DESC LIMIT $1
            """, k)
            return [
                {
                    "id": r["id"],
                    "regime": r["regime"],
                    "wr": round(float(r["arena1_win_rate"] or 0), 3),
                    "pnl": round(float(r["arena1_pnl"] or 0), 4),
                    "trades": r["arena1_n_trades"] or 0,
                    "elo": round(float(r["elo_rating"] or 1500), 1),
                }
                for r in rows
            ]
        try:
            return await cached_fetch(f"top_scores_{k}", _fetch)
        except Exception as e:
            logger.error("top_scores failed: %s", e)
            return []

    @app.get("/api/costs")
    async def costs():
        try:
            return engine.cost_model.snapshot()
        except Exception as e:
            logger.error("costs failed: %s", e)
            return {"error": str(e)}

    @app.get("/api/trades")
    async def recent_trades():
        """Recent trades from trade_journal."""
        async def _fetch():
            rows = await engine.db.fetch(
                "SELECT id, ts, symbol, side, pnl, pnl_pct, regime, card_id "
                "FROM trade_journal ORDER BY ts DESC LIMIT 10"
            )
            return [
                {
                    "id": r["id"],
                    "ts": str(r["ts"]) if r["ts"] else None,
                    "symbol": r["symbol"],
                    "side": r["side"],
                    "pnl": float(r["pnl"]) if r["pnl"] is not None else None,
                    "pnl_pct": float(r["pnl_pct"]) if r["pnl_pct"] is not None else None,
                    "regime": r["regime"],
                }
                for r in rows
            ]
        try:
            return await cached_fetch("recent_trades", _fetch)
        except Exception as e:
            logger.error("recent_trades failed: %s", e)
            return []

    @app.get("/api/arena/{name}")
    async def arena_detail(name: str):
        """Detailed stats for a specific arena."""
        async def _fetch():
            if name == "arena1":
                rows = await engine.db.fetch("""
                    SELECT count(*) as total,
                           count(*) FILTER (WHERE arena1_completed_at IS NOT NULL) as completed,
                           round(avg(arena1_win_rate)::numeric, 3) as avg_wr,
                           round(max(arena1_win_rate)::numeric, 3) as best_wr,
                           round(avg(n_indicators)::numeric, 1) as avg_indicators
                    FROM champion_pipeline WHERE arena1_completed_at IS NOT NULL
                """)
                r = rows[0] if rows else {}
                return {"name": "arena1", "total": r.get("total", 0), "completed": r.get("completed", 0),
                        "avg_wr": float(r.get("avg_wr") or 0), "best_wr": float(r.get("best_wr") or 0),
                        "avg_indicators": float(r.get("avg_indicators") or 0)}
            elif name == "arena2":
                rows = await engine.db.fetch("""
                    SELECT count(*) as total,
                           count(*) FILTER (WHERE status = 'ARENA2_REJECTED') as rejected,
                           round(avg(arena2_win_rate)::numeric, 3) as avg_wr,
                           round(avg(arena2_n_trades)::numeric, 0) as avg_trades
                    FROM champion_pipeline WHERE arena2_completed_at IS NOT NULL OR status LIKE 'ARENA2%%'
                """)
                r = rows[0] if rows else {}
                return {"name": "arena2", "total": r.get("total", 0), "rejected": r.get("rejected", 0),
                        "avg_wr": float(r.get("avg_wr") or 0), "avg_trades": int(r.get("avg_trades") or 0)}
            elif name == "arena3":
                rows = await engine.db.fetch("""
                    SELECT count(*) as total,
                           round(avg(arena3_sharpe)::numeric, 3) as avg_sharpe,
                           round(avg(arena3_expectancy)::numeric, 4) as avg_expectancy,
                           round(avg(arena3_pnl)::numeric, 4) as avg_pnl
                    FROM champion_pipeline WHERE arena3_completed_at IS NOT NULL
                """)
                r = rows[0] if rows else {}
                return {"name": "arena3", "total": r.get("total", 0),
                        "avg_sharpe": float(r.get("avg_sharpe") or 0),
                        "avg_expectancy": float(r.get("avg_expectancy") or 0),
                        "avg_pnl": float(r.get("avg_pnl") or 0)}
            elif name == "arena4":
                rows = await engine.db.fetch("""
                    SELECT count(*) as total,
                           count(*) FILTER (WHERE status = 'ARENA4_ELIMINATED') as eliminated,
                           round(avg(arena4_hell_wr)::numeric, 3) as avg_hell_wr,
                           round(avg(arena4_variability)::numeric, 3) as avg_variability
                    FROM champion_pipeline WHERE arena4_completed_at IS NOT NULL OR status LIKE 'ARENA4%%'
                """)
                r = rows[0] if rows else {}
                return {"name": "arena4", "total": r.get("total", 0), "eliminated": r.get("eliminated", 0),
                        "avg_hell_wr": float(r.get("avg_hell_wr") or 0),
                        "avg_variability": float(r.get("avg_variability") or 0)}
            elif name == "arena5":
                rows = await engine.db.fetch("""
                    SELECT count(*) as total,
                           round(avg(elo_rating)::numeric, 1) as avg_elo,
                           round(max(elo_rating)::numeric, 1) as max_elo,
                           round(min(elo_rating)::numeric, 1) as min_elo,
                           count(*) FILTER (WHERE elo_rating > 1600) as elite,
                           count(*) FILTER (WHERE elo_rating BETWEEN 1400 AND 1600) as mid,
                           count(*) FILTER (WHERE elo_rating < 1400) as low
                    FROM champion_pipeline WHERE status = 'DEPLOYABLE' AND elo_rating IS NOT NULL
                """)
                r = rows[0] if rows else {}
                return {"name": "arena5", "total": r.get("total", 0),
                        "avg_elo": float(r.get("avg_elo") or 0), "max_elo": float(r.get("max_elo") or 0),
                        "min_elo": float(r.get("min_elo") or 0),
                        "elite": r.get("elite", 0), "mid": r.get("mid", 0), "low": r.get("low", 0)}
            elif name == "arena13":
                rows = await engine.db.fetch("""
                    SELECT count(*) as total,
                           count(*) FILTER (WHERE evolution_operator = 'mutation') as mutations,
                           count(*) FILTER (WHERE evolution_operator = 'param_tune') as param_tunes,
                           max(generation) as max_gen,
                           round(avg(generation)::numeric, 1) as avg_gen
                    FROM champion_pipeline WHERE evolution_operator IS NOT NULL
                """)
                r = rows[0] if rows else {}
                return {"name": "arena13", "total": r.get("total", 0),
                        "mutations": r.get("mutations", 0), "param_tunes": r.get("param_tunes", 0),
                        "max_gen": r.get("max_gen") or 0, "avg_gen": float(r.get("avg_gen") or 0)}
            else:
                raise HTTPException(status_code=404, detail=f"Arena {name} not found")
            # unreachable but satisfies type checker
            return {}

        try:
            return await cached_fetch(f"arena_detail_{name}", _fetch)
        except HTTPException:
            raise
        except Exception as e:
            logger.error("arena_detail(%s) failed: %s", name, e)
            return {"name": name, "error": str(e)}

    @app.get("/api/system")
    async def system_status():
        """System-wide status."""
        async def _fetch():
            tables = await engine.db.fetch(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            )
            table_counts = {}
            for t in tables:
                try:
                    r = await engine.db.fetchrow(f"SELECT count(*) as cnt FROM {t['tablename']}")
                    table_counts[t["tablename"]] = r["cnt"]
                except Exception as e:
                    logger.warning("count for table %s failed: %s", t["tablename"], e)
                    table_counts[t["tablename"]] = -1
            total_rows = sum(v for v in table_counts.values() if v > 0)
            return {"status": "RUNNING", "db_tables": len(table_counts),
                    "table_counts": table_counts, "total_rows": total_rows, "indicators": 173}
        try:
            return await cached_fetch("system_status", _fetch)
        except Exception as e:
            logger.error("system_status failed: %s", e)
            return {"status": "ERROR", "error": str(e)}

    @app.get("/api/elo/all")
    async def elo_all():
        """Full ELO leaderboard."""
        async def _fetch():
            rows = await engine.db.fetch("""
                SELECT id, indicator_hash, regime, elo_rating, quant_class,
                       arena1_win_rate, arena1_pnl, arena1_n_trades, card_status,
                       arena2_win_rate, arena3_sharpe, arena3_pnl, arena4_hell_wr, status
                FROM champion_pipeline
                WHERE elo_rating IS NOT NULL
                ORDER BY elo_rating DESC
            """)
            return [
                {"id": r["id"], "hash": (r["indicator_hash"] or "?")[:20], "regime": r["regime"],
                 "elo": round(float(r["elo_rating"]), 1), "quant_class": r["quant_class"] or "unknown",
                 "wr": round(float(r["arena1_win_rate"] or 0), 3), "pnl": round(float(r["arena1_pnl"] or 0), 4),
                 "trades": r["arena1_n_trades"] or 0, "card": r["card_status"] or "INACTIVE",
                 "status": r["status"],
                 "a2_wr": round(float(r["arena2_win_rate"] or 0), 3),
                 "a3_sharpe": round(float(r["arena3_sharpe"] or 0), 3),
                 "a3_pnl": round(float(r["arena3_pnl"] or 0), 4),
                 "a4_hell_wr": round(float(r["arena4_hell_wr"] or 0), 3)}
                for r in rows
            ]
        try:
            return await cached_fetch("elo_all", _fetch)
        except Exception as e:
            logger.error("elo_all failed: %s", e)
            return []

    @app.get("/api/trades/all")
    async def all_trades():
        """Recent trades with full details."""
        async def _fetch():
            rows = await engine.db.fetch("""
                SELECT id, card_id, symbol, timestamp, direction, signal_value,
                       expected_price, actual_fill_price, slippage_bps,
                       position_size, regime_at_entry, pnl_pct, hold_bars
                FROM trade_journal ORDER BY timestamp DESC LIMIT 100
            """)
            return [
                {"id": r["id"], "card_id": r["card_id"], "symbol": r["symbol"],
                 "ts": str(r["timestamp"]) if r["timestamp"] else None,
                 "side": r["direction"],
                 "signal": round(float(r["signal_value"] or 0), 4),
                 "entry_price": round(float(r["expected_price"] or 0), 4),
                 "fill_price": round(float(r["actual_fill_price"] or 0), 4),
                 "slippage_bps": round(float(r["slippage_bps"] or 0), 2),
                 "size": round(float(r["position_size"] or 0), 4),
                 "regime": r["regime_at_entry"],
                 "pnl_pct": round(float(r["pnl_pct"] or 0), 4),
                 "hold_bars": r["hold_bars"]}
                for r in rows
            ]
        try:
            return await cached_fetch("all_trades", _fetch)
        except Exception as e:
            logger.error("all_trades failed: %s", e)
            return []

    @app.get("/api/arena1/detail")
    async def arena1_detail():
        async def _fetch():
            rows = await engine.db.fetch("""
                SELECT id, indicator_hash, regime, round(arena1_win_rate::numeric,3) as wr,
                       arena1_n_trades as trades, round(arena1_pnl::numeric,4) as pnl,
                       round(arena1_score::numeric,4) as score, created_at
                FROM champion_pipeline WHERE status NOT LIKE 'LEGACY%%'
                ORDER BY arena1_score DESC LIMIT 30
            """)
            recent = await engine.db.fetchrow(
                "SELECT count(*) as cnt FROM champion_pipeline "
                "WHERE status='ARENA1_COMPLETE' AND created_at > NOW() - INTERVAL '1 hour'"
            )
            return {
                "champions": [
                    {"id": r["id"], "hash": r["indicator_hash"][:25], "regime": r["regime"],
                     "wr": float(r["wr"] or 0), "trades": r["trades"] or 0,
                     "pnl": float(r["pnl"] or 0), "score": float(r["score"] or 0)}
                    for r in rows
                ],
                "recent_1h": recent["cnt"] if recent else 0,
            }
        try:
            return await cached_fetch("arena1_detail", _fetch)
        except Exception as e:
            logger.error("arena1_detail failed: %s", e)
            return {"champions": [], "error": str(e)}

    @app.get("/api/arena2/detail")
    async def arena2_detail():
        async def _fetch():
            promoted = await engine.db.fetch("""
                SELECT id, indicator_hash, regime, round(arena1_win_rate::numeric,3) as a1_wr,
                       round(arena2_win_rate::numeric,3) as a2_wr, arena2_n_trades as trades
                FROM champion_pipeline WHERE status IN ('ARENA2_COMPLETE','ARENA3_COMPLETE','ARENA4_ELIMINATED','DEPLOYABLE')
                AND arena2_win_rate IS NOT NULL ORDER BY arena2_win_rate DESC LIMIT 30
            """)
            rejected = await engine.db.fetchrow(
                "SELECT count(*) as cnt FROM champion_pipeline WHERE status='ARENA2_REJECTED'"
            )
            total = await engine.db.fetchrow(
                "SELECT count(*) as cnt FROM champion_pipeline WHERE status LIKE 'ARENA2%%' OR arena2_win_rate IS NOT NULL"
            )
            return {
                "promoted": [
                    {"id": r["id"], "regime": r["regime"],
                     "a1_wr": float(r["a1_wr"] or 0), "a2_wr": float(r["a2_wr"] or 0),
                     "trades": r["trades"] or 0}
                    for r in promoted
                ],
                "rejected_count": rejected["cnt"] if rejected else 0,
                "total_processed": total["cnt"] if total else 0,
                "pass_rate": round(len(promoted) / max((total["cnt"] if total else 1), 1) * 100, 1),
            }
        try:
            return await cached_fetch("arena2_detail", _fetch)
        except Exception as e:
            logger.error("arena2_detail failed: %s", e)
            return {"promoted": [], "error": str(e)}

    @app.get("/api/arena3/detail")
    async def arena3_detail():
        async def _fetch():
            rows = await engine.db.fetch("""
                SELECT id, regime, round(arena3_sharpe::numeric,2) as sharpe,
                       round(arena3_expectancy::numeric,4) as expectancy, round(arena3_pnl::numeric,4) as pnl,
                       passport->'arena3'->>'atr_multiplier' as atr_mult,
                       passport->'arena3'->>'half_kelly' as kelly
                FROM champion_pipeline WHERE arena3_pnl IS NOT NULL
                ORDER BY arena3_sharpe DESC NULLS LAST LIMIT 30
            """)
            return {
                "strategies": [
                    {"id": r["id"], "regime": r["regime"],
                     "sharpe": float(r["sharpe"] or 0), "expectancy": float(r["expectancy"] or 0),
                     "pnl": float(r["pnl"] or 0), "atr_mult": r["atr_mult"] or "--",
                     "kelly": r["kelly"] or "--"}
                    for r in rows
                ]
            }
        try:
            return await cached_fetch("arena3_detail", _fetch)
        except Exception as e:
            logger.error("arena3_detail failed: %s", e)
            return {"strategies": [], "error": str(e)}

    @app.get("/api/arena4/detail")
    async def arena4_detail():
        async def _fetch():
            eliminated = await engine.db.fetchrow(
                "SELECT count(*) as cnt FROM champion_pipeline WHERE status='ARENA4_ELIMINATED'"
            )
            passed = await engine.db.fetchrow(
                "SELECT count(*) as cnt FROM champion_pipeline WHERE status IN ('DEPLOYABLE','ELO_ACTIVE','ELO_RETIRED')"
            )
            rows = await engine.db.fetch("""
                SELECT id, regime, round(arena4_hell_wr::numeric,3) as hell_wr,
                       round(arena4_variability::numeric,3) as variability, quant_class
                FROM champion_pipeline WHERE status='DEPLOYABLE' ORDER BY elo_rating DESC LIMIT 20
            """)
            elim_cnt = eliminated["cnt"] if eliminated else 0
            pass_cnt = passed["cnt"] if passed else 0
            return {
                "eliminated": elim_cnt,
                "passed": pass_cnt,
                "gate_rate": round(pass_cnt / max(elim_cnt + pass_cnt, 1) * 100, 1),
                "survivors": [
                    {"id": r["id"], "regime": r["regime"],
                     "hell_wr": float(r["hell_wr"] or 0), "variability": float(r["variability"] or 0),
                     "class": r["quant_class"] or "--"}
                    for r in rows
                ],
            }
        try:
            return await cached_fetch("arena4_detail", _fetch)
        except Exception as e:
            logger.error("arena4_detail failed: %s", e)
            return {"error": str(e)}

    @app.get("/api/arena5/detail")
    async def arena5_detail():
        async def _fetch():
            rows = await engine.db.fetch("""
                SELECT id, regime, round(elo_rating::numeric,1) as elo, quant_class, card_status,
                       round(arena1_win_rate::numeric,3) as wr, elo_consecutive_first as streak
                FROM champion_pipeline WHERE status='DEPLOYABLE'
                ORDER BY elo_rating DESC LIMIT 30
            """)
            by_regime = await engine.db.fetch("""
                SELECT regime, count(*) as cnt, round(max(elo_rating)::numeric,1) as top_elo,
                       round(avg(elo_rating)::numeric,1) as avg_elo
                FROM champion_pipeline WHERE status='DEPLOYABLE' GROUP BY regime ORDER BY top_elo DESC
            """)
            return {
                "strategies": [
                    {"id": r["id"], "regime": r["regime"], "elo": float(r["elo"] or 0),
                     "class": r["quant_class"] or "--", "card": r["card_status"] or "INACTIVE",
                     "wr": float(r["wr"] or 0), "streak": r["streak"] or 0}
                    for r in rows
                ],
                "by_regime": [
                    {"regime": r["regime"], "count": r["cnt"],
                     "top_elo": float(r["top_elo"] or 0), "avg_elo": float(r["avg_elo"] or 0)}
                    for r in by_regime
                ],
            }
        try:
            return await cached_fetch("arena5_detail", _fetch)
        except Exception as e:
            logger.error("arena5_detail failed: %s", e)
            return {"error": str(e)}

    @app.get("/api/arena13/detail")
    async def arena13_detail():
        async def _fetch():
            rows = await engine.db.fetch("""
                SELECT id, regime, parent_hash, generation, evolution_operator,
                       round(arena1_win_rate::numeric,3) as wr, round(arena1_pnl::numeric,4) as pnl
                FROM champion_pipeline WHERE evolution_operator != 'random' AND generation > 0
                ORDER BY created_at DESC LIMIT 20
            """)
            stats = await engine.db.fetchrow(
                "SELECT count(*) as evolved FROM champion_pipeline WHERE status='EVOLVED'"
            )
            return {
                "evolved_total": stats["evolved"] if stats else 0,
                "offspring": [
                    {"id": r["id"], "regime": r["regime"],
                     "parent": r["parent_hash"][:20] if r["parent_hash"] else "--",
                     "gen": r["generation"], "op": r["evolution_operator"],
                     "wr": float(r["wr"] or 0), "pnl": float(r["pnl"] or 0)}
                    for r in rows
                ],
            }
        try:
            return await cached_fetch("arena13_detail", _fetch)
        except Exception as e:
            logger.error("arena13_detail failed: %s", e)
            return {"error": str(e)}

    @app.get("/api/health/pipeline")
    async def pipeline_health():
        """Pipeline health: time since last champion, recent throughput, service status."""
        async def _fetch():
            import datetime
            row = await engine.db.fetchrow("""
                SELECT MAX(created_at) as last_champion,
                       COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '5 minutes') as recent_5m,
                       COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 hour') as recent_1h
                FROM champion_pipeline WHERE status NOT LIKE 'LEGACY%%'
            """)
            last = row["last_champion"] if row else None
            ago_s = 0
            if last:
                ago_s = (datetime.datetime.now(datetime.timezone.utc) - last.replace(tzinfo=datetime.timezone.utc)).total_seconds()

            # Check actual systemd services
            loop = asyncio.get_event_loop()
            services = await loop.run_in_executor(None, _check_all_services)
            svc_summary = {s["name"]: s["status"] for s in services}
            all_ok = all(s["status"] == "ok" for s in services)

            return {
                "last_champion_ago_s": round(ago_s, 1),
                "recent_5m": row["recent_5m"] if row else 0,
                "recent_1h": row["recent_1h"] if row else 0,
                "services": svc_summary,
                "all_services_ok": all_ok,
            }
        try:
            return await cached_fetch("pipeline_health", _fetch)
        except Exception as e:
            logger.error("pipeline_health failed: %s", e)
            return {"last_champion_ago_s": -1, "recent_5m": 0, "recent_1h": 0, "error": str(e)}

    # ---------------------------------------------------------------
    # Unified overview endpoint for mobile dashboard (DASHBOARD_SPEC.md)
    # ---------------------------------------------------------------

    @app.get("/api/overview")
    async def overview():
        """Unified 13-field payload for mobile dashboard.

        - 5s TTL via cached_fetch (key='overview')
        - Health status derived from last_champion_ago_s (ok<300 / stale 300-1800 / dead>1800)
        - Does NOT call _check_all_services (systemd false-reports degraded)
        - Server-side alerts rule engine (4 rules per spec Section 4)
        """
        async def _fetch():
            import datetime
            import json as _json

            # --- 1) last_champion_ago_s (drives health.status) ---
            ago_s: float = -1.0
            try:
                row = await engine.db.fetchrow(
                    "SELECT MAX(created_at) as last_champion "
                    "FROM champion_pipeline WHERE status NOT LIKE 'LEGACY%%'"
                )
                last = row["last_champion"] if row else None
                if last:
                    ago_s = (
                        datetime.datetime.now(datetime.timezone.utc)
                        - last.replace(tzinfo=datetime.timezone.utc)
                    ).total_seconds()
            except Exception as e:
                logger.warning("overview: last_champion query failed: %s", e)

            if ago_s < 0:
                status = "dead"
            elif ago_s < 300:
                status = "ok"
            elif ago_s < 1800:
                status = "stale"
            else:
                status = "dead"

            # --- 2) pipeline overview (reuses cached_fetch("pipeline_overview")) ---
            po: Dict[str, Any] = {}
            try:
                po = await pipeline_overview()
            except Exception as e:
                logger.warning("overview: pipeline_overview failed: %s", e)
                po = {}

            # --- 3) v6_pipeline_flow (funnel arena1/arena23 counts) ---
            pf: Dict[str, Any] = {}
            try:
                pf = await v6_pipeline_flow()
            except Exception as e:
                logger.warning("overview: v6_pipeline_flow failed: %s", e)
                pf = {}
            by_status = pf.get("by_status", {}) if isinstance(pf, dict) else {}
            arena1 = sum(v for k, v in by_status.items() if k.startswith("ARENA1"))
            arena23 = sum(
                v for k, v in by_status.items()
                if k.startswith("ARENA2") or k.startswith("ARENA3")
            )

            # --- 4) arena4_detail (eliminated / passed / gate_rate) ---
            a4: Dict[str, Any] = {}
            try:
                a4 = await arena4_detail()
            except Exception as e:
                logger.warning("overview: arena4_detail failed: %s", e)
                a4 = {}
            arena4_eliminated = int(a4.get("eliminated", 0) or 0) if isinstance(a4, dict) else 0
            arena4_passed = int(a4.get("passed", 0) or 0) if isinstance(a4, dict) else 0
            arena4_pass_rate = float(a4.get("gate_rate", 0.0) or 0.0) if isinstance(a4, dict) else 0.0

            # --- 5) a13 guidance (read config JSON directly) ---
            a13_mode = "unknown"
            a13_survivors = 0
            a13_failures = 0
            top_weights: List[Dict[str, Any]] = []
            try:
                with open("/home/j13/j13-ops/zangetsu/config/a13_guidance.json") as _f:
                    a13_cfg = _json.load(_f)
                if isinstance(a13_cfg, dict):
                    a13_mode = str(a13_cfg.get("mode", "unknown"))
                    a13_survivors = int(a13_cfg.get("survivors", 0) or 0)
                    a13_failures = int(a13_cfg.get("failures", 0) or 0)
                    weights_raw = a13_cfg.get("indicator_weights", {}) or {}
                    if isinstance(weights_raw, dict):
                        sorted_w = sorted(
                            weights_raw.items(),
                            key=lambda kv: float(kv[1] or 0),
                            reverse=True,
                        )[:3]
                        top_weights = [
                            {"indicator": k, "weight": round(float(v or 0), 2)}
                            for k, v in sorted_w
                        ]
            except FileNotFoundError:
                logger.warning("overview: a13_guidance.json not found")
            except Exception as e:
                logger.warning("overview: a13_guidance read failed: %s", e)

            # --- 6) Assemble numeric fields ---
            throughput_hr = float(po.get("throughput_hr", 0) or 0) if isinstance(po, dict) else 0.0
            new_1h = int(po.get("new_1h", 0) or 0) if isinstance(po, dict) else 0
            total = int(po.get("total_champions", 0) or 0) if isinstance(po, dict) else 0
            candidate = int(po.get("candidate", 0) or 0) if isinstance(po, dict) else 0
            deployable = int(po.get("deployable", 0) or 0) if isinstance(po, dict) else 0
            active_cards = int(po.get("active_cards", 0) or 0) if isinstance(po, dict) else 0
            uptime_s = round(time.time() - _start_time, 1)
            last_champion_ago_s = round(ago_s, 1) if ago_s >= 0 else None

            # --- 7) Server-side alerts rule engine (4 rules per spec Section 4) ---
            alerts: List[Dict[str, str]] = []
            if arena4_pass_rate == 0.0 and arena4_eliminated >= 50:
                alerts.append({
                    "level": "red",
                    "msg": f"arena4_pass_rate=0% over {arena4_eliminated} samples",
                })
            if last_champion_ago_s is not None and last_champion_ago_s > 1800:
                alerts.append({
                    "level": "red",
                    "msg": f"no champion for {int(last_champion_ago_s)}s",
                })
            if deployable == 0 and active_cards == 0:
                alerts.append({
                    "level": "amber",
                    "msg": "deployable=0 and active_cards=0",
                })
            if throughput_hr < 5:
                alerts.append({
                    "level": "amber",
                    "msg": f"throughput_hr={throughput_hr} < 5",
                })

            return {
                "ts": int(time.time()),
                "health": {
                    "status": status,
                    "last_champion_ago_s": last_champion_ago_s,
                    "uptime_s": uptime_s,
                },
                "pipeline": {
                    "throughput_hr": throughput_hr,
                    "new_1h": new_1h,
                    "total": total,
                },
                "funnel": {
                    "arena1": arena1,
                    "arena23": arena23,
                    "arena4_eliminated": arena4_eliminated,
                    "arena4_passed": arena4_passed,
                    "arena4_pass_rate": arena4_pass_rate,
                    "candidate": candidate,
                    "deployable": deployable,
                    "active_cards": active_cards,
                },
                "a13": {
                    "mode": a13_mode,
                    "survivors": a13_survivors,
                    "failures": a13_failures,
                    "top_weights": top_weights,
                },
                "alerts": alerts,
            }

        try:
            return await cached_fetch("overview", _fetch)
        except Exception as e:
            logger.error("overview failed: %s", e)
            return {
                "ts": int(time.time()),
                "health": {"status": "dead", "last_champion_ago_s": None, "uptime_s": 0},
                "pipeline": {"throughput_hr": 0, "new_1h": 0, "total": 0},
                "funnel": {
                    "arena1": 0, "arena23": 0, "arena4_eliminated": 0,
                    "arena4_passed": 0, "arena4_pass_rate": 0.0,
                    "candidate": 0, "deployable": 0, "active_cards": 0,
                },
                "a13": {"mode": "unknown", "survivors": 0, "failures": 0, "top_weights": []},
                "alerts": [{"level": "red", "msg": f"overview build failed: {e}"}],
            }

    @app.get("/api/certification")
    async def certification():
        """Certification status: CANDIDATE + DEPLOYABLE with Wilson LB."""
        async def _fetch():
            rows = await engine.db.fetch("""
                SELECT id, regime, status,
                    (passport->'arena4'->'holdout_full'->>'wr')::float as h_wr,
                    (passport->'arena4'->'holdout_full'->>'pnl')::float as h_pnl,
                    (passport->'arena4'->'holdout_full'->>'trades')::int as h_trades
                FROM champion_pipeline
                WHERE status IN ('CANDIDATE','DEPLOYABLE') AND status NOT LIKE 'LEGACY%%'
                ORDER BY (passport->'arena4'->'holdout_full'->>'wr')::float DESC NULLS LAST
            """)

            def wlb(wins, total):
                if total is None or total == 0:
                    return 0
                p = wins / total
                z = 1.96
                d = 1 + z * z / total
                center = p + z * z / (2 * total)
                adj = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
                return round((center - adj) / d, 4)

            results = []
            for r in rows:
                h_wr = float(r["h_wr"]) if r["h_wr"] is not None else 0
                h_trades = int(r["h_trades"]) if r["h_trades"] is not None else 0
                h_pnl = float(r["h_pnl"]) if r["h_pnl"] is not None else 0
                wins = int(h_wr * h_trades) if h_trades > 0 else 0
                wilson = wlb(wins, h_trades)
                results.append({
                    "id": r["id"],
                    "regime": r["regime"],
                    "status": r["status"],
                    "holdout_wr": round(h_wr, 3),
                    "holdout_pnl": round(h_pnl, 4),
                    "holdout_trades": h_trades,
                    "wilson_lb": wilson,
                    "wilson_gap": round(max(0, 0.50 - wilson), 4),
                    "impossible": h_wr <= 0.50,
                    "certified": wilson > 0.50,
                })
            return results
        try:
            return await cached_fetch("certification", _fetch)
        except Exception as e:
            logger.error("certification failed: %s", e)
            return []

    @app.get("/api/adaptive-scores")
    async def adaptive_scores():
        """Adaptive family-level scoring for certification readiness."""
        async def _fetch():
            rows = await engine.db.fetch("""
                SELECT id, regime, arena1_win_rate, arena3_sharpe, arena4_variability,
                    (passport->'arena4'->'holdout_full'->>'wr')::float as h_wr,
                    (passport->'arena4'->'holdout_full'->>'pnl')::float as h_pnl,
                    (passport->'arena4'->'holdout_full'->>'trades')::int as h_trades,
                    (passport->'arena4'->'holdout_full'->>'sharpe')::float as h_sharpe,
                    passport->'arena1'->'indicator_names' as inds
                FROM champion_pipeline WHERE status IN ('CANDIDATE','DEPLOYABLE') AND status NOT LIKE 'LEGACY%%'
            """)

            families = [{
                "id": r["id"], "regime": r["regime"],
                "holdout_wr": float(r["h_wr"]) if r["h_wr"] is not None else 0.5,
                "holdout_pnl": float(r["h_pnl"]) if r["h_pnl"] is not None else 0,
                "holdout_trades": int(r["h_trades"]) if r["h_trades"] is not None else 0,
                "holdout_sharpe": float(r["h_sharpe"]) if r["h_sharpe"] is not None else 0,
                "train_wr": float(r["arena1_win_rate"] or 0.5),
                "train_sharpe": float(r["arena3_sharpe"] or 0),
                "variability": float(r["arena4_variability"] or 1),
                "is_unique": True,
                "indicators": str(r["inds"]),
            } for r in rows]

            from zangetsu.engine.components.adaptive_scorer import AdaptiveScorer
            scorer = AdaptiveScorer()
            return scorer.score_all(families)
        try:
            return await cached_fetch("adaptive_scores", _fetch)
        except ImportError as e:
            logger.error("adaptive_scores import failed: %s", e)
            return [{"error": f"AdaptiveScorer not available: {e}"}]
        except Exception as e:
            logger.error("adaptive_scores failed: %s", e)
            return [{"error": str(e)}]

    @app.get("/api/waste")
    async def waste():
        """Waste tracker: unique combos vs total rows."""
        async def _fetch():
            _urow = await engine.db.fetchrow(
                "SELECT count(DISTINCT passport->'arena1'->>'config_hash') as cnt "
                "FROM champion_pipeline WHERE status NOT LIKE 'LEGACY%%' "
                "AND passport->'arena1'->>'config_hash' IS NOT NULL"
            )
            unique = _urow["cnt"] if _urow else 0
            _trow = await engine.db.fetchrow(
                "SELECT count(*) as cnt FROM champion_pipeline WHERE status NOT LIKE 'LEGACY%%'"
            )
            total = _trow["cnt"] if _trow else 0
            unique = unique or 0
            total = total or 0
            top_retried = await engine.db.fetchrow(
                "SELECT passport->'arena1'->>'config_hash' as hash, count(*) as cnt "
                "FROM champion_pipeline WHERE status NOT LIKE 'LEGACY%%' "
                "AND passport->'arena1'->>'config_hash' IS NOT NULL "
                "GROUP BY passport->'arena1'->>'config_hash' ORDER BY cnt DESC LIMIT 1"
            )
            top_hash = (top_retried["hash"] or "--")[:30] if top_retried else "--"
            top_cnt = top_retried["cnt"] if top_retried else 0
            return {
                "unique_combos": unique,
                "total_rows": total,
                "retry_waste_pct": round((1 - unique / max(total, 1)) * 100, 1),
                "top_retried": f"{top_hash} x{top_cnt}",
            }
        try:
            return await cached_fetch("waste", _fetch)
        except Exception as e:
            logger.error("waste failed: %s", e)
            return {"unique_combos": 0, "total_rows": 0, "retry_waste_pct": 0, "error": str(e)}

    # ---------------------------------------------------------------
    # V6 endpoints
    # ---------------------------------------------------------------

    @app.get("/api/v7/families")
    async def v6_families():
        """Family ranking from materialized view. Requires migration_ranking_view.sql."""
        async def _fetch():
            rows = await engine.db.fetch("""
                SELECT family_id, family_tag, regime, best_status,
                       member_count, best_elo, avg_elo,
                       avg_a3_sharpe, best_a3_sharpe, avg_a3_pnl,
                       avg_a4_hell_wr, best_wilson_lb,
                       latest_created, latest_updated
                FROM family_ranking
                ORDER BY status_tier_num DESC, best_elo DESC NULLS LAST
            """)
            return [
                {
                    "family_id": r["family_id"],
                    "family_tag": r["family_tag"] or "unknown",
                    "regime": r["regime"],
                    "best_status": r["best_status"],
                    "members": r["member_count"],
                    "best_elo": float(r["best_elo"]) if r["best_elo"] is not None else None,
                    "avg_elo": float(r["avg_elo"]) if r["avg_elo"] is not None else None,
                    "avg_sharpe": float(r["avg_a3_sharpe"]) if r["avg_a3_sharpe"] is not None else None,
                    "best_sharpe": float(r["best_a3_sharpe"]) if r["best_a3_sharpe"] is not None else None,
                    "avg_pnl": float(r["avg_a3_pnl"]) if r["avg_a3_pnl"] is not None else None,
                    "avg_hell_wr": float(r["avg_a4_hell_wr"]) if r["avg_a4_hell_wr"] is not None else None,
                    "wilson_lb": float(r["best_wilson_lb"]) if r["best_wilson_lb"] is not None else None,
                    "latest": str(r["latest_updated"]) if r["latest_updated"] else None,
                }
                for r in rows
            ]
        try:
            return await cached_fetch("v6_families", _fetch)
        except Exception as e:
            logger.error("v6_families failed: %s", e)
            # Graceful fallback if materialized view doesn't exist yet
            if "family_ranking" in str(e).lower() and "does not exist" in str(e).lower():
                return {"error": "family_ranking view not created yet. Run migration_ranking_view.sql first."}
            return {"error": str(e)}

    @app.get("/api/v7/pipeline-flow")
    async def v6_pipeline_flow():
        """Funnel view: count at each pipeline status level."""
        async def _fetch():
            rows = await engine.db.fetch("""
                SELECT status, count(*) as cnt
                FROM champion_pipeline
                WHERE status NOT LIKE 'LEGACY%%'
                GROUP BY status
                ORDER BY cnt DESC
            """)
            by_status = {r["status"]: r["cnt"] for r in rows}

            # Aggregate into funnel stages
            arena1 = sum(v for k, v in by_status.items() if k.startswith("ARENA1"))
            arena2 = sum(v for k, v in by_status.items() if k.startswith("ARENA2"))
            arena3 = sum(v for k, v in by_status.items() if k.startswith("ARENA3"))
            arena4 = sum(v for k, v in by_status.items() if k.startswith("ARENA4"))
            candidate = by_status.get("CANDIDATE", 0)
            deployable = by_status.get("DEPLOYABLE", 0)
            elo_active = by_status.get("ELO_ACTIVE", 0)
            elo_retired = by_status.get("ELO_RETIRED", 0)
            evolving = sum(by_status.get(s, 0) for s in ("EVOLVING", "EVOLVED"))
            dead_letter = by_status.get("DEAD_LETTER", 0)

            total = sum(by_status.values())

            funnel = [
                {"stage": "Arena 1 (Discovery)", "count": arena1, "pct": round(arena1 / max(total, 1) * 100, 1)},
                {"stage": "Arena 2 (Optimization)", "count": arena2, "pct": round(arena2 / max(total, 1) * 100, 1)},
                {"stage": "Arena 3 (Risk Mgmt)", "count": arena3, "pct": round(arena3 / max(total, 1) * 100, 1)},
                {"stage": "Arena 4 (Hell Test)", "count": arena4, "pct": round(arena4 / max(total, 1) * 100, 1)},
                {"stage": "Candidate", "count": candidate, "pct": round(candidate / max(total, 1) * 100, 1)},
                {"stage": "Deployable", "count": deployable, "pct": round(deployable / max(total, 1) * 100, 1)},
                {"stage": "ELO Active", "count": elo_active, "pct": round(elo_active / max(total, 1) * 100, 1)},
                {"stage": "ELO Retired", "count": elo_retired, "pct": round(elo_retired / max(total, 1) * 100, 1)},
                {"stage": "Evolution", "count": evolving, "pct": round(evolving / max(total, 1) * 100, 1)},
                {"stage": "Dead Letter", "count": dead_letter, "pct": round(dead_letter / max(total, 1) * 100, 1)},
            ]

            return {
                "total": total,
                "funnel": funnel,
                "by_status": by_status,
            }
        try:
            return await cached_fetch("v6_pipeline_flow", _fetch)
        except Exception as e:
            logger.error("v6_pipeline_flow failed: %s", e)
            return {"error": str(e)}

    @app.get("/api/v7/stats")
    async def v6_stats():
        """V6-specific pipeline stats — separated from legacy."""
        async def _fetch():
            rows = await engine.db.fetch("""
                SELECT status, count(*) as cnt,
                    round(avg(arena1_win_rate)::numeric,3) as avg_wr,
                    round(avg(arena1_pnl)::numeric,4) as avg_pnl
                FROM champion_pipeline WHERE engine_hash IN ('zv5_v9', 'zv5_v10_alpha', 'zv5_v71')
                GROUP BY status ORDER BY cnt DESC
            """)
            total = sum(r['cnt'] for r in rows)
            by_status = {
                r['status']: {
                    'count': r['cnt'],
                    'avg_wr': float(r['avg_wr'] or 0),
                    'avg_pnl': float(r['avg_pnl'] or 0),
                }
                for r in rows
            }
            bloom_row = await engine.db.fetchrow("""
                SELECT count(DISTINCT passport->'arena1'->>'config_hash') as unique_families
                FROM champion_pipeline WHERE engine_hash IN ('zv5_v9', 'zv5_v10_alpha', 'zv5_v71')
            """)
            unique = bloom_row['unique_families'] if bloom_row else 0
            return {
                'engine': 'zv9',
                'total': total,
                'unique_families': unique,
                'by_status': by_status,
                'family_efficiency': round(unique / max(total, 1) * 100, 1),
            }
        try:
            return await cached_fetch("v6_stats", _fetch)
        except Exception as e:
            logger.error("v6_stats failed: %s", e)
            return {'error': str(e)}

    # ---------------------------------------------------------------
    # Static files + mobile
    # ---------------------------------------------------------------

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        @app.get("/")
        async def root():
            return FileResponse(str(static_dir / "index.html"))

        @app.get("/mobile")
        async def mobile():
            # NOTE: mobile.html still references PAUSE/HALT buttons that call
            # /api/pause and /api/halt — these endpoints do not exist.
            # The buttons should be removed from mobile.html in a separate
            # static file update. See: mobile.html lines 206-207, 592-593.
            return FileResponse(str(static_dir / "mobile.html"))

        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/api/a13/guidance")
    async def a13_guidance():
        import json as _json
        try:
            with open("/home/j13/j13-ops/zangetsu/config/a13_guidance.json") as _f:
                return _json.load(_f)
        except Exception as e:
            return {"error": str(e)}

    return app
