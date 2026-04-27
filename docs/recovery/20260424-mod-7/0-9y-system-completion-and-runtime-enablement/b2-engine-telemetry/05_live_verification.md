# 05 — Live Verification (Subprogram B2)

## Live state

| DB query | Result | Interpretation |
|---|---|---|
| `SELECT COUNT(*) FROM engine_telemetry` | **0** (verified 18:21Z, identical to all prior captures) | engine_telemetry remains empty by design (champion-gated flush + 10 dead counters) |
| `SELECT * FROM fresh_pool_process_health` | 0 rows | view depends on engine_telemetry; cannot return rows when source is empty |
| `SELECT * FROM fresh_pool_outcome_health` | 1 row (j01: 89 fresh, 0 deployable, 0 indicator usage) | outcome side is populated and accurate |
| Last 100 `arena_batch_metrics` JSONL events | 100 events; CI=0, UNKNOWN_REJECT=0, residual={0:100} | JSONL canonical telemetry is healthy and current |

## Behavior consistency check

The B2 verdict claims:
- engine_telemetry obsolete in favor of JSONL canonical
- no source change → 0 row count is expected to remain

Re-query `SELECT COUNT(*) FROM engine_telemetry` post-PR (after merge + Alaya converge): expected to remain 0. If it changes (rows appear), this would indicate that some other code path also writes to the table — which would falsify the static call-graph trace in 01_telemetry_writer_trace.md.

## What changes after this PR merges

- engine_telemetry table: still 0 rows (no behavior change)
- fresh_pool_process_health view: still empty (no behavior change)
- arena_batch_metrics JSONL: continues to emit normally (~16 batches/min, residual=0)
- Documentation: a clear declaration that JSONL is canonical

## Restart not needed

This subprogram does not modify runtime code. No worker restart is required for B2 to take effect — its effect is documentation-only.

(Note: workers ARE still pre-B1 source mtime; restarting them to pick up B1's aggregate_metrics emit fields is a separate authorization scoped to B1 / Subprogram C live-data dependency. B2 verdict is independent.)
