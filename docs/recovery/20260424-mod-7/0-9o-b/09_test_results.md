# 0-9O-B — Test Results

## 1. 新增測試套件

`zangetsu/tests/test_feedback_budget_allocator.py` — 62 tests，
覆蓋 TEAM ORDER §9.1–§9.8 + extra edge cases。

```
$ python3 -m pytest zangetsu/tests/test_feedback_budget_allocator.py
============================= test session starts ==============================
platform darwin -- Python 3.14.3, pytest-9.0.2, pluggy-1.6.0
collected 62 items

zangetsu/tests/test_feedback_budget_allocator.py ......................... [ 40%]
.........................................                                  [100%]

======================== 62 passed, 1 warning in 0.21s =========================
```

## 2. 對照 §9 要求

| § | Required test | 實際測試 |
| --- | --- | --- |
| §9.1 | `test_dry_run_budget_allocation_schema_contains_required_fields` | ✅ |
| §9.1 | `test_allocator_output_mode_is_dry_run` | ✅ |
| §9.1 | `test_allocator_output_applied_is_false` | ✅ |
| §9.1 | `test_allocator_version_is_0_9o_b` | ✅ |
| §9.2 | `test_weights_sum_to_one` | ✅ |
| §9.2 | `test_weight_calculation_is_deterministic` | ✅ |
| §9.2 | `test_weight_calculation_does_not_mutate_inputs` | ✅ |
| §9.2 | `test_exploration_floor_enforced` | ✅ |
| §9.2 | `test_negative_scores_do_not_create_negative_weights` | ✅ |
| §9.2 | `test_all_non_actionable_profiles_use_safe_fallback` | ✅ |
| §9.2 | `test_unknown_profile_does_not_dominate_allocation` | ✅ |
| §9.3 | `test_confidence_a1_a2_a3_available_allows_actionable_dry_run` | ✅ |
| §9.3 | `test_low_confidence_blocks_actionable_recommendation` | ✅ |
| §9.3 | `test_low_sample_size_blocks_actionable_recommendation` | ✅ |
| §9.3 | `test_min_sample_size_20_required` | ✅ |
| §9.3 | `test_missing_a2_a3_metrics_blocks_actionability` | ✅ |
| §9.3 | `test_counter_inconsistency_blocks_actionability` | ✅ |
| §9.4 | `test_signal_too_sparse_penalty_reduces_dry_run_weight` | ✅ |
| §9.4 | `test_oos_fail_penalty_reduces_dry_run_weight` | ✅ |
| §9.4 | `test_unknown_reject_penalty_strongly_reduces_confidence` | ✅ |
| §9.4 | `test_counter_inconsistency_marks_profile_non_actionable` | ✅ |
| §9.5 | `test_detects_signal_too_sparse_dominant_bottleneck` | ✅ |
| §9.5 | `test_detects_oos_fail_dominant_bottleneck` | ✅ |
| §9.5 | `test_detects_unknown_reject_dominant_bottleneck` | ✅ |
| §9.5 | `test_detects_low_sample_size_bottleneck` | ✅ |
| §9.5 | `test_detects_no_actionable_profile_bottleneck` | ✅ |
| §9.6 | `test_feedback_decision_record_stores_allocator_output` | ✅ |
| §9.6 | `test_feedback_decision_record_mode_remains_dry_run` | ✅ |
| §9.6 | `test_feedback_decision_record_applied_false_enforced` | ✅ |
| §9.6 | `test_feedback_decision_record_rejects_or_overrides_applied_true` | ✅ |
| §9.6 | `test_feedback_decision_record_has_no_apply_method` | ✅ |
| §9.6 | `test_feedback_decision_record_contains_safety_constraints` | ✅ |
| §9.7 | `test_allocator_not_imported_by_alpha_generation_runtime` | ✅ |
| §9.7 | `test_allocator_not_imported_by_arena_runtime` | ✅ |
| §9.7 | `test_allocator_not_imported_by_execution_runtime` | ✅ |
| §9.7 | `test_allocator_output_not_consumed_by_generation_runtime` | ✅ |
| §9.7 | `test_no_generation_budget_file_changed` | ✅ |
| §9.7 | `test_no_sampling_weight_file_changed` | ✅ |
| §9.8 | `test_no_threshold_constants_changed` | ✅ |
| §9.8 | `test_a2_min_trades_still_pinned` | ✅ |
| §9.8 | `test_a3_thresholds_still_pinned` | ✅ |
| §9.8 | `test_arena_pass_fail_behavior_unchanged` | ✅ |
| §9.8 | `test_champion_promotion_unchanged` | ✅ |
| §9.8 | `test_deployable_count_semantics_unchanged` | ✅ |
| §9.8 | `test_profile_score_remains_read_only` | ✅ |
| §9.8 | `test_next_budget_weight_dry_run_not_applied` | ✅ |
| extra | `test_allocator_event_type_is_dry_run_budget_allocation` | ✅ |
| extra | `test_allocator_invariants_resilient_to_caller_kwargs` | ✅ |
| extra | `test_allocator_invariants_resilient_to_post_construction_mutation` | ✅ |
| extra | `test_serialize_allocation_emits_valid_json` | ✅ |
| extra | `test_compute_proposed_weights_zero_score_uses_floor_only` | ✅ |
| extra | `test_compute_proposed_weights_handles_empty_input` | ✅ |
| extra | `test_equal_weight_fallback_deterministic_and_normalized` | ✅ |
| extra | `test_evaluate_profile_actionability_missing_fields` | ✅ |
| extra | `test_detects_missing_a2_a3_bottleneck` | ✅ |
| extra | `test_bottleneck_published_in_allocation_record` | ✅ |
| extra | `test_allocator_handles_dataclass_input` | ✅ |
| extra | `test_allocator_handles_none_input` | ✅ |
| extra | `test_allocator_handles_garbage_input` | ✅ |
| extra | `test_safe_allocate_returns_value_on_success` | ✅ |
| extra | `test_previous_profile_weights_used_as_fallback` | ✅ |
| extra | `test_allocator_input_count_matches_coerceable_inputs` | ✅ |

46 個 §9 對應測試 + 16 個 extra edge case 測試 = 62 / 62 PASS。
落在 order 規定的 35–60 區間之上（含 extra 邊界測試）。

## 3. 鄰近既有套件無 regression

```
$ python3 -m pytest \
    zangetsu/tests/test_a2_a3_arena_batch_metrics.py \
    zangetsu/tests/test_arena_pass_rate_telemetry.py \
    zangetsu/tests/test_generation_profile_identity_and_scoring.py \
    zangetsu/tests/test_arena_rejection_taxonomy.py
========================= 8 failed, 160 passed in 0.43s ========================
```

8 個 failed 全為 pre-existing local Mac fail，root cause 為
`arena_pipeline.py` 模組頂端 `os.chdir('/home/j13/j13-ops')`，路徑只
存在於 Alaya 生產機。已在 P7-PR4B 期間驗證為 main 上同樣 fail。
**0 個 regression 來自 0-9O-B**。

## 4. Local Mac 終局統計

- **新增 0-9O-B suite**：62 PASS / 0 FAIL
- **既有可執行 suite**：160 PASS / 0 regression
- **既有 pre-existing fail（與本 PR 無關）**：8

CI 於 Alaya 上的預期：所有 0-9O-A / P7-PR4B / P7-PR4-LITE / 0-9I /
0-9H / 0-9G / 0-9F 既有測試 + 62 新增 = 全 PASS。
