# 02 — CONFIG SPEC

**TEAM ORDER**: 0-9Y-HE1-HORIZON-TARGET-PLUMBING
**Date**: 2026-04-28
**Phase**: 2 / 7

## Environment variables
| Name | Type | Default | Allowed values |
|---|---|---|---|
| `ACTIVE_A1_HORIZONS` | comma-separated ints | `60` | each value `>= 1`, deduplicated, sorted |
| `ARENA_HORIZON_MODE` | str | `FIXED` | `FIXED` / `SIMPLE_CYCLE` / `RANDOM_UNIFORM` |
| `ARENA_HORIZON_FIXED` | int | `60` | `>= 1` |
| `ALPHA_FORWARD_HORIZON` | int (legacy) | `60` | preserved for backward compatibility — used as inner `_forward_returns` env-fallback when no explicit horizon arg |

## Resolution rules

### Mode resolution
| ENV value | Resolved | Notes |
|---|---|---|
| unset | `FIXED` | preserves pre-HE1 production behavior |
| `""` (empty) | `FIXED` | defensive |
| `"FIXED"` / `"fixed"` | `FIXED` | case-insensitive |
| `"SIMPLE_CYCLE"` / `"simple_cycle"` | `SIMPLE_CYCLE` | |
| `"RANDOM_UNIFORM"` / `"random_uniform"` | `RANDOM_UNIFORM` | |
| any other string (typo, garbage) | `FIXED` (with WARNING log) | **fail-safe to FIXED** — never crash worker |

### Active horizons resolution
| ENV value | Resolved |
|---|---|
| unset | `(60,)` |
| `""` (empty) | `(60,)` |
| `"60"` | `(60,)` |
| `"60,180,240,360"` | `(60, 180, 240, 360)` |
| `"  60 , 180  "` (whitespace) | `(60, 180)` (trimmed, parsed, deduped, sorted) |
| `"60,abc,180"` (mixed valid/invalid) | `(60, 180)` (skip invalid + WARN log) |
| `"abc"` (all invalid) | `(60,)` (fallback + WARN log) |
| `"-30,60"` (negative) | `(60,)` (skip negatives + WARN log) |

### Fixed horizon fallback
| ENV value | Resolved |
|---|---|
| unset | `60` |
| `""` | `60` |
| `"180"` | `180` |
| `"abc"` | `60` (WARN log) |
| `"-1"` | `60` (WARN log) |

## Selection algorithm (per round)

```python
def select_horizon(round_index: int) -> int:
    cfg = get_horizon_config()
    if cfg.mode == "FIXED":
        return cfg.fixed_horizon
    if cfg.mode == "SIMPLE_CYCLE":
        return cfg.active_horizons[round_index % len(cfg.active_horizons)]
    if cfg.mode == "RANDOM_UNIFORM":
        return random.choice(cfg.active_horizons)
    # unreachable (mode validated at config load); defensive fallback
    return cfg.fixed_horizon
```

`round_index` is the 0-based monotonic counter `round_number - 1` from `arena_pipeline.py`.

## Cache & immutability
The resolved config is cached at module import time via `_CONFIG = _resolve()`. Production never auto-toggles. A change to env requires explicit worker restart.

`refresh_horizon_config()` is exposed for tests / debug only.

## Public API of `horizon_config.py`
```python
class HorizonConfig:
    active_horizons: tuple[int, ...]  # default (60,)
    mode: str                         # "FIXED" | "SIMPLE_CYCLE" | "RANDOM_UNIFORM"
    fixed_horizon: int                # default 60

    @property
    def is_multi_horizon(self) -> bool: ...   # True if len(active_horizons) > 1

def get_horizon_config() -> HorizonConfig: ...
def refresh_horizon_config() -> HorizonConfig: ...
def select_horizon(round_index: int) -> int: ...
```

## Logging
- On module import: log INFO with resolved config (e.g., `"[he1] horizons=(60,) mode=FIXED fixed=60"`).
- On invalid env: log WARN with the offending value and chosen fallback.
- On every selected horizon per round: NOT logged at INFO (would flood); the horizon will appear in `arena_batch_metrics["aggregate_metrics"]["horizon"]` as durable telemetry.

## Compatibility with legacy `ALPHA_FORWARD_HORIZON`
The existing `_forward_returns(close)` reads `ALPHA_FORWARD_HORIZON` env directly. After HE1:
- New signature: `_forward_returns(close, horizon: int | None = None)`
- When `horizon is None` (any caller that does not pass it explicitly): falls back to `int(os.environ.get('ALPHA_FORWARD_HORIZON', '60'))` — **bit-identical to pre-HE1**.
- When `horizon` is explicit: uses that value — overrides env.

This dual contract guarantees no third-party caller of `_forward_returns` (if any exists outside the engine) breaks. The HE1 internal callers always pass explicit `horizon`.

## Forbidden flags
The following are **NOT introduced** by HE1 and CANNOT be enabled via any env var defined here:
- CANARY enable
- production rollout enable
- alpha_zoo write enable
- runtime calibration write
- A2_MIN_TRADES override
- validator threshold override
- cost model override

A grep for `ARENA_HORIZON_*` / `ACTIVE_A1_HORIZONS` in `horizon_config.py` returns only the three documented flags above. No back-doors.

## Verdict
**CONFIG_SPEC_READY** — env-driven, read-only at import, fail-safe to pre-HE1 baseline on any invalid input.

## Next
Phase 3 — patch implementation.
