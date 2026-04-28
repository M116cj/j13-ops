# 05 — TEST REPORT

**TEAM ORDER**: 0-9Y-TF4-INTEGRATION-DECISION
**Date**: 2026-04-28
**Phase**: 5 / 8

## Commands run

### 1. TF4 module-specific
```
.venv/bin/python3 -m pytest -q zangetsu/tests/test_tf4_aggregation_config.py
```
**Result**: `7 passed in 0.09s` ✅

### 2. TF2 + TF3 + TF4 union
```
.venv/bin/python3 -m pytest -q \
    zangetsu/tests/test_tf4_aggregation_config.py \
    zangetsu/tests/test_tf3_shadow.py \
    zangetsu/tests/test_signal_aggregation.py
```
**Result**: `29 passed in 0.17s` ✅

### 3. Targeted regression
```
.venv/bin/python3 -m pytest -q zangetsu/tests \
    -k "signal_aggregation or aggregation or arena_batch_metrics or telemetry or taxonomy or arena_pass_rate or arena_telemetry or arena1_simulation or tf3 or tf4" \
    --ignore=zangetsu/tests/policy
```
**Result**: `194 passed, 3 skipped, 587 deselected in 0.88s` ✅

### 4. py_compile
```
.venv/bin/python3 -m py_compile \
    zangetsu/services/aggregation_config.py \
    zangetsu/services/arena_pipeline.py \
    zangetsu/tests/test_tf4_aggregation_config.py
```
**Result**: `PYCOMPILE_OK` ✅

## TF4 7 tests
| # | Test | Status |
|---|---|---|
| 1 | `OFF mode identical to baseline` | ✅ |
| 2 | `STRENGTH_FILTER reduces signals` | ✅ |
| 3 | `TOP_K_PER_BAR deterministic` | ✅ |
| 4 | `skipped_count correct` (across all 4 modes) | ✅ |
| 5 | `conservation holds` (random fixtures × 20 trials × 3 profiles) | ✅ |
| 6 | `config invalid handling` (invalid mode/Q/TOPK → fallback to defaults) | ✅ |
| 7 | `config_no_forbidden_refs` (tokenize-scan against 27 forbidden tokens) | ✅ |

## Coverage of master-order required tests
| Required test | TF4 test# | Status |
|---|---|---|
| 1. OFF mode identical to baseline | #1 | ✅ |
| 2. STRENGTH_FILTER reduces signals | #2 | ✅ |
| 3. TOP_K_PER_BAR deterministic | #3 | ✅ |
| 4. skipped_count correct | #4 | ✅ |
| 5. conservation holds | #5 | ✅ |
| 6. config invalid handling | #6 | ✅ |

## TF2 + TF3 still pass (regression)
| Suite | Count | Status |
|---|---|---|
| TF2 module (`test_signal_aggregation.py`) | 13 / 13 | ✅ |
| TF3 module (`test_tf3_shadow.py`) | 9 / 9 | ✅ |
| TF4 module (`test_tf4_aggregation_config.py`) | 7 / 7 | ✅ |
| **Union TF2+TF3+TF4** | **29 / 29** | ✅ |

No regression in TF2 or TF3 tests after TF4 patch.

## Targeted regression breakdown (-k filter)
| Categories matched | Tests passing |
|---|---|
| signal_aggregation, aggregation, arena_batch_metrics, telemetry, taxonomy, arena_pass_rate, arena_telemetry, arena1_simulation, tf3, tf4 | **194** PASS, 3 skipped, 587 deselected |
| Failures | **0** |
| Errors | **0** |

## Pre-existing test-rig note
`tests/policy/test_exception_overlay.py` calls `sys.exit()` at module-import (predates all TF orders). Worked around by `--ignore=zangetsu/tests/policy`. Unchanged by TF4.

## Default-path baseline check
Default OFF (`ARENA_AGGREGATION_MODE` unset) verified via:
1. **Direct config check**: `get_aggregation_config()` returns `AggregationConfig(mode="OFF", strength_quantile=0.95, top_k=50, is_active=False)` — confirmed in interpreter.
2. **TF4 test #1**: when MODE=OFF, signals + sizes pass-through bit-for-bit.
3. **Test #4 OFF case**: `_TF4_CFG.is_active is False` → no aggregation invoked.

## Aggregation-ON behavior verified
| Test | Mode | Q / TOPK | Expected | Observed |
|---|---|---|---|---|
| #2 | STRENGTH_FILTER | Q=0.50 | weakest entry suppressed | ✅ first entry (s=0.10) zeroed |
| #3 | TOP_K_PER_BAR | TOPK=1 | only strongest kept | ✅ only s=0.95 entry kept |
| #4 | HYBRID_TOPK_STRENGTH | Q=0.50, TOPK=1 | strict Q + strict K | ✅ skipped ≥2 entries |
| #4 | (all modes) | (varied) | conservation entered = kept + skipped | ✅ |

## Invalid-config handling verified
| Input | Result |
|---|---|
| `ARENA_AGGREGATION_MODE=GARBAGE_VALUE` | mode → OFF (fallback + WARN log) ✅ |
| `ARENA_AGGREGATION_MODE=strength_filter` | mode → STRENGTH_FILTER (case-insensitive) ✅ |
| `ARENA_AGGREGATION_Q=1.5` (out of range) | Q → 0.95 (DEFAULT_Q) ✅ |
| `ARENA_AGGREGATION_Q=not_a_number` | Q → 0.95 ✅ |
| `ARENA_AGGREGATION_TOPK=-5` (negative) | TOPK → 50 (DEFAULT_TOPK) ✅ |
| `ARENA_AGGREGATION_TOPK=abc` | TOPK → 50 ✅ |
| empty strings | all defaults ✅ |

## STOP-conditions check (Phase 5 spec)
| STOP cause | Status |
|---|---|
| Baseline changed | ❌ no — TF4 test #1 verifies OFF = pass-through |
| Tests fail | ❌ no — 7/7 TF4, 29/29 union, 194 regression |
| Conservation broken | ❌ no — TF4 tests #4 + #5 verify per-mode conservation |

✅ **No STOP triggered.**

## Verdict
**PHASE_5_COMPLETE** — all 6 master-order required tests pass + 1 forbidden-token scan + targeted regression with no failures.

## Next
Phase 6 — controlled diff & forbidden audit.
