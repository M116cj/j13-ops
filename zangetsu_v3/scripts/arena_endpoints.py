"""
Zangetsu V3.1 — Arena Pipeline Status Endpoints
Separate router module to avoid merge conflicts with dashboard_server.py.

Usage in dashboard_server.py:
    from arena_endpoints import arena_router
    app.include_router(arena_router)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter

# ---------------------------------------------------------------------------
# Config — all paths configurable via env, with sane defaults
# ---------------------------------------------------------------------------

ARENA1_RESULTS_DIR = Path(os.getenv("ZV3_ARENA1_RESULTS_DIR", "arena1_results"))
ARENA1_TOTAL_RUNS = int(os.getenv("ZV3_ARENA1_TOTAL_RUNS", "55"))

FACTOR_POOL_PATH = Path(os.getenv("ZV3_FACTOR_POOL_PATH", "factor_pool.json"))

ARENA3_CHECKPOINT_DIR = Path(os.getenv("ZV3_ARENA3_CHECKPOINT_DIR", "arena3_checkpoints"))

# All five regimes the system operates on
REGIMES = [
    "BULL_TREND",
    "BEAR_TREND",
    "RANGE_BOUND",
    "HIGH_VOL",
    "LOW_VOL",
]

arena_router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _arena1_status() -> dict[str, Any]:
    """Scan arena1_results/ directory for completed .json result files."""
    if not ARENA1_RESULTS_DIR.exists():
        return {
            "status": "not_started",
            "completed_runs": 0,
            "total_runs": ARENA1_TOTAL_RUNS,
            "latest_run": "",
            "latest_time": "",
        }

    result_files = sorted(
        ARENA1_RESULTS_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
    )
    completed = len(result_files)

    latest_run = ""
    latest_time = ""
    if result_files:
        latest = result_files[-1]
        latest_run = latest.stem  # e.g. "BULL_TREND_h1"
        try:
            mtime = latest.stat().st_mtime
            latest_time = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
        except OSError:
            pass

    if completed >= ARENA1_TOTAL_RUNS:
        status = "completed"
    elif completed > 0:
        status = "running"
    else:
        status = "not_started"

    return {
        "status": status,
        "completed_runs": completed,
        "total_runs": ARENA1_TOTAL_RUNS,
        "latest_run": latest_run,
        "latest_time": latest_time,
    }


def _arena2_status() -> dict[str, Any]:
    """Check factor_pool.json existence and count factors."""
    if not FACTOR_POOL_PATH.exists():
        return {
            "status": "not_started",
            "factor_count": 0,
            "factor_pool_path": str(FACTOR_POOL_PATH),
        }

    try:
        data = json.loads(FACTOR_POOL_PATH.read_text())
        if isinstance(data, list):
            factor_count = len(data)
        elif isinstance(data, dict):
            # might be {"factors": [...]} or flat dict of factors
            factors = data.get("factors", data)
            factor_count = len(factors) if isinstance(factors, (list, dict)) else 0
        else:
            factor_count = 0
    except (json.JSONDecodeError, OSError):
        factor_count = 0

    return {
        "status": "completed" if factor_count > 0 else "not_started",
        "factor_count": factor_count,
        "factor_pool_path": str(FACTOR_POOL_PATH),
    }


def _arena3_regime_status(regime: str) -> dict[str, Any]:
    """Read per-regime Arena 3 checkpoint if available."""
    base = {
        "name": regime,
        "gen": 0,
        "qd_score": 0.0,
        "elites": 0,
        "status": "pending",
    }

    # Look for checkpoint file: arena3_checkpoints/{regime}.json
    checkpoint = ARENA3_CHECKPOINT_DIR / f"{regime}.json"
    if not checkpoint.exists():
        return base

    try:
        cp = json.loads(checkpoint.read_text())
        base["gen"] = cp.get("generation", 0)
        base["qd_score"] = cp.get("qd_score", 0.0)
        base["elites"] = cp.get("elites", cp.get("elite_count", 0))

        if cp.get("completed", False):
            base["status"] = "completed"
        elif base["gen"] > 0:
            base["status"] = "running"
        # else stays "pending"
    except (json.JSONDecodeError, OSError):
        pass

    return base


def _arena3_status() -> dict[str, Any]:
    """Aggregate Arena 3 status across all regimes."""
    regimes = [_arena3_regime_status(r) for r in REGIMES]

    statuses = {r["status"] for r in regimes}
    if all(s == "completed" for s in statuses):
        overall = "completed"
    elif any(s == "running" for s in statuses):
        overall = "running"
    elif any(s == "completed" for s in statuses):
        # Some done, some pending
        overall = "running"
    else:
        overall = "not_started"

    return {
        "status": overall,
        "regimes": regimes,
    }


# ---------------------------------------------------------------------------
# GET /api/arena
# ---------------------------------------------------------------------------


@arena_router.get("/api/arena")
def arena_pipeline_status():
    """Return Arena 1/2/3 pipeline progress."""
    return {
        "arena1": _arena1_status(),
        "arena2": _arena2_status(),
        "arena3": _arena3_status(),
    }
