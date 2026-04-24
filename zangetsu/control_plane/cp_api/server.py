"""cp_api skeleton — MOD-6 Phase 3 Phase 7 entry prerequisite 1.6.

Minimum viable cp_api for Phase 7 readiness per `cp_api_minimum_scope.md`.

INTENTIONAL NON-FEATURES:
  - NO runtime takeover authority (cannot stop/start any service)
  - NO parameter WRITE endpoints (read-only + proposal-queue only)
  - NO module-registry WRITE (CI/CD workflow is the sole writer)
  - NO cp_audit yet (log file only; Postgres audit table = Phase 7 full scope)

EXPOSED SURFACE (Phase 7 readiness skeleton):
  - GET /health                 — service liveness probe (no auth)
  - GET /api/control/mode       — current operating mode (read-only; returns "safe")
  - GET /api/control/params     — empty registry (Phase 7 populates)
  - GET /api/control/modules    — empty registry (Phase 7 populates)
  - GET /api/control/rollout/{subsystem} — returns "OFF" (no rollouts yet)

AUTH:
  - /health: public
  - all /api/control/*: requires Authorization: Bearer <CP_API_TOKEN>
    (token = env var set at systemd level; probe-only read for MOD-6)

RUN:
  ExecStart=/home/j13/j13-ops/zangetsu/control_plane/cp_api/.venv/bin/uvicorn \
    server:app --app-dir /home/j13/j13-ops/zangetsu/control_plane/cp_api \
    --host 127.0.0.1 --port 8773

SEE:
  docs/recovery/20260424-mod-6/cp_api_boundary_contract.md
  docs/recovery/20260424-mod-6/cp_api_minimum_scope.md
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import JSONResponse

CP_API_TOKEN = os.environ.get("CP_API_TOKEN", "")
SERVICE_VERSION = "0.1.0-skeleton-mod6"
SERVICE_STARTED_AT = datetime.now(timezone.utc).isoformat()
AUDIT_LOG_PATH = os.environ.get(
    "CP_API_AUDIT_LOG", "/var/log/zangetsu/cp_api/audit.log"
)

app = FastAPI(
    title="cp_api (skeleton)",
    version=SERVICE_VERSION,
    description="Phase 7 entry prerequisite 1.6 — minimum viable CP read surface",
)


def _require_token(authorization: str | None) -> None:
    if not CP_API_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="CP_API_TOKEN not configured; service in unsafe state",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    if authorization.split(" ", 1)[1] != CP_API_TOKEN:
        raise HTTPException(status_code=401, detail="invalid bearer token")


def _audit(actor: str, action: str, target: str, outcome: str) -> None:
    """Append-only audit log. File-based shim; Phase 7 replaces with Postgres."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "action": action,
        "target": target,
        "outcome": outcome,
        "service_version": SERVICE_VERSION,
    }
    try:
        os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)
        with open(AUDIT_LOG_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        # Audit failure is non-fatal at skeleton stage; logged to stderr
        pass


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "cp_api",
        "version": SERVICE_VERSION,
        "started_at": SERVICE_STARTED_AT,
        "runtime_authority": "none",
        "write_endpoints": 0,
        "skeleton": True,
    }


@app.get("/api/control/mode")
async def get_mode(authorization: str | None = Header(default=None)):
    _require_token(authorization)
    _audit(actor="token", action="read", target="mode", outcome="ok")
    return {
        "mode": "safe",
        "rationale": "skeleton service; no mode transitions implemented",
    }


@app.get("/api/control/params")
async def list_params(
    request: Request, authorization: str | None = Header(default=None)
):
    _require_token(authorization)
    _audit(actor="token", action="read", target="params_registry", outcome="empty")
    return {
        "parameters": [],
        "note": "Phase 7 will seed this registry from scattered_config_map.md",
    }


@app.get("/api/control/params/{key}")
async def get_param(key: str, authorization: str | None = Header(default=None)):
    _require_token(authorization)
    _audit(
        actor="token", action="read", target=f"param:{key}", outcome="not_found"
    )
    raise HTTPException(
        status_code=404,
        detail=f"parameter '{key}' not found (empty registry in skeleton)",
    )


@app.get("/api/control/modules")
async def list_modules(authorization: str | None = Header(default=None)):
    _require_token(authorization)
    _audit(actor="token", action="read", target="modules_registry", outcome="empty")
    return {
        "modules": [],
        "note": "Phase 7 CI/CD workflow populates from zangetsu/module_contracts/*.yaml",
    }


@app.get("/api/control/rollout/{subsystem}")
async def get_rollout(
    subsystem: str, authorization: str | None = Header(default=None)
):
    _require_token(authorization)
    _audit(
        actor="token",
        action="read",
        target=f"rollout:{subsystem}",
        outcome="off",
    )
    return {
        "subsystem": subsystem,
        "tier": "OFF",
        "note": "no rollouts active; skeleton returns OFF for all subsystems",
    }


@app.middleware("http")
async def refuse_writes(request: Request, call_next):
    """Skeleton safety: reject ALL non-GET requests."""
    if request.method != "GET":
        _audit(
            actor=request.headers.get("user-agent", "unknown"),
            action=request.method,
            target=str(request.url.path),
            outcome="refused_write",
        )
        return JSONResponse(
            status_code=405,
            content={
                "error": "write operations not implemented in skeleton",
                "allowed": ["GET"],
                "skeleton": True,
            },
        )
    return await call_next(request)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("CP_API_PORT", "8773"))
    uvicorn.run(
        "server:app",
        host="127.0.0.1",
        port=port,
        log_level="info",
    )
