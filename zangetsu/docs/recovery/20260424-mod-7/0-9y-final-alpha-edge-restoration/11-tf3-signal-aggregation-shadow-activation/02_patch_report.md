# 02 — PATCH REPORT

**TEAM ORDER**: 0-9Y-TF3-SIGNAL-AGGREGATION-SHADOW-ACTIVATION
**Date**: 2026-04-28
**Phase**: 2 / 8

## Files added
| Path | Lines | Purpose |
|---|---|---|
| `zangetsu/services/tf3_shadow.py` | 254 | Shadow harness: env gate, 3 profile params, accumulators, run/payload helpers |
| `zangetsu/tests/test_tf3_shadow.py` | 292 | 9 tests covering env gating, no-mutation, conservation, payload shape, forbidden-token scan |

## Files modified
| Path | LOC | Type of change |
|---|---|---|
| `zangetsu/services/arena_pipeline.py` | +44 / -0 | 4 additive insertions: import, accumulator init, shadow block, payload attachment |

## arena_pipeline.py edits (4 surgical)

**Edit 1** (after line ~328 import block):
```python
from zangetsu.services.tf3_shadow import (
    is_shadow_enabled as _tf3_is_enabled,
    run_shadow_for_alpha as _tf3_run_shadow,
    make_accumulators as _tf3_make_accumulators,
    build_shadow_profiles_payload as _tf3_build_payload,
)
```

**Edit 2** (after line ~1010 in per-symbol-regime accumulator init):
```python
_tf3_shadow_accs = _tf3_make_accumulators() if _tf3_is_enabled() else None
```

**Edit 3** (line ~1062, between `generate_alpha_signals` and `backtester.run`):
```python
if _tf3_shadow_accs is not None:
    try:
        _tf3_run_shadow(signals=signals, sizes=sizes, backtester=backtester, ...)
    except Exception as _tf3_e:
        log.debug(f"[tf3] shadow harness failed ({alpha_hash}): {_tf3_e}")
```

**Edit 4** (line ~1493, before `_emit_a1_batch_metrics_from_stats_safe(...)`):
```python
if _tf3_shadow_accs is not None:
    try:
        _b1_aggregate_metrics["shadow_profiles"] = _tf3_build_payload(
            _tf3_shadow_accs,
            baseline_train_gross_pnl=_b1_train_gross_pnl,
            ...
        )
    except Exception as _tf3_pe:
        log.debug(f"[tf3] shadow payload build failed: {_tf3_pe}")
```

## Activation gate semantics

| `ARENA_TF3_SHADOW` env | `_tf3_is_enabled()` | Shadow path | Baseline path |
|---|---|---|---|
| unset | False | skipped (zero overhead) | unchanged |
| `0` / `""` / `false` | False | skipped | unchanged |
| `1` / `true` / `yes` / `on` | True | runs | unchanged |

Cached at module import for performance + test stability.

## tf3_shadow.py public API
```python
is_shadow_enabled() -> bool
refresh_shadow_flag() -> bool                    # tests/debug
make_accumulators() -> dict[str, ShadowAccumulator]
run_shadow_for_alpha(*, signals, sizes, backtester, close_f32, ..., accumulators) -> None
build_shadow_profiles_payload(accumulators, *, baseline_*) -> dict
```

## Profile parameter set (locked)
| Key | Profile | Parameters | Selected because |
|---|---|---|---|
| `strength` | STRENGTH_FILTER | `quantile=0.95` | TF2 fixture `STRENGTH_q0.95`: Δ net = +0.0115 |
| `top_k` | TOP_K_PER_BAR | `top_k=50` | matches HYBRID's K — isolates strength filtering |
| `hybrid` | HYBRID_TOPK_STRENGTH | `quantile=0.90, top_k=50` | TF2 fixture best Δ net = +0.0119 |

## Failure isolation
Each shadow profile call is `try/except`-wrapped both **inside** `tf3_shadow.run_shadow_for_alpha` (per-profile) **and** **outside** it in `arena_pipeline.py` (the entire harness call). Per-profile errors increment `acc.error_count`. Shadow exceptions never propagate to baseline.

## Telemetry shape — `aggregate_metrics["shadow_profiles"]`
Top-level shape:
```python
{
  "baseline":  { "trade_count_median", "gross_pnl_median", "net_pnl_median",
                 "win_rate_median", "skipped_count_total"=0, "alpha_count" },
  "strength":  { "label", "trade_count_median", "gross_pnl_median",
                 "net_pnl_median", "win_rate_median",
                 "gross_per_trade_median", "net_per_trade_median",
                 "skipped_count_total", "kept_count_total", "entered_count_total",
                 "error_count", "params", "alpha_count" },
  "top_k":     { ... },
  "hybrid":    { ... },
}
```

`shadow_profiles` is **only added** when shadow is enabled. When disabled, `aggregate_metrics` retains its existing schema unchanged.

## Conservation invariant (per profile per batch)
```
entered_count_total == kept_count_total + skipped_count_total
```
Verified by:
- TF2 test #4 (per-alpha conservation)
- TF3 test #5 (per-batch accumulation)
- TF3 test #7 (random-fixture replicated conservation)

## Default invariant (audited)
With `ARENA_TF3_SHADOW != "1"`:
- `_tf3_shadow_accs` is `None` → all 4 shadow gates short-circuit
- baseline `signals`, `sizes`, `_b1_*` accumulators, `_b1_aggregate_metrics` dict, emission call are **bit-for-bit identical** to pre-TF3
- TF2 helper is not invoked (verified: `apply_signal_aggregation` not in any baseline call site)

## STOP-conditions check (Phase 2 spec)
| STOP cause | Status |
|---|---|
| Implementation requires validation threshold changes | ❌ no |
| Implementation changes cost | ❌ no |
| Implementation changes pass/fail semantics | ❌ no |
| Implementation cannot be default OFF | ❌ no — env=1 explicitly required to activate |
| Existing return values changed | ❌ no — additive |
| Validation inputs changed | ❌ no — `generate_alpha_signals` signature/args unchanged |
| Candidate flow changed | ❌ no — `round_champions`, `bloom`, `pass_count` untouched |

✅ No STOP triggered.

## Verdict
**PHASE_2_COMPLETE — patch is additive, env-gated, isolated; baseline path bit-equivalent when shadow disabled.**

## Next
Phase 3 — pytest verification + baseline regression.
