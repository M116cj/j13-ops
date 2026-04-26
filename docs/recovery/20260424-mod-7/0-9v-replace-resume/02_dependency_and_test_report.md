# 02 — Dependency and Test Report

## 1. Python Environment

| Field | Value |
| --- | --- |
| System `python3` | `/usr/bin/python3` |
| Version | `Python 3.12.3` |
| zangetsu venv | `/home/j13/j13-ops/zangetsu/.venv/bin/python` (symlink to `/usr/bin/python3`) |
| pytest | `9.0.3` (in venv) |

## 2. Test File Presence

All 10 expected test files **PRESENT** under `zangetsu/tests/`:

```
PRESENT: test_sparse_canary_observer.py
PRESENT: test_sparse_canary_readiness.py
PRESENT: test_sparse_canary_observation_runner.py
PRESENT: test_feedback_budget_allocator.py
PRESENT: test_a2_a3_arena_batch_metrics.py
PRESENT: test_generation_profile_identity_and_scoring.py
PRESENT: test_feedback_budget_consumer.py
PRESENT: test_profile_attribution_audit.py
PRESENT: test_sparse_canary_replay.py
PRESENT: test_passport_profile_attribution.py
```

## 3. Test Run

### Command

```bash
zangetsu/.venv/bin/python -m pytest \
  zangetsu/tests/test_sparse_canary_observer.py \
  zangetsu/tests/test_sparse_canary_readiness.py \
  zangetsu/tests/test_sparse_canary_observation_runner.py \
  zangetsu/tests/test_feedback_budget_allocator.py \
  zangetsu/tests/test_a2_a3_arena_batch_metrics.py \
  zangetsu/tests/test_generation_profile_identity_and_scoring.py \
  zangetsu/tests/test_feedback_budget_consumer.py \
  zangetsu/tests/test_profile_attribution_audit.py \
  zangetsu/tests/test_sparse_canary_replay.py \
  zangetsu/tests/test_passport_profile_attribution.py \
  -q --tb=line
```

### Result

```
........................................................................ [ 14%]
........................................................................ [ 29%]
........................................................................ [ 43%]
........................................................................ [ 58%]
........................................................................ [ 72%]
........................................................................ [ 87%]
...............................................................          [100%]
495 passed in 1.11s
```

| Field | Value |
| --- | --- |
| Tests collected | 495 |
| Passed | **495** |
| Failed | 0 |
| Skipped | 0 |
| Errors | 0 |
| Wall time | 1.11 s |

## 4. Comparison vs. Mac Proxy

| Suite | Mac (PR #18-#28) | Alaya (this run) |
| --- | --- | --- |
| `test_sparse_canary_observer` | 71 PASS | included |
| `test_sparse_canary_readiness` | 45 PASS | included |
| `test_sparse_canary_observation_runner` | 21 PASS | included |
| `test_feedback_budget_allocator` | 62 PASS | included |
| `test_a2_a3_arena_batch_metrics` | 54 PASS | included |
| `test_generation_profile_identity_and_scoring` | (covered) | included |
| `test_feedback_budget_consumer` | 81 PASS | included |
| `test_profile_attribution_audit` | 56 PASS | included |
| `test_sparse_canary_replay` | 23 PASS | included |
| `test_passport_profile_attribution` | 40 PASS | included |
| **Total Mac (P7-PR4B + 9 sparse PRs)** | 453 PASS / 0 regression | — |
| **Total Alaya (this run)** | — | **495 PASS / 0 fail / 0 skip** |

The Alaya count exceeds Mac because (a) Alaya doesn't have the Mac-only `os.chdir('/home/j13/j13-ops')` failures (Mac-side `arena_pipeline.py:18` issue does not apply on Alaya since the path exists there), and (b) the 0-9V-CLEAN sync brought several PRs forward that added test cases since the prior Mac counts were taken.

## 5. Failure Classification

| Class | Count | Detail |
| --- | --- | --- |
| Real-logic failures | 0 | — |
| Environment-only failures | 0 | — |
| Skipped tests | 0 | — |

→ **No `BLOCKED_TEST_FAILURE`.**

## 6. Phase B Verdict

→ **PASS.** Tests confirm the post-CLEAN main is healthy on Alaya. Safe to proceed to Phase C.
