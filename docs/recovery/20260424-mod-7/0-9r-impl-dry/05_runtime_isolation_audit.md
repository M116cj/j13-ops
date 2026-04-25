# 05 — Runtime Isolation Audit

## 1. Forbidden import direction

The consumer is **downstream** of allocator + audit + identity. No
runtime / Arena / execution module may import the consumer.

```
                  feedback_budget_consumer.py  (this PR)
                              ▲
                              │
            READS (read-only types + constants):
                              │
              ┌───────────────┼──────────────────────────┐
              │               │                          │
feedback_budget_   feedback_decision_   generation_profile_*
allocator.py       record.py            (identity + metrics)
                              ▲
                              │
                arena_pass_rate_telemetry.py
                              ▲
                              │
                arena_pipeline / arena23 / arena45  (Arena runtime)
```

The consumer module sits at the leaf — there is no edge **out** of it
into runtime.

## 2. Verified-by-test isolation

| Test | Direction |
| --- | --- |
| `test_no_runtime_import_by_generation` | `arena_pipeline.py` does not contain `feedback_budget_consumer` |
| `test_no_runtime_import_by_arena` | `arena23_orchestrator.py` / `arena45_orchestrator.py` / `arena_gates.py` clean |
| `test_no_runtime_import_by_execution` | `alpha_signal_live.py` / `data_collector.py` / `alpha_dedup.py` / `alpha_ensemble.py` / `alpha_discovery.py` clean |
| `test_consumer_output_not_consumed_by_runtime` | walks `services/*.py`, asserts `SparseCandidateDryRunPlan` and `from zangetsu.services.feedback_budget_consumer` absent |
| `test_no_generation_budget_file_changed` | `arena_pipeline.py` does not reference the consumer |
| `test_no_sampling_weight_file_changed` | consumer source does not import `alpha_engine`, no `sampling_weight = ...` assignment |
| `test_consumer_not_imported_by_existing_consumer_substitutes` | no module exposes `budget_apply` / `apply_consumer_output` / `commit_plan` symbols |

## 3. Allowed downstream consumers

Only allowed:

- Tests (`zangetsu/tests/test_feedback_budget_consumer.py`).
- Offline reports / dashboards (none committed yet).
- Future PR-D `0-9S-READY` documentation.

When future PR (e.g. `0-9R-IMPL-APPLY`) wires the consumer into a
real generation budget consumer, it must:

1. Be authorized by an explicit j13 order.
2. Pass through `0-9S CANARY` first.
3. Implement its own runtime isolation tests at that boundary.

## 4. Apply-path absence

Public surface of `feedback_budget_consumer`:

```
ALLOWED_INTERVENTIONS, BLOCK_*, CONSUMER_VERSION, DEFAULT_*,
EVENT_TYPE_SPARSE_CANDIDATE_DRY_RUN_PLAN, EMA_ALPHA_MAX,
INTERVENTION_PB_*, MODE_DRY_RUN, PLAN_STATUS_*,
SMOOTHING_WINDOW_MIN, SparseCandidateDryRunPlan,
TELEMETRY_VERSION, UNKNOWN_REJECT_VETO, VERDICT_*,
consume, ema_smooth, enforce_floor_and_diversity,
limit_step, required_plan_fields, safe_consume, serialize_plan
```

No `apply` / `commit` / `execute` / `dispatch` / `publish` /
`run_apply` symbol. Verified by `test_consumer_has_no_apply_method`.

## 5. Forbidden symbol grep

```
grep -nE "^def apply_|^class Apply" \
    zangetsu/services/feedback_budget_consumer.py
# expected: empty
```

```
grep -rn "feedback_budget_consumer" zangetsu/services/ \
    | grep -v feedback_budget_consumer.py \
    | grep -v feedback_budget_allocator.py
# expected: empty
```

(`feedback_budget_allocator.py` is allow-listed because the consumer
imports allocator types; the import direction is one-way and that's
fine.)
