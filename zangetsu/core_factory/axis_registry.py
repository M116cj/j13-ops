"""Axis registry for 0-9AB tournament.

Tracks axis identity, role, component availability, and component-grammar mapping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .constants import AXIS_ROLES


@dataclass(frozen=True)
class AxisDescriptor:
    axis_id: str
    role: str  # primary / shadow / fallback / deferred
    components: tuple[str, ...]  # symbolic component family names
    requires_data: tuple[str, ...]  # data layer dependencies
    note: str = ""


_REGISTRY: dict[str, AxisDescriptor] = {
    "H": AxisDescriptor(
        axis_id="H",
        role="primary",
        components=("regime", "funding_oi", "cross_sectional"),
        requires_data=("ohlcv", "funding", "oi"),
        note="Hybrid: Regime gate x Funding/OI direction x Cross-sectional rank",
    ),
    "C": AxisDescriptor(
        axis_id="C",
        role="shadow",
        components=("regime",),
        requires_data=("ohlcv",),
        note="Regime conditional fitness",
    ),
    "D": AxisDescriptor(
        axis_id="D",
        role="shadow",
        components=("cross_sectional",),
        requires_data=("ohlcv",),
        note="Cross-sectional relative strength",
    ),
    "E": AxisDescriptor(
        axis_id="E",
        role="fallback",
        components=("liquidity_volume_shock",),
        requires_data=("ohlcv",),
        note="Liquidity / volume shock fallback",
    ),
    "A": AxisDescriptor(
        axis_id="A",
        role="deferred",
        components=("microstructure_imbalance",),
        requires_data=("bid_ask", "depth", "trade_prints"),
        note="Microstructure imbalance — deferred to 0-9ZB data capture",
    ),
}


def list_axes() -> tuple[AxisDescriptor, ...]:
    return tuple(_REGISTRY.values())


def get_axis(axis_id: str) -> AxisDescriptor:
    if axis_id not in _REGISTRY:
        raise KeyError(f"unknown axis: {axis_id}; known={tuple(_REGISTRY)}")
    return _REGISTRY[axis_id]


def deferred_axes() -> tuple[AxisDescriptor, ...]:
    return tuple(d for d in _REGISTRY.values() if d.role == "deferred")


def active_axes() -> tuple[AxisDescriptor, ...]:
    return tuple(d for d in _REGISTRY.values() if d.role in {"primary", "shadow"})


def fallback_axes() -> tuple[AxisDescriptor, ...]:
    return tuple(d for d in _REGISTRY.values() if d.role == "fallback")


def axis_role_map() -> Mapping[str, str]:
    return dict(AXIS_ROLES)
