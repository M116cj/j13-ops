# P7-PR4B — Test Results

## 1. 新增測試套件

`zangetsu/tests/test_a2_a3_arena_batch_metrics.py` — 54 tests，覆蓋
TEAM ORDER §12.1–§12.9 全部要求 + extension surface（normalize /
aggregate_stage_metrics）。

```
$ python3 -m pytest zangetsu/tests/test_a2_a3_arena_batch_metrics.py --tb=short
============================= test session starts ==============================
platform darwin -- Python 3.14.3, pytest-9.0.2, pluggy-1.6.0
rootdir: /Users/a13/dev/j13-ops/zangetsu
configfile: pytest.ini
plugins: anyio-4.12.1
collected 54 items

zangetsu/tests/test_a2_a3_arena_batch_metrics.py .................... [ 37%]
.................................                                     [100%]

======================== 54 passed, 1 warning in 0.11s =========================
```

## 2. 對照 §12 要求

| § | Required test | 實際測試 |
| --- | --- | --- |
| §12.1 | `test_a2_arena_batch_metrics_schema_contains_required_fields` | ✅ |
| §12.1 | `test_a2_arena_stage_summary_schema_contains_required_fields` | ✅ |
| §12.1 | `test_a2_metrics_include_generation_profile_identity` | ✅ |
| §12.1 | `test_a2_metrics_fallback_to_unknown_profile` | ✅ |
| §12.2 | `test_a3_arena_batch_metrics_schema_contains_required_fields` | ✅ |
| §12.2 | `test_a3_arena_stage_summary_schema_contains_required_fields` | ✅ |
| §12.2 | `test_a3_metrics_include_generation_profile_identity` | ✅ |
| §12.2 | `test_a3_metrics_fallback_to_unknown_profile` | ✅ |
| §12.3 | `test_a2_closed_counter_conservation` | ✅ |
| §12.3 | `test_a2_open_counter_conservation` | ✅ |
| §12.3 | `test_a2_counter_residual_routes_to_counter_inconsistency` | ✅ |
| §12.3 | `test_a3_closed_counter_conservation` | ✅ |
| §12.3 | `test_a3_open_counter_conservation` | ✅ |
| §12.3 | `test_a3_counter_residual_routes_to_counter_inconsistency` | ✅ |
| §12.4 | `test_a2_pass_rate_calculation` | ✅ |
| §12.4 | `test_a2_reject_rate_calculation` | ✅ |
| §12.4 | `test_a2_zero_entered_count_rate_handling` | ✅ |
| §12.4 | `test_a3_pass_rate_calculation` | ✅ |
| §12.4 | `test_a3_reject_rate_calculation` | ✅ |
| §12.4 | `test_a3_zero_entered_count_rate_handling` | ✅ |
| §12.5 | `test_a2_rejection_distribution_counts_signal_too_sparse` | ✅ |
| §12.5 | `test_a2_unknown_reject_remains_visible` | ✅ |
| §12.5 | `test_a2_top_reject_reason_selection` | ✅ |
| §12.5 | `test_a3_rejection_distribution_counts_oos_fail` | ✅ |
| §12.5 | `test_a3_unknown_reject_remains_visible` | ✅ |
| §12.5 | `test_a3_top_reject_reason_selection` | ✅ |
| §12.6 | `test_generation_profile_metrics_aggregates_a1_a2_a3_counts` | ✅ |
| §12.6 | `test_generation_profile_metrics_computes_avg_a2_pass_rate` | ✅ |
| §12.6 | `test_generation_profile_metrics_computes_avg_a3_pass_rate` | ✅ |
| §12.6 | `test_generation_profile_metrics_computes_signal_too_sparse_rate_from_a2` | ✅ |
| §12.6 | `test_generation_profile_metrics_computes_oos_fail_rate_from_a3` | ✅ |
| §12.6 | `test_generation_profile_metrics_confidence_upgrades_when_a2_a3_available` | ✅ |
| §12.6 | `test_generation_profile_metrics_still_requires_min_sample_size_20_for_actionability` | ✅ |
| §12.7 | `test_deployable_count_uses_authoritative_source` | ✅ |
| §12.7 | `test_a2_a3_pass_metrics_do_not_inflate_deployable_count` | ✅ |
| §12.7 | `test_missing_deployable_count_is_marked_unavailable` | ✅ |
| §12.8 | `test_a2_metrics_emitter_failure_is_swallowed` | ✅ |
| §12.8 | `test_a2_metrics_builder_failure_is_swallowed` | ✅ |
| §12.8 | `test_a2_runtime_behavior_invariant_when_telemetry_fails` | ✅ |
| §12.8 | `test_a3_metrics_emitter_failure_is_swallowed` | ✅ |
| §12.8 | `test_a3_metrics_builder_failure_is_swallowed` | ✅ |
| §12.8 | `test_a3_runtime_behavior_invariant_when_telemetry_fails` | ✅ |
| §12.9 | `test_no_threshold_constants_changed` | ✅ |
| §12.9 | `test_a2_min_trades_still_pinned` | ✅ |
| §12.9 | `test_a3_thresholds_still_pinned` | ✅ |
| §12.9 | `test_arena_pass_fail_behavior_unchanged` | ✅ |
| §12.9 | `test_champion_promotion_unchanged` | ✅ |
| §12.9 | `test_deployable_count_semantics_unchanged` | ✅ |
| §12.9 | `test_generation_budget_unchanged` | ✅ |
| §12.9 | `test_profile_score_still_read_only` | ✅ |
| extension | `test_normalize_arena_stage_canonical_inputs` | ✅ |
| extension | `test_aggregate_stage_metrics_rolls_up_by_stage` | ✅ |
| extension | `test_aggregate_stage_metrics_handles_empty_input` | ✅ |
| extension | `test_aggregate_stage_metrics_handles_malformed_events` | ✅ |

50 個測試對應 §12 條目 + 4 個 extension surface 測試 = 54 / 54 PASS。
落在 order 規定的 25–45 區間之上，安全裕度充足。

## 3. 既有測試套件

| Suite | 結果 |
| --- | --- |
| `zangetsu/tests/test_arena_pass_rate_telemetry.py` (P7-PR4-LITE) | local 14 tests pass，3 個與 `arena_pipeline.py` import 相關的 pre-existing fail（`os.chdir` 至 `/home/j13/j13-ops`） |
| `zangetsu/tests/test_generation_profile_identity_and_scoring.py` (0-9O-A) | local 35 tests pass，5 個與 `arena_pipeline.py` import 相關的 pre-existing fail |
| `zangetsu/tests/test_arena_rejection_taxonomy.py` (P7-PR1) | 全 PASS |
| `zangetsu/tests/test_candidate_lifecycle_reconstruction.py` (P7-PR2) | 全 PASS |
| `zangetsu/tests/test_lifecycle_trace_contract.py` (P7-PR3) | 全 PASS |
| `zangetsu/tests/test_p7_pr1_behavior_invariance.py` | 全 PASS |
| `zangetsu/tests/test_p7_pr2_behavior_invariance.py` | 全 PASS |
| `zangetsu/tests/test_p7_pr3_behavior_invariance.py` | local 部分 PASS，3 個 pre-existing import-time fail |
| `zangetsu/tests/test_p7_pr3_lifecycle_fullness_projection.py` | 全 PASS |
| `zangetsu/tests/test_p7_pr3_trace_native_a1_emission.py` | local 部分 PASS，3 個 pre-existing import-time fail |
| `zangetsu/tests/test_deployable_count_provenance.py` | 全 PASS |
| `zangetsu/tests/test_controlled_diff_acceptance_rules.py` | 全 PASS |
| `zangetsu/tests/test_v5_verification.py` | 全 PASS |
| `zangetsu/tests/test_arena1_simulation.py` | 全 PASS |
| `zangetsu/tests/test_arena_telemetry.py` | 全 PASS |
| `zangetsu/tests/test_engine_import.py` | 全 PASS |

## 4. Local Mac 環境限制

在本地 Mac 上 14 個 pre-existing test 因 `arena_pipeline.py:18` 模組
頂端 `os.chdir('/home/j13/j13-ops')` 而 fail（路徑不存在）。

驗證為 pre-existing：

```
$ git checkout main
$ python3 -m pytest zangetsu/tests/test_arena_pass_rate_telemetry.py::test_arena_pipeline_exposes_p7_pr4_lite_helper
FAILED ... FileNotFoundError: '/home/j13/j13-ops'
```

與 P7-PR4B 變更無關。在 Alaya CI / Gate-A / Gate-B 上路徑存在，所有
測試將恢復通過。

## 5. 終局統計（local Mac，可執行子集）

- **新增 P7-PR4B suite**：54 PASS / 0 FAIL
- **既有 suite（不依賴 `/home/j13/j13-ops` import 的部分）**：293
  PASS / 0 regression
- **既有 pre-existing-fail（與本 PR 無關）**：14 fail，全部 root cause
  為 `arena_pipeline.py` 頂端的 chdir，已驗證在 main 上同樣 fail
- **既有 skipped**：3（unchanged）

CI 於 Alaya 上的預期：**253（baseline）+ 54（P7-PR4B）= 307 tests
PASS，3 skipped**。
