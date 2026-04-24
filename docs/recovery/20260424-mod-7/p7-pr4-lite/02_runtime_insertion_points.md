# P7-PR4-LITE — Runtime Insertion Points

All runtime changes are additive, exception-safe, non-blocking, and
behavior-invariant. The only modified runtime file is
`zangetsu/services/arena_pipeline.py`, authorized under the 0-9M
`EXPLAINED_TRACE_ONLY` pathway.

## 1. Module import + helper block

**File**: `zangetsu/services/arena_pipeline.py`
**Lines**: ~95–145 (module-level, right after existing imports)

Added:

- `try: from zangetsu.services.arena_pass_rate_telemetry import ...` with
  `_ARENA_PASS_RATE_TELEMETRY_AVAILABLE` flag.
- `_make_a1_batch_metrics_safe(*, run_id, batch_id)` — returns a new
  `ArenaStageMetrics` accumulator (or `None`). Never raises.
- `_emit_a1_batch_metrics_safe(accumulator, *, deployable_count, log)` —
  closes accumulator and emits an `arena_batch_metrics` event. Never raises.
- `_emit_a1_batch_metrics_from_stats_safe(*, run_id, batch_id, entered_count,
  passed_count, stats, log)` — zero-intrusion wrapper: builds + emits an
  event directly from the existing `stats` dict used by `arena_pipeline`.

Canonical reason mapping is delegated to
`arena_rejection_taxonomy.classify()`.

Residuals that imply counter inconsistency are routed to
`COUNTER_INCONSISTENCY` rather than raising.

## 2. A1 batch emission call site

**File**: `zangetsu/services/arena_pipeline.py`
**Line**: ~1142 (immediately after the existing round-close log line)

```python
# P7-PR4-LITE: aggregate A1 batch pass-rate telemetry.
# Zero-intrusion: derives entered_count / passed_count from existing
# `len(alphas)` and `round_champions`; rejection distribution from
# `stats[reject_*]`. Emission is exception-safe — emitter failure
# cannot alter Arena decisions above. The _pb provenance bundle
# provides run_id where available.
_emit_a1_batch_metrics_from_stats_safe(
    run_id=getattr(_pb, "run_id", "") or "",
    batch_id=f"R{round_number}-{sym}-{regime}",
    entered_count=len(alphas),
    passed_count=round_champions,
    stats=stats,
    log=log,
)
```

**Zero-intrusion guarantees**:

- No new variables introduced before this call.
- `len(alphas)`, `round_champions`, and `stats` already exist in scope.
- No change to Arena pass/fail branching above this line.
- `_pb.run_id` access is `getattr(..., "")` — missing attribute does not raise.

## 3. A2 / A3 insertion plan

A2 / A3 orchestrators (`arena23_orchestrator.py`, `arena45_orchestrator.py`)
are **not modified in P7-PR4-LITE**. The module-level helper block is
stage-agnostic and supports A2 / A3 wiring in a subsequent trace-only order
without further changes to `arena_pass_rate_telemetry.py`.

## 4. What was not changed

- No threshold file touched.
- No champion promotion code touched.
- No `deployable_count` semantics change.
- No execution / capital / risk code touched.
- No service restart.
- No CANARY activation.
- No production rollout.

## 5. Controlled-diff classification

`config.arena_pipeline_sha` changes from
`888e2fdd4b4af5f6f6523256462d02ba012dafa64c968663fd6d8225bc749142` to
`30e66a9d4a14f248e7dde9d2512ec4c577b43667c22a3e08a222fc2c93cd980f`, which is
authorized via `--authorize-trace-only config.arena_pipeline_sha` and
classifies as **EXPLAINED_TRACE_ONLY** (0-9M pathway).
