# 02 — Safe Intervention Scope

## 1. Allowed scope (this PR)

| Class | Code | Implementation |
| --- | --- | --- |
| Profile exploration floor | `PB-FLOOR` | `enforce_floor_and_diversity(..., floor=0.05)` |
| Profile diversity preservation | `PB-DIV` | `enforce_floor_and_diversity(..., diversity_cap_min=2)` |
| Profile shift recommendation | `PB-SHIFT` | EMA + max-step + final renormalization → `final_dry_run_weights` |

`ALLOWED_INTERVENTIONS = ("PB-FLOOR", "PB-DIV", "PB-SHIFT")` — exact
tuple locked by `test_allowed_interventions_only`.

## 2. Forbidden scope (this PR)

| Class | Code | Reason |
| --- | --- | --- |
| Profile suppression | PB-SUPPRESS | needs CANARY + j13 order (§02 0-9R taxonomy) |
| Profile quarantine | PB-QUARANTINE | requires cooldown / re-entry rule (PB-RESURRECT pair) |
| Profile resurrection | PB-RESURRECT | depends on QUARANTINE first |
| Mutation pressure adjust | PB-MUT | changes generator behavior — high risk |
| Density-aware preset | PB-DENSITY | new generation profile preset — generation policy change |
| Pre-A2 density screen | PRE-A2-SCREEN | candidate prefilter — generation policy change |

None of these codes appear in the consumer's source as either
intervention selectors or implementation paths. Verified by
`test_forbidden_pb_suppress_not_executed` and
`test_forbidden_pb_quarantine_not_executed`.

## 3. SparseCandidateDryRunPlan schema (28 fields)

| Field | Type | Notes |
| --- | --- | --- |
| `telemetry_version` | str | `"1"` |
| `plan_id` | str | `plan-<hex>` UUID prefix |
| `run_id` | str | caller-supplied |
| `created_at` | str | UTC ISO8601 |
| `mode` | str | enforced `"DRY_RUN"` |
| `applied` | bool | enforced `False` |
| `consumer_version` | str | enforced `"0-9R-IMPL-DRY"` |
| `source_allocation_id` | str | from `DryRunBudgetAllocation.decision_id` |
| `attribution_verdict` | str | `GREEN` / `YELLOW` / `RED` / `UNAVAILABLE` |
| `confidence` | str | passthrough from allocation |
| `plan_status` | str | `ACTIONABLE_DRY_RUN` / `NON_ACTIONABLE` / `BLOCKED` |
| `actionable_profile_count` | int | passthrough |
| `observed_bottleneck` | str | passthrough |
| `selected_interventions` | list[str] | subset of `ALLOWED_INTERVENTIONS` |
| `previous_profile_weights` | dict | caller-supplied or allocation-supplied |
| `allocator_proposed_weights` | dict | passthrough from allocator |
| `smoothed_proposed_weights` | dict | after EMA |
| `max_step_limited_weights` | dict | after step clip |
| `final_dry_run_weights` | dict | after floor + diversity, sum=1.0 |
| `exploration_floor` | float | `0.05` |
| `diversity_cap` | int | `2` |
| `ema_alpha` | float | ≤ 0.20 |
| `smoothing_window` | int | ≥ 5 |
| `max_step_abs` | float | ≤ 0.10 |
| `safety_constraints` | list[str] | inherited from `DEFAULT_SAFETY_CONSTRAINTS` + YELLOW marker if applicable |
| `non_actionable_reasons` | dict[str, list[str]] | from allocator |
| `block_reasons` | list[str] | governance-grade gating failures |
| `expected_effect` | str | `"DRY_RUN_..."` |
| `rollback_requirements` | list[str] | nine-item default tuple |
| `source` | str | `"feedback_budget_consumer"` |

`event_type` added by `to_event()`: `sparse_candidate_dry_run_plan`.

## 4. Smoothing knob defaults & limits

| Knob | Default | Limit |
| --- | --- | --- |
| `ema_alpha` | `0.20` | `0 < α ≤ 0.20` (caller bad input → reset to default) |
| `smoothing_window` | `5` | `≥ 5` (caller bad input → reset to default) |
| `max_step_abs` | `0.10` | `0 < step ≤ 1.0` (caller bad input → reset to default) |
| `exploration_floor` | `0.05` | `0.05 ≤ floor < 1.0` (caller bad input → reset to default) |
| `diversity_cap_min` | `2` | `≥ 1` (caller bad input → reset to default) |

All clamped in `__post_init__`.

## 5. Block reasons

```
INPUT_MODE_NOT_DRY_RUN
INPUT_APPLIED_TRUE
INPUT_BAD_ALLOCATOR_VERSION
ATTRIBUTION_VERDICT_RED
LOW_CONFIDENCE
LOW_SAMPLE_SIZE
FEWER_THAN_TWO_ACTIONABLE_PROFILES
UNKNOWN_REJECT_TOO_HIGH
COUNTER_INCONSISTENCY
```

The first three are governance-grade → `plan_status = BLOCKED`. The
remaining are content-grade → `plan_status = NON_ACTIONABLE`.
