# 04 — Dependency and Test Report

## 1. Status

**SKIPPED.** Test validation requires the post-sync code on Alaya. Since fast-forward did not happen (Phase C BLOCKED_DIRTY_STATE), running tests against the pre-PR-A baseline + dirty WIP would be **diagnostic only** and could mislead — many test files don't exist on Alaya yet:

| Test file | Present on Alaya |
| --- | --- |
| `test_sparse_canary_observer.py` | **NO** (shipped via PR #25) |
| `test_sparse_canary_readiness.py` | **NO** (PR #25) |
| `test_sparse_canary_observation_runner.py` | **NO** (PR #26) |
| `test_sparse_canary_replay.py` | **NO** (PR #27) |
| `test_feedback_budget_allocator.py` | **NO** (PR #19) |
| `test_a2_a3_arena_batch_metrics.py` | DIRTY (untracked file from local WIP) |
| `test_generation_profile_identity_and_scoring.py` | YES (PR #17) |
| `test_feedback_budget_consumer.py` | **NO** (PR #23) |
| `test_profile_attribution_audit.py` | **NO** (PR #22) |

## 2. Python environment

| Field | Value |
| --- | --- |
| Default `python3` | `/usr/bin/python3` |
| Version | 3.12.3 |
| zangetsu venv | `/home/j13/j13-ops/zangetsu/.venv/bin/python3` (active for cron jobs and live processes) |
| pip | available (not version-checked since unused) |

The system Python 3.12.3 satisfies the Mac CI (Python 3.14.3) requirement
band (we don't use 3.14-only features).

## 3. Mac-side validation as proxy

While Alaya tests cannot run pre-sync, the Mac-side test results for the
same code (origin/main = `73b931d2`) are documented across the prior 10
PRs:

| Suite | PR | Tests | Result |
| --- | --- | --- | --- |
| `test_a2_a3_arena_batch_metrics.py` | PR #18 | 54 | PASS |
| `test_feedback_budget_allocator.py` | PR #19 | 62 | PASS |
| `test_passport_profile_attribution.py` | PR #21 | 40 | PASS |
| `test_profile_attribution_audit.py` | PR #22 | 56 | PASS |
| `test_feedback_budget_consumer.py` | PR #23 | 81 | PASS |
| `test_sparse_canary_observer.py` | PR #25 | 71 | PASS |
| `test_sparse_canary_readiness.py` | PR #25 | 45 | PASS |
| `test_sparse_canary_observation_runner.py` | PR #26 | 21 | PASS |
| `test_sparse_canary_replay.py` | PR #27 | 23 | PASS |
| **Total** | — | **453** | **PASS / 0 regression** |

Plus 8 Mac pre-existing fails (tied to `arena_pipeline.py:18` `os.chdir('/home/j13/j13-ops')` — these tests should PASS on Alaya since the path exists there).

## 4. Post-sync re-test plan

Once j13 resolves dirty state (per `03` §7) and we fast-forward to `73b931d2`:

```bash
ssh j13@100.123.49.102 "
  cd /home/j13/j13-ops
  zangetsu/.venv/bin/python -m pytest \
    zangetsu/tests/test_sparse_canary_observer.py \
    zangetsu/tests/test_sparse_canary_readiness.py \
    zangetsu/tests/test_sparse_canary_observation_runner.py \
    zangetsu/tests/test_sparse_canary_replay.py \
    zangetsu/tests/test_feedback_budget_allocator.py \
    zangetsu/tests/test_a2_a3_arena_batch_metrics.py \
    zangetsu/tests/test_generation_profile_identity_and_scoring.py \
    zangetsu/tests/test_feedback_budget_consumer.py \
    zangetsu/tests/test_profile_attribution_audit.py
"
```

Expected: ≥ 453 PASS (Alaya doesn't have the `os.chdir` problem so 8 pre-existing Mac fails should also PASS, putting Alaya at ~461).

## 5. Conclusion

Test validation is deferred until dirty state resolved + fast-forward complete. Mac-side validation provides high-confidence proxy for the new code's correctness; Alaya-side re-validation is the next required step after dirty state cleanup.
