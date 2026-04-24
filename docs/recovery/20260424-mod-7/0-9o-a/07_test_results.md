# 0-9O-A — Test Results

## 1. Baseline (before 0-9O-A)

Run against `origin/main` SHA
`2e385097002d64446548a145dc88d05dcc9769ef` (P7-PR4-LITE merge):

```
$ python3 -m pytest zangetsu/tests/ \
    --ignore=zangetsu/tests/policy/test_exception_overlay.py \
    --ignore=zangetsu/tests/test_integration.py \
    --tb=no -q
211 passed, 3 skipped, 1 warning
```

The pre-existing async failures in `test_integration.py` (missing
`pytest-asyncio` plugin) are unrelated and were present before
0-9O-A. They remain excluded via `--ignore`, consistent with
P7-PR4-LITE.

## 2. After 0-9O-A

```
$ python3 -m pytest zangetsu/tests/ \
    --ignore=zangetsu/tests/policy/test_exception_overlay.py \
    --ignore=zangetsu/tests/test_integration.py \
    --tb=short -q
253 passed, 3 skipped, 1 warning in 0.66s
```

- 211 baseline preserved — zero regression.
- **42 new tests** added in
  `tests/test_generation_profile_identity_and_scoring.py`.

## 3. New tests by category

| Category | Count | Pass |
|----------|-------|------|
| Profile identity | 8 | 8 |
| Canonical JSON | 3 | 3 |
| Generation profile metrics | 7 | 7 |
| Scoring | 7 | 7 |
| Dry-run budget recommendation | 3 | 3 |
| Feedback decision record | 5 | 5 |
| Behavior invariance | 6 | 6 |
| arena_pipeline integration | 3 | 3 |
| **Total** | **42** | **42** |

## 4. Dedicated suite

```
$ python3 -m pytest \
    zangetsu/tests/test_generation_profile_identity_and_scoring.py -v
======================== 42 passed, 1 warning in 0.54s =========================
```

## 5. Critical tests

### `test_profile_fingerprint_is_stable_for_key_order_changes`

Confirms two permutations of the same config dict produce identical
fingerprints. PASS.

### `test_profile_fingerprint_excludes_timestamps`

Confirms adding `timestamp`, `created_at`, `updated_at` to a config
does NOT change the fingerprint. PASS.

### `test_profile_identity_failure_does_not_block_telemetry`

Feeds a mapping whose `items()` raises. `safe_resolve_profile_identity`
returns UNKNOWN_PROFILE / UNAVAILABLE_FINGERPRINT. PASS.

### `test_feedback_decision_record_rejects_applied_true`

Tries `build_feedback_decision_record(run_id="x", applied=True)`. The
constructor `__post_init__` overrides `applied=False`. Additionally,
mutating `record.applied = True` after construction is defeated by
`to_event()` which re-applies the invariant at serialization time. PASS.

### `test_next_budget_weight_dry_run_is_not_applied`

Confirms that without `min_sample_size_met`, the recommendation pins
exactly at `EXPLORATION_FLOOR = 0.05`, so any future allocator reading
this field can trivially detect non-actionable state. PASS.

### `test_scoring_does_not_modify_arena_decisions`

Snapshots all uppercase module attributes of `arena_pipeline` before
and after a scoring call; asserts they are identical. PASS.

### `test_arena_pipeline_helper_accepts_profile_identity_kwargs`
### `test_arena_pipeline_helper_falls_back_when_identity_omitted`

Confirm the helper accepts the new kwargs and still falls back when
they are omitted (backwards-compatible with legacy callers). PASS.

## 6. Conclusion

No regression. 42 new tests all PASS. Behavior invariance confirmed.
