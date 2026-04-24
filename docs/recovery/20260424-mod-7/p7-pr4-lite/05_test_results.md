# P7-PR4-LITE — Test Results

## 1. Baseline (before P7-PR4-LITE)

Run against `origin/main` SHA `6b718411f0aca57fadf396e4d86edece7b073bb1`
(0-9N merge):

```
$ python3 -m pytest zangetsu/tests/ \
    --ignore=zangetsu/tests/policy/test_exception_overlay.py \
    --tb=no -q
3 failed, 169 passed, 3 skipped, 1 warning in 0.58s
```

The 3 failures are **pre-existing** (`test_integration.py::test_db /
test_checkpoint / test_console_api` — async support requires a
`pytest-asyncio` plugin not installed in this environment; unrelated to
P7-PR4-LITE).

The module-level `sys.exit(...)` in
`zangetsu/tests/policy/test_exception_overlay.py` is also pre-existing and
is excluded via `--ignore`.

Baseline pinned for invariance: **169 pass**.

## 2. After P7-PR4-LITE

```
$ python3 -m pytest zangetsu/tests/ \
    --ignore=zangetsu/tests/policy/test_exception_overlay.py \
    --ignore=zangetsu/tests/test_integration.py \
    --tb=short -q
211 passed, 3 skipped, 1 warning in 0.64s
```

- 169 baseline preserved (no regression).
- **42 new tests** added in `tests/test_arena_pass_rate_telemetry.py`.
- No pre-existing test modified.

## 3. New tests by category

| Category | Tests | Pass |
|----------|-------|------|
| Schema | 5 | 5 |
| Counter conservation | 7 | 7 |
| Rate calculation | 4 | 4 |
| Rejection distribution | 5 | 5 |
| Generation profile fallback | 3 | 3 |
| Deployable count | 3 | 3 |
| Failure safety | 5 | 5 |
| Behavior invariance | 5 | 5 |
| Stage summary aggregation | 2 | 2 |
| Pipeline helper integration | 3 | 3 |
| **Total** | **42** | **42** |

## 4. Dedicated suite output

```
$ python3 -m pytest zangetsu/tests/test_arena_pass_rate_telemetry.py -v
========================== 42 passed, 1 warning in 0.52s ==========================
```

All 42 PASS. See transcript for full list.

## 5. Critical tests

### `test_trace_only_pass_events_do_not_inflate_deployable_count`

Confirms that when `deployable_count` is not supplied by caller, the
emitted event carries `deployable_count=None` — **not** `passed_count`.
PASS.

### `test_runtime_behavior_invariant_when_telemetry_fails`

Simulates an emitter that raises. Confirms the caller proceeds unchanged.
PASS.

### `test_no_threshold_constants_changed_under_p7_pr4_lite`

Pins `A2_MIN_TRADES=25`, `A3_SEGMENTS=5`, `A3_MIN_TRADES_PER_SEGMENT=15`,
`A3_MIN_WR_PASSES=4`, `A3_MIN_PNL_PASSES=4`, `A3_WR_FLOOR=0.45`. PASS.

### `test_arena_pass_fail_behavior_unchanged_*`

Three pinned cases (too-few-trades, non-positive-pnl, edge-accept) all
match the baseline outcomes. PASS.

### `test_arena_pipeline_exposes_p7_pr4_lite_helper`

Confirms `_emit_a1_batch_metrics_from_stats_safe` is importable from
`arena_pipeline`. PASS.

## 6. Conclusion

No regression. 42 new tests all PASS. Behavior invariance confirmed.
