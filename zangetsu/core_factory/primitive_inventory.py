"""Primitive inventory for 0-9AB shadow tournament.

Wraps a curated subset of zangetsu.engine.components.alpha_primitives so that
unsupported operators fail closed (no silent drop). Pure-function imports only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

# Reuse production primitives (pure functions, numba-compiled).
# This import is read-only; no side effects.
from zangetsu.engine.components import alpha_primitives as P


@dataclass(frozen=True)
class PrimitiveSpec:
    name: str
    arity: int  # 1 or 2
    family: str  # arithmetic / time_series / transform / cross_sectional
    fn: Callable
    needs_window: bool = False


_INVENTORY: dict[str, PrimitiveSpec] = {
    # arithmetic (binary)
    "add": PrimitiveSpec("add", 2, "arithmetic", P.add),
    "sub": PrimitiveSpec("sub", 2, "arithmetic", P.sub),
    "mul": PrimitiveSpec("mul", 2, "arithmetic", P.mul),
    "protected_div": PrimitiveSpec("protected_div", 2, "arithmetic", P.protected_div),
    # transforms (unary)
    "neg": PrimitiveSpec("neg", 1, "transform", P.neg),
    "sign": PrimitiveSpec("sign", 1, "transform", P.sign_x),
    "tanh": PrimitiveSpec("tanh", 1, "transform", P.tanh_x),
    # time-series (unary, windowed)
    "delta": PrimitiveSpec("delta", 1, "time_series", P.delta, needs_window=True),
    "ts_mean": PrimitiveSpec("ts_mean", 1, "time_series", P.ts_mean, needs_window=True),
    "ts_std": PrimitiveSpec("ts_std", 1, "time_series", P.ts_std, needs_window=True),
    "ts_rank": PrimitiveSpec("ts_rank", 1, "time_series", P.ts_rank, needs_window=True),
}


def supported_primitives() -> tuple[str, ...]:
    return tuple(_INVENTORY)


def get_primitive(name: str) -> PrimitiveSpec:
    if name not in _INVENTORY:
        # Fail closed — never silently drop an unsupported operator.
        raise UnsupportedOperatorError(name)
    return _INVENTORY[name]


def primitives_by_family(family: str) -> tuple[PrimitiveSpec, ...]:
    return tuple(s for s in _INVENTORY.values() if s.family == family)


class UnsupportedOperatorError(Exception):
    """Raised when grammar references a primitive not registered here."""
    def __init__(self, name: str):
        super().__init__(f"unsupported_operator: {name}")
        self.name = name


def evaluate_field(field_name: str, data: dict[str, np.ndarray]) -> np.ndarray:
    """Resolve a base-field reference (close/high/low/open/volume/oi/funding) from data dict."""
    if field_name not in data:
        raise UnsupportedOperatorError(f"field:{field_name}")
    arr = data[field_name]
    return np.asarray(arr, dtype=np.float32)
