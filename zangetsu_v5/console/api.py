"""FastAPI endpoints for parameter control (Console).

Provides runtime parameter tuning, arena control, cost model overrides,
and engine health queries. All CONSOLE_HOOK parameters are writable here.
"""
from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING

from fastapi import FastAPI, HTTPException

from .models import (
    ArenaControlRequest,
    ArenaControlResponse,
    ConfigResponse,
    ConfigUpdate,
    CostOverride,
    HealthResponse,
)

if TYPE_CHECKING:
    from ..engine.core import ArenaEngine


def create_console_app(engine: "ArenaEngine") -> FastAPI:
    """Create the Console FastAPI application bound to an engine instance."""

    app = FastAPI(
        title="Zangetsu V5 Console",
        description="Runtime parameter tuning and arena control",
        version="5.0.0",
    )

    @app.get("/config", response_model=ConfigResponse)
    async def get_config() -> ConfigResponse:
        return ConfigResponse(changed=[], current=engine.config.to_dict())

    @app.put("/config", response_model=ConfigResponse)
    async def update_config(req: ConfigUpdate) -> ConfigResponse:
        changed = engine.apply_config_update(req.overrides)
        return ConfigResponse(changed=changed, current=engine.config.to_dict())

    @app.get("/config/{param_name}")
    async def get_param(param_name: str) -> Dict[str, Any]:
        if not hasattr(engine.config, param_name):
            raise HTTPException(404, detail="Parameter not found: " + param_name)
        return {"name": param_name, "value": getattr(engine.config, param_name)}

    @app.put("/config/{param_name}")
    async def set_param(param_name: str, value: Any) -> Dict[str, Any]:
        changed = engine.apply_config_update({param_name: value})
        if not changed:
            raise HTTPException(400, detail="Parameter unchanged or not found")
        return {"name": param_name, "value": getattr(engine.config, param_name)}

    @app.post("/arena/control", response_model=ArenaControlResponse)
    async def arena_control(req: ArenaControlRequest) -> ArenaControlResponse:
        engine.log.info(
            "Arena control request",
            arena=req.arena_name, action=req.action, symbol=req.symbol,
        )
        try:
            if req.action == "start":
                await engine.start_arena(req.arena_name)
            elif req.action == "stop":
                await engine.stop_arena(req.arena_name)
            elif req.action == "pause":
                await engine.pause_arena(req.arena_name)
            elif req.action == "resume":
                await engine.resume_arena(req.arena_name)
            elif req.action == "reset":
                await engine.stop_arena(req.arena_name)
                await engine.start_arena(req.arena_name)
            return ArenaControlResponse(
                arena_name=req.arena_name,
                action=req.action,
                success=True,
                message=f"{req.action} completed",
            )
        except Exception as e:
            engine.log.error(
                "arena_control failed",
                arena=req.arena_name, action=req.action, error=str(e),
            )
            return ArenaControlResponse(
                arena_name=req.arena_name,
                action=req.action,
                success=False,
                message=str(e),
            )

    @app.get("/costs")
    async def get_costs() -> Dict[str, Any]:
        return engine.cost_model.snapshot()

    @app.put("/costs")
    async def update_cost(override: CostOverride) -> Dict[str, Any]:
        from ..config.cost_model import SymbolCost
        current = engine.cost_model.get(override.symbol)
        updated = SymbolCost(
            symbol=override.symbol,
            taker_bps=override.taker_bps if override.taker_bps is not None else current.taker_bps,
            maker_bps=override.maker_bps if override.maker_bps is not None else current.maker_bps,
            funding_8h_avg_bps=override.funding_8h_avg_bps if override.funding_8h_avg_bps is not None else current.funding_8h_avg_bps,
            slippage_bps=override.slippage_bps if override.slippage_bps is not None else current.slippage_bps,
            min_notional_usd=current.min_notional_usd,
        )
        engine.cost_model.update_symbol(override.symbol, updated)
        return {"symbol": override.symbol, "cost": engine.cost_model.get(override.symbol).__dict__}

    @app.get("/health", response_model=HealthResponse)
    async def health() -> Dict[str, Any]:
        return engine.health.collect_all()

    @app.get("/api/health", response_model=HealthResponse)
    async def api_health() -> Dict[str, Any]:
        return engine.health.collect_all()

    @app.get("/status")
    async def status() -> Dict[str, Any]:
        return engine.status()

    @app.get("/api/status")
    async def api_status() -> Dict[str, Any]:
        return engine.status()

    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    from pathlib import Path

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/")
        async def root():
            return FileResponse(str(static_dir / "index.html"))

    return app
