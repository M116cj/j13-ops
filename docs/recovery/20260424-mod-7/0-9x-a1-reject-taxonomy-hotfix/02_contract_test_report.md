# 02 — Contract Test Report

Order: TEAM ORDER 0-9X-A1-REJECT-TAXONOMY-HOTFIX
Phase: 3
Date (UTC): 2026-04-27
Author: Claude Lead

## Test files added / changed

| File | Operation | Lines added |
|---|---|---|
| `zangetsu/tests/test_arena_rejection_taxonomy.py` | appended (existing 300-line file) | +60 lines / 5 new tests |

No new test file created (existing one preferred per order spec). No existing test modified semantically.

## 5 required tests — implementation summary

1. **`test_pr43_validation_rejects_are_mapped`** — `classify("reject_train_neg_pnl")[0] != UNKNOWN_REJECT` AND `classify("reject_combined_sharpe_low")[0] != UNKNOWN_REJECT`.
2. **`test_pr43_validation_rejects_have_expected_canonical_reason`** — exact canonical reasons: `COST_NEGATIVE` for `reject_train_neg_pnl`, `LOW_BACKTEST_SCORE` for `reject_combined_sharpe_low`.
3. **`test_unknown_reject_fallback_still_works`** — `classify("some_totally_unknown_reason_for_fallback_test")[0] == UNKNOWN_REJECT`.
4. **`test_raw_to_reason_contains_pr43_keys`** — both raw keys exist in `RAW_TO_REASON`.
5. **`test_existing_core_mappings_unchanged`** — 5 existing stable mappings (`reject_few_trades`, `reject_neg_pnl`, `reject_val_neg_pnl`, `reject_val_low_sharpe`, `reject_val_low_wr`) classify to their pre-hotfix canonical reasons.

## Commands run

```bash
cd /Users/a13/dev/j13-ops
python3 -m pytest -q zangetsu/tests/test_arena_rejection_taxonomy.py
python3 -m pytest -q zangetsu/tests -k "taxonomy or rejection or reject_reason or arena_batch_metrics"
```

## Pass / fail counts

### Targeted suite (`zangetsu/tests/test_arena_rejection_taxonomy.py`)

```
35 passed, 1 warning in 0.06s
```

- 30 pre-existing tests: PASS
- 5 new tests added by this hotfix: PASS
- Total: **35 / 35 PASS**

The 1 warning is `PytestConfigWarning: Unknown config option: asyncio_mode` — pre-existing pytest config warning, environmental, unrelated to taxonomy.

### Nearby filter (`-k "taxonomy or rejection or reject_reason or arena_batch_metrics"`)

```
3 skipped, 623 deselected, 1 warning, 2 errors in 0.37s
```

The 2 collection errors are pre-existing, environment-specific:

| Test file | Error | Classification |
|---|---|---|
| `zangetsu/tests/policy/test_exception_overlay.py` | `PolicyRegistryError: registry not found: /home/j13/j13-ops/zangetsu/config/family_strategy_policy_v0.yaml` | Pre-existing — Alaya-only path; previously documented in TEAM ORDER 0-9X-POST-DB-COLD-BOOT-RECOVERY-FAST Phase 5 evidence |
| `zangetsu/tests/test_lookahead_bias.py` | `FileNotFoundError: '/home/j13/j13-ops'` (hardcoded `os.chdir` at line 12) | Pre-existing — Alaya-only path; same prior evidence |

Both errors are in the test file's `import` / collection stage on Mac and are unrelated to the taxonomy module. Their existence pre-dates this hotfix and is documented in the previous order's `Phase 5 — Minimal post-merge tests` evidence.

### Failure classification

| Class | Count |
|---|---|
| New failure attributable to this hotfix | 0 |
| Pre-existing collection errors (Mac env) | 2 |
| Skipped pre-existing | 3 |
| Pass on this hotfix | 35 / 35 |

## Proof of "no validator behavior tested or changed"

- All 5 new tests assert on `classify()` and `RAW_TO_REASON` only.
- No new test imports `arena_pipeline`, `arena_gates`, `alpha_signal`, or any validator/strategy module.
- No new test references thresholds (A2_MIN_TRADES, sharpe gates, win-rate gates) or modifies their values.
- Tests are pure mapping-contract assertions — same shape as the 30 pre-existing tests.

## STOP conditions evaluation

| STOP condition | Triggered? |
|---|---|
| taxonomy tests fail | NO — 35/35 PASS |
| fallback `UNKNOWN_REJECT` behavior is broken | NO — `test_unknown_reject_fallback_still_works` PASS |
| existing mapping behavior changes unexpectedly | NO — `test_existing_core_mappings_unchanged` PASS |

**No STOP. Proceed to Phase 4.**
