# 02 — Source Write-Path Trace

## 1. Function Inventory

| Stage | Function / line | Purpose |
| --- | --- | --- |
| Generation loop | `async def main()` at `zangetsu/services/arena_pipeline.py:411` | top-level coroutine |
| Candidate evaluation | `engine.compile_alpha` + `backtester.run` (lines 909-948) | compile / backtest each alpha |
| Train-side rejection | line 965 (`bt.total_trades < 30`) | first cliff: `reject_few_trades` |
| Holdout-side validation | lines 985-1020 (val backtest using holdout split) | OOS validation |
| Holdout-side rejection cliffs | lines 1021-1037 | 5 reject paths |
| Build passport | lines 1063-1099 | metadata bundle |
| Persistence: provenance bundle | line 1116: `_pb = _get_or_build_provenance(...)` | **only set if all val gates passed** |
| INSERT INTO champion_pipeline_staging | lines 1117-1158 | 23-column INSERT with `status='ARENA1_COMPLETE'` |
| admission_validator | line 1160: `SELECT admission_validator($1)` | promotes staging → fresh |
| _flush_telemetry | line 1167 | engine_telemetry per round |
| Per-round batch metrics emit | line 1218: `_emit_a1_batch_metrics_from_stats_safe(run_id=getattr(_pb, "run_id", "") or "", ...)` | **CRASH SITE** |

## 2. Target Table for First Materialized Write

`INSERT INTO public.champion_pipeline_staging (...) RETURNING id`, then `SELECT admission_validator(staging_id)`. Verdict `'admitted'` writes a copy into `champion_pipeline_fresh` via the validator.

## 3. Preconditions Before INSERT (val-filter chain)

| # | Filter | Gate |
| --- | --- | --- |
| 1 | alpha→signal compile success | exception → `continue` |
| 2 | backtest (train) success | exception → `continue` |
| 3 | `bt.total_trades >= 30` | `reject_few_trades` |
| 4 | val signal std >= 1e-10 | `reject_val_constant` |
| 5 | val backtest success | `reject_val_error` |
| 6 | `bt_val.total_trades >= 15` | `reject_val_few_trades` |
| 7 | `bt_val.net_pnl > 0` | `reject_val_neg_pnl` |
| 8 | `bt_val.sharpe_ratio >= 0.3` | `reject_val_low_sharpe` |
| 9 | `wilson_lower(val_winning, val_total) >= 0.52` | `reject_val_low_wr` |

ALL 9 must pass for `_pb` to be built and INSERT to run.

## 4. Critical Source Bug: `_pb` Scope Issue

`_pb` is only assigned at line 1116 inside the per-alpha block, after all 9 val gates pass. There is NO other assignment of `_pb` in the function.

After the inner `for alpha in alphas:` loop ends, the per-round telemetry emit at line 1218 unconditionally references `_pb`:

```python
_emit_a1_batch_metrics_from_stats_safe(
    run_id=getattr(_pb, "run_id", "") or "",
    batch_id=f"R{round_number}-{sym}-{regime}",
    entered_count=len(alphas),
    passed_count=round_champions,
    ...
)
```

If no alpha in the round passes all 9 val gates, `_pb` was never assigned in any iteration. Python's local-variable lookup raises `UnboundLocalError` before `getattr` runs (because `_pb` is detected as a local in this function — the slot exists but was never filled).

This is the exact crash site that kills the asyncio `main` coroutine every cron cycle.

## 5. Phase 2 Classification

Per order §7:

| Verdict | Match? |
| --- | --- |
| WRITE_PATH_PRESENT_AND_REACHABLE | NO (loop crashes before any candidate passes all gates) |
| WRITE_PATH_PRESENT_BUT_GATED (val filters too strict) | partial (filters are strict but not the root cause) |
| **WRITE_PATH_PRESENT_BUT_NOT_CALLED** | **YES — closest match** (write code exists, but loop crashes before any successful round-emit + INSERT pair runs) |
| WRITE_PATH_DISABLED_BY_CONFIG | NO |
| WRITE_PATH_EXCEPTION_SWALLOWED | NO (exception kills asyncio.run, not suppressed) |
| WRITE_PATH_MISSING | NO |
| WRITE_PATH_UNKNOWN | NO |

→ **Phase 2 verdict: WRITE_PATH_PRESENT_BUT_NOT_CALLED.** Python source bug at line 1218 crashes the round-end batch-metrics emit before any candidate INSERT ever has the chance to run successfully.
