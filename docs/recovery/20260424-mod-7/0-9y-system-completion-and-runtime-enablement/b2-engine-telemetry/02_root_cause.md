# 02 — Root Cause (Subprogram B2)

## Two distinct failures

### Failure 1 — flush gating

`_flush_telemetry(db)` is called **only** inside the champion-success path at `arena_pipeline.py:1337`. Since v0.7.1 deployment (2026-04-20) the system has produced 0 new champions, so the call has not fired. Result: 0 INSERTs into `engine_telemetry`.

**Why it was wired this way:** the original v0.7.1 governance design assumed champions would be produced periodically (the `fresh_pool_process_health` view's 1-hour rolling window suggests that expectation). When the alpha generation entered `feature_space_exhaustion` mode (per 0-9X-PIPELINE-DEPLOYABLE-FLOW-DIAGNOSIS), the gating became a permanent blocker.

### Failure 2 — counter wiring gap

10 of the 12 `_telemetry_counters` keys are never incremented:

```
compile_success_count, compile_exception_count,
evaluate_success_count, evaluate_exception_count,
indicator_terminal_call_count, indicator_terminal_exception_count,
cache_hit_count, cache_miss_count,
nan_inf_count, zero_variance_count
```

The corresponding runtime concepts ARE counted in the local `stats` dict (e.g., `stats["alpha_compile_errors"]`, `stats["reject_val_constant"]`, `stats["bloom_hits"]`), but those increments populate a different dict — never the `_telemetry_counters` dict that `_flush_telemetry()` reads.

This is an apparent design intent that was not completed: the counter dict was declared, the flush was wired, but the per-event increment lines were never written.

## Why this rises to v0.7.1's process-health gap

The v0.7.1 dual-evidence governance design (per 0-9X-CANARY readiness review) requires both an *outcome* health view (`fresh_pool_outcome_health` — works) and a *process* health view (`fresh_pool_process_health` — fed by engine_telemetry → currently empty).

With `engine_telemetry` empty, the dual-evidence design has only the outcome side functional. The process-health view exists but always returns 0 rows.

## Why JSONL is the canonical telemetry now

Three reasons:

1. **Coverage:** `arena_batch_metrics` JSONL provides 15 numeric metrics + 21 availability flags + 4 identifiers per batch (after B1). Compare to engine_telemetry's 12 declared / 2 wired metrics.

2. **Frequency:** JSONL emits ~16 batches/min (verified by Phase 1 of 0-9X-CANARY-READINESS-REVIEW). engine_telemetry's flush is throttled to 5 min AND gated on champion success.

3. **Already deployed:** PR #50 (per-round delta accounting) + PR #49 (taxonomy fix) + PR #55 (B1 aggregate_metrics) have all been verified live on the JSONL stream. A consumer migrating to JSONL needs no schema change.

## Path-forward classification

| Path | Description | Effort | Risk |
|---|---|---|---|
| A — Move flush outside champion block | Single line move; ~2 LOC change | Low | Low (per-round flush throttled internally to 5 min, harmless) |
| B — Wire up the 10 dead counters | Add 10 increment sites in arena_pipeline.py compile/evaluate/indicator/cache paths | Medium | Medium (touches hot path, could affect performance) |
| C — Declare engine_telemetry obsolete in favor of JSONL | Docs only | Minimal | None |
| D — Drop engine_telemetry table + view | DB schema change | Medium | High (forbidden in B2 scope; v0.7.1 governance migration) |

## Selected path

**Path C — declare engine_telemetry obsolete in favor of JSONL canonical.**

Rationale:
- Path C is docs-only; no source code change; no DB change; no runtime behavior change
- Path A would persist 12 rows of mostly zeros every 5 min — pure log noise
- Path B would need careful performance review of the hot path, plus tests for each of 10 new increment sites — out of B2's lean scope
- Path D is forbidden (DB schema migration not justified)
- The JSONL stream is already the canonical telemetry surface; this PR codifies that fact and unblocks future orders that depend on observability

The next-recommended sub-orders for the future paths:

```
TEAM ORDER 0-9Y-B2A-FLUSH-GATING-PATCH         (path A, optional follow-up)
TEAM ORDER 0-9Y-B2B-PROCESS-COUNTER-WIRING     (path B, optional follow-up)
TEAM ORDER 0-9Y-B2D-ENGINE-TELEMETRY-RETIRE    (path D, requires constitution amendment)
```

None of these are required to unblock the master 0-9Y program — Subprogram C only needs the JSONL stream + B1's new aggregate fields.
