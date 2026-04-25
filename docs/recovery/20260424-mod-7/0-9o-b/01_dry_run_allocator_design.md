# 0-9O-B — Dry-Run Feedback Budget Allocator Design

## 1. 動機

P7-PR4B 已把 A1 / A2 / A3 aggregate `arena_batch_metrics` 接通，
0-9O-A 已交付 `generation_profile_metrics` + `profile_score`（read-only）
+ `next_budget_weight_dry_run`（dry-run only）+ 三態 confidence。

0-9O-B 把這些訊號連成第一個完整的「黑箱回饋迴路」，但完全限定在
**dry-run** — 只計算建議，不施加。

```
A1/A2/A3 arena_batch_metrics
  → generation_profile_metrics
  → profile_score
  → confidence gate
  → dry-run budget allocator   ← THIS PR
  → feedback_decision_record
  → proposed_profile_weights_dry_run
```

## 2. 範圍硬限制

依 TEAM ORDER 0-9O-B §3 / §5 / §15：

- 不修改 alpha / formula / mutation / crossover / search policy / 真實
  generation budget / sampling weights / candidate creation。
- 不修改 thresholds（含 `A2_MIN_TRADES`、A3 segment threshold）、
  Arena pass/fail、rejection semantics、champion promotion、
  `deployable_count` semantics。
- 不修改 execution / capital / risk / broker / production runtime。
- 不啟動 CANARY、production rollout、weaken branch protection。
- **不可被 generation runtime / Arena runtime / execution runtime
  import**。Allocator 只能被 tests / offline reports / docs 使用。

## 3. 解法概述

新增單一模組 `zangetsu/services/feedback_budget_allocator.py`，純 Python，
無 IO / DB / 網路 / Arena 依賴。輸入是 `generation_profile_metrics` 的
read-only view（dataclass 或 dict），輸出是
`DryRunBudgetAllocation` event 物件（可序列化為 JSON）。

```
┌─────────────────────────────────────────────────────────────────────┐
│ feedback_budget_allocator.py（新模組）                              │
│                                                                     │
│  allocate_dry_run_budget(profile_metrics, *, run_id,                │
│                            previous_profile_weights=None)           │
│    │                                                                │
│    ├─ _coerce_metric             ← dataclass / dict → mapping        │
│    ├─ evaluate_profile_actionability                                 │
│    │     ├─ 必填欄位             → REASON_MISSING_FIELDS             │
│    │     ├─ confidence != FULL   → REASON_LOW_CONFIDENCE / ...       │
│    │     ├─ sample_size < 20     → REASON_LOW_SAMPLE_SIZE            │
│    │     ├─ A2/A3 missing        → REASON_MISSING_A2_A3              │
│    │     └─ unknown_rate >= 0.20 → REASON_COUNTER_INCONSISTENCY      │
│    ├─ classify_bottleneck                                            │
│    │     SIGNAL_TOO_SPARSE / OOS_FAIL / UNKNOWN_REJECT /             │
│    │     LOW_SAMPLE_SIZE / MISSING_A2_A3 / NO_ACTIONABLE             │
│    ├─ compute_proposed_weights                                        │
│    │     raw = max(score + 1, 0); UNKNOWN_PROFILE capped；           │
│    │     再加 EXPLORATION_FLOOR → 比例分配 → 嚴格 sum=1.0             │
│    └─ DryRunBudgetAllocation                                          │
│         post_init enforces mode=DRY_RUN, applied=False                │
│         to_event() 重新確認上述兩條                                   │
│                                                                     │
│  to_feedback_decision_record(allocation)                            │
│    → 透過既有 0-9O-A builder 再做一次 dry-run 不變式檢核            │
└─────────────────────────────────────────────────────────────────────┘
```

## 4. Dry-run 不變式

兩層獨立保證（防呆）：

1. **`DryRunBudgetAllocation.__post_init__`**：強制
   `mode = "DRY_RUN"`、`applied = False`、`allocator_version = "0-9O-B"`。
   即便 caller 傳入 `applied=True`、`mode="APPLIED"`，post_init 會立刻
   覆寫回去。
2. **`to_event()`**：再次強制 `mode` / `applied` / `allocator_version`，
   防止 post-construction mutation 留下違規 payload。
3. **`to_feedback_decision_record()`**：繞回既有 0-9O-A
   `FeedbackDecisionRecord` builder，第三層獨立檢核。

`feedback_budget_allocator.py` 不暴露任何 `apply` / `commit` / `execute`
function。

## 5. 不被 runtime 消費的保證

- 所有 imports 為 `from zangetsu.services.generation_profile_metrics`、
  `feedback_decision_record`、`generation_profile_identity` —
  **單向**：allocator 讀這些模組的 read-only 常數 + builder，沒有任何
  runtime module 反向 import allocator。
- 由 `09_test_results.md` 中
  `test_allocator_not_imported_by_alpha_generation_runtime`
  / `test_allocator_not_imported_by_arena_runtime`
  / `test_allocator_not_imported_by_execution_runtime`
  / `test_allocator_output_not_consumed_by_generation_runtime`
  四個 source-text 測試強制驗證。

## 6. Schema 與 0-9O-A 的關係

`DryRunBudgetAllocation` 的 fields 與 0-9O-A
`FeedbackDecisionRecord` 部分重疊。兩者各自獨立自帶不變式檢核；
透過 `to_feedback_decision_record()` 把 allocation 轉成 record 是
建議使用方式，但兩者也可獨立序列化。

## 7. 後續

0-9O-B 完成後仍**不能**真的調 budget。下一步：

- **0-9R**：Sparse-Candidate Black-Box Optimization Design — 利用
  allocator 的 dominance / bottleneck 診斷設計 generation profile policy
  的調整策略（仍 dry-run）。
- **0-9R-IMPL**：實際 generation-profile policy 調整，需 j13 明確授權。
- **0-9S**：CANARY readiness gate。
- **0-9T**：production rollout。
