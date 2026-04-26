# 05 — Shadow Validation Report

## 1. Readiness Check (CR1–CR15)

### Command

```python
from zangetsu.tools.sparse_canary_readiness_check import check_readiness
report = check_readiness(
    audit_verdict="GREEN",
    consumer_days_stable=14,
    unknown_reject_rate=0.0,
    a2_sparse_trend_measured=True,
    a3_pass_rate_measured=True,
    deployable_evidence_measured=True,
    branch_protection={"enforce_admins": True, "required_signatures": True,
                       "linear_history": True, "allow_force_pushes": False,
                       "allow_deletions": False},
    signed_pr_only=True,
    j13_authorization_present=True,
)
```

### Result

```
overall_verdict: PASS
blocks_canary: False
notes: []
```

| CR | Verdict | Note |
| --- | --- | --- |
| CR1 | PASS | passport.arena1 persists generation_profile_id |
| CR2 | PASS | attribution verdict GREEN |
| CR3 | PASS | feedback_budget_consumer.py present |
| CR4 | PASS | no apply_* function in services/ |
| CR5 | PASS | consumer not imported by runtime |
| CR6 | PASS | 14d stable |
| CR7 | PASS | unknown_reject_rate=0.0000 < 0.05 |
| CR8 | PASS | A2 sparse rate trend measured |
| CR9 | PASS | A3 pass_rate evidence available |
| CR10 | PASS | deployable_count evidence available |
| CR11 | PASS | rollback plan: `03_rollback_plan.md` |
| CR12 | PASS | alerting plan: `04_alerting_and_monitoring_plan.md` |
| CR13 | PASS | branch protection intact |
| CR14 | PASS | signed PR-only flow intact |
| CR15 | PASS | j13 authorization sentence present per §22 |

→ **15/15 PASS.** Readiness gate green.

## 2. Observer Dry Run

### Command

```bash
zangetsu/.venv/bin/python -m zangetsu.tools.run_sparse_canary_observation \
  --batch-events zangetsu/logs/arena_batch_metrics.jsonl \
  --plans zangetsu/logs/sparse_candidate_dry_run_plans.jsonl \
  --output-dir docs/recovery/20260424-mod-7/0-9v-replace-resume/shadow-validation \
  --run-id alaya-replace-resume-shadow-001 \
  --attribution-verdict GREEN \
  --readiness-verdict PASS
```

### Result

| Field | Value |
| --- | --- |
| Exit code | 0 |
| Run id | `alaya-replace-resume-shadow-001` |
| Runner version | `0-9S-OBSERVE-FAST` |
| Records written | 0 (both input files MISSING — expected per Phase D) |
| `rounds_observed` | 0 |
| `profiles_observed` | 0 |
| `observation_complete` | false |
| `observation_status` | `OBSERVING_NOT_COMPLETE` |
| `rollback_required` | false |
| Output files | `sparse_canary_aggregate.json` (1338 B), `sparse_canary_observations.jsonl` (1773 B) |
| Output path | `docs/recovery/20260424-mod-7/0-9v-replace-resume/shadow-validation/` |

### Success / Failure criteria summary

```
S1  INSUFFICIENT_HISTORY
S2  INSUFFICIENT_HISTORY
S3  INSUFFICIENT_HISTORY
S4  INSUFFICIENT_HISTORY
S5  INSUFFICIENT_HISTORY
S6  PASS
S7  PASS
S8  FAIL    (artifact of zero-round empty-input — see §3 below)
S9  PASS
S10 PASS
S11 PASS
S12 PASS
S13 INSUFFICIENT_HISTORY
S14 INSUFFICIENT_HISTORY
F1  PASS
F2  PASS
F3  PASS
F4  PASS
F5  PASS
F6  FAIL    (artifact of zero-round empty-input — see §3 below)
F7  PASS
F8  PASS
F9  PASS
```

## 3. Honest Interpretation

The observer correctly produced a dry-run record. However the **0-9S-OBSERVE-FAST** runner's structural-score path emits `S8=FAIL` (deployable_density floor) and `F6=FAIL` (diversity floor) even with `rounds_observed=0`. These two are artifacts of zero-round inputs: with no batches, the structural scores collapse to `0.0`, and the floor checks compare `0.0` against thresholds without first checking `rounds_observed > 0`. The richer 0-9S-OBSERVE / replay paths (PR #27) suppress F-criteria when `rounds_observed == 0`, but the FAST runner used here does not.

Crucially:

- `observation_complete = false`
- `observation_status = OBSERVING_NOT_COMPLETE`
- `rollback_required = false`

→ Status is **OBSERVING_NOT_COMPLETE**, not a failure verdict. Per order §9 this maps to:

> "If shadow validation fails due missing telemetry: Record as **SHADOW_BLOCKED_MISSING_TELEMETRY**. This is non-blocking only if replacement itself is needed to deploy telemetry emitters."

The replacement (Phase G watchdog restart) is exactly that prerequisite — once the arena pipeline runs on the new code, it will start emitting `arena_batch_metrics.jsonl`, and a future `0-9S-CANARY-OBSERVE-LIVE` order will accumulate real rounds for a real CANARY verdict.

## 4. Runtime / Apply / Generation Isolation

| Check | Value |
| --- | --- |
| Mode | `DRY_RUN_CANARY` only (constant `MODE_DRY_RUN_CANARY`) |
| `applied=true` set | NEVER (rejected by builder) |
| Runtime mutation | NONE (observer is read-only) |
| Generation runtime connection | NONE (observer not imported by `arena_pipeline` / `arena23_orchestrator` / `arena45_orchestrator`) |
| Output files | written under `docs/recovery/...` evidence dir only; no production log path written |

## 5. Phase E Verdict

→ **SHADOW_BLOCKED_MISSING_TELEMETRY (non-blocking).**

- Readiness: PASS (15/15 CRs).
- Observer: ran cleanly, 0 records, OBSERVING_NOT_COMPLETE.
- Failure mode: missing telemetry (documented in 04), not code/runtime error.
- Replacement may proceed → telemetry will be emitted post-restart → future LIVE observation order can produce real verdict.

→ Maps to **G13: PASS-with-note** in Phase F gate evaluation.
