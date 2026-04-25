# 0-9O-B — Allocator Input / Output Schema

## 1. 輸入

`allocate_dry_run_budget(profile_metrics, *, run_id,
previous_profile_weights=None)`。

`profile_metrics` 為任意可疊代物，每個元素為 `GenerationProfileMetrics`
dataclass instance 或 dict-like mapping。允許的欄位：

| 欄位 | 用途 |
| --- | --- |
| `generation_profile_id` | rank / weights dict 的鍵 |
| `generation_profile_fingerprint` | 透傳到 decision record |
| `profile_score` | weight transform 的輸入 |
| `avg_a1_pass_rate` | 診斷用 |
| `avg_a2_pass_rate` | 結合 `total_entered_a2` 偵測 missing-A2 |
| `avg_a3_pass_rate` | 結合 `total_entered_a3` 偵測 missing-A3 |
| `avg_deployable_count` | 診斷用 |
| `signal_too_sparse_rate` / `signal_too_sparse_count` | bottleneck 統計 |
| `oos_fail_rate` / `oos_fail_count` | bottleneck 統計 |
| `unknown_reject_rate` / `unknown_reject_count` | counter inconsistency 偵測 |
| `instability_penalty` | 透傳 |
| `sample_size_rounds` | sample-size gate |
| `min_sample_size_met` | sample-size gate |
| `confidence` | confidence gate（必須等於 `CONFIDENCE_A1_A2_A3_METRICS_AVAILABLE` 才可 actionable） |
| `next_budget_weight_dry_run` | 透傳；不直接使用 |
| `total_entered_a2` / `total_entered_a3` | 偵測 stage 是否上線 |

**缺欄位行為**：未滿足 `_REQUIRED_INPUT_FIELDS`（含
`generation_profile_id` / `profile_score` / `avg_a2_pass_rate` /
`avg_a3_pass_rate` / `sample_size_rounds` / `min_sample_size_met` /
`confidence`）→ profile 標 `REASON_MISSING_FIELDS`，allocator 不
crash。

**Coercion 失敗**（非 dict、非 dataclass、`None`、原生型別）→ 整個
profile 跳過，並在 `non_actionable_reasons["__coercion_failed__"]`
記錄 `REASON_MISSING_FIELDS`。

**Mutation 保證**：allocator 透過 `dict(metric)` 拷貝後才操作，呼叫端
傳入物件不被改動。由
`test_weight_calculation_does_not_mutate_inputs` 驗證。

## 2. 輸出

`DryRunBudgetAllocation` dataclass，必填 fields（24 項，由
`required_allocation_fields()` 公開列舉）：

| 欄位 | 說明 |
| --- | --- |
| `telemetry_version` | 固定 `"1"` |
| `decision_id` | UUID-prefixed (`alloc-`) |
| `run_id` | caller 提供 |
| `created_at` | UTC ISO8601 |
| `mode` | 強制 `"DRY_RUN"` |
| `applied` | 強制 `False` |
| `confidence` | 來自 generation_profile_metrics 或 `NO_ACTIONABLE_PROFILE` |
| `allocator_version` | 強制 `"0-9O-B"` |
| `input_profile_count` | 成功 coerce 的 profile 數 |
| `actionable_profile_count` | 通過所有 gate 的 profile 數 |
| `non_actionable_profile_count` | profile-level rejected 數（不含 coercion failure） |
| `exploration_floor` | `0.05` |
| `min_sample_size_rounds` | `20` |
| `previous_profile_weights` | caller 提供（可空） |
| `proposed_profile_weights_dry_run` | 計算結果，sum=1.0 |
| `profile_scores` | 對每個 profile id 的 score 紀錄 |
| `profile_ranks` | actionable profiles 的 1-based 排序 |
| `non_actionable_reasons` | `{profile_id: [reason, …]}` |
| `observed_bottleneck` | 6 種枚舉 |
| `top_reject_reasons` | aggregate 統計排序後的 reasons |
| `expected_effect` | 固定 dry-run 字串，無 effect |
| `safety_constraints` | 含 `NOT_APPLIED_TO_RUNTIME` 等 8 條 |
| `reason` | 人類可讀說明 |
| `source` | `"feedback_budget_allocator"` |

`event_type` 在 `to_event()` 中加上：`dry_run_budget_allocation`。

## 3. 序列化

`serialize_allocation(allocation) -> str`：JSON 字串，`sort_keys=True`，
失敗回空字串。

## 4. 與 `feedback_decision_record` 的橋接

`to_feedback_decision_record(allocation) -> FeedbackDecisionRecord`：

- 用既有 0-9O-A `build_feedback_decision_record(...)` 構造記錄。
- 把 allocation 的所有 dry-run 欄位透傳。
- record 自帶獨立的 `mode=DRY_RUN` / `applied=False` 不變式 — 第二層
  獨立檢核。
