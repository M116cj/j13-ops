# P7-PR4-LITE — Counter Conservation Invariant

## 1. Invariant statement

For each `ArenaStageMetrics` record the following must hold:

### Closed stage (batch finished, emitted as `arena_batch_metrics`)

```
entered_count = passed_count + rejected_count + skipped_count + error_count
in_flight_count = 0
```

### Open / streaming stage (not yet closed)

```
entered_count = passed_count + rejected_count + skipped_count + error_count + in_flight_count
in_flight_count >= 0
```

All counters must be non-negative integers.

## 2. Enforcement

`arena_pass_rate_telemetry.validate_counter_conservation(metrics)` returns
`(ok: bool, reason: str)` and is called by every builder and accumulator
close path. Violations are logged and routed to the
`COUNTER_INCONSISTENCY` rejection bucket rather than raised, so a
counter-level bug never alters Arena runtime behavior.

## 3. Accumulator API

`ArenaStageMetrics` exposes:

- `on_entered(n=1)` — increments `entered_count` and `in_flight_count`.
- `on_passed(n=1)` — decrements `in_flight_count`, increments `passed_count`.
- `on_rejected(reason, n=1)` — decrements `in_flight_count`, increments
  `rejected_count`, and records the canonical reason.
- `on_skipped(n=1)`, `on_error(n=1)` — symmetric.
- `mark_closed()` — drains any residual `in_flight_count` into
  `error_count` defensively and sets `closed=True`.

Each transition preserves the open-stage invariant. `mark_closed()`
re-establishes the closed-stage invariant.

## 4. Residual handling

The zero-intrusion helper
`_emit_a1_batch_metrics_from_stats_safe(...)` computes `rejected_count` from
the sum of the canonical reason bucket; any residual (i.e. `entered_count -
passed_count - rejected_count`) is attributed to `COUNTER_INCONSISTENCY`
rather than silently absorbed. This keeps the invariant explicit and
measurable.

## 5. Tests

- `test_closed_stage_counter_conservation`
- `test_closed_stage_rejects_nonzero_in_flight`
- `test_open_stage_counter_conservation_with_in_flight`
- `test_counter_conservation_rejects_invalid_counts`
- `test_counter_conservation_rejects_negative_counter`
- `test_arena_stage_metrics_accumulator_preserves_conservation`
- `test_arena_stage_metrics_drains_in_flight_on_close`

All PASS.

## 6. Non-goals

- No faked precision: when `skipped_count` / `error_count` cannot be
  determined, the helper uses `0` only if that is logically valid. If not,
  the residual is routed to `COUNTER_INCONSISTENCY`.
- Conservation does not imply semantic correctness; it only implies that
  counts add up. Arena pass/fail logic itself is **not** touched.
