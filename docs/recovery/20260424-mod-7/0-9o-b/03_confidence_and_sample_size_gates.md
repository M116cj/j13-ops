# 0-9O-B — Confidence & Sample-Size Gates

## 1. Per-profile 條件

`evaluate_profile_actionability(metric)` 串接以下檢核（順序固定，原因
追加 `reasons` list）：

```
1. _has_required_fields(metric) == False
   → reasons += [REASON_MISSING_FIELDS]
   → return (False, reasons)            # short-circuit

2. confidence != "CONFIDENCE_A1_A2_A3_METRICS_AVAILABLE"
   ├─ confidence == "LOW_CONFIDENCE_UNTIL_A2_A3_METRICS_AVAILABLE"
   │     → reasons += [REASON_MISSING_A2_A3]
   ├─ confidence == "LOW_SAMPLE_SIZE_UNTIL_20_ROUNDS"
   │     → reasons += [REASON_LOW_SAMPLE_SIZE]
   └─ otherwise
         → reasons += [REASON_LOW_CONFIDENCE]

3. min_sample_size_met != True OR sample_size_rounds < 20
   → reasons += [REASON_LOW_SAMPLE_SIZE]   # de-duped

4. (avg_a2_pass_rate == 0 AND total_entered_a2 == 0)
   OR (avg_a3_pass_rate == 0 AND total_entered_a3 == 0)
   → reasons += [REASON_MISSING_A2_A3]   # de-duped

5. unknown_reject_rate >= UNKNOWN_REJECT_VETO (= 0.20)
   → reasons += [REASON_COUNTER_INCONSISTENCY]

return (len(reasons) == 0, reasons)
```

## 2. 全局 confidence

| 情境 | `allocation.confidence` | `applied` |
| --- | --- | --- |
| ≥ 1 profile actionable | `CONFIDENCE_A1_A2_A3_METRICS_AVAILABLE` | `False` |
| 0 profile actionable | `NO_ACTIONABLE_PROFILE` | `False` |

無論哪一種，`applied=False` 維持不變 — 這是 dry-run-only 不變式，
與 actionability 解耦。

## 3. 「`actionable=True` 仍然 `applied=False`」

這條順序 **永遠成立**。actionable 只是說「dry-run 推薦可信度足夠」，
**不**意味要 apply。`expected_effect` 在 actionable 情境下為
`"DRY_RUN_ALLOCATION_RECOMMENDED_NOT_APPLIED"`，在 non-actionable 為
`"DRY_RUN_NON_ACTIONABLE_NO_RECOMMENDATION_APPLIED"`。

## 4. 對應測試

`test_feedback_budget_allocator.py`：

- `test_confidence_a1_a2_a3_available_allows_actionable_dry_run`
- `test_low_confidence_blocks_actionable_recommendation`
- `test_low_sample_size_blocks_actionable_recommendation`
- `test_min_sample_size_20_required`
- `test_missing_a2_a3_metrics_blocks_actionability`
- `test_counter_inconsistency_blocks_actionability`
- `test_evaluate_profile_actionability_missing_fields`

每個 reason 至少對應一個測試。
