# 0-9O-B — feedback_decision_record Integration

## 1. 既有 0-9O-A 模組

`zangetsu/services/feedback_decision_record.py`（0-9O-A 交付）已完整
支援所有 0-9O-B 要求的 fields：

| 0-9O-B §7 fields | 0-9O-A 既有 |
| --- | --- |
| `decision_id` | ✅ auto-generated `dec-` 前綴 |
| `telemetry_version` | ✅ |
| `run_id` | ✅ |
| `created_at` | ✅ UTC ISO8601 |
| `mode` | ✅ 強制 `DRY_RUN` |
| `previous_profile_weights` | ✅ |
| `proposed_profile_weights_dry_run` | ✅ |
| `profile_scores` | ✅ |
| `observed_bottleneck` | ✅ |
| `top_reject_reasons` | ✅ |
| `expected_effect` | ✅ |
| `confidence` | ✅ |
| `min_sample_size_met` | ✅ |
| `safety_constraints` | ✅ |
| `applied` | ✅ 強制 `False` |
| `reason` | ✅ |
| `source` | ✅ |

`__post_init__` + `to_event()` 已雙層強制 `mode=DRY_RUN` /
`applied=False`，沒有 `apply()` method。0-9O-B 不需修改本檔。

## 2. 0-9O-B 整合方式

新模組 `feedback_budget_allocator.py` 提供：

```python
def to_feedback_decision_record(allocation: DryRunBudgetAllocation):
    return build_feedback_decision_record(
        run_id=allocation.run_id,
        previous_profile_weights=allocation.previous_profile_weights,
        proposed_profile_weights_dry_run=allocation.proposed_profile_weights_dry_run,
        profile_scores=allocation.profile_scores,
        observed_bottleneck=allocation.observed_bottleneck,
        top_reject_reasons=allocation.top_reject_reasons,
        expected_effect=allocation.expected_effect,
        confidence=allocation.confidence,
        min_sample_size_met=(
            allocation.confidence == CONFIDENCE_A1_A2_A3_AVAILABLE
        ),
        safety_constraints=allocation.safety_constraints,
        reason=allocation.reason,
        source="feedback_budget_allocator",
    )
```

兩個模組各自獨立 dry-run 不變式檢核（雙層）：

1. `DryRunBudgetAllocation.__post_init__` / `to_event()` —
   `mode=DRY_RUN`、`applied=False`、`allocator_version="0-9O-B"`。
2. `FeedbackDecisionRecord.__post_init__` / `to_event()` —
   `mode=DRY_RUN`、`applied=False`、`safety_constraints` 含
   `NOT_APPLIED_TO_RUNTIME`。

## 3. 安全測試

`test_feedback_budget_allocator.py`：

- `test_feedback_decision_record_stores_allocator_output`
- `test_feedback_decision_record_mode_remains_dry_run`
- `test_feedback_decision_record_applied_false_enforced`
- `test_feedback_decision_record_rejects_or_overrides_applied_true`
- `test_feedback_decision_record_has_no_apply_method`
- `test_feedback_decision_record_contains_safety_constraints`

`test_feedback_decision_record_has_no_apply_method` 用 `dir()` 走訪
public names 並斷言沒有任何 `apply*` 開頭的 export — 雙層防呆。
