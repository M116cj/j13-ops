# 0-9O-B — Bottleneck Explanation Model

## 1. 目的

讓 dry-run allocation record 的讀者能在 30 秒內看出：

- 系統現在的瓶頸是什麼類型？
- top reject reasons 是哪些？

## 2. 規則

`classify_bottleneck(metrics, *, actionable_count) -> (label, top_list)`：

### 2.1 結構性 bottleneck（actionable_count == 0）

從輸入 metrics 推斷：

```
any metric.confidence == LOW_CONFIDENCE_UNTIL_A2_A3_METRICS_AVAILABLE
    → MISSING_A2_A3_METRICS

elif any metric.confidence == LOW_SAMPLE_SIZE_UNTIL_20_ROUNDS
     OR any metric.min_sample_size_met != True
    → LOW_SAMPLE_SIZE

else
    → NO_ACTIONABLE_PROFILE
```

### 2.2 內容性 bottleneck（actionable_count > 0）

聚合所有 input metrics 的 reject 計數：

```
sparse  = sum(metric.signal_too_sparse_count)
oos     = sum(metric.oos_fail_count)
unknown = sum(metric.unknown_reject_count)
total   = sparse + oos + unknown

if total <= 0:
    return ("UNKNOWN", [])

contributions = sorted([
  ("SIGNAL_TOO_SPARSE", sparse, SIGNAL_TOO_SPARSE_DOMINANT),
  ("OOS_FAIL",          oos,    OOS_FAIL_DOMINANT),
  ("UNKNOWN_REJECT",    unknown, UNKNOWN_REJECT_DOMINANT),
], key=lambda kv: -kv[1])

leader_share = leader_val / total
if leader_share >= BOTTLENECK_DOMINANCE_THRESHOLD (= 0.40):
    bottleneck = leader_label
else:
    bottleneck = "UNKNOWN"

top_list = [name for name, val, _ in contributions if val > 0]
```

## 3. 標籤集

| 常數 | 字串 | 觸發 |
| --- | --- | --- |
| `BOTTLENECK_SIGNAL_TOO_SPARSE` | `"SIGNAL_TOO_SPARSE_DOMINANT"` | actionable + sparse share >= 40% |
| `BOTTLENECK_OOS_FAIL` | `"OOS_FAIL_DOMINANT"` | actionable + oos share >= 40% |
| `BOTTLENECK_UNKNOWN_REJECT` | `"UNKNOWN_REJECT_DOMINANT"` | actionable + unknown share >= 40% |
| `BOTTLENECK_LOW_SAMPLE` | `"LOW_SAMPLE_SIZE"` | non-actionable + low sample only |
| `BOTTLENECK_MISSING_A2_A3` | `"MISSING_A2_A3_METRICS"` | non-actionable + 缺 A2/A3 |
| `BOTTLENECK_NO_ACTIONABLE` | `"NO_ACTIONABLE_PROFILE"` | 無 input 或無 reject 訊號 |
| `BOTTLENECK_UNKNOWN` | `"UNKNOWN"` | actionable + 無單一 dominant |

## 4. 測試覆蓋

- `test_detects_signal_too_sparse_dominant_bottleneck`
- `test_detects_oos_fail_dominant_bottleneck`
- `test_detects_unknown_reject_dominant_bottleneck`
- `test_detects_low_sample_size_bottleneck`
- `test_detects_missing_a2_a3_bottleneck`
- `test_detects_no_actionable_profile_bottleneck`
- `test_bottleneck_published_in_allocation_record`

## 5. 對 0-9R 的提示

| Bottleneck | 對 0-9R 的暗示 |
| --- | --- |
| `SIGNAL_TOO_SPARSE_DOMINANT` | generation profile 太鬆，trades 太少 — 0-9R 設計 sparse-candidate 補強策略，但**不可弱化** `A2_MIN_TRADES` |
| `OOS_FAIL_DOMINANT` | overfitting 跡象 — 0-9R 應加強 OOS guard，不是放寬 |
| `UNKNOWN_REJECT_DOMINANT` | taxonomy / visibility 問題 — 應先補 reject taxonomy，再看 budget |
| `LOW_SAMPLE_SIZE` | 等更多 round；不加 budget |
| `MISSING_A2_A3_METRICS` | 等 P7-PR4B-style 資料齊全；不加 budget |
| `NO_ACTIONABLE_PROFILE` | 全 fallback，不調 |
