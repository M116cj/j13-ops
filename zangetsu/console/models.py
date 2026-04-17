"""Pydantic models for console API requests/responses."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ConfigUpdate(BaseModel):
    """Request to update one or more configuration parameters."""
    overrides: Dict[str, Any] = Field(
        ..., description="Map of setting_name -> new_value"
    )


class ConfigResponse(BaseModel):
    """Response after config update."""
    changed: List[str] = Field(default_factory=list, description="Changed field names")
    current: Dict[str, Any] = Field(default_factory=dict, description="Current settings snapshot")


class ArenaControlRequest(BaseModel):
    """Request to control an arena (start/stop/reset)."""
    arena_name: str
    action: str = Field(..., pattern="^(start|stop|pause|resume|reset)$")
    symbol: Optional[str] = None


class ArenaControlResponse(BaseModel):
    """Response from arena control."""
    arena_name: str
    action: str
    success: bool
    message: str = ""


class CostOverride(BaseModel):
    """Override cost model for a symbol."""
    symbol: str
    taker_bps: Optional[float] = None
    maker_bps: Optional[float] = None
    funding_8h_avg_bps: Optional[float] = None
    slippage_bps: Optional[float] = None


class HealthResponse(BaseModel):
    """Engine health status."""
    status: str
    uptime_s: float
    components: Dict[str, Any]
