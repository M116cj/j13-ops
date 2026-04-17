"""Standalone dashboard launcher — serves dashboard without full engine."""
import sys, os
sys.path.insert(0, os.path.expanduser("~/j13-ops/zangetsu_v5"))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import json
import uvicorn

DB_DSN = f"dbname=zangetsu_v5 user=zangetsu password={os.getenv('ZV5_DB_PASSWORD', '')} host=127.0.0.1 port=5432"

app = FastAPI(title="Zangetsu V5 Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.expanduser("~/j13-ops/zangetsu_v5/dashboard/static")


def get_conn():
    return psycopg2.connect(DB_DSN)


@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/mobile")
async def mobile():
    return FileResponse(os.path.join(STATIC_DIR, "mobile.html"))


@app.get("/api/pipeline")
async def pipeline_status():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT state, entered_at, metadata FROM pipeline_state ORDER BY entered_at DESC LIMIT 1")
    row = cur.fetchone()
    cur.execute("SELECT count(*) FROM champion_pipeline")
    total = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM champion_pipeline WHERE status='DEPLOYABLE'")
    deployable = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM champion_pipeline WHERE is_active_card=true")
    active = cur.fetchone()[0]
    cur.execute("SELECT status, count(*) FROM champion_pipeline GROUP BY status ORDER BY status")
    by_status = dict(cur.fetchall())
    conn.close()
    return {
        "state": row[0] if row else "IDLE",
        "since": str(row[1]) if row else None,
        "total_champions": total,
        "deployable": deployable,
        "active_cards": active,
        "by_status": by_status,
        "throughput_hr": 0,
    }


@app.get("/api/elo")
async def elo_leaderboard():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, regime, status, elo, quant_class,
               passport->'arena1'->>'base_win_rate' as wr,
               is_active_card
        FROM champion_pipeline
        WHERE elo IS NOT NULL
        ORDER BY elo DESC LIMIT 20
    """)
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "regime": r[1], "status": r[2], "elo": r[3],
             "quant_class": r[4], "win_rate": r[5], "is_active_card": r[6]} for r in rows]


@app.get("/api/active-cards")
async def active_cards():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, regime, elo, quant_class,
               passport->'arena1'->>'base_win_rate' as wr,
               status
        FROM champion_pipeline
        WHERE is_active_card = true
        ORDER BY elo DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "regime": r[1], "elo": r[2], "quant_class": r[3],
             "win_rate": r[4], "status": r[5]} for r in rows]


@app.get("/api/arenas")
async def arena_status():
    """Per-arena status with candidates and best scores."""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT arena, count(*), max(created_at)
        FROM pipeline_audit_log
        GROUP BY arena
        ORDER BY arena
    """)
    arena_rows = cur.fetchall()

    cur.execute("SELECT status, count(*) FROM champion_pipeline GROUP BY status")
    status_counts = dict(cur.fetchall())

    cur.execute("""
        SELECT status, max(elo) FROM champion_pipeline
        WHERE elo IS NOT NULL GROUP BY status
    """)
    best_scores = dict(cur.fetchall())

    cur.execute("""
        SELECT arena, count(*) FROM pipeline_audit_log
        WHERE created_at > now() - interval '5 minutes'
        GROUP BY arena
    """)
    recent_activity = dict(cur.fetchall())
    conn.close()

    STATUS_TO_ARENA = {
        "ARENA1_DISCOVERY": "arena1", "ARENA2_THRESHOLD": "arena2",
        "ARENA3_PNL": "arena3", "ARENA4_VALIDATION": "arena4",
        "ARENA5_ELO": "arena5", "DEPLOYABLE": "arena5",
    }

    arena_candidates = {}
    for sk, cnt in status_counts.items():
        an = STATUS_TO_ARENA.get(sk)
        if an:
            arena_candidates[an] = arena_candidates.get(an, 0) + cnt

    arena_best = {}
    for sk, sc in best_scores.items():
        an = STATUS_TO_ARENA.get(sk)
        if an and sc is not None:
            ex = arena_best.get(an)
            if ex is None or float(sc) > ex:
                arena_best[an] = float(sc)

    arenas = []
    for r in arena_rows:
        name = r[0]
        is_running = recent_activity.get(name, 0) > 0
        arenas.append({
            "name": name,
            "status": "running" if is_running else ("complete" if r[1] > 0 else "idle"),
            "events": r[1],
            "last_activity": str(r[2]) if r[2] else None,
            "candidates_processed": arena_candidates.get(name, 0),
            "best_score": arena_best.get(name),
        })

    known = {"arena1", "arena2", "arena3", "arena4", "arena5", "arena13"}
    seen = {a["name"] for a in arenas}
    for name in sorted(known - seen):
        arenas.append({
            "name": name, "status": "idle", "events": 0,
            "last_activity": None,
            "candidates_processed": arena_candidates.get(name, 0),
            "best_score": arena_best.get(name),
        })

    return {
        "arenas": sorted(arenas, key=lambda x: x["name"]),
        "status_counts": status_counts,
    }


@app.get("/api/components")
async def components():
    """Component health check."""
    results = []
    # DB check
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        conn.close()
        results.append({"name": "database", "status": "ok", "details": {}})
    except Exception as e:
        results.append({"name": "database", "status": "error", "details": {"error": str(e)}})

    # GPU check
    try:
        import subprocess
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total,temperature.gpu,utilization.gpu",
             "--format=csv,noheader,nounits"],
            timeout=5
        ).decode().strip()
        parts = out.split(", ")
        results.append({"name": "gpu", "status": "ok", "details": {
            "vram_used_mb": int(parts[0]),
            "vram_total_mb": int(parts[1]),
            "temp_c": int(parts[2]),
            "util_pct": int(parts[3]),
        }})
    except Exception as e:
        results.append({"name": "gpu", "status": "error", "details": {"error": str(e)}})

    # Indicator engine check
    try:
        import zangetsu_indicators as zi
        e = zi.IndicatorEngine(seed=1)
        results.append({"name": "indicator_engine", "status": "ok", "details": {
            "count": e.indicator_count(),
            "hash": e.engine_hash()[:16],
        }})
    except Exception as e:
        results.append({"name": "indicator_engine", "status": "error", "details": {"error": str(e)}})

    return results


@app.get("/api/gpu")
async def gpu_status():
    """GPU detailed status."""
    try:
        import subprocess
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.used,memory.total,temperature.gpu,utilization.gpu,power.draw",
             "--format=csv,noheader,nounits"],
            timeout=5
        ).decode().strip()
        parts = [p.strip() for p in out.split(", ")]
        return {
            "available": True,
            "name": parts[0],
            "vram_used_mb": int(parts[1]),
            "vram_total_mb": int(parts[2]),
            "temp_c": int(parts[3]),
            "util_pct": int(parts[4]),
            "power_w": float(parts[5]),
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


@app.get("/api/trades")
async def recent_trades():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM trade_journal ORDER BY ts DESC LIMIT 20")
    if cur.description:
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    else:
        rows = []
    conn.close()
    return rows


@app.get("/api/system")
async def system_status():
    result = {"status": "READY", "indicators": 0, "engine_hash": "", "db_tables": 0}
    try:
        import zangetsu_indicators as zi
        e = zi.IndicatorEngine(seed=1)
        result["indicators"] = e.indicator_count()
        result["engine_hash"] = e.engine_hash()[:16]
    except Exception:
        pass
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
        result["db_tables"] = cur.fetchone()[0]
        conn.close()
    except Exception:
        pass
    return result


# Compatibility routes (no /api prefix) for dashboard.api consumers
@app.get("/pipeline")
async def pipeline_compat():
    return await pipeline_status()


@app.get("/elo")
async def elo_compat():
    return await elo_leaderboard()


@app.get("/health")
async def health_compat():
    return {"status": "ok"}


# Mount static last to avoid route conflicts
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9901)
