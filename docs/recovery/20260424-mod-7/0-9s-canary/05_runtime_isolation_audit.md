# 05 — Runtime Isolation Audit (0-9S-CANARY)

> Stack `0-9P/R-STACK-v2`：PR-A `a8a8ba9`（attribution audit）→ PR-B
> `3219b805`（feedback budget allocator）→ PR-C `fe3075f`（feedback
> budget consumer）→ PR-D `0d7f67d`（0-9S-READY rollback / alerting
> plan）→ **本 PR：0-9S-CANARY observer + readiness checker**。
>
> 本檔證明：本 PR 新增的兩個 module
> （`zangetsu/services/sparse_canary_observer.py` 與
> `zangetsu/tools/sparse_canary_readiness_check.py`）以及它們的測試套件
> （`test_sparse_canary_observer.py` + `test_sparse_canary_readiness.py`，
> 116/116 PASS）— **皆未進入** generation runtime / Arena runtime /
> execution runtime；observer 的輸出 **不被** 任何 runtime 模組消費。
>
> 對齊 TEAM ORDER 0-9S-CANARY §11（runtime isolation）+ §6（allowed scope）
> + §7（forbidden import direction）+ CLAUDE.md §17.1 SINGLE TRUTH /
> §17.6 STALE-SERVICE CHECK。

---

## 1. Isolation principle — observer 是 leaf module

Observer 沿用 0-9R-IMPL-DRY 05 章建立的 **leaf module** pattern：
模組位於整條 data flow 的 **末端**，只 READ 上游 read-only 型別與
constants，**沒有任何邊指回 runtime**。

```
                   sparse_canary_observer.py  (this PR)
                              ▲
                              │
              READS (read-only types + constants):
                              │
                  ┌───────────┼─────────────────┐
                  │           │                 │
   feedback_budget_   feedback_budget_   feedback_decision_
   consumer.py        allocator.py       record.py
                              ▲
                              │
                arena_pass_rate_telemetry.py
                              ▲
                              │
                arena_pipeline / arena23 / arena45  (Arena runtime)
                              ▲
                              │
                alpha_signal_live / alpha_dedup / alpha_ensemble /
                alpha_discovery / data_collector  (execution runtime)
```

### 1.1 三條硬性 invariant

1. **No edge OUT** — observer 不被任何 runtime / Arena / execution
   module import；輸出結構 `SparseCanaryObservation` 不被 runtime 消費。
2. **No apply method** — observer 對外 surface 不存在 `apply_*` /
   `commit_*` / `execute_*` 公開 symbol（與 0-9R-IMPL-DRY 05 §4 同樣
   principle，但範圍擴大到 sparse-canary 命名空間）。
3. **Hard-coded mode** — `mode` 欄位永遠是 `MODE_DRY_RUN_CANARY`
   constant，sealed by `__post_init__` 和 `to_event()` 兩道
   normalization；**不存在** `mode == "APPLY"` 的 runtime 切換路徑。

任何違反上述三條都會被 `test_sparse_canary_observer.py` 中的對應測試
直接 FAIL，無法 merge（CI Gate-A）。

### 1.2 與 PR-C consumer 的對稱性

PR-C 的 `feedback_budget_consumer.py` 同樣是 leaf；本 PR 的 observer
新增一層更外側的 leaf — 它讀 consumer 的型別（`SparseCandidateDryRunPlan`）
卻 **不被** consumer 反向 import。換言之：

```
runtime → arena → telemetry → allocator → consumer → observer
       (forward-only data flow, never reversed)
```

每一步都是 read-only 引用上游 type；上游從不向下 reach。Observer 是
這條 chain 的 **terminal vertex**。

---

## 2. Forbidden import direction（per order §11 / §7）

下列 import direction 被本 PR 顯式禁止並由測試驗證：

### 2.1 模組層級禁止 import

| # | Forbidden direction | 驗證測試 |
| --- | --- | --- |
| 2.1.1 | `arena_pipeline.py` import `sparse_canary_observer` | `test_canary_observer_not_imported_by_generation_runtime` |
| 2.1.2 | `arena23_orchestrator.py` import `sparse_canary_observer` | `test_canary_observer_not_imported_by_arena_runtime` |
| 2.1.3 | `arena45_orchestrator.py` import `sparse_canary_observer` | `test_canary_observer_not_imported_by_arena_runtime` |
| 2.1.4 | `arena_gates.py` import `sparse_canary_observer` | `test_canary_observer_not_imported_by_arena_runtime` |
| 2.1.5 | `alpha_signal_live.py` import `sparse_canary_observer` | `test_canary_observer_not_imported_by_execution_runtime` |
| 2.1.6 | `alpha_dedup.py` import `sparse_canary_observer` | `test_canary_observer_not_imported_by_execution_runtime` |
| 2.1.7 | `alpha_ensemble.py` import `sparse_canary_observer` | `test_canary_observer_not_imported_by_execution_runtime` |
| 2.1.8 | `alpha_discovery.py` import `sparse_canary_observer` | `test_canary_observer_not_imported_by_execution_runtime` |
| 2.1.9 | `data_collector.py` import `sparse_canary_observer` | `test_canary_observer_not_imported_by_execution_runtime` |
| 2.1.10 | `arena_pipeline.py` import `feedback_budget_consumer` | `test_feedback_consumer_not_imported_by_generation_runtime`（PR-C inherited） |
| 2.1.11 | Allocator output (`DryRunBudgetAllocation` / `allocate_dry_run_budget`) referenced in `arena_pipeline.py` | `test_allocator_output_not_consumed_by_generation_runtime`（PR-B inherited，本 PR 擴 allow-list） |

### 2.2 結構層級禁止狀態

| # | Forbidden state | 驗證測試 |
| --- | --- | --- |
| 2.2.1 | `apply()` method exists on observer | `test_no_apply_method_exists` |
| 2.2.2 | `applied=true` representable in `SparseCanaryObservation` | `test_observation_post_init_resets_applied_to_false` + `test_observation_to_event_does_not_propagate_applied_true` |
| 2.2.3 | `mode` switchable to `"APPLY"` | `test_no_runtime_switchable_apply_mode_exists` |
| 2.2.4 | `SparseCanaryObservation` referenced in any runtime / Arena / execution / non-allow-listed services file | `test_observer_output_not_consumed_by_runtime` |

### 2.3 為什麼三層全部覆蓋

`arena_pipeline` = generation runtime（產生 alpha candidate）
`arena23/arena45/arena_gates` = Arena runtime（A1/A2/A3 evaluation）
`alpha_signal_live/...` = execution runtime（live trading I/O）

三者構成 zangetsu 從 generation → evaluation → execution 的完整 critical
path；observer 不可進入任一層，否則就不再是 dry-run observation。

---

## 3. Verified-by-test isolation matrix

| Test name | Direction verified |
| --- | --- |
| `test_canary_observer_not_imported_by_generation_runtime` | `arena_pipeline.py` clean — 不含 `sparse_canary_observer` |
| `test_canary_observer_not_imported_by_arena_runtime` | `arena23_orchestrator.py` / `arena45_orchestrator.py` / `arena_gates.py` 三個檔案 clean |
| `test_canary_observer_not_imported_by_execution_runtime` | `alpha_signal_live.py` 加上 `alpha_dedup` / `alpha_ensemble` / `alpha_discovery` / `data_collector` 全部 clean |
| `test_feedback_consumer_not_imported_by_generation_runtime` | inherited check（PR-C），確保新 observer 不打開 consumer 進入 generation 的旁路 |
| `test_allocator_output_not_consumed_by_generation_runtime` | `DryRunBudgetAllocation` / `allocate_dry_run_budget` 兩個 symbol 在 `arena_pipeline.py` 都不存在 |
| `test_no_apply_method_exists` | `dir(sparse_canary_observer)` walk；無任何 `apply_*` 公開 symbol |
| `test_no_runtime_switchable_apply_mode_exists` | source-text scan：source 內不存在 `mode == "APPLY"` / `mode = "APPLY"` 兩種 path |
| `test_observer_output_not_consumed_by_runtime` | walk `zangetsu/services/*.py`（excluding observer 自身），assert 既無 `SparseCanaryObservation` 字面，也無 `from zangetsu.services.sparse_canary_observer` import |
| `test_observation_post_init_resets_applied_to_false` | 構造 dataclass 帶 `applied=True` → `__post_init__` 強制歸 False |
| `test_observation_to_event_does_not_propagate_applied_true` | event payload 不可攜帶 `applied=true`；強 normalize |
| `test_observer_mode_constant_is_dry_run` | `MODE_DRY_RUN_CANARY` constant 字面為 `"DRY_RUN_CANARY"`；無 `MODE_APPLY` constant 出現 |
| `test_safe_observe_swallows_runtime_errors` | `safe_observe()` 任一上游錯誤都回 None，不向上拋（fail-closed），確保 observer 即使壞掉也不污染 runtime |

> 116/116 PASS — 包含上述所有 isolation 測試 + observer 行為正確性測試
> + readiness checker CR1–CR12 測試。

---

## 4. Allow-list extensions for prior tests

PR-B（allocator）與 PR-C（consumer）已建立兩個 isolation 測試，
分別 walk `zangetsu/services/*.py` 並 assert 自身 output struct **未被**
非允許清單中的下游 module reference。本 PR 在 services 目錄新增
`sparse_canary_observer.py`，自然要把它加進兩個測試的 allow-list。

### 4.1 修改清單（minimal、純 allow-list 加一字串）

```
zangetsu/tests/test_feedback_budget_allocator.py
  └─ test_allocator_output_not_consumed_by_generation_runtime
       allow_list += {"sparse_canary_observer.py"}
       (joins existing entry: "feedback_budget_consumer.py")

zangetsu/tests/test_feedback_budget_consumer.py
  └─ test_consumer_output_not_consumed_by_runtime
       allow_list += {"sparse_canary_observer.py"}
```

### 4.2 為什麼這是 maintenance 而非 isolation 鬆綁

- Allow-list 只 whitelist「合法的下游 type-only reader」。Observer
  讀 allocator 的 `DryRunBudgetAllocation` type 與 consumer 的
  `SparseCandidateDryRunPlan` type，都是 read-only type/constant 引用。
- Allow-list 並 **不允許** 反向 import（observer → allocator/consumer 是
  forward 引用；allocator/consumer 不會 import observer）。
- 測試本身的「runtime 不可消費 allocator/consumer 輸出」這條 invariant
  維持原狀；只是把已知合法的 sibling leaf module 加入 sibling
  whitelist，避免假陽性。
- 這個改動範圍 = 在 `set` literal 中加一個字串；不修改 assertion
  邏輯、不修改 walk 目錄、不修改 forbidden symbol 清單。

對齊 TEAM ORDER 0-9S-CANARY §6 (allowed scope)：本 PR 的修改限於
新增 observer + readiness checker + 對應測試 + 兩個既有測試的
allow-list 擴充；**沒有** 觸碰 runtime / Arena / execution 任一檔案。

---

## 5. Apply-path absence

### 5.1 公開 surface（observer + readiness checker）

```
sparse_canary_observer.py public symbols:
  ATTRIBUTION_VERDICT_GREEN, ATTRIBUTION_VERDICT_YELLOW, ATTRIBUTION_VERDICT_RED,
  EVENT_TYPE_SPARSE_CANARY_OBSERVATION,
  FAILURE_F1_A2_IMPROVE_A3_COLLAPSE, FAILURE_F2_DEPLOYABLE_DOWN,
  FAILURE_F3_OOS_FAIL_INCREASE, FAILURE_F4_UNKNOWN_REJECT_INCREASE,
  FAILURE_F5_PROFILE_COLLAPSE, FAILURE_F6_EXPLORATION_FLOOR_VIOLATED,
  FAILURE_F7_ATTRIBUTION_RED, FAILURE_F8_ROLLBACK_UNAVAILABLE,
  FAILURE_F9_COMPOSITE_REGRESSION,
  MODE_DRY_RUN_CANARY,
  OBSERVER_VERSION,
  SUCCESS_VERDICT_INSUFFICIENT_HISTORY, SUCCESS_VERDICT_PASS,
  SUCCESS_VERDICT_PENDING, SUCCESS_VERDICT_REGRESS,
  SparseCanaryBaseline, SparseCanaryObservation, SparseCanaryObservationContext,
  evaluate_failure_criteria, evaluate_success_criteria,
  observe, safe_observe, serialize_observation
```

```
sparse_canary_readiness_check.py public symbols:
  CR1_BASELINE_SNAPSHOT, CR2_ATTRIBUTION_VERDICT, ..., CR12_ALERT_PLAN,
  ReadinessCheckResult,
  run_readiness_checks, format_readiness_report
  (offline tool entrypoint: __main__)
```

### 5.2 不存在的 symbol（顯式列出）

下列名稱在本 PR 新增的兩個 module 中 **皆不存在**：

```
apply_budget         apply_plan          apply_consumer
apply_allocator      apply_canary        apply_recommendation
apply_weights        apply_sampling      apply_generation
commit_observation   execute_observation publish_observation
dispatch_observation run_apply           apply_observation
```

驗證：

- 公開 surface 由 `dir()` walk 在 `test_no_apply_method_exists` 比對。
- 額外由 readiness checker 的 `_grep_apply_def()` 函數在 CR4 階段
  跑 source-text grep（`^def apply_(budget|plan|consumer|allocator|
  canary|recommendation|weights|sampling|generation)`）；命中即 FAIL。

### 5.3 既有 trading helper 例外（不在禁止清單）

zangetsu codebase 中 **早已存在** 三個 trading 用 helper：

```
apply_trailing_stop  (alpha_signal_live.py)
apply_fixed_target   (alpha_signal_live.py)
apply_tp_strategy    (alpha_signal_live.py)
```

它們：

- **僅修改 numpy signal array**（per-bar TP/SL post-processing）；
- 不修改 budget、不修改 sampling weight、不修改 generation profile；
- 與 sparse-canary domain 完全無交集。

`_grep_apply_def()` 的 regex 故意只匹配 `apply_(budget|plan|consumer|
allocator|canary|recommendation|weights|sampling|generation)`，上述
三個 trading helper 不在 alternation 內，因此屬於 exempt prior art。

---

## 6. Forbidden symbol grep examples

### 6.1 確認本 PR 兩個 module 不含 sparse-canary 命名空間的 apply def

```bash
grep -nE "^def apply_(budget|plan|consumer|allocator|canary|recommendation|weights|sampling|generation)" \
    zangetsu/services/sparse_canary_observer.py \
    zangetsu/tools/sparse_canary_readiness_check.py
# expected: empty
```

### 6.2 確認 services 內沒有除自身與兩個合法 sibling 以外的 module 引用 observer

```bash
grep -rn "sparse_canary_observer" zangetsu/services/ \
  | grep -v sparse_canary_observer.py \
  | grep -v feedback_budget_consumer.py \
  | grep -v feedback_budget_allocator.py
# expected: empty
```

> 為什麼把 consumer 和 allocator 加進 grep -v：兩個 module 在
> `__doc__` / 註解中可能 cross-reference observer 名稱（為了 traceability），
> 但 **沒有** import 它。Allow-list 是 documentation-level 引用，不是
> runtime import。實際 import 由 `test_canary_observer_not_imported_by_*`
> 系列 AST 測試保證。

### 6.3 確認 generation runtime 不引用 allocator / consumer 的輸出 type

```bash
grep -nE "DryRunBudgetAllocation|allocate_dry_run_budget|SparseCandidateDryRunPlan" \
    zangetsu/services/arena_pipeline.py
# expected: empty
```

### 6.4 確認 source 沒有 runtime-switchable APPLY mode

```bash
grep -nE 'mode\s*==\s*"APPLY"|mode\s*=\s*"APPLY"|MODE_APPLY' \
    zangetsu/services/sparse_canary_observer.py
# expected: empty
```

---

## 7. Output isolation

`SparseCanaryObservation` 是 observer 唯一對外 emit 的結構；entry
points 是 `observe()` / `safe_observe()` / `serialize_observation()`。
這四個名字 **不被** 任何 runtime / Arena / execution 模組引用。

### 7.1 驗證範圍（`test_observer_output_not_consumed_by_runtime`）

該測試 walk `zangetsu/services/*.py`（排除 `sparse_canary_observer.py`
本身），對每個檔案做兩個 assertion：

1. 檔案內容不含字面 `SparseCanaryObservation`；
2. 檔案內容不含 `from zangetsu.services.sparse_canary_observer`。

兩個 assertion 都必須對 services 目錄下所有非自身 `.py` 檔通過。

### 7.2 額外的 entry-point 檢查

`observe` / `safe_observe` / `serialize_observation` 三個函數名也由
`test_canary_observer_not_imported_by_*` 系列做 AST 級驗證：在 generation
/ Arena / execution 三層的指定檔案中，import 表內不可出現它們。

### 7.3 為什麼 output 隔離很重要

Observer 的目的是「觀察」而不是「驅動」。如果 runtime 開始消費
observation 結果，就會出現一條 hidden feedback loop：

```
runtime → telemetry → allocator → consumer → observer
   ▲                                             │
   └─────────────── (forbidden hidden edge) ─────┘
```

這條邊一旦出現，dry-run observation 就變成了 implicit apply path，
完全違反 0-9S-CANARY 的「observe-only」契約。`test_observer_output_
not_consumed_by_runtime` 是 **守住這條邊** 的關鍵 invariant。

---

## 8. Cross-reference summary（每條 isolation 規則對應的測試）

| Isolation rule | Enforcing test(s) | File |
| --- | --- | --- |
| Observer not imported by generation runtime | `test_canary_observer_not_imported_by_generation_runtime` | `test_sparse_canary_observer.py` |
| Observer not imported by Arena runtime（arena23/arena45/arena_gates）| `test_canary_observer_not_imported_by_arena_runtime` | `test_sparse_canary_observer.py` |
| Observer not imported by execution runtime（alpha_signal_live + alpha_dedup + alpha_ensemble + alpha_discovery + data_collector）| `test_canary_observer_not_imported_by_execution_runtime` | `test_sparse_canary_observer.py` |
| Consumer not imported by generation runtime（PR-C inherited）| `test_feedback_consumer_not_imported_by_generation_runtime` | `test_sparse_canary_observer.py` |
| Allocator output not consumed by generation runtime（PR-B inherited，本 PR 擴 allow-list）| `test_allocator_output_not_consumed_by_generation_runtime` | `test_feedback_budget_allocator.py` |
| Consumer output not consumed by runtime（PR-C inherited，本 PR 擴 allow-list）| `test_consumer_output_not_consumed_by_runtime` | `test_feedback_budget_consumer.py` |
| No `apply_*` public symbol on observer | `test_no_apply_method_exists` | `test_sparse_canary_observer.py` |
| No runtime-switchable APPLY mode | `test_no_runtime_switchable_apply_mode_exists` | `test_sparse_canary_observer.py` |
| `applied=true` reset by `__post_init__` | `test_observation_post_init_resets_applied_to_false` | `test_sparse_canary_observer.py` |
| `applied=true` not propagated by `to_event()` | `test_observation_to_event_does_not_propagate_applied_true` | `test_sparse_canary_observer.py` |
| Observer mode constant locked to DRY_RUN_CANARY | `test_observer_mode_constant_is_dry_run` | `test_sparse_canary_observer.py` |
| Observer output (`SparseCanaryObservation`) not referenced in any runtime/Arena/execution/non-allow-listed services file | `test_observer_output_not_consumed_by_runtime` | `test_sparse_canary_observer.py` |
| `safe_observe` swallows upstream errors（fail-closed）| `test_safe_observe_swallows_runtime_errors` | `test_sparse_canary_observer.py` |
| Readiness checker CR4：no `apply_*` def in any service | `test_canary_blocks_when_apply_def_present`（hypothetical-positive flip）| `test_sparse_canary_readiness.py` |
| Readiness checker CR11：rollback plan exists | `test_canary_finds_rollback_plan_in_repo` | `test_sparse_canary_readiness.py` |
| Readiness checker CR12：alert plan exists | `test_canary_finds_alert_plan_in_repo` | `test_sparse_canary_readiness.py` |

---

## 9. 驗證命令清單（合併 PR review 時人工 spot-check）

```bash
# 9.1 跑全部 116 個測試
cd /Users/a13/dev/j13-ops
pytest zangetsu/tests/test_sparse_canary_observer.py \
       zangetsu/tests/test_sparse_canary_readiness.py -v
# expected: 116 passed

# 9.2 確認三層 runtime 都不 import observer
for f in arena_pipeline.py arena23_orchestrator.py arena45_orchestrator.py \
         arena_gates.py alpha_signal_live.py alpha_dedup.py \
         alpha_ensemble.py alpha_discovery.py data_collector.py; do
  echo "=== $f ==="
  grep -E "sparse_canary_observer|SparseCanaryObservation" "zangetsu/services/$f" \
    "zangetsu/services/$f" 2>/dev/null || echo "  (clean)"
done
# expected: 全部 (clean)

# 9.3 確認沒有 apply_<sparse-canary-domain> 函數
grep -rnE "^def apply_(budget|plan|consumer|allocator|canary|recommendation|weights|sampling|generation)" \
    zangetsu/services/ zangetsu/tools/
# expected: empty

# 9.4 確認 observer 自身不可切到 APPLY mode
grep -nE 'MODE_APPLY|mode\s*=\s*"APPLY"|mode\s*==\s*"APPLY"' \
    zangetsu/services/sparse_canary_observer.py
# expected: empty
```

---

## 10. 結論

- Observer + readiness checker 是 leaf module；圖上無 outgoing edge
  指向 generation / Arena / execution runtime。
- 三層 runtime forbidden import direction 由 12 個測試共同覆蓋，
  全部位於 `test_sparse_canary_observer.py` + `test_sparse_canary_readiness.py`。
- `apply()` method、`applied=true` propagation、`mode == "APPLY"` 切換
  路徑全部不存在，並由 source-text + AST 兩種測試共同 enforce。
- 對既有測試的修改限於 PR-B / PR-C 兩個 isolation 測試的 allow-list
  擴充（純 maintenance）；isolation 邏輯本身未鬆綁。
- 116/116 PASS 是 PR merge 的必要條件，CI Gate-A 阻擋任何 isolation
  測試 regression。

> 本檔對齊：TEAM ORDER 0-9S-CANARY §6 / §7 / §11 + CLAUDE.md §17.1 SINGLE
> TRUTH + §17.6 STALE-SERVICE CHECK + 0-9R-IMPL-DRY 05_runtime_isolation_audit.md
> （pattern source）+ 0-9S-READY 03_rollback_plan.md（rollback contract）
> + 0-9S-READY 04_alerting_and_monitoring_plan.md（alerting contract）。

---

## 11. Cross-reference

- `docs/recovery/20260424-mod-7/0-9r-impl-dry/05_runtime_isolation_audit.md` — pattern source
- `docs/recovery/20260424-mod-7/0-9s-ready/03_rollback_plan.md` — rollback contract this PR adheres to
- `docs/recovery/20260424-mod-7/0-9s-ready/04_alerting_and_monitoring_plan.md` — alerting contract this PR adheres to
- `docs/recovery/20260424-mod-7/0-9s-canary/06_rollback_and_alerting_verification.md` — sibling doc (本 PR)
- `zangetsu/services/sparse_canary_observer.py` — module under audit
- `zangetsu/tools/sparse_canary_readiness_check.py` — offline tool under audit
- `zangetsu/tests/test_sparse_canary_observer.py` — isolation + behavior tests
- `zangetsu/tests/test_sparse_canary_readiness.py` — CR1–CR12 tests
- CLAUDE.md §17.1 SINGLE TRUTH — VIEW deployable_count 是 truth 之源
- CLAUDE.md §17.6 STALE-SERVICE CHECK — process 必須比 source 新才能宣告 done
