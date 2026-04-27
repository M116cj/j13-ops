# 01 — Telemetry Writer Trace (Subprogram B2)

## Static call graph

```
arena_pipeline.py:311  _telemetry_counters = {12 keys, all init = 0}
arena_pipeline.py:326  _last_telemetry_flush_ts = 0.0
arena_pipeline.py:385  async def _flush_telemetry(db):
                           if elapsed < 300s: return
                           rows = [(run_id, worker_id, strategy_id, k, v) for k, v in counters.items()]
                           await db.executemany('INSERT INTO engine_telemetry ...', rows)
                           _last_telemetry_flush_ts = now
                           # NOTE: counters NEVER reset → cumulative semantics
                       except Exception: pass
arena_pipeline.py:1334 _telemetry_counters['admitted_count'] += 1   ← only inside champion-success block
arena_pipeline.py:1336 _telemetry_counters['rejected_count'] += 1   ← only inside champion-success block
arena_pipeline.py:1337 await _flush_telemetry(db)                   ← only inside champion-success block
```

## Counter wiring matrix

| Counter key | Has incrementer? | Where? |
|---|---|---|
| compile_success_count | ❌ NO | nowhere |
| compile_exception_count | ❌ NO | nowhere (`stats["alpha_compile_errors"] += 1` at L998 is a separate dict) |
| evaluate_success_count | ❌ NO | nowhere |
| evaluate_exception_count | ❌ NO | nowhere |
| indicator_terminal_call_count | ❌ NO | nowhere |
| indicator_terminal_exception_count | ❌ NO | nowhere |
| cache_hit_count | ❌ NO | nowhere (`stats["bloom_hits"]` at L1044 is separate; not the same metric) |
| cache_miss_count | ❌ NO | nowhere |
| nan_inf_count | ❌ NO | nowhere |
| zero_variance_count | ❌ NO | nowhere (`stats["reject_val_constant"]` at L1116 is separate dict) |
| **admitted_count** | ✅ YES | arena_pipeline.py:1334 (inside champion-success path) |
| **rejected_count** | ✅ YES | arena_pipeline.py:1336 (inside champion-success path) |

**Of the 12 declared counters, 10 are dead code** — initialized but never incremented anywhere in the codebase. Only `admitted_count` and `rejected_count` ever change from 0, and even those only fire when an alpha makes it all the way through A1's 9-stage gate chain to the DB INSERT block.

(The `fresh_pool_process_health` view's CHECK-constraint metric_name list at `engine_telemetry.valid_telemetry_metric` includes 14 names — adding `round_duration_ms` and `population_size` to the dict's 12 — but these too are absent from the runtime increment sites.)

## Caller graph

```
_flush_telemetry callers:
    arena_pipeline.py:1337  inside the champion-success try block
                            → fires only when:
                                a) alpha passed A1 fitness (train_neg_pnl ✓)
                                b) alpha passed all val gates (val_few/val_neg/val_sharpe/val_wr ✓)
                                c) alpha passed combined_sharpe ≥ 0.4 ✓
                                d) DB INSERT into champion_pipeline_staging succeeded
                                e) admission_validator returned a verdict
```

In the last 6.5 days the conjunction (a) ∧ (b) ∧ (c) ∧ (d) ∧ (e) has been **false 100% of the time** (carry-forward: `zangetsu_status.deployable_count = 0`, last admission `2026-04-21 04:34:21Z`). Therefore `_flush_telemetry()` has not been called once in the current runtime cohort.

## DB writer schema

```
INSERT INTO engine_telemetry (run_id, worker_id, strategy_id, metric_name, value)
VALUES (, , , , )
```

Where metric_name is constrained by:

```
CHECK (metric_name = ANY (ARRAY[
  'compile_success_count', 'compile_exception_count',
  'evaluate_success_count', 'evaluate_exception_count',
  'indicator_terminal_call_count', 'indicator_terminal_exception_count',
  'cache_hit_count', 'cache_miss_count',
  'nan_inf_count', 'zero_variance_count',
  'admitted_count', 'rejected_count',
  'round_duration_ms', 'population_size'
]))
```

The CHECK constraint declares 14 valid metrics; the writer dict at L311 declares 12; the increment sites populate only 2.

## Process-health view dependency

`fresh_pool_process_health` view (definition extracted from `\d+ fresh_pool_process_health`):

- Reads `engine_telemetry` rows where `ts > NOW() - INTERVAL '1 hour'`
- Aggregates by `strategy_id`
- Outputs: compile_exception_count, evaluate_exception_count, indicator_terminal_exception_count, cache_hit_rate (derived from cache_hit/cache_miss), nan_inf_count, zero_variance_count, admitted_rate, rejected_rate (derived from admitted/rejected)

Because `engine_telemetry` has 0 rows, the view's `FROM` clause sub-query yields no rows → the view itself returns 0 rows.

## Equivalent observability via JSONL

The per-batch `arena_batch_metrics` event in `zangetsu/logs/engine.jsonl` provides:
- entered_count, passed_count, rejected_count, skipped_count, error_count, in_flight_count
- pass_rate, reject_rate
- top_reject_reason, reject_reason_distribution (richer than admitted/rejected counts)
- generation_profile_id, generation_profile_fingerprint
- timestamp_start, timestamp_end
- **plus B1's new aggregate_metrics + aggregate_metrics_availability** (since PR #55):
  - 15 numeric/identifier keys (gross_pnl, net_pnl, cost, sharpe, total_trades, signal_density, etc.)
  - 21 availability flags

This JSONL stream is **a strict superset** of what engine_telemetry would carry, and it fires **per batch** (~16 batches/min observed), not per champion-success event.

## Conclusion of trace

The engine_telemetry writer is structurally correct (the SQL is fine, the schema is fine), but it is **gated by the wrong precondition**: the only call site fires only on champion-success, which has not occurred since 2026-04-21. Even if the gating were fixed, 10 of 12 counters are dead code and would emit zeros.

The arena_batch_metrics JSONL stream already provides equivalent and superior observability and is actively populated. **engine_telemetry is functionally obsolete** under the current pipeline shape.
