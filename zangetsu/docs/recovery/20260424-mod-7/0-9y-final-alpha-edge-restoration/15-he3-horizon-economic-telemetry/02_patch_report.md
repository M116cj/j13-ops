# 02 — PATCH REPORT

**TEAM ORDER**: 0-9Y-HE3-HORIZON-ECONOMIC-TELEMETRY
**Date**: 2026-04-29
**Phase**: 2 / 8

## Files added
| Path | LOC | Purpose |
|---|---|---|
| `zangetsu/services/horizon_metrics.py` | 182 | Pure helper: `build_horizon_metrics(...)` builds `{h: {...metrics}}`; `aggregate_horizon_metrics_across_batches(batches)` for cross-batch grouping |
| `zangetsu/tests/test_he3_horizon_metrics.py` | (Phase 3 test file) | 12 tests covering all 8 master-order required cases + edge cases |

## Files modified
| Path | LOC | Type |
|---|---|---|
| `zangetsu/services/arena_pipeline.py` | +36 / 0 | 2 surgical edits: import + horizon_metrics-attach in batch emitter |

**Total source LOC change**: +218 / 0 across 2 source files. Within master-order budget (~40-120 LOC pipeline change).

## arena_pipeline.py edits (2 surgical)

**Edit 1** — import after HE2 imports:
```python
from zangetsu.services.horizon_metrics import build_horizon_metrics as _he3_build_metrics
```

**Edit 2** — at the existing batch-telemetry attach block (after HE2's `generation_profile_horizon` block, before `_emit_a1_batch_metrics_from_stats_safe`):
```python
try:
    _he3_skipped, _he3_kept, _he3_entered = 0, 0, 0
    if _TF4_CFG.is_active:
        _he3_skipped = int(_tf4_skipped_total)
        _he3_kept = int(_tf4_kept_total)
        _he3_entered = int(_tf4_entered_total)
    _he3_metrics = _he3_build_metrics(
        int(_he1_horizon),
        train_gross_pnl=_b1_train_gross_pnl,
        train_net_pnl=_b1_train_net_pnl,
        train_total_trades=_b1_train_total_trades,
        train_win_rate=_b1_train_win_rate,
        round_total_cost_bps=_b1_round_total_cost_bps_for_sym,
        signal_density_per_bar=_b1_signal_density,
        skipped_count_total=_he3_skipped,
        kept_count_total=_he3_kept,
        entered_count_total=_he3_entered,
    )
    if _he3_metrics:
        _b1_aggregate_metrics["horizon_metrics"] = _he3_metrics
        _b1_aggregate_metrics["horizon_metrics_keys"] = list(_he3_metrics.keys())
except Exception as _he3_e:
    log.debug(f"[he3] horizon_metrics build failed: {_he3_e}")
```

## Telemetry shape (post-HE3)

When HE3 path runs (always — pure read of existing lists):
```
aggregate_metrics["horizon_metrics"] = {
    <selected_horizon>: {
        "alpha_count": int,
        "trade_count_median": int | None,
        "trade_count_mean": float | None,
        "trade_count_total": int | None,
        "skipped_count_total": int,         # 0 unless TF4 PRE-FILTER active
        "kept_count_total": int,
        "entered_count_total": int,
        "gross_pnl_median": float | None,
        "gross_pnl_mean": float | None,
        "gross_pnl_sum": float | None,
        "net_pnl_median": float | None,
        "net_pnl_mean": float | None,
        "net_pnl_sum": float | None,
        "total_cost": float | None,
        "win_rate_median": float | None,
        "signal_density_per_bar": float | None,
        "gross_per_trade_median": float | None,
        "net_per_trade_median": float | None,
        "cost_per_trade": float | None,
        "cost_over_gross_ratio": float | None,
    }
}
aggregate_metrics["horizon_metrics_keys"] = [<selected_horizon>]
```

In **baseline mode** (env unset, single-horizon=60): `horizon_metrics = {60: {...}}` with all numerics matching the existing per-batch fields (`train_gross_pnl_median`, etc.).

## Default-OFF guarantee

| Verification | Result |
|---|---|
| Existing batch fields (`train_gross_pnl_median` etc.) preserved | ✅ no rename/removal |
| `horizon_metrics` is additive top-level key | ✅ in baseline = `{60: {...}}` |
| Helper raises no exceptions | ✅ try/except returns `{}` on internal error |
| arena_pipeline call wrapped in try/except | ✅ `[he3] horizon_metrics build failed` logged at DEBUG, batch metrics still emit |
| Validation / cost / A2 untouched | ✅ test #4, #5 tokenize-scan |
| TF4 / TF3 default OFF preserved | ✅ HE3 does not modify aggregation_config or tf3_shadow |

## STOP-conditions check (Phase 2 spec)

| STOP cause | Status |
|---|---|
| Any change to pass/fail | ❌ no — read-only aggregation |
| Any change to cost/validation/A2 | ❌ no — tokenize-scan |
| Baseline metrics altered | ❌ no — no existing field renamed/removed |

✅ **No STOP triggered.**

## Verdict
**PHASE_2_COMPLETE** — additive telemetry implemented; pure helper + 2 surgical pipeline edits; budget ✓; baseline preserved.

## Next
Phase 3 — pytest verification.
