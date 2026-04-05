"""Configuration loader for Zangetsu V3.

This module provides a minimal yet structured loader that maps the
``config/config.yaml`` file into nested dataclasses.  It keeps the
surface area small so downstream code can rely on attribute access
without dragging in pandas or other heavy dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class DatabaseConfig:
    host: str
    port: int
    user: str
    password: str
    dbname: str


@dataclass
class DataConfig:
    symbols: list[str]
    embargo_days: int
    holdout_months: int


@dataclass
class RegimeConfig:
    min_states: int
    max_states: int
    lookback: int
    debounce_bars: int
    ramp_up_bars: int


@dataclass
class SearchConfig:
    threads: int
    cache_gb: float
    sos_threshold: float
    min_elites: int


@dataclass
class LiveConfig:
    max_stale_seconds: int
    max_net_exposure: float
    max_gross_exposure: float
    max_per_regime_exposure: float
    max_per_symbol_net: float
    max_concurrent_positions: int


@dataclass
class PathsConfig:
    strategies: str
    data: str
    logs: str


@dataclass
class Config:
    database: DatabaseConfig
    data: DataConfig
    regime: RegimeConfig
    search: SearchConfig
    live: LiveConfig
    paths: PathsConfig


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_config(path: Optional[str | Path] = None) -> Config:
    """Load configuration from ``config/config.yaml`` by default.

    Parameters
    ----------
    path: optional
        Custom path to a YAML file.  If omitted, the project‑relative
        ``config/config.yaml`` is used.

    Returns
    -------
    Config
        Populated configuration object with nested dataclasses.
    """

    cfg_path = Path(path) if path is not None else Path("config/config.yaml")
    raw = _load_yaml(cfg_path)

    return Config(
        database=DatabaseConfig(**raw["database"]),
        data=DataConfig(**raw["data"]),
        regime=RegimeConfig(**raw["regime"]),
        search=SearchConfig(**raw["search"]),
        live=LiveConfig(**raw["live"]),
        paths=PathsConfig(**raw["paths"]),
    )


__all__ = [
    "DatabaseConfig",
    "DataConfig",
    "RegimeConfig",
    "SearchConfig",
    "LiveConfig",
    "PathsConfig",
    "Config",
    "load_config",
]

