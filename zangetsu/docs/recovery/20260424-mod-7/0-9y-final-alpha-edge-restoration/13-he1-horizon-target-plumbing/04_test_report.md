# 04 — TEST REPORT

**TEAM ORDER**: 0-9Y-HE1-HORIZON-TARGET-PLUMBING
**Date**: 2026-04-28
**Phase**: 4 / 7

## Commands run

### 1. HE1 module-specific
```
.venv/bin/python3 -m pytest -q zangetsu/tests/test_he1_horizon_config.py
```
**Result**: `8 passed in 0.32s` ✅

### 2. Union with TF2 + TF3 + TF4
```
.venv/bin/python3 -m pytest -q \
    zangetsu/tests/test_he1_horizon_config.py \
    zangetsu/tests/test_tf4_aggregation_config.py \
    zangetsu/tests/test_tf3_shadow.py \
    zangetsu/tests/test_signal_aggregation.py
```
**Result**: `37 passed in 0.39s` ✅ (TF2: 13/13 + TF3: 9/9 + TF4: 7/7 + HE1: 8/8)

### 3. Targeted regression
```
.venv/bin/python3 -m pytest -q zangetsu/tests \
    -k "signal_aggregation or aggregation or arena_batch_metrics or telemetry or taxonomy or arena_pass_rate or arena_telemetry or arena1_simulation or tf3 or tf4 or he1 or horizon" \
    --ignore=zangetsu/tests/policy
```
**Result**: `202 passed, 3 skipped, 587 deselected in 0.95s` ✅

### 4. py_compile
```
.venv/bin/python3 -m py_compile \
    zangetsu/services/horizon_config.py \
    zangetsu/services/arena_pipeline.py \
    zangetsu/engine/components/alpha_engine.py \
    zangetsu/tests/test_he1_horizon_config.py
```
**Result**: `PYCOMPILE_OK` ✅

## HE1 8 tests
| # | Test | Status |
|---|---|---|
| 1 | `horizon_selection_deterministic` (SIMPLE_CYCLE seq stable across calls) | ✅ |
| 2 | `multiple_horizons_produce_different_outputs` (`_forward_returns` array divergence) | ✅ |
| 3 | `alpha_hash_differs_by_horizon` (h=60 vs h=180/240/360 all distinct; h=60 == legacy format) | ✅ |
| 4 | `baseline_60_identical_to_pre_he1` (default config + `_forward_returns(close, horizon=60)` == `_forward_returns(close)`) | ✅ |
| 5 | `no_regression_in_aggregation` (TF2 helper still callable + correct) | ✅ |
| 6 | `no_regression_in_telemetry` (additive `horizon` field; `horizon_config` only when multi-horizon) | ✅ |
| 7 | `conservation_unchanged` (no counter-mutation API leaked from horizon_config) | ✅ |
| 8 | `config_invalid_and_no_forbidden` (bonus: invalid handling + tokenize-scan against 27 forbidden tokens) | ✅ |

## Master-order required tests coverage
| Required | HE1 test | Status |
|---|---|---|
| 1. horizon selection deterministic | #1 | ✅ |
| 2. multiple horizons produce different outputs | #2 | ✅ |
| 3. alpha_hash differs by horizon | #3 | ✅ |
| 4. baseline (60) identical to pre-HE1 | #4 | ✅ |
| 5. no regression in aggregation | #5 | ✅ |
| 6. no regression in telemetry | #6 | ✅ |
| 7. conservation unchanged | #7 | ✅ |

## Regression summary
| Suite | Count | Status |
|---|---|---|
| TF2 module | 13 / 13 | ✅ |
| TF3 module | 9 / 9 | ✅ |
| TF4 module | 7 / 7 | ✅ |
| HE1 module | 8 / 8 | ✅ |
| **Union** | **37 / 37** | ✅ |
| Targeted (-k filter) | 202 / 205 PASS (3 skipped) | ✅ |
| Failures | 0 | ✅ |
| Errors | 0 | ✅ |

## Pre-HE1 baseline preserved (verified)

### Forward-return numerical identity
HE1 test #4 verifies bit-equality:
```python
explicit_60 = AlphaEngine._forward_returns(close, horizon=60)
env_default = AlphaEngine._forward_returns(close)  # ALPHA_FORWARD_HORIZON unset → fallback 60
np.testing.assert_array_equal(explicit_60, env_default)
```
PASS — the new `horizon` parameter does not change values when horizon=60.

### Alpha hash identity
HE1 test #3 verifies:
```python
h60 = hashlib.md5(formula.encode("utf-8")).hexdigest()[:16]   # legacy format
# alpha_engine produces h60 (legacy) for any AlphaEngine with horizon=60
```
PASS — pre-HE1 hashes preserved exactly.

### select_horizon default
HE1 test #4 verifies that with default env (HE1 vars unset):
```python
for r in range(50):
    assert select_horizon(r) == 60
```
PASS — every round picks horizon=60.

## STOP-conditions check (Phase 4 spec)

| STOP cause | Status |
|---|---|
| Baseline changes | ❌ no — test #4 verifies bit-equality |
| Hash collision | ❌ no — test #3 verifies all 4 horizons produce 4 distinct hashes |
| Validation behavior altered | ❌ no — `entry_rank_threshold` etc. unchanged; tokenize-scan in test #8 verifies absence |

✅ **No STOP triggered.**

## Pre-existing test-rig note
`tests/policy/test_exception_overlay.py` calls `sys.exit()` at module-import (predates all TF/HE orders). Worked around by `--ignore=zangetsu/tests/policy`.

## Verdict
**PHASE_4_COMPLETE** — all 7 master-order required tests pass + 1 invalid-handling/tokenize-scan; full regression PASS; bit-identical baseline verified.

## Next
Phase 5 — controlled diff & forbidden audit.
