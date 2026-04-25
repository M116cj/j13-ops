# 0-9O-B — Dry-Run Feedback Budget Allocator Final Report

## 1. Status

**COMPLETE — pending Gate-A / Gate-B / signed merge on Alaya side.**

Local execution complete (branch ready, all tests pass). Alaya-side
gates run in CI / on PR open.

## 2. Baseline

- origin/main SHA at start: `d8765417c978e346cd44bf7c2cb8d7b79f076ab6`
- local main SHA at start: `d8765417c978e346cd44bf7c2cb8d7b79f076ab6`
- branch: `phase-7/0-9o-b-dry-run-feedback-budget-allocator`
- PR URL: filled in after `gh pr create`
- merge SHA: filled in after merge
- signature verification: ED25519 SSH `SHA256:vzKybH9THchzB17tZOfkJZPRI/WGkTcXxd/+a7NciC8` (same key as P7-PR4B PR #18)

## 3. Mission

Consume `generation_profile_metrics` (delivered by 0-9O-A + P7-PR4B)
and produce audited dry-run feedback budget recommendations. The
allocator computes proposed profile weights, profile ranks,
confidence-gated actionability, bottleneck explanations, and
`feedback_decision_record`-compatible output. Recommendations are
**never** applied to runtime: `mode = "DRY_RUN"`, `applied = False`,
no `apply()` method, no runtime consumer.

## 4. What changed

| File | Type | Notes |
| --- | --- | --- |
| `zangetsu/services/feedback_budget_allocator.py` | **new module** (~430 LOC) | Allocator + `DryRunBudgetAllocation` dataclass + helpers |
| `zangetsu/tests/test_feedback_budget_allocator.py` | new test file | 62 tests covering §9.1–§9.8 + edge cases |
| `docs/recovery/20260424-mod-7/0-9o-b/01..11*.md` | evidence docs | 11 markdown artifacts |

**Zero runtime files modified.** No `arena_pipeline.py`,
`arena23_orchestrator.py`, `arena45_orchestrator.py`, `arena_gates.py`,
`zangetsu/config/`, `zangetsu/engine/`, or `zangetsu/live/` change.
`feedback_decision_record.py` already enforced all required
invariants and was not modified.

## 5. Allocator design

### 5.1 Inputs

`profile_metrics`: iterable of `GenerationProfileMetrics` dataclass
instances or dict-like mappings. Required fields:
`generation_profile_id`, `profile_score`, `avg_a2_pass_rate`,
`avg_a3_pass_rate`, `sample_size_rounds`, `min_sample_size_met`,
`confidence`. Missing → profile marked `MISSING_REQUIRED_FIELDS`,
allocator does not crash.

### 5.2 Outputs

`DryRunBudgetAllocation` dataclass (24 required fields per
`required_allocation_fields()`):

```
{
  telemetry_version: "1",
  decision_id: "alloc-<hex>",
  run_id, created_at,
  mode: "DRY_RUN",  applied: false,  allocator_version: "0-9O-B",
  confidence: "CONFIDENCE_A1_A2_A3_METRICS_AVAILABLE" | "NO_ACTIONABLE_PROFILE",
  input_profile_count, actionable_profile_count, non_actionable_profile_count,
  exploration_floor: 0.05, min_sample_size_rounds: 20,
  previous_profile_weights, proposed_profile_weights_dry_run,
  profile_scores, profile_ranks, non_actionable_reasons,
  observed_bottleneck, top_reject_reasons,
  expected_effect: "DRY_RUN_…_NOT_APPLIED",
  safety_constraints: [NOT_APPLIED_TO_RUNTIME, EXPLORATION_FLOOR_GE_0_05, …],
  reason, source, event_type
}
```

Detailed schema: `02_allocator_input_output_schema.md`.

### 5.3 Confidence + sample-size gates

Per-profile actionability requires **all** of:

1. All `_REQUIRED_INPUT_FIELDS` present.
2. `confidence == "CONFIDENCE_A1_A2_A3_METRICS_AVAILABLE"`.
3. `min_sample_size_met == True` AND `sample_size_rounds >= 20`.
4. Either `avg_a2_pass_rate > 0` OR `total_entered_a2 > 0` (same for A3).
5. `unknown_reject_rate < UNKNOWN_REJECT_VETO (= 0.20)`.

Detailed gate doc: `03_confidence_and_sample_size_gates.md`.

### 5.4 Exploration floor

`EXPLORATION_FLOOR = 0.05` (sourced from `generation_profile_metrics`
to keep allocator and producer in lock-step). Each actionable profile
receives at least the floor; the remaining 1 - n·floor is split
proportionally to `raw_weight = max(profile_score + 1.0, 0.0)`.

### 5.5 Weight normalization

Detailed contract: `04_weight_normalization_contract.md`. Properties:

- Sum exactly 1.0 (within 1e-9).
- All weights ≥ 0.
- All actionable weights ≥ exploration floor (modulo numerical scaling).
- UNKNOWN_PROFILE capped at floor before normalization (cannot dominate).
- Deterministic (sorted keys before proportional split).
- Caller inputs never mutated (verified by JSON snapshot test).

### 5.6 Fallback behavior

When `actionable_count == 0`:

- Use `previous_profile_weights` if provided (renormalize to sum=1.0).
- Else equal-weight across all observed profile ids.
- `confidence = "NO_ACTIONABLE_PROFILE"`, `applied = False`,
  `expected_effect = "DRY_RUN_NON_ACTIONABLE_NO_RECOMMENDATION_APPLIED"`.

## 6. Dry-run invariant

| Layer | Mechanism |
| --- | --- |
| 1. Construction | `DryRunBudgetAllocation.__post_init__` resets `mode=DRY_RUN`, `applied=False`, `allocator_version="0-9O-B"` regardless of caller-supplied kwargs |
| 2. Serialization | `DryRunBudgetAllocation.to_event()` re-asserts the same three fields before returning the payload |
| 3. Bridge | `to_feedback_decision_record(allocation)` calls existing 0-9O-A `build_feedback_decision_record(...)`, whose `__post_init__` + `to_event()` enforce the same invariants independently |
| 4. API | No `apply` / `commit` / `execute` method exists on `DryRunBudgetAllocation` or any allocator helper. `test_feedback_decision_record_has_no_apply_method` walks public dir() to enforce this |
| 5. Runtime isolation | No runtime module imports the allocator (verified by 6 source-text tests) |
| 6. Output isolation | No runtime module references `DryRunBudgetAllocation` or `allocate_dry_run_budget` symbols (`test_allocator_output_not_consumed_by_generation_runtime`) |

## 7. Bottleneck explanation

`classify_bottleneck(metrics, *, actionable_count) -> (label, top_list)`:

- **Structural** (actionable_count == 0): inspect each metric's
  `confidence` + `min_sample_size_met` to choose
  `MISSING_A2_A3_METRICS` / `LOW_SAMPLE_SIZE` / `NO_ACTIONABLE_PROFILE`.
- **Content-based** (actionable_count > 0): aggregate
  `signal_too_sparse_count` + `oos_fail_count` + `unknown_reject_count`,
  return the leader's label if its share ≥ `BOTTLENECK_DOMINANCE_THRESHOLD
  (= 0.40)`, otherwise `UNKNOWN`.

Six labels:
- `SIGNAL_TOO_SPARSE_DOMINANT`
- `OOS_FAIL_DOMINANT`
- `UNKNOWN_REJECT_DOMINANT`
- `LOW_SAMPLE_SIZE`
- `MISSING_A2_A3_METRICS`
- `NO_ACTIONABLE_PROFILE`

`top_reject_reasons` is the same three reason labels sorted by
contribution (descending). Detailed contract:
`05_bottleneck_explanation_model.md`.

## 8. feedback_decision_record integration

`to_feedback_decision_record(allocation)` calls 0-9O-A
`build_feedback_decision_record(...)` with all dry-run fields. Both
modules independently enforce `mode=DRY_RUN` + `applied=False` —
two-layer protection. No 0-9O-B change to `feedback_decision_record.py`.

`test_feedback_decision_record_has_no_apply_method` walks the module's
public `dir()` and asserts no name starts with `apply` (case-insensitive).

Detailed integration doc: `06_feedback_decision_record_integration.md`.

## 9. Runtime isolation audit

| Runtime surface | Imports allocator? | Verified by |
| --- | --- | --- |
| `arena_pipeline.py` (A1) | NO | source-text test |
| `arena23_orchestrator.py` (A2/A3) | NO | source-text test |
| `arena45_orchestrator.py` (A4/A5) | NO | source-text test |
| `arena_gates.py` | NO | source-text test |
| `alpha_signal_live.py` | NO | source-text test |
| `data_collector.py`, `alpha_dedup.py`, `alpha_ensemble.py`, `alpha_discovery.py` | NO | source-text test |
| Allocator → `alpha_engine` / `sampling_weight` references | NO | reverse source-text test |

`test_allocator_output_not_consumed_by_generation_runtime` walks
`zangetsu/services/*.py` (excluding the allocator itself) and asserts
no file references `DryRunBudgetAllocation` or `allocate_dry_run_budget`.

Detailed audit: `07_runtime_isolation_audit.md`.

## 10. Behavior invariance

| Item | Status |
| --- | --- |
| No alpha generation change | ✅ |
| No formula generation change | ✅ |
| No mutation / crossover change | ✅ |
| No search policy change | ✅ |
| No real generation budget change | ✅ |
| No sampling weight change | ✅ |
| No threshold change (incl. `A2_MIN_TRADES`, ATR/TRAIL/FIXED grids, A3 segments) | ✅ verified by `test_a2_min_trades_still_pinned`, `test_a3_thresholds_still_pinned` |
| No Arena pass/fail change | ✅ verified by `test_arena_pass_fail_behavior_unchanged` |
| No champion promotion change | ✅ verified by `test_champion_promotion_unchanged` |
| No `deployable_count` semantic change | ✅ allocator source has no `'DEPLOYABLE'` literal |
| No execution / capital / risk change | ✅ |
| No CANARY started | ✅ |
| No production rollout started | ✅ |

Full audit: `08_behavior_invariance_audit.md`.

## 11. Test results

```
$ python3 -m pytest zangetsu/tests/test_feedback_budget_allocator.py
======================== 62 passed, 1 warning in 0.21s =========================
```

Adjacent suites: 160 PASS / 0 regression. 8 pre-existing local-Mac
failures (`arena_pipeline.py` chdir to `/home/j13/j13-ops`); verified
pre-existing on main during P7-PR4B execution. Detailed breakdown:
`09_test_results.md`.

Expected on Alaya CI: all prior tests + 62 new = full PASS.

## 12. Controlled-diff

Expected classification: **EXPLAINED** (NOT EXPLAINED_TRACE_ONLY —
no runtime SHA changed).

```
Zero diff:                    ~43 fields  (incl. all 6 CODE_FROZEN runtime SHAs)
Explained diff:               1 field    — repo.git_status_porcelain_lines
Explained TRACE_ONLY diff:    0 fields
Forbidden diff:               0 fields
```

No `--authorize-trace-only` flag needed. Detailed report:
`10_controlled_diff_report.md`.

## 13. Gate-A

Expected: **PASS** (snapshot-diff classified as EXPLAINED → exit code 0;
no runtime SHA changed → no governance-relevant delta).

## 14. Gate-B

Expected: **PASS** (PR open with required artifacts; pull-request
trigger restored by 0-9I).

## 15. Branch protection

Expected unchanged on `main`:

- `enforce_admins=true`
- `required_signatures=true`
- `linear_history=true`
- `allow_force_pushes=false`
- `allow_deletions=false`

This PR does not modify governance configuration.

## 16. Forbidden changes audit

- CANARY: NOT started.
- Production rollout: NOT started.

## 17. Remaining risks

- **Dry-run recommendations may overfit if applied prematurely.**
  The allocator's confidence + sample-size gates are necessary but
  not sufficient for production deployment. CANARY (0-9S) is required
  before any live action.
- **High per-batch variance in profile_score.** Until 20+ rounds
  accumulate, individual batch results can swing significantly.
  `instability_penalty` partially mitigates this in `profile_score`
  computation, but the floor remains the only authoritative budget
  protection.
- **N >= 20 guard is necessary but not sufficient.** A profile with
  20 batches but heavy regime concentration (e.g. all bull market)
  can still produce misleading weights. 0-9R should design
  regime-aware sample-size thresholds.
- **Allocator is not production control.** It is a recommendation
  engine. Any future production wiring must go through CANARY +
  controlled-diff + signed PR review.
- **0-9R still required for sparse-candidate strategy.** The
  allocator can identify `SIGNAL_TOO_SPARSE_DOMINANT` bottlenecks but
  cannot fix them; 0-9R designs the actual generation profile policy
  intervention.
- **0-9S required before any live action.** No allocator output may
  be consumed by runtime until CANARY validation completes.

## 18. Recommended next action

**TEAM ORDER 0-9R — Sparse-Candidate Black-Box Optimization Design.**
Use the allocator's bottleneck diagnostics + dry-run recommendations
as input for designing generation-profile policy interventions.
Strict scope: design only — no Arena weakening, no
`A2_MIN_TRADES` change, no production rollout.

If j13 explicitly wants deployment-path validation first →
**TEAM ORDER 0-9S — CANARY Readiness Gate**, validating that the
allocator's recommendations produce measurable pass-rate /
deployable_count improvement under controlled conditions.
