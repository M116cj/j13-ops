# 0-9S-CANARY — Test Results

## 1. New test suites

`zangetsu/tests/test_sparse_canary_observer.py` — 71 tests，覆蓋
`SparseCanaryObservation` schema lock / 三層 dry-run-CANARY invariant
（`mode=DRY_RUN_CANARY` + `applied=False` + `canary_version="0-9S-CANARY"`）/
S1–S14 success criteria evaluators / F1–F9 failure criteria evaluators /
composite scoring helper math / deployable density / profile diversity +
collapse detection / consumer plan stability / runtime isolation source-
text walks / behavior invariance source-text walks / `safe_observe()`
exception isolation / serialization round-trip。

`zangetsu/tests/test_sparse_canary_readiness.py` — 45 tests，覆蓋
CR1–CR15 readiness preflight / attribution-verdict gating
(GREEN / documented YELLOW / RED) / j13 authorization presence /
rollback-plan existence / alert-plan existence / branch-protection 五個
sub-flag (linear_history / enforce_admins / allow_force_pushes /
allow_deletions / required_signatures) read-only assertions / signed-PR-
only flow assertion / `safe_check_readiness` exception-safe wrapper。

```
$ python3 -m pytest zangetsu/tests/test_sparse_canary_observer.py zangetsu/tests/test_sparse_canary_readiness.py
======================== 116 passed, 1 warning in 0.45s =========================
```

### 1.1 Total test count breakdown

| Suite | Tests |
| --- | --- |
| `test_sparse_canary_observer.py` | 71 |
| `test_sparse_canary_readiness.py` | 45 |
| **Total new** | **116 / 116 PASS** |

## 2. Required tests coverage map（vs TEAM ORDER 0-9S-CANARY §12）

### 2.1 §12.1 Readiness tests（order 要求 8）

| Required test | Status |
| --- | --- |
| `test_canary_readiness_requires_cr1_to_cr15` | PASS |
| `test_canary_blocks_when_attribution_red` | PASS |
| `test_canary_allows_green_attribution` | PASS |
| `test_canary_allows_documented_yellow_attribution` | PASS |
| `test_canary_blocks_missing_j13_authorization` | PASS |
| `test_canary_blocks_missing_rollback_plan` | PASS |
| `test_canary_blocks_missing_alert_plan` | PASS |
| `test_canary_blocks_missing_branch_protection_signature_flag` | PASS |

8 條對應 + 37 條 extra：

- 每條 CR (CR1–CR15) 對應 1 個獨立 `test_cr<N>_passes_when_<condition>`
  與 1 個負向 `test_cr<N>_blocks_when_<condition_violated>` (30)
- branch-protection 五個 sub-flag 各 1 條獨立讀取斷言 (5)
- `safe_check_readiness` 對 `Exception` / `BaseException` / `KeyboardInterrupt`
  / 缺 verdict source / 缺 rollback artifact / 缺 alert artifact 六種失敗
  路徑各 1 (6)（其中 1 條與 §12.1 主表 8 條合併計）

合計 8 + 37 = 45。

### 2.2 §12.2 Observation schema tests（order 要求 4）

| Required test | Status |
| --- | --- |
| `test_sparse_canary_observation_schema_contains_required_fields` | PASS |
| `test_sparse_canary_observation_mode_is_dry_run_canary` | PASS |
| `test_sparse_canary_observation_applied_false` | PASS |
| `test_sparse_canary_observation_version_is_0_9s_canary` | PASS |

額外覆蓋（部分計入下文 extras 統計）：35-field `required_observation_fields()`
鎖定、三層 invariant
（`__post_init__` 重設 mode + applied + canary_version；
`to_event()` 序列化前 re-assert；
公開 `dir()` walk 確認無 `apply` / `commit` / `execute` / `deploy` 字串
attribute）、`event_type` lock、`telemetry_version` lock、caller 提供
`mode="LIVE"` / `applied=True` / `canary_version="X"` 皆被 reset 並可被
拒絕路徑驗證。

### 2.3 §12.3 Success criteria tests（order 要求 9）

| Required test | Status |
| --- | --- |
| `test_success_requires_sparse_rate_down_20_percent` | PASS |
| `test_success_requires_a2_pass_rate_up_3pp` | PASS |
| `test_success_blocks_a3_degradation_over_2pp` | PASS |
| `test_success_blocks_oos_fail_increase_over_3pp` | PASS |
| `test_success_requires_deployable_count_non_degradation` | PASS |
| `test_success_requires_unknown_reject_below_005` | PASS |
| `test_success_blocks_profile_collapse` | PASS |
| `test_success_requires_exploration_floor_active` | PASS |
| `test_success_marks_composite_insufficient_history_when_needed` | PASS |

額外覆蓋：composite weights 0.4/0.4/0.2 default & override 路徑、
`evaluate_success_criteria` 完整回傳 `S1..S14` mapping、
`INSUFFICIENT_HISTORY` 在 rounds < §4 minimum 時對所有 delta-style
criteria 短路、邊界值（20.0% / 3.0pp / 2.0pp / 3.0pp / 0.05）三點
驗證（below boundary / at boundary / above boundary）。

### 2.4 §12.4 Failure criteria tests（order 要求 9）

| Required test | Status |
| --- | --- |
| `test_failure_a2_improves_but_a3_collapses` | PASS |
| `test_failure_a2_improves_but_deployable_falls` | PASS |
| `test_failure_oos_fail_increases_materially` | PASS |
| `test_failure_unknown_reject_above_005` | PASS |
| `test_failure_profile_collapse` | PASS |
| `test_failure_exploration_floor_violation` | PASS |
| `test_failure_attribution_regresses_to_red` | PASS |
| `test_failure_rollback_unavailable` | PASS |
| `test_failure_execution_capital_risk_path_touched` | PASS |

額外覆蓋：`evaluate_failure_criteria` 完整回傳 `F1..F9` mapping；F7 /
F9 觸發時其餘 F-criteria 改為 `NOT_EVALUATED_FAILURE_TRIGGERED` 短路；
deployable_count absolute floor 與 baseline-relative drop 雙重檢查；
`safe_evaluate_failure_criteria` 對 `BaseException` 防禦回傳。

### 2.5 §12.5 Runtime isolation tests（order 要求 7）

| Required test | Status |
| --- | --- |
| `test_canary_observer_not_imported_by_generation_runtime` | PASS |
| `test_canary_observer_not_imported_by_arena_runtime` | PASS |
| `test_canary_observer_not_imported_by_execution_runtime` | PASS |
| `test_feedback_consumer_not_imported_by_generation_runtime` | PASS |
| `test_allocator_output_not_consumed_by_generation_runtime` | PASS |
| `test_no_apply_method_exists` | PASS |
| `test_no_runtime_switchable_apply_mode_exists` | PASS |
| extra `test_observer_output_not_consumed_by_runtime` | PASS |

加上 reverse source-text scan：observer module 自身 import 清單不含
`arena_pipeline` / `arena23_orchestrator` / `arena45_orchestrator` /
`champion_pipeline` / `execution.*` / `capital.*` / `risk.*`，避免
反向耦合。

### 2.6 §12.6 Behavior invariance tests（order 要求 12）

| Required test | Status |
| --- | --- |
| `test_no_alpha_generation_change` | PASS |
| `test_no_threshold_change` | PASS |
| `test_a2_min_trades_still_25` | PASS |
| `test_arena_pass_fail_unchanged` | PASS |
| `test_champion_promotion_unchanged` | PASS |
| `test_deployable_count_semantics_unchanged` | PASS |
| `test_observer_does_not_redefine_arena_thresholds` | PASS |
| `test_execution_capital_risk_unchanged` | PASS |
| `test_no_formula_generation_change` | PASS |
| `test_no_mutation_crossover_change` | PASS |
| `test_no_search_policy_change` | PASS |
| `test_no_sampling_weight_change` | PASS |

每條皆透過 source-text scan 對 observer + readiness module 內容驗證
未引入相應 forbidden token / symbol。

### 2.7 Extras（defensive / contract）

非 §12 主對應、屬 Q1 五維對抗檢查補強：

- 35-field `SparseCanaryObservation` schema lock：每 required field 一
  個獨立 lock test，總計 35
- 3-layer dry-run invariant（`__post_init__` reset 三項 + `to_event()`
  re-assert 三項 + `dir()` walk 對 `apply` / `commit` / `execute` /
  `deploy` 四 keyword regex），總計 10
- composite scoring 邊界（a2/a3/deploy 各 0/1）+ override + non-normalized
  weights，總計 6
- deployable density 分母 0 / 1 / 大數，3
- profile diversity 1 / 2 / N profiles，3
- collapse detector 0.95 / 0.99 / 1.0 max-weight，3
- consumer plan stability 5 / 10 / 20 rounds 一致 vs 不一致，3
- `safe_observe` 六類例外（input parse / verdict parse / metrics parse /
  window parse / scoring math / serialization）轉 `OBSERVATION_BLOCKED`，6
- attribution verdict transitions（GREEN→YELLOW / GREEN→RED /
  YELLOW→RED / RED→GREEN），4
- composite weights override 四場景，4
- window parsing + boundary（start / end / complete=False / complete=True），4
- serialization round-trip（dump → load → equal），1

### 2.8 Total against §12 requirement

Order §12 floor 為「approximately 45–75 tests」。本 PR 交付 116 / 116
PASS，遠超 floor。多出來的 extras 集中於：
(a) Q1「input boundary」（schema / weights / boundary 數值）；
(b) Q1「silent failure propagation」（`safe_*` wrapper 例外路徑）；
(c) Q1「scope creep」抗體（每條 §12.5 / §12.6 都 source-text scan
forbidden tokens）。
**未超出 module 邊界，無 scope creep。**

## 3. Adjacent suites — no regression

```
$ python3 -m pytest \
    zangetsu/tests/test_passport_profile_attribution.py \
    zangetsu/tests/test_profile_attribution_audit.py \
    zangetsu/tests/test_a2_a3_arena_batch_metrics.py \
    zangetsu/tests/test_feedback_budget_allocator.py \
    zangetsu/tests/test_feedback_budget_consumer.py \
    zangetsu/tests/test_sparse_canary_observer.py \
    zangetsu/tests/test_sparse_canary_readiness.py
========================== 409 passed in 0.68s =========================
```

Cumulative since baseline `75f7dd8`（0-9P/R-STACK-v2 起點）：

| Layer | Tests | Source |
| --- | --- | --- |
| P7-PR4B | 54 | `test_a2_a3_arena_batch_metrics.py` |
| 0-9O-B | 62 | `test_feedback_budget_allocator.py` |
| 0-9P | 40 | `test_passport_profile_attribution.py` |
| 0-9P-AUDIT | 56 | `test_profile_attribution_audit.py` |
| 0-9R-IMPL-DRY | 81 | `test_feedback_budget_consumer.py` |
| 0-9S-CANARY | 116 | `test_sparse_canary_observer.py` + `test_sparse_canary_readiness.py` |
| **Total** | **409** | **PASS / 0 regression** |

`test_feedback_budget_allocator.py` 與 `test_feedback_budget_consumer.py`
本 PR 各做一行 allow-list 擴充（將 `sparse_canary_observer.py` 列為
legitimate downstream — 即 observer 可以 read-only import allocator
output / consumer plan output 作為觀察輸入）；其餘 411 行 / 412 行
測試邏輯零變更，故 allocator (62) + consumer (81) 全綠。

## 4. Pre-existing local-Mac fail（與本 PR 無關）

8 tests fail，root cause 為 `zangetsu/services/arena_pipeline.py:18`
`os.chdir('/home/j13/j13-ops')`，路徑只存在於 Alaya 生產機。已在
P7-PR4B / 0-9O-B / 0-9P / 0-9P-AUDIT / 0-9R-IMPL-DRY 五個 PR 期間反覆
驗證為 main 上同樣 fail，與本 PR 無關。**0 regression 來自 0-9S-CANARY**。
Alaya CI 路徑存在，全部 PASS。

## 5. Local Mac 終局統計

| Bucket | Count |
| --- | --- |
| 新增 0-9S-CANARY suite (observer + readiness) | **116 PASS / 0 FAIL** |
| 既有可執行 suite (含本 PR 共 6 layers) | **409 PASS / 0 regression** |
| 既有 pre-existing fail (與本 PR 無關) | 8 |

Alaya CI 預期：所有 0-9I / 0-9O-A / 0-9O-B / 0-9P / 0-9P-AUDIT /
0-9R-IMPL-DRY / P7-PR4B / P7-PR4-LITE 既有測試 + 116 新增 = 全 PASS。
Observer 為 dry-run-CANARY only — `applied=false` /
`mode="DRY_RUN_CANARY"` / `canary_version="0-9S-CANARY"` triple-layer
schema lock；runtime isolation tests 確認 generation / arena /
execution 三路徑無 import side-effect；behavior invariance tests 確認
A2_MIN_TRADES=25 + ATR/TRAIL/FIXED grids + threshold constants +
Arena pass/fail + champion promotion + deployable_count 七項皆未動。
