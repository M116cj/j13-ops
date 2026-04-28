# 03 — CONFIG & FLAG SPEC

**TEAM ORDER**: 0-9Y-TF4-INTEGRATION-DECISION
**Date**: 2026-04-28
**Phase**: 3 / 8

## Environment variables
| Name | Type | Default | Allowed values |
|---|---|---|---|
| `ARENA_AGGREGATION_MODE` | str | `OFF` | `OFF` / `STRENGTH_FILTER` / `TOP_K_PER_BAR` / `HYBRID_TOPK_STRENGTH` |
| `ARENA_AGGREGATION_Q` | float | `0.95` | `(0.0, 1.0)` exclusive |
| `ARENA_AGGREGATION_TOPK` | int | `50` | `>= 0` |

(case-insensitive matching for MODE; trims whitespace; empty / unset → default)

## Resolution rules

### Mode resolution
| ENV value | Resolved | Notes |
|---|---|---|
| unset | `OFF` | default |
| `""` (empty) | `OFF` | default; defensive |
| `"OFF"` / `"off"` | `OFF` | |
| `"STRENGTH_FILTER"` / `"strength_filter"` | `STRENGTH_FILTER` | matches TF2 `PROFILE_STRENGTH_FILTER` |
| `"TOP_K_PER_BAR"` / `"top_k_per_bar"` | `TOP_K_PER_BAR` | |
| `"HYBRID_TOPK_STRENGTH"` / `"hybrid_topk_strength"` | `HYBRID_TOPK_STRENGTH` | |
| any other string (typo, garbage) | `OFF` (with WARNING log) | **fail-safe to OFF** — never crash a worker |

**Decision**: invalid mode → **fallback to OFF** (NOT fail-closed crash). Rationale:
- The arena_pipeline workers are long-running production processes.
- A typo in `.env` should NOT prevent the system from starting.
- A WARNING-level log entry is emitted at module import + on first observation in batch metrics so operators can detect & fix.
- Master-order Phase 3 explicitly allows either approach; this is the documented choice.

### Param resolution
- `ARENA_AGGREGATION_Q`: parse as float; on `ValueError` or out-of-range → fall back to **0.95**, log WARNING.
- `ARENA_AGGREGATION_TOPK`: parse as int; on `ValueError` or `< 0` → fall back to **50**, log WARNING.
- Used only when MODE selects them:
  - `STRENGTH_FILTER` uses `Q` only (`TOPK` ignored)
  - `TOP_K_PER_BAR` uses `TOPK` only (`Q` ignored)
  - `HYBRID_TOPK_STRENGTH` uses both
  - `OFF` uses neither

## Cache & immutability

### Read-only at module import
The resolved config is cached at module-import time (in `zangetsu/services/aggregation_config.py`). The cached value is what the running worker uses for the lifetime of the process.

This satisfies master-order Phase 3 rule:
> flags must be read-only for production (not toggled automatically)

A change to env requires **explicit worker restart** (via `zangetsu_ctl.sh restart`).

### Test override hook
`refresh_aggregation_config()` is exposed for tests (and for development inspection). It re-reads the env and returns a new resolved config. Production code never calls this.

## Behavior matrix

| MODE | Q | TOPK | apply_signal_aggregation called? | Profile invoked |
|---|---|---|---|---|
| OFF | (any) | (any) | **NO** — pre-filter is a no-op pass-through | — |
| STRENGTH_FILTER | 0.95 | (ignored) | YES | `PROFILE_STRENGTH_FILTER`, `strength_quantile=0.95` |
| TOP_K_PER_BAR | (ignored) | 50 | YES | `PROFILE_TOP_K_PER_BAR`, `top_k=50` |
| HYBRID_TOPK_STRENGTH | 0.90 | 50 | YES | `PROFILE_HYBRID`, `strength_quantile=0.90, top_k=50` |

When MODE != OFF and aggregation is invoked but raises an exception (defensive guard), the exception is caught at the call site, logged at DEBUG, and the original `(signals, sizes)` pass through unchanged — **never block the alpha**. Conservation telemetry records this case.

## Public API of `aggregation_config.py`
```python
class AggregationConfig:
    mode: str                 # "OFF" / "STRENGTH_FILTER" / "TOP_K_PER_BAR" / "HYBRID_TOPK_STRENGTH"
    strength_quantile: float  # 0.95 default
    top_k: int                # 50 default
    is_active: bool           # True iff mode != "OFF"

def get_aggregation_config() -> AggregationConfig: ...
def refresh_aggregation_config() -> AggregationConfig: ...   # test/debug only
```

## Coexistence with TF3 shadow

| ARENA_AGGREGATION_MODE | ARENA_TF3_SHADOW | Effect |
|---|---|---|
| OFF | unset / 0 | baseline (default; identical to pre-TF4) |
| OFF | 1 | TF3 shadow only — 3 profiles in shadow_profiles dict |
| STRENGTH_FILTER (etc.) | unset / 0 | TF4 pre-filter — production path uses 1 profile |
| STRENGTH_FILTER (etc.) | 1 | TF4 pre-filter + TF3 shadow — production uses 1, telemetry parallel-runs all 3 |

Pre-filter and shadow are **orthogonal**. Combination is supported but not required. Workers in production typically run with both `OFF` (baseline) by default.

## Forbidden flags (per master-order)
The following flags are **NOT introduced** by TF4 and CANNOT be enabled via any environment variable defined here:
- CANARY enable
- production rollout enable
- alpha_zoo write enable
- runtime calibration write
- A2_MIN_TRADES override
- validator threshold override
- cost model override

A grep for `ARENA_AGGREGATION_*` in `aggregation_config.py` returns only the three documented flags above. No back-doors.

## Verdict
**PHASE_3_COMPLETE** — configuration spec defined, fail-safe behavior documented, read-only-at-import cache pattern locked, coexistence matrix with TF3 shadow specified, forbidden flag back-door audit clean.

## Next
Phase 4 — minimal patch implementation (~20-60 LOC budget).
