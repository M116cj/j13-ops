"""TF4 Aggregation Config — production-grade env-driven flags.

TEAM ORDER: 0-9Y-TF4-INTEGRATION-DECISION
Status:     production pre-filter, default OFF.

Reads:
  ARENA_AGGREGATION_MODE   (OFF | STRENGTH_FILTER | TOP_K_PER_BAR | HYBRID_TOPK_STRENGTH)
  ARENA_AGGREGATION_Q      (float in (0, 1), default 0.95)
  ARENA_AGGREGATION_TOPK   (int >= 0, default 50)

Resolution:
  - case-insensitive mode match
  - invalid mode  → fallback to OFF, WARN log (do NOT crash worker)
  - invalid Q     → fallback to 0.95, WARN log
  - invalid TOPK  → fallback to 50,   WARN log

The resolved config is cached at module-import time. Production uses
`get_aggregation_config()`. `refresh_aggregation_config()` is for tests / debug.

Forbidden:
  - no CANARY / production / alpha_zoo / capital / risk flags
  - no validator / cost / A2_MIN_TRADES override
"""
from __future__ import annotations

import os
import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


MODE_OFF = "OFF"
MODE_STRENGTH_FILTER = "STRENGTH_FILTER"
MODE_TOP_K_PER_BAR = "TOP_K_PER_BAR"
MODE_HYBRID_TOPK_STRENGTH = "HYBRID_TOPK_STRENGTH"

ALLOWED_MODES = frozenset({
    MODE_OFF, MODE_STRENGTH_FILTER, MODE_TOP_K_PER_BAR, MODE_HYBRID_TOPK_STRENGTH,
})

DEFAULT_Q = 0.95
DEFAULT_TOPK = 50


@dataclass(frozen=True)
class AggregationConfig:
    mode: str
    strength_quantile: float
    top_k: int

    @property
    def is_active(self) -> bool:
        return self.mode != MODE_OFF


def _resolve_mode(raw: str | None) -> str:
    if raw is None:
        return MODE_OFF
    s = raw.strip().upper()
    if s == "":
        return MODE_OFF
    if s in ALLOWED_MODES:
        return s
    log.warning(
        f"[tf4] invalid ARENA_AGGREGATION_MODE={raw!r}; "
        f"falling back to OFF. allowed={sorted(ALLOWED_MODES)}"
    )
    return MODE_OFF


def _resolve_quantile(raw: str | None) -> float:
    if raw is None or str(raw).strip() == "":
        return DEFAULT_Q
    try:
        v = float(raw)
    except (ValueError, TypeError):
        log.warning(f"[tf4] invalid ARENA_AGGREGATION_Q={raw!r}; falling back to {DEFAULT_Q}")
        return DEFAULT_Q
    if not (0.0 < v < 1.0):
        log.warning(f"[tf4] ARENA_AGGREGATION_Q={v} out of (0,1); falling back to {DEFAULT_Q}")
        return DEFAULT_Q
    return v


def _resolve_topk(raw: str | None) -> int:
    if raw is None or str(raw).strip() == "":
        return DEFAULT_TOPK
    try:
        v = int(raw)
    except (ValueError, TypeError):
        log.warning(f"[tf4] invalid ARENA_AGGREGATION_TOPK={raw!r}; falling back to {DEFAULT_TOPK}")
        return DEFAULT_TOPK
    if v < 0:
        log.warning(f"[tf4] ARENA_AGGREGATION_TOPK={v} < 0; falling back to {DEFAULT_TOPK}")
        return DEFAULT_TOPK
    return v


def _resolve() -> AggregationConfig:
    return AggregationConfig(
        mode=_resolve_mode(os.environ.get("ARENA_AGGREGATION_MODE")),
        strength_quantile=_resolve_quantile(os.environ.get("ARENA_AGGREGATION_Q")),
        top_k=_resolve_topk(os.environ.get("ARENA_AGGREGATION_TOPK")),
    )


# Cache resolved config at module-import time.
_CONFIG = _resolve()


def get_aggregation_config() -> AggregationConfig:
    """Return the cached, immutable aggregation config (resolved at import)."""
    return _CONFIG


def refresh_aggregation_config() -> AggregationConfig:
    """Re-read env and replace cached config. For tests / debug ONLY.

    Production code MUST NOT call this function — config is read-only at
    import time, change-triggered worker restart is the canonical path.
    """
    global _CONFIG
    _CONFIG = _resolve()
    return _CONFIG
