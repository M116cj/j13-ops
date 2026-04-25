# P7-PR4B — Counter Conservation Invariant

## 1. 守恆規則

沿用 P7-PR4-LITE / `arena_pass_rate_telemetry.py` 既有規則：

```
closed batch:  entered = passed + rejected + skipped + error
open   batch:  entered = passed + rejected + skipped + error + in_flight
```

由 `validate_counter_conservation(entered, passed, rejected, skipped,
error, in_flight, open_stage)` 定義。所有計數欄位非負；`open_stage=False`
且 `in_flight_count != 0` 一律拒絕。

## 2. 在 A2 / A3 orchestrator 中如何成立

`ArenaStageMetrics` 提供以下方法保證守恆：

| 動作 | 計數變化 |
| --- | --- |
| `on_entered()` | `entered_count += 1`, `in_flight_count += 1` |
| `on_passed()` | `passed_count += 1`, `in_flight_count -= 1` |
| `on_rejected(reason)` | `rejected_count += 1`, `in_flight_count -= 1` |
| `on_skipped(reason)` | `skipped_count += 1`, `in_flight_count -= 1` |
| `on_error(reason)` | `error_count += 1`, `in_flight_count -= 1` |
| `mark_closed()` | 若 `in_flight_count > 0` 則計入 `skipped_count` 並
                    在 reject_counter 加 `BATCH_CLOSED_WITH_IN_FLIGHT` |

在 A2 / A3 orchestrator 中，每個 champion 的處理都對應一次
`on_entered()`，緊接 `on_passed()` / `on_rejected(...)` / `on_error(...)`
其中之一。`in_flight_count` 在每次 outcome 確定後立刻 decrement，因此
每個 batch 在被 flush 時 `in_flight_count == 0`，符合 closed-batch
不變式。

## 3. Outcome 對應表

`_p7pr4b_record_outcome` 中的對應：

| `outcome` | 觸發呼叫 | 來源情境 |
| --- | --- | --- |
| `"PASSED"` | `acc.on_passed()` | A2 `improved=True` 或 A3 result `is not None` |
| `"REJECTED"` | `acc.on_rejected(canonical)` | A2 `result is None` / dedup / `improved=False`；A3 `result is None` |
| `"ERROR"` | `acc.on_error(...)` | runtime exception path（被 try-except 捕捉） |

`canonical` 來自 `_p7pr4b_canonicalize_reason(raw_reason, stage)`，
透過 `arena_rejection_taxonomy.classify` 將 orchestrator 的 reject
log line 對應到 18 個 canonical reasons 之一；無法分類者落到
`UNKNOWN_REJECT`。

## 4. 何時 `entered = passed + rejected + skipped + error` 不成立？

理論上不會。實務上若 telemetry helper 失敗（例如
`_p7pr4b_make_acc_safe` 回傳 None 後，後續 outcome 也無法 increment），
整個 champion 不會被計入該 batch；下一個 champion 又啟動新的 batch
sequence。因此即使 telemetry partial-failure，仍維持守恆 — 只是樣本
數比實際處理少。

## 5. 殘差路由

若上游 stage（這裡 P7-PR4B 不負責 A1 path）的 reject_total 與 entered
- passed 不等，由 `arena_pipeline._emit_a1_batch_metrics_from_stats_safe`
路由：

```python
residual = entered - passed - rejected
if residual > 0:
    skipped_count = residual
elif residual < 0:
    reject_counter.add("COUNTER_INCONSISTENCY", abs(residual))
    rejected_count += abs(residual)
```

A2 / A3 orchestrator 的 wiring 不需要 residual routing，因為每個
champion 都恰恰會走進其中一個 outcome branch。

## 6. 對應測試

`zangetsu/tests/test_a2_a3_arena_batch_metrics.py`：

- `test_a2_closed_counter_conservation`
- `test_a2_open_counter_conservation`
- `test_a2_counter_residual_routes_to_counter_inconsistency`
- `test_a3_closed_counter_conservation`
- `test_a3_open_counter_conservation`
- `test_a3_counter_residual_routes_to_counter_inconsistency`

`test_arena_pass_rate_telemetry.py`（P7-PR4-LITE 既有）也持續驗證底層
守恆規則。
