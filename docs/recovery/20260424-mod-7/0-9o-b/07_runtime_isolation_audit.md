# 0-9O-B — Runtime Isolation Audit

## 1. 規則

依 TEAM ORDER 0-9O-B §3.27 / §4.3 / §15.18-21，allocator 模組
**不得**被以下 runtime 模組 import 或呼叫：

- alpha generation modules (`alpha_engine`, `alpha_signal_live`,
  `alpha_discovery`, `alpha_dedup`, `alpha_ensemble`)
- formula generation modules
- mutation modules
- crossover modules
- search policy modules
- `arena_pipeline.py`（A1 runtime）
- `arena23_orchestrator.py`（A2/A3 runtime）
- `arena45_orchestrator.py`（A4/A5 runtime）
- execution modules
- risk modules
- capital modules
- production runtime modules

Allocator 只能被：

- tests
- offline reports / dashboards / docs
- 未來授權的 `feedback_budget_allocator_runtime`（暫不存在）

## 2. 強制驗證測試

`test_feedback_budget_allocator.py`：

| 測試 | 機制 |
| --- | --- |
| `test_allocator_not_imported_by_alpha_generation_runtime` | 讀 `arena_pipeline.py` source，斷言不含 `feedback_budget_allocator` |
| `test_allocator_not_imported_by_arena_runtime` | 對 `arena23_orchestrator.py` / `arena45_orchestrator.py` / `arena_gates.py` 同上 |
| `test_allocator_not_imported_by_execution_runtime` | 對 `alpha_signal_live.py` / `data_collector.py` / `alpha_dedup.py` / `alpha_ensemble.py` / `alpha_discovery.py` 同上 |
| `test_allocator_output_not_consumed_by_generation_runtime` | 走訪 `services/*.py`（除 `feedback_budget_allocator.py` 自身），斷言不含 `DryRunBudgetAllocation` 或 `allocate_dry_run_budget` symbol |
| `test_no_generation_budget_file_changed` | 同上對 `arena_pipeline.py` |
| `test_no_sampling_weight_file_changed` | 反向：allocator source 不含 `alpha_engine` 或 `sampling_weight` 字串 |

任一測試失敗 = isolation 違規 = STOP。

## 3. 單向 import graph

```
                        feedback_budget_allocator.py
                                  ▲
              READS (read-only constants + builder):
                                  │
                       ┌──────────┴──────────┐
                       │                     │
   generation_profile_metrics.py   feedback_decision_record.py
                       ▲                     ▲
                       │                     │
   generation_profile_identity.py    arena_pass_rate_telemetry.py
                                              ▲
                                              │
                              arena_pipeline / arena23 / arena45
                              (Arena runtime — produces metrics)
```

Allocator 在 graph 末端，**沒有任何反向 edge**。

## 4. 驗證命令

```bash
# 確認 runtime 檔案沒有引用 allocator
grep -rn "feedback_budget_allocator" zangetsu/services/ | \
    grep -v feedback_budget_allocator.py

# 應為空輸出
```

```bash
# 確認 allocator 沒有引用 runtime 檔案
grep -nE "import .*alpha_engine|sampling_weight|arena_pipeline|arena23|arena45" \
    zangetsu/services/feedback_budget_allocator.py

# 應為空輸出
```
