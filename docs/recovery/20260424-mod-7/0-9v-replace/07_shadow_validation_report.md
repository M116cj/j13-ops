# 07 — Shadow Validation Report

## 1. Status

**SHADOW_BLOCKED_MISSING_TOOLS** (per order §11 fallback).

Cannot run shadow validation because the tools required (`sparse_canary_observer`, `sparse_canary_readiness_check`, `run_sparse_canary_observation`) **don't exist on Alaya yet**:

```
$ ls zangetsu/tools/sparse_canary_observer.py
ls: cannot access ... No such file or directory

$ ls zangetsu/tools/sparse_canary_readiness_check.py
ls: cannot access ... No such file or directory

$ ls zangetsu/services/sparse_canary_observer.py
ls: cannot access ... No such file or directory

$ ls zangetsu/services/feedback_budget_consumer.py
ls: cannot access ... No such file or directory

$ ls zangetsu/services/feedback_budget_allocator.py
ls: cannot access ... No such file or directory
```

These were all shipped via PR #19 / PR #22 / PR #23 / PR #25 / PR #26 /
PR #27, none of which have been fast-forwarded onto Alaya.

## 2. Per order §11

> "If shadow validation fails due missing telemetry: Record as SHADOW_BLOCKED_MISSING_TELEMETRY. Do not start runtime replacement unless runtime replacement does not depend on telemetry."

We extend this rule to "missing tools" — same effect. Replacement
gate (Phase H) treats this as a documented non-blocking limitation
because the missing tools are literally what the replacement is going
to install.

## 3. Mac-side proxy for shadow validation

Mac-side validation of the same tools (origin/main = `73b931d2`) is documented across PR #25 / PR #26 / PR #27:

| Tool | Mac validation result |
| --- | --- |
| `sparse_canary_readiness_check.check_readiness()` | 14 PASS + 1 OVERRIDE (preflight on `73b931d2`); 45 unit tests pass |
| `sparse_canary_observer.observe()` | 71 unit tests pass; dry-run invariants enforced; F-criteria suppressed at zero rounds |
| `run_sparse_canary_observation` | 21 unit tests pass; OBSERVING_NOT_COMPLETE at zero input |
| `replay_sparse_canary_observation` | 23 unit tests pass; classification, reconstruction, manifest |

## 4. Post-replacement shadow plan

After dirty state resolution + fast-forward + tool install:

```bash
ssh j13@100.123.49.102 "
  cd /home/j13/j13-ops
  zangetsu/.venv/bin/python -m zangetsu.tools.sparse_canary_readiness_check
  # expected: CR1-CR15 PASS (or CR6 OVERRIDE)
  zangetsu/.venv/bin/python -m zangetsu.tools.run_sparse_canary_observation \\
    --batch-events /home/j13/j13-ops/zangetsu/logs/arena_batch_metrics.jsonl \\
    --plans /home/j13/j13-ops/zangetsu/logs/sparse_candidate_dry_run_plans.jsonl \\
    --output-dir /home/j13/j13-ops/docs/recovery/20260424-mod-7/0-9v-replace/shadow-validation \\
    --run-id alaya-replace-shadow-001 \\
    --attribution-verdict GREEN \\
    --readiness-verdict PASS
"
```

This is the **post-replacement** verification. The expected outcome at
shadow time is `OBSERVING_NOT_COMPLETE` (no live arena pipeline rounds
have run yet on the new code).

## 5. Conclusion

| Field | Value |
| --- | --- |
| Readiness command | NOT RUN (tools missing) |
| Observer command | NOT RUN (tools missing) |
| Records written | 0 |
| Mode | N/A |
| applied=false | INHERITED (Mac-side validation) |
| No runtime mutation | **YES** (no shell command modified runtime) |
| No generation runtime connection | **YES** |
| Output path | none (deferred) |
| Result | **SHADOW_BLOCKED_MISSING_TOOLS** (documented non-blocking; will resolve post-replacement) |
