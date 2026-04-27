# 03 — Conservation Verification (Phase 4)

**Phase 4 Verdict:** `CONSERVATION_PASS`

## Conservation identity

Per arena_batch_metrics emit semantics, every batch must satisfy:

```
entered_count = passed_count + sum(reject_reason_distribution.values()) + skipped_count
```

Equivalently, the residual `r = entered − passed − rejected − skipped` must be 0 for every batch.

Pre-fix bug: `stats[reject_*]` was worker-lifetime cumulative while `entered_count` was per-round; after warmup, residual went strongly negative and `abs(residual)` was deposited into a synthetic `COUNTER_INCONSISTENCY` bucket on every emit (≈50% of A1 reject distribution). PR #50 introduces `_compute_a1_reject_deltas(current_stats, prev_snapshot, stats_keys) → (deltas, new_snapshot)` that publishes per-round increments against a per-process snapshot, restoring the identity.

## Parser

Source: `/tmp/0_9x_post_restart_new_engine.jsonl` (96 events with `event_type=arena_batch_metrics`)

For each batch:
```
entered  = obj['entered_count']            # canonical
passed   = obj['passed_count']             # canonical
skipped  = obj['skipped_count']            # canonical
rejected = sum(reject_reason_distribution.values())
declared_rejected = obj['rejected_count']  # canonical (also published)
residual = entered − passed − rejected − skipped
```

Field names verified against actual emitted JSON; no parser ambiguity.

## Aggregate result

| Metric | Value |
|---|---|
| total batches parsed | **96** |
| bad batches (residual ≠ 0 OR CI ≠ 0 OR UNKNOWN_REJECT ≠ 0) | **0** |
| `COUNTER_INCONSISTENCY` total across all batches | **0** |
| `UNKNOWN_REJECT` total across all batches | **0** |
| `residual` value set across all batches | `{0}` |
| `rejected_count − sum(distribution)` value set | `{0}` |
| `entered_count` range | `[10, 10]` |
| `passed_count` range | `[0, 0]` |
| reject reasons union | `{COST_NEGATIVE, LOW_BACKTEST_SCORE, SIGNAL_TOO_SPARSE}` |

## First three rows

```
ts=2026-04-27T17:04:02Z batch=R271801-LINKUSDT-BULL_TREND
  entered=10 passed=0 rejected_sum=10 rejected_declared=10 skipped=0 residual=0
  CI=0 UNKNOWN=0  top=[(COST_NEGATIVE, 10)]

ts=2026-04-27T17:04:02Z batch=R417101-SOLUSDT-BULL_TREND
  entered=10 passed=0 rejected_sum=10 rejected_declared=10 skipped=0 residual=0
  CI=0 UNKNOWN=0  top=[(COST_NEGATIVE, 10)]

ts=2026-04-27T17:04:15Z batch=R417102-AAVEUSDT-BULL_TREND
  entered=10 passed=0 rejected_sum=10 rejected_declared=10 skipped=0 residual=0
  CI=0 UNKNOWN=0  top=[(COST_NEGATIVE, 10)]
```

## Bad rows

None. The parser inserted into `bad` any row with `residual ≠ 0`, `COUNTER_INCONSISTENCY ≠ 0`, or `UNKNOWN_REJECT ≠ 0`. The list is empty.

## Pass-criteria checklist

| Criterion | Status |
|---|---|
| ≥ 5 new batches parsed after patched workers active | ✅ 96 |
| `COUNTER_INCONSISTENCY` total = 0 (or proven edge-case) | ✅ 0 |
| `UNKNOWN_REJECT` total = 0 (or explainable raw-unknown) | ✅ 0 |
| `residual` = 0 for parsed batches | ✅ residual set = {0} |
| canonical buckets visible if rejects occurred | ✅ COST_NEGATIVE, SIGNAL_TOO_SPARSE, LOW_BACKTEST_SCORE — all canonical `RejectionReason` enum members |

## Phase 4 Classification

```
CONSERVATION_PASS
```

## Note on field ambiguity

No parser-field ambiguity was encountered. The arena_batch_metrics schema (see `zangetsu/services/arena_pass_rate_telemetry.py: build_arena_batch_metrics`) uses canonical names `entered_count` / `passed_count` / `rejected_count` / `skipped_count` / `reject_reason_distribution`, all present in every emit.
