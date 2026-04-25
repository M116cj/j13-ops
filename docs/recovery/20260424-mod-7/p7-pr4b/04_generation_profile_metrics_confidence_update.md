# P7-PR4B — Generation Profile Metrics Confidence Update

## 1. 背景

0-9O-A 在 `generation_profile_metrics.py` 引入 `profile_score`（read-only）
與 `next_budget_weight_dry_run`（dry-run only），並用兩態 confidence
marker 表示資料完整度：

```
LOW_CONFIDENCE_UNTIL_A2_A3_METRICS_AVAILABLE
CONFIDENCE_FULL  (= a2/a3 available AND sample_size_met)
```

P7-PR4B 把 A2 / A3 aggregate batch metrics 接通後，原本的二態粒度太粗
— 無法區分 "A2/A3 已上線但樣本還不夠" vs "A2/A3 還沒上線" 這兩種
不同的等待原因。

## 2. P7-PR4B 規則（依 TEAM ORDER §8）

```
no a2/a3 metrics                   → LOW_CONFIDENCE_UNTIL_A2_A3_METRICS_AVAILABLE
a2/a3 + sample_size_rounds < 20    → LOW_SAMPLE_SIZE_UNTIL_20_ROUNDS
a2/a3 + sample_size_rounds >= 20   → CONFIDENCE_A1_A2_A3_METRICS_AVAILABLE
```

所有 marker string value 與 order 規定完全一致。

## 3. 程式碼變更

`zangetsu/services/generation_profile_metrics.py`：

```python
CONFIDENCE_LOW_UNTIL_A2_A3 = "LOW_CONFIDENCE_UNTIL_A2_A3_METRICS_AVAILABLE"
CONFIDENCE_A1_A2_A3_AVAILABLE = "CONFIDENCE_A1_A2_A3_METRICS_AVAILABLE"
CONFIDENCE_LOW_SAMPLE_SIZE = "LOW_SAMPLE_SIZE_UNTIL_20_ROUNDS"
# Backwards-compatible alias for prior consumers.
CONFIDENCE_FULL = CONFIDENCE_A1_A2_A3_AVAILABLE
```

`aggregate_batches_for_profile()` 三態解析：

```python
a2_a3_available = (
    metrics.total_entered_a2 > 0
    and metrics.total_entered_a3 > 0
)
if not a2_a3_available:
    metrics.confidence = CONFIDENCE_LOW_UNTIL_A2_A3
elif not metrics.min_sample_size_met:
    metrics.confidence = CONFIDENCE_LOW_SAMPLE_SIZE
else:
    metrics.confidence = CONFIDENCE_A1_A2_A3_AVAILABLE
```

## 4. 既有契約保留

| 契約 | 維持 |
| --- | --- |
| `profile_score` 是 read-only 觀察指標 | ✅ 不變 |
| `next_budget_weight_dry_run` 在 sample 不足時等於 EXPLORATION_FLOOR | ✅ 不變 |
| `min_sample_size_met = (sample_size_rounds >= 20)` | ✅ 不變 |
| `CONFIDENCE_FULL` 仍可被 import 使用 | ✅ alias 到 CONFIDENCE_A1_A2_A3_AVAILABLE |
| 所有 0-9O-A test 通過 | ✅ 沒有測試 assertion 依賴二態邏輯破裂 |

## 5. Sample size guard 仍然 active

`min_sample_size_rounds = 20` 仍保留。當 `min_sample_size_met == False`
時：

- `compute_dry_run_budget_weight(profile_score,
  min_sample_size_met=False) == EXPLORATION_FLOOR`，意即 dry-run
  recommendation 強制等於 floor，不會升級為 actionable budget。
- `metrics.confidence` 顯示 `LOW_SAMPLE_SIZE_UNTIL_20_ROUNDS`，提醒
  下游 dashboard / Calcifer / 觀察者 sample 還不夠。

## 6. Deployable_count 規則 unchanged

`aggregate_batches_for_profile` 既有規則保留：只把 batch event 中
`isinstance(deployable_count, int)` 的整數值納入計算。`None` 或缺失
皆視為 UNAVAILABLE。

P7-PR4B 在 `arena23_orchestrator.py` 的所有 emission 都顯式傳入
`deployable_count=None`，確保 trace-only A2/A3 pass events 不會
inflate `total_deployable_count`。authoritative source 仍是
`champion_pipeline_fresh.status = 'DEPLOYABLE'`，由 A4 / A5 promotion
gate 寫入。

## 7. 對應測試

新增於 `zangetsu/tests/test_a2_a3_arena_batch_metrics.py`：

- `test_generation_profile_metrics_confidence_upgrades_when_a2_a3_available`
  — 直接驗證三態解析。
- `test_generation_profile_metrics_still_requires_min_sample_size_20_for_actionability`
  — 即便 A2/A3 metrics 齊全，sample 不足時 `next_budget_weight_dry_run`
  仍鎖死於 `EXPLORATION_FLOOR`。
- `test_generation_profile_metrics_aggregates_a1_a2_a3_counts`
- `test_generation_profile_metrics_computes_avg_a2_pass_rate`
- `test_generation_profile_metrics_computes_avg_a3_pass_rate`
- `test_generation_profile_metrics_computes_signal_too_sparse_rate_from_a2`
- `test_generation_profile_metrics_computes_oos_fail_rate_from_a3`
- `test_deployable_count_uses_authoritative_source`
- `test_a2_a3_pass_metrics_do_not_inflate_deployable_count`
- `test_missing_deployable_count_is_marked_unavailable`

`test_generation_profile_identity_and_scoring.py`（0-9O-A 既有）持續
通過 — 既有測試只 assert `LOW_UNTIL_A2_A3` path（A1-only 場景），P7-PR4B
未動該 path。
