# 03 — PATCH REPORT

**TEAM ORDER**: 0-9Y-TF2-SIGNAL-AGGREGATION-PROTOTYPE
**Date**: 2026-04-28
**Phase**: 3 / 8

## Files added
| Path | Lines | Purpose |
|---|---|---|
| `zangetsu/services/signal_aggregation.py` | 419 | Pure helper: `apply_signal_aggregation(signals, sizes, profile, ...) → AggregationResult` with 5 profiles (OFF, STRENGTH_FILTER, TOP_K_PER_BAR, HYBRID_TOPK_STRENGTH, CONSENSUS_2_OF_3-deferred) |
| `zangetsu/tests/test_signal_aggregation.py` | 411 | 13 tests covering all required Phase 3 cases |

## Files modified
**None.** TF2 patch is purely additive. Live arena_pipeline path is not touched; default profile = OFF, never invoked from production code in this PR.

## Public API
```python
from zangetsu.services.signal_aggregation import (
    apply_signal_aggregation,
    AggregationResult,
    PROFILE_OFF, PROFILE_STRENGTH_FILTER, PROFILE_TOP_K_PER_BAR,
    PROFILE_HYBRID, PROFILE_CONSENSUS,
    ALLOWED_PROFILES,
)

result = apply_signal_aggregation(
    signals,           # int8 [N]   — generate_alpha_signals output
    sizes,             # float64 [N] — generate_alpha_signals output
    profile=PROFILE_STRENGTH_FILTER,
    strength=sizes,    # optional; defaults to `sizes` (= |rank-0.5|*2)
    strength_quantile=0.90,
)
```

## AggregationResult (frozen dataclass)
- `signals: int8 ndarray` — filtered (suppressed trade segments → 0)
- `sizes: float64 ndarray` — filtered
- `kept: bool ndarray` — length = entered_count
- `profile: str`
- `entered_count: int` — number of entry edges in input
- `kept_count: int`
- `skipped_count: int`
- `metadata: dict` — `strength_threshold`, `top_k`, `skip_reason_distribution`, `mean_strength_kept`, `mean_strength_skipped`, plus `deferred_not_implemented` for CONSENSUS

## Required tests (13 / 13 PASS)
| # | Test | Status |
|---|---|---|
| 1 | `baseline_profile_returns_all_signals` | ✅ |
| 2 | `strength_filter_keeps_strongest_only` | ✅ |
| 3 | `top_k_per_bar_keeps_k_deterministically` (incl. tiebreak) | ✅ |
| 4 | `skipped_count_conservation` (across all 6 profiles) | ✅ |
| 5 | `nan_strength_handled_safely` | ✅ |
| 6 | `unknown_profile_fails_closed` | ✅ |
| 7 | `no_mutation_or_documented_mutation` (input arrays + memory) | ✅ |
| 8 | `telemetry_fields_present` (8 top-level + 5 metadata) | ✅ |
| 9 | `validation_thresholds_unchanged` (tokenize-based scan) | ✅ |
| 10 | `cost_model_unchanged` | ✅ |
| 11 | `A2_MIN_TRADES_unchanged` | ✅ |
| 12 | `no_alpha_zoo_write_path` | ✅ |
| 13 | `no_canary_or_production_flags_enabled` | ✅ |

```
$ pytest -q zangetsu/tests/test_signal_aggregation.py
.............                                                            [100%]
13 passed in 0.14s
```

## Test rig note (false-positive avoidance)
Tests 9–13 originally used naive `string in source` greps and tripped on the module's prose **docstring** (which legitimately documents what the helper does NOT touch). Final implementation uses `tokenize.tokenize()` to scan only NAME/NUMBER/OP tokens — comments and string literals are excluded. This catches actual code references but allows informational docstring prose. Pattern documented in `_has_code_token` / `_has_code_substring` helpers at the top of the test module.

## STOP-conditions check (Phase 3 spec)
| STOP cause | Status |
|---|---|
| Implementation requires validation threshold changes | ❌ no |
| Implementation changes cost | ❌ no |
| Implementation changes pass/fail semantics | ❌ no |
| Implementation cannot be default OFF | ❌ no — `OFF` is pass-through, sentinel-tested |

✅ No STOP triggered.

## Safety invariants verified by tests
| Invariant | Test |
|---|---|
| OFF/BASELINE = pass-through | #1 |
| Conservation `entered = kept + skipped` | #4 (across 6 profiles) |
| Pure function (no input mutation) | #7 |
| Deterministic top-K with stable tiebreak | #3 |
| NaN-safe | #5 |
| Fails closed on unknown profile / bad params | #6 |
| Validator/cost/A2 untouched in code | #9, #10, #11 |
| alpha_zoo / CANARY / prod paths absent | #12, #13 |

## Architecture: where TF2 hooks into live path
**Live path**: `arena_pipeline.py` line 1049 calls `generate_alpha_signals()` then `backtester.run()`. **TF2 makes ZERO changes to this path.** The helper is a separate module callable only from a SHADOW-evaluation harness that the next phase will invoke offline.

When SHADOW invokes a non-OFF profile, the conservation telemetry will increment `skipped_count` (already in batch schema, currently always 0 in baseline).

## Verdict
**PHASE_3_COMPLETE — implementation passes all 13 required tests with no STOP triggers.**

## Next
Proceed to Phase 4 — broader test report + py_compile + safety greps.
