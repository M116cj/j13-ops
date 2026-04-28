# 04 — PATCH REPORT

**TEAM ORDER**: 0-9Y-TF4-INTEGRATION-DECISION
**Date**: 2026-04-28
**Phase**: 4 / 8

## Files added
| Path | Lines | Purpose |
|---|---|---|
| `zangetsu/services/aggregation_config.py` | 125 | env-driven config resolver: `ARENA_AGGREGATION_MODE`/`Q`/`TOPK`, fail-safe fallbacks, immutable cached config |
| `zangetsu/tests/test_tf4_aggregation_config.py` | 251 | 7 tests covering all 6 master-order required cases plus tokenize-scan |

## Files modified
| Path | LOC | Type |
|---|---|---|
| `zangetsu/services/arena_pipeline.py` | +60 / −0 | 4 surgical additive edits: imports, accumulator init, pre-filter hook, telemetry attachment |

**Total diff**: +60 LOC additive in `arena_pipeline.py` — within master-order budget (~20-60). 0 deletions. 0 forbidden touches.

## arena_pipeline.py edits (4 surgical)

**Edit 1** (after TF3 imports block):
```python
from zangetsu.services.aggregation_config import get_aggregation_config as _tf4_get_config
from zangetsu.services.signal_aggregation import (
    apply_signal_aggregation as _tf4_apply,
    PROFILE_STRENGTH_FILTER as _TF4_P_STRENGTH,
    PROFILE_TOP_K_PER_BAR as _TF4_P_TOPK,
    PROFILE_HYBRID as _TF4_P_HYBRID,
)
_TF4_CFG = _tf4_get_config()
_TF4_PROFILE_MAP = {
    "STRENGTH_FILTER": _TF4_P_STRENGTH,
    "TOP_K_PER_BAR": _TF4_P_TOPK,
    "HYBRID_TOPK_STRENGTH": _TF4_P_HYBRID,
}
```

**Edit 2** (per-symbol-regime accumulator init, alongside `_tf3_shadow_accs`):
```python
_tf4_skipped_total = 0
_tf4_kept_total = 0
_tf4_entered_total = 0
```
Default = 0 across the board; only incremented when `_TF4_CFG.is_active`.

**Edit 3** (pre-filter hook, between TF3 shadow and `backtester.run`):
```python
if _TF4_CFG.is_active:
    try:
        _tf4_kwargs = {}
        if _TF4_CFG.mode in ("STRENGTH_FILTER", "HYBRID_TOPK_STRENGTH"):
            _tf4_kwargs["strength_quantile"] = _TF4_CFG.strength_quantile
        if _TF4_CFG.mode in ("TOP_K_PER_BAR", "HYBRID_TOPK_STRENGTH"):
            _tf4_kwargs["top_k"] = _TF4_CFG.top_k
        _tf4_res = _tf4_apply(
            signals, sizes,
            profile=_TF4_PROFILE_MAP[_TF4_CFG.mode],
            strength=sizes,
            **_tf4_kwargs,
        )
        signals = _tf4_res.signals
        sizes = _tf4_res.sizes
        _tf4_entered_total += _tf4_res.entered_count
        _tf4_kept_total += _tf4_res.kept_count
        _tf4_skipped_total += _tf4_res.skipped_count
    except Exception as _tf4_e:
        log.debug(f"[tf4] pre-filter failed ({alpha_hash}): {_tf4_e}")
```

**Edit 4** (telemetry attachment, before `_emit_a1_batch_metrics_from_stats_safe`):
```python
if _TF4_CFG.is_active:
    _b1_aggregate_metrics["aggregation_mode"] = _TF4_CFG.mode
    _b1_aggregate_metrics["aggregation_skipped_count_total"] = _tf4_skipped_total
    _b1_aggregate_metrics["aggregation_kept_count_total"] = _tf4_kept_total
    _b1_aggregate_metrics["aggregation_entered_count_total"] = _tf4_entered_total
    _b1_aggregate_metrics["aggregation_params"] = {
        "strength_quantile": _TF4_CFG.strength_quantile,
        "top_k": _TF4_CFG.top_k,
    }
```

## Order of execution per alpha
```
generate_alpha_signals(...)
    ↓
[TF3 shadow] (only when ARENA_TF3_SHADOW=1; runs on ORIGINAL signals)
    ↓
[TF4 pre-filter] (only when ARENA_AGGREGATION_MODE != OFF; mutates signals/sizes references)
    ↓
backtester.run(signals, sizes, ...) [unchanged validation]
```

The order matters: TF3 shadow runs **before** TF4 pre-filter so shadow profiles always compare against the **unfiltered** baseline (otherwise shadow would be measuring relative to the pre-filtered signals, which would obscure the comparison signal).

## Default-OFF guarantee
With unset `ARENA_AGGREGATION_MODE`:
- `_TF4_CFG.is_active` evaluates to `False`
- All 4 hook gates short-circuit
- `signals`/`sizes` references are NOT reassigned
- `_b1_aggregate_metrics` dict has identical schema to pre-TF4
- **Bit-for-bit identical to pre-TF4 baseline path**

Verified by:
- TF4 test #1: `_TF4_CFG.is_active is False` when env unset → branch taken yields identical arrays
- Targeted regression suite: 194 PASS (3 skipped) when MODE=OFF (default)

## STOP-conditions check (Phase 4 spec)
| STOP cause | Status |
|---|---|
| Patch affects validation | ❌ no — `entry_rank_threshold` etc. unchanged; `generate_alpha_signals` call unchanged |
| Patch changes baseline behavior | ❌ no — when MODE=OFF, `_TF4_CFG.is_active` is False → all 4 gates no-op |
| Patch alters pass/fail counts | ❌ no — `passed_count`, `rejected_count`, `entered_count` (alpha-level) untouched |
| Refactor of existing logic | ❌ no — purely additive |
| Mutation of signal objects | ✅ documented — when ACTIVE, `signals` and `sizes` are **reassigned** to filtered copies (apply_signal_aggregation always returns new arrays); originals not mutated, just dropped from the local scope |

✅ **No STOP triggered.**

## Verdict
**PHASE_4_COMPLETE** — minimal additive patch (+60 LOC) within budget; default OFF preserves bit-equivalent baseline; production pre-filter activated only when env explicitly opts in.

## Next
Phase 5 — pytest verification (6 required + targeted regression).
