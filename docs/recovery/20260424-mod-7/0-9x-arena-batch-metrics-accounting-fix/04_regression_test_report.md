# 04 — Regression Test Report

Order: TEAM ORDER 0-9X-ARENA-BATCH-METRICS-ACCOUNTING-FIX
Phase: 4
Date (UTC): 2026-04-27
Author: Claude Lead

## Test file

`zangetsu/tests/test_arena_batch_metrics_accounting.py` — **new file**, 186 lines, 6 tests.

## Why AST extraction (not direct import)

`zangetsu/services/arena_pipeline.py` cannot be imported on the Mac test runner: heavy runtime deps (`pyarrow`, Rust extensions in `indicator_engine/target/release`, hard-coded `os.chdir('/home/j13/j13-ops')` at module top, etc.) make full-module import infeasible without Alaya's environment.

The pure helper `_compute_a1_reject_deltas` is intentionally written without runtime dependencies so it remains testable. Tests load the helper and the `_A1_REJECT_STATS_KEYS` constant via `ast.parse` + `ast.get_source_segment` + `exec`, executing each in an isolated namespace. This is a recognized pattern for testing utility functions inside heavy modules.

```python
def _load_helper_and_keys():
    text = _ARENA_PIPELINE_PATH.read_text()
    tree = ast.parse(text)
    # ... walk top-level nodes, extract _compute_a1_reject_deltas and _A1_REJECT_STATS_KEYS
    ns: dict = {}
    exec(keys_src, ns)
    exec(helper_src, ns)
    return ns["_compute_a1_reject_deltas"], ns["_A1_REJECT_STATS_KEYS"]
```

## Tests written (4 required + 2 belt-and-braces)

### Required by order spec

1. **`test_residual_zero_per_batch`** — simulate two consecutive batches with steady-state cumulative growth; assert `entered = passed + sum(deltas) + skipped` holds with skipped ≥ 0.
2. **`test_counter_inconsistency_not_triggered_for_valid_data`** — when `entered_count` is consistent with `passed + sum(deltas)`, the residual is ≥ 0 → no `COUNTER_INCONSISTENCY` add.
3. **`test_existing_distribution_keys_preserved`** — `_A1_REJECT_STATS_KEYS` matches the canonical 10-tuple in arena_pipeline.py; each key, when nonzero in current and zero in prev, surfaces in deltas with the correct value.
4. **`test_first_batch_initialization`** — empty prev → current values become deltas; snapshot covers all 10 keys including zeros; second call with same cumul → empty deltas (idempotent steady-state).

### Belt-and-braces guards

5. **`test_helper_is_pure_does_not_mutate_input`** — caller's `prev_snapshot` dict must not be mutated; helper returns a new dict.
6. **`test_negative_or_zero_delta_not_counted`** — when current ≤ previous (no growth or counter rollback), no delta emitted; snapshot still tracks the new (possibly lower) current value.

## Test command + result

```
$ python3 -m pytest -q zangetsu/tests/test_arena_batch_metrics_accounting.py -v
============================= test session starts ==============================
platform darwin -- Python 3.14.3, pytest-9.0.2, pluggy-1.6.0
rootdir: /Users/a13/dev/j13-ops/zangetsu
configfile: pytest.ini
plugins: anyio-4.12.1
collected 6 items

zangetsu/tests/test_arena_batch_metrics_accounting.py ......             [100%]

========================= 6 passed, 1 warning in 0.12s =========================
```

**6 / 6 PASS.**

## Failure classification

- new failures attributable to this hotfix: **0**
- pre-existing failures inherited: not run (targeted test only)
- environment-specific issues: none

## Proof no validator behavior tested or changed

The 6 tests exercise only `_compute_a1_reject_deltas` (pure dict/int arithmetic) and the `_A1_REJECT_STATS_KEYS` tuple. No test imports or invokes:
- `arena_pipeline.py` runtime decision code
- `arena_gates.arena2_pass / arena3_pass / arena4_pass`
- `_emit_a1_batch_metrics_from_stats_safe` itself (only its pure helper)
- `_ArenaStageMetrics` / `_build_batch_metrics` / `_safe_emit_arena_metrics`
- `arena_rejection_taxonomy.classify`
- threshold constants (`A2_MIN_TRADES` etc.)
- DB/admission/champion-promotion code paths

The tests are pure-Python unit tests on dict arithmetic.

## STOP-condition evaluation

| STOP condition | Triggered? |
|---|---|
| taxonomy / accounting tests fail | NO — 6/6 PASS |
| existing mapping behavior changes unexpectedly | NO — `_A1_REJECT_STATS_KEYS` matches canonical 10-tuple |
| helper raises on edge inputs | NO — handles empty prev, zero current, equal current=prev, current<prev (rollback) |

**No STOP. Proceed to Phase 5.**
