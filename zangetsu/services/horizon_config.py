"""HE1 Horizon Config — multi-horizon plumbing for A1.

TEAM ORDER: 0-9Y-HE1-HORIZON-TARGET-PLUMBING
Status:     infrastructure-only, default = single horizon = 60 (pre-HE1 baseline).

Reads:
  ACTIVE_A1_HORIZONS    (comma-sep ints, default "60")
  ARENA_HORIZON_MODE    (FIXED | SIMPLE_CYCLE | RANDOM_UNIFORM; default FIXED)
  ARENA_HORIZON_FIXED   (int >= 1, default 60)

Resolution:
  - case-insensitive mode match
  - invalid mode → fallback to FIXED (do NOT crash worker)
  - invalid horizons list → fallback to (60,) + WARN
  - invalid fixed → fallback to 60 + WARN
  - duplicates removed; sorted

The resolved config is cached at module-import time. Production code uses
`get_horizon_config()` and `select_horizon(round_index)`.
`refresh_horizon_config()` is for tests/debug.

Forbidden:
  - no CANARY / production / alpha_zoo / capital / risk flags
  - no validator / cost / A2_MIN_TRADES override
"""
from __future__ import annotations

import os
import random
import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


MODE_FIXED = "FIXED"
MODE_SIMPLE_CYCLE = "SIMPLE_CYCLE"
MODE_RANDOM_UNIFORM = "RANDOM_UNIFORM"

ALLOWED_MODES = frozenset({MODE_FIXED, MODE_SIMPLE_CYCLE, MODE_RANDOM_UNIFORM})

DEFAULT_HORIZONS = (60,)
DEFAULT_FIXED = 60
DEFAULT_MODE = MODE_FIXED


@dataclass(frozen=True)
class HorizonConfig:
    active_horizons: tuple
    mode: str
    fixed_horizon: int

    @property
    def is_multi_horizon(self) -> bool:
        return len(self.active_horizons) > 1


def _resolve_horizons(raw: str | None) -> tuple:
    if raw is None or str(raw).strip() == "":
        return DEFAULT_HORIZONS
    parts = [p.strip() for p in str(raw).split(",")]
    out = []
    bad = []
    for p in parts:
        if p == "":
            continue
        try:
            v = int(p)
        except (ValueError, TypeError):
            bad.append(p)
            continue
        if v < 1:
            bad.append(p)
            continue
        out.append(v)
    if bad:
        log.warning(
            f"[he1] ACTIVE_A1_HORIZONS: skipping invalid entries {bad}; "
            f"keeping {out or list(DEFAULT_HORIZONS)}"
        )
    if not out:
        return DEFAULT_HORIZONS
    return tuple(sorted(set(out)))


def _resolve_mode(raw: str | None) -> str:
    if raw is None:
        return DEFAULT_MODE
    s = str(raw).strip().upper()
    if s == "":
        return DEFAULT_MODE
    if s in ALLOWED_MODES:
        return s
    log.warning(
        f"[he1] invalid ARENA_HORIZON_MODE={raw!r}; falling back to {DEFAULT_MODE}. "
        f"allowed={sorted(ALLOWED_MODES)}"
    )
    return DEFAULT_MODE


def _resolve_fixed(raw: str | None) -> int:
    if raw is None or str(raw).strip() == "":
        return DEFAULT_FIXED
    try:
        v = int(raw)
    except (ValueError, TypeError):
        log.warning(f"[he1] invalid ARENA_HORIZON_FIXED={raw!r}; falling back to {DEFAULT_FIXED}")
        return DEFAULT_FIXED
    if v < 1:
        log.warning(f"[he1] ARENA_HORIZON_FIXED={v} < 1; falling back to {DEFAULT_FIXED}")
        return DEFAULT_FIXED
    return v


def _resolve() -> HorizonConfig:
    cfg = HorizonConfig(
        active_horizons=_resolve_horizons(os.environ.get("ACTIVE_A1_HORIZONS")),
        mode=_resolve_mode(os.environ.get("ARENA_HORIZON_MODE")),
        fixed_horizon=_resolve_fixed(os.environ.get("ARENA_HORIZON_FIXED")),
    )
    log.info(
        f"[he1] horizon config resolved: horizons={cfg.active_horizons} "
        f"mode={cfg.mode} fixed={cfg.fixed_horizon} multi={cfg.is_multi_horizon}"
    )
    return cfg


# Cache at module-import.
_CONFIG = _resolve()


def get_horizon_config() -> HorizonConfig:
    """Return the cached horizon config (resolved at import time)."""
    return _CONFIG


def refresh_horizon_config() -> HorizonConfig:
    """Re-read env and replace cached config. For tests / debug ONLY."""
    global _CONFIG
    _CONFIG = _resolve()
    return _CONFIG


def select_horizon(round_index: int) -> int:
    """Return the horizon for the given round (0-based round_index).

    Behavior:
      - FIXED: always returns fixed_horizon (default 60)
      - SIMPLE_CYCLE: round-robin over active_horizons
      - RANDOM_UNIFORM: uniform random choice from active_horizons

    When `active_horizons` is the default `(60,)`, all 3 modes return 60 →
    bit-identical to pre-HE1 baseline.
    """
    cfg = _CONFIG
    if cfg.mode == MODE_FIXED:
        return cfg.fixed_horizon
    if cfg.mode == MODE_SIMPLE_CYCLE:
        if not cfg.active_horizons:
            return cfg.fixed_horizon
        return cfg.active_horizons[int(round_index) % len(cfg.active_horizons)]
    if cfg.mode == MODE_RANDOM_UNIFORM:
        if not cfg.active_horizons:
            return cfg.fixed_horizon
        return random.choice(cfg.active_horizons)
    # Defensive — _resolve_mode already validated, but guard against a future bug.
    return cfg.fixed_horizon
