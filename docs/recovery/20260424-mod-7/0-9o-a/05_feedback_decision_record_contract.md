# 0-9O-A — feedback_decision_record Contract

## 1. Purpose

Append-only audit record for a proposed generation-budget change. In
0-9O-A every record is **dry-run** — the contract does not permit
recording an applied decision.

## 2. Event type

`event_type = "feedback_decision_record"`, `telemetry_version = "1"`.

## 3. Fields

| Field | Type | Invariant |
|-------|------|-----------|
| `decision_id` | string | `"dec-" + 16 hex chars` |
| `telemetry_version` | string | `"1"` |
| `run_id` | string | caller-supplied |
| `created_at` | RFC3339 Z | UTC |
| `mode` | string | MUST equal `"DRY_RUN"` |
| `mode_must_equal` | string | MUST equal `"DRY_RUN"` |
| `previous_profile_weights` | dict | `{profile_id: float}` |
| `proposed_profile_weights_dry_run` | dict | `{profile_id: float}` (NOT applied) |
| `profile_scores` | dict | `{profile_id: float}` |
| `observed_bottleneck` | string | free-form |
| `top_reject_reasons` | list[string] | canonical reason names |
| `expected_effect` | string | free-form |
| `confidence` | string | `LOW / MEDIUM / HIGH` |
| `min_sample_size_met` | bool | surfaced from metrics |
| `safety_constraints` | list[string] | defaults to `DEFAULT_SAFETY_CONSTRAINTS` |
| `applied` | bool | MUST equal `False` |
| `applied_must_equal_false` | bool | MUST equal `True` |
| `reason` | string | free-form |
| `source` | string | `"feedback_decision_record"` |

## 4. Invariant enforcement

Invariants are enforced at three layers:

1. **Constructor default**: `mode="DRY_RUN"`, `applied=False`.
2. **`__post_init__`**: unconditionally resets `mode`, `applied`,
   `mode_must_equal`, `applied_must_equal_false` regardless of what the
   caller passed in — including `applied=True`.
3. **`to_event()`**: re-applies the same four invariants at serialization
   time, so if a caller mutates the dataclass field directly after
   construction, the emitted JSON still carries `applied=False`.

## 5. Default safety constraints

Every record auto-populates `safety_constraints` with:

```
A2_MIN_TRADES_UNCHANGED
ARENA_PASS_FAIL_LOGIC_UNCHANGED
CHAMPION_PROMOTION_UNCHANGED
DEPLOYABLE_COUNT_SEMANTICS_UNCHANGED
EXECUTION_CAPITAL_RISK_UNCHANGED
EXPLORATION_FLOOR_GE_0_05
NOT_APPLIED_TO_RUNTIME
DRY_RUN_MODE_ENFORCED
```

## 6. Builders

| Function | Behavior |
|----------|----------|
| `build_feedback_decision_record(...)` | returns a `FeedbackDecisionRecord`; raises on fundamental kwarg misuse (e.g. missing `run_id`) |
| `safe_build_feedback_decision_record(**kwargs)` | exception-safe wrapper returning `None` on error |
| `serialize_feedback_decision_record(record)` | JSON-serializes; never raises (empty string on error) |

## 7. Append-only discipline

The schema has no `revised_from`, no mutation timestamp, no
`last_updated_at`. Each record represents a single decision moment. A
follow-up decision emits a new record with its own `decision_id` and
`created_at`.

## 8. Not in scope

- Writing records to persistent storage (Postgres / JSONL) — future
  0-9O-B.
- Consuming records to mutate the generation runtime — future 0-9O-B.
- Revising / recalling records — explicitly forbidden.

## 9. Tests covering this contract

- `test_feedback_decision_record_is_append_only_shape`
- `test_feedback_decision_record_mode_is_dry_run`
- `test_feedback_decision_record_applied_is_false`
- `test_feedback_decision_record_rejects_applied_true`
- `test_feedback_decision_record_contains_safety_constraints`
