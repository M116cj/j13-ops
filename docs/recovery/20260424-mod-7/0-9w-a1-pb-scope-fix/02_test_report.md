# 02 — Focused Regression Tests

## 1. Baseline Suite

```bash
zangetsu/.venv/bin/python -m pytest \
  zangetsu/tests/test_a2_a3_arena_batch_metrics.py \
  zangetsu/tests/test_sparse_canary_observer.py \
  zangetsu/tests/test_sparse_canary_readiness.py \
  zangetsu/tests/test_sparse_canary_observation_runner.py \
  zangetsu/tests/test_passport_profile_attribution.py \
  zangetsu/tests/test_profile_attribution_audit.py \
  zangetsu/tests/test_feedback_budget_allocator.py \
  zangetsu/tests/test_feedback_budget_consumer.py \
  zangetsu/tests/test_generation_profile_identity_and_scoring.py \
  zangetsu/tests/test_sparse_canary_replay.py \
  -q --tb=line
```

## 2. Result

```
........................................................................ [ 14%]
........................................................................ [ 29%]
........................................................................ [ 43%]
........................................................................ [ 58%]
........................................................................ [ 72%]
........................................................................ [ 87%]
...............................................................          [100%]
495 passed in 0.90s
```

| Field | Value |
| --- | --- |
| Tests collected | 495 |
| Passed | **495** |
| Failed | 0 |
| Skipped | 0 |
| Errors | 0 |
| Wall time | 0.90 s |

## 3. Comparison vs. Pre-Patch Baseline

PR #34 reported 189 PASS in 0.28 s (CANARY-related subset). PR #30 reported 495 PASS in 1.11 s (full Phase 7 suite). **This run reproduces the 495 PASS baseline** with the patch in place — no regression from the patch.

## 4. Why No New Test Was Added

The order's Phase 2 says "Add or run a focused test if safe and local-only" — adding is optional. Reasons we did not add a new test:

- The patch is one default-initialization line; testing it via unit test would essentially mock the entire `main()` async coroutine, which is heavyweight.
- The runtime validation in Phase 5 / Phase 6 (post-merge log + DB watch) directly verifies the patch effect by observing whether the UnboundLocalError stops appearing in cron-spawned worker logs.
- Adding a unit test would touch `zangetsu/tests/`, which is acceptable per the order, but not strictly necessary.

## 5. Failure Classification

| Class | Count |
| --- | --- |
| Real-logic failures | 0 |
| Environment-only failures | 0 |
| Skipped tests | 0 |

## 6. Phase 2 Verdict

PASS. Patch does not regress any of the 495 existing tests.
