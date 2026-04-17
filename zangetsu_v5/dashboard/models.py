"""Pydantic models for Dashboard API responses."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ArenaStatus(BaseModel):
    name: str
    active: bool
    total_promoted: int = 0
    best_score: float = 0.0
    metrics: Dict[str, Any] = {}


class BacktestSummary(BaseModel):
    strategy_id: str
    win_rate: float
    net_pnl: float
    sharpe: float
    max_drawdown: float
    n_trades: int
    avg_hold_bars: float = 0.0


class ComponentHealth(BaseModel):
    name: str
    status: str
    details: Dict[str, Any] = {}


class ELOEntry(BaseModel):
    strategy_id: str
    elo: float
    arena_origin: str = ""
    regime: str = ""
    wins: int = 0
    losses: int = 0
    draws: int = 0


class ELOLeaderboard(BaseModel):
    entries: List[ELOEntry]
    total_strategies: int


class EvolutionStats(BaseModel):
    generation: int
    population_size: int
    best_fitness: float
    diversity: float
    stagnation: int


class PipelineOverview(BaseModel):
    arenas: List[ArenaStatus]
    total_strategies_evaluated: int = 0
    total_strategies_promoted: int = 0
    pipeline_throughput_per_hour: float = 0.0
