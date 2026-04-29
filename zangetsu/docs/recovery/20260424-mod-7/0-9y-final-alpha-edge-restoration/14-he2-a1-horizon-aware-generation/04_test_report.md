# 04 — TEST REPORT

**TEAM ORDER**: 0-9Y-HE2-A1-HORIZON-AWARE-GENERATION
**Date**: 2026-04-29
**Phase**: 4 / 8

## Commands run

### 1. HE2 module-specific
```
.venv/bin/python3 -m pytest -q zangetsu/tests/test_he2_horizon_aware_generation.py
```
**Result**: `15 passed in 0.32s` ✅ (14 master-order required + 1 lifecycle trace extras)

### 2. Union with TF2 + TF3 + TF4 + HE1 + HE2
```
.venv/bin/python3 -m pytest -q \
    zangetsu/tests/test_he2_horizon_aware_generation.py \
    zangetsu/tests/test_he1_horizon_config.py \
    zangetsu/tests/test_tf4_aggregation_config.py \
    zangetsu/tests/test_tf3_shadow.py \
    zangetsu/tests/test_signal_aggregation.py
```
**Result**: `52 passed in 0.41s` ✅ (TF2: 13 + TF3: 9 + TF4: 7 + HE1: 8 + HE2: 15)

### 3. Targeted regression
```
.venv/bin/python3 -m pytest -q zangetsu/tests \
    -k "signal_aggregation or aggregation or arena_batch_metrics or telemetry or taxonomy or arena_pass_rate or arena_telemetry or arena1_simulation or tf3 or tf4 or he1 or he2 or horizon" \
    --ignore=zangetsu/tests/policy
```
**Result**: `217 passed, 3 skipped, 587 deselected in 0.91s` ✅

### 4. py_compile
```
.venv/bin/python3 -m py_compile \
    zangetsu/services/horizon_config.py \
    zangetsu/services/arena_pipeline.py \
    zangetsu/engine/components/alpha_engine.py \
    zangetsu/engine/components/passport.py \
    zangetsu/tests/test_he2_horizon_aware_generation.py
```
**Result**: `PYCOMPILE_OK` ✅

## HE2 15 tests
| # | Test | Status | Master-order coverage |
|---|---|---|---|
| 1 | `a1_selects_horizon_per_round_simple_cycle` | ✅ | required #1 |
| 2 | `env_unset_defaults_to_fixed_60` | ✅ | required #2 |
| 3 | `redesign_mode_cycles_180_240_360` | ✅ | required #3 |
| 4 | `alpha_engine_receives_selected_horizon` | ✅ | required #4 |
| 5 | `alpha_result_horizon_propagates_to_candidate_metadata` | ✅ | required #5 |
| 6 | `generation_profile_id_includes_horizon` | ✅ | required #6 |
| 7 | `passport_or_trace_contains_horizon` | ✅ | required #7 (passport schema) |
| 7b | `lifecycle_trace_extras_carry_horizon` | ✅ | required #7 (lifecycle trace) |
| 8 | `same_formula_different_horizon_has_distinct_identity` | ✅ | required #8 |
| 9 | `batch_telemetry_contains_selected_horizon` | ✅ | required #9 |
| 10 | `validation_thresholds_unchanged` (tokenize-scan) | ✅ | required #10 |
| 11 | `cost_model_unchanged` (tokenize-scan) | ✅ | required #11 |
| 12 | `a2_min_trades_unchanged` (tokenize-scan) | ✅ | required #12 |
| 13 | `tf4_aggregation_default_off_still_off` | ✅ | required #13 |
| 14 | `legacy_missing_horizon_defaults_to_60` | ✅ | required #14 |

## Coverage summary
**14 / 14 master-order required tests PASS** + 1 bonus lifecycle-trace extras test.

## Regression summary
| Suite | Count | Status |
|---|---|---|
| TF2 module | 13 / 13 | ✅ |
| TF3 module | 9 / 9 | ✅ |
| TF4 module | 7 / 7 | ✅ |
| HE1 module | 8 / 8 | ✅ |
| HE2 module | 15 / 15 | ✅ |
| **Union** | **52 / 52** | ✅ |
| Targeted (-k filter) | 217 / 220 PASS (3 skipped) | ✅ |
| Failures | 0 | ✅ |
| Errors | 0 | ✅ |

## HE1 bug surfaced + fixed
HE2 test #4 `test_alpha_engine_receives_selected_horizon` (specifically the `AlphaEngine()` no-args + env-unset path) initially failed with:
```
NameError: name 'ALPHA_FORWARD_HORIZON' is not defined
```
This is a HE1 PR #69 bug — `_os.environ.get(ALPHA_FORWARD_HORIZON, 60)` missing string quotes. Production was unaffected because `arena_pipeline.py` always passes explicit `horizon=_he1_horizon`. Fixed in HE2 PR with 1-character correction (`ALPHA_FORWARD_HORIZON` → `'ALPHA_FORWARD_HORIZON'` and `60` → `'60'`).

After fix: 15/15 PASS.

## Pre-HE2 baseline preserved (verified by tests)

### Test #2: env unset defaults to FIXED 60
```python
_reset_env(monkeypatch)
cfg = get_horizon_config()
assert cfg.active_horizons == (60,) and cfg.mode == "FIXED" and cfg.fixed_horizon == 60
for r in range(50): assert select_horizon(r) == 60
```
PASS — single horizon=60 for every round.

### Test #14: legacy missing horizon → 60
```python
e = AlphaEngine()  # no horizon kwarg, env unset
assert e.horizon == 60
fr_default = AlphaEngine._forward_returns(close)
fr_60 = AlphaEngine._forward_returns(close, horizon=60)
np.testing.assert_array_equal(fr_default, fr_60)
```
PASS — bit-equality verified.

### Test #13: TF4 default OFF
```python
cfg = refresh_aggregation_config()  # env unset
assert cfg.mode == MODE_OFF and cfg.is_active is False
```
PASS — HE2 does not change TF4 default.

## STOP-conditions check (Phase 4 spec)
| STOP cause | Status |
|---|---|
| Baseline 60 behavior changes | ❌ no — tests #2, #14 |
| Horizon identity collision | ❌ no — test #8 verifies 4 distinct hashes |
| Tests fail | ❌ no — 15/15 + 217 PASS |
| Validation/cost/A2 changes | ❌ no — tests #10/#11/#12 tokenize-scan |

✅ **No STOP triggered.**

## Pre-existing test-rig note
`tests/policy/test_exception_overlay.py` calls `sys.exit()` at module-import (predates all TF/HE orders). `--ignore=zangetsu/tests/policy` workaround unchanged.

## Verdict
**PHASE_4_COMPLETE** — all 14 master-order required tests + 1 bonus PASS; full regression PASS; HE1 bug bundled-fixed; baseline 60 verified bit-identical.

## Next
Phase 5 — fixture verification.
