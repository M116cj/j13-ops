# 03 — Test Report (Subprogram B1)

## Test runs

### B1 specific tests

`tests/test_b1_aggregate_metrics_exposure.py` — 10 tests covering:

1. `test_b1_arena_batch_metrics_defaults_none` — defaults are None on the frozen event ✅
2. `test_b1_arena_stage_metrics_defaults_none` — defaults are None on the accumulator ✅
3. `test_b1_builder_passes_none_when_unset` — None flows through if accumulator never sets fields ✅
4. `test_b1_builder_passes_populated_aggregates` — populated values flow through verbatim ✅
5. `test_b1_to_dict_includes_new_fields` — `to_dict()` includes the new fields ✅
6. `test_b1_to_json_round_trip_preserves_aggregates` — JSON round-trip preserves values ✅
7. `test_b1_to_json_round_trip_with_none_aggregates` — JSON serializes None as null cleanly ✅
8. `test_b1_conservation_holds_with_aggregates_present` — entered = passed + rejected + skipped still holds ✅
9. `test_b1_conservation_holds_with_aggregates_none` — same when aggregates absent ✅
10. `test_b1_emit_wrapper_signature_accepts_aggregates` — wrapper signature has the new kwargs with None defaults ✅

```
============================== 10 passed in 0.57s ==============================
```

### Pre-existing telemetry test sweep (regression)

```
$ .venv/bin/python -m pytest tests/test_arena_batch_metrics_accounting.py \
    tests/test_a2_a3_arena_batch_metrics.py \
    tests/test_arena_pass_rate_telemetry.py \
    tests/test_b1_aggregate_metrics_exposure.py -q

........................................................................ [ 64%]
........................................                                 [100%]
112 passed in 0.68s
```

**102 pre-existing tests + 10 new B1 tests = 112 total, 0 failures.**

Key tests covered by the regression sweep:
- `test_arena_batch_metrics_accounting.py` — PR #50 conservation tests (the original COUNTER_INCONSISTENCY accounting fix tests)
- `test_arena_pass_rate_telemetry.py` — telemetry schema tests (A2_MIN_TRADES sanity, reject reason counter, builder semantics)
- `test_a2_a3_arena_batch_metrics.py` — A2/A3 arena_batch_metrics emit path tests

If any of these had broken, the conservation invariant or schema would be at risk; all green.

### Tests intentionally not run

- The full A1 worker integration test path requires the live arena_pipeline runtime; this is exercised in `04_live_sample.md` post-restart.
- Existing tests outside the telemetry surface (e.g., `test_watchdog_cold_boot.py`) are not in B1's scope and were not modified.

## Pass criteria check

| Master-order pass criterion | Status |
|---|---|
| telemetry includes new fields | ✅ |
| null availability flags work | ✅ |
| pass/fail result unchanged | ✅ (no decision-changing code modified) |
| no validation threshold changes | ✅ (verified in 05_controlled_diff_report.md) |
| existing telemetry conservation still passes | ✅ (PR #50 tests + new B1 conservation tests both green) |

All five criteria met.
