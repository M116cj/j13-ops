# 01 — Dry-Run Consumer Design

## 1. Mission

Build the **dry-run runtime consumer** of 0-9O-B's
`DryRunBudgetAllocation` — produce sparse-candidate intervention
plans without ever touching real generation budget, sampling
weights, or any Arena gate.

## 2. Module

`zangetsu/services/feedback_budget_consumer.py` (new). Pure-Python.
No DB / network / filesystem IO. Imports limited to:

- `zangetsu.services.feedback_budget_allocator` (read-only types)
- `zangetsu.services.feedback_decision_record` (`DEFAULT_SAFETY_CONSTRAINTS`)
- `zangetsu.services.generation_profile_identity` (`UNKNOWN_PROFILE_ID`)
- `zangetsu.services.generation_profile_metrics` (constants only)

## 3. Three-layer dry-run invariant

1. `SparseCandidateDryRunPlan.__post_init__` resets `mode=DRY_RUN`,
   `applied=False`, `consumer_version="0-9R-IMPL-DRY"` regardless of
   caller-supplied kwargs.
2. `to_event()` re-asserts the same fields at serialization time.
3. No public `apply` / `commit` / `execute` symbol. Verified by
   `dir()`-based test.
4. No runtime module imports the consumer (verified by source-text
   tests).

## 4. Allowed interventions

| Code | Description |
| --- | --- |
| `PB-FLOOR` | Per-profile exploration floor enforcement |
| `PB-DIV` | Profile diversity preservation |
| `PB-SHIFT` | Dry-run shift recommendation only |

`ALLOWED_INTERVENTIONS = ("PB-FLOOR", "PB-DIV", "PB-SHIFT")` — locked
by test. PB-SUPPRESS / PB-QUARANTINE / PB-RESURRECT / PB-MUT /
PB-DENSITY / PRE-A2-SCREEN are explicitly absent.

## 5. Gating chain

A plan is `ACTIONABLE_DRY_RUN` only when **all** of:

- Allocation `mode == "DRY_RUN"` and `applied is False`
- `confidence == "CONFIDENCE_A1_A2_A3_METRICS_AVAILABLE"`
- `actionable_profile_count >= 2`
- No profile flagged `COUNTER_INCONSISTENCY`
- Aggregate `unknown_reject_rate < 0.05` (consumer-stricter than
  allocator's 0.20)
- Attribution verdict not `RED` (verdict from 0-9P-AUDIT)
- (Optional caller-side) all profile metrics report
  `sample_size_rounds >= 20`

When any check fails: plan is `NON_ACTIONABLE` (or `BLOCKED` for
governance-grade failures like applied=True input). The plan is
still emitted with `applied=False` so observers can record the
attempt.

## 6. Smoothing pipeline

```
allocator_proposed_weights
    │
    ▼  ema_smooth(α ≤ 0.20, window ≥ 5)
smoothed_proposed_weights
    │
    ▼  limit_step(prev_weights, max_step ≤ 0.10)
max_step_limited_weights
    │
    ▼  enforce_floor_and_diversity(floor=0.05, cap_min=2)
final_dry_run_weights   (sums to 1.0)
```

UNKNOWN_PROFILE is capped at floor before normalization. Sum-to-1.0
sanity rebalance at the end of `enforce_floor_and_diversity`.

## 7. Plan schema (28 fields)

See `02_safe_intervention_scope.md` §3. Locked by `required_plan_fields()`.

## 8. Failure handling

- `consume()` never raises; pathological inputs produce a
  `BLOCKED` plan with `block_reasons` populated.
- `safe_consume()` wrapper additionally catches any internal
  exception and returns `BLOCKED` with the exception class name in
  `reason`.

## 9. Out of scope

- Connecting plans to real generation budget.
- Mutation / crossover probability change.
- Threshold change.
- Arena pass/fail change.
- Champion promotion change.
- Deployable_count semantics change.
- CANARY activation.
- Production rollout.
