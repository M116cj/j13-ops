# 0-9O-B — Behavior Invariance Audit

## 1. Forbidden changes（§3 / §5 / §15）

| 項目 | 維持？ | 驗證 |
| --- | --- | --- |
| Alpha generation behavior | ✅ unchanged | `arena_pipeline.py`、`alpha_engine` 系列檔案未動 |
| Formula generation behavior | ✅ unchanged | DSL / AST 編譯路徑未動 |
| Mutation / crossover behavior | ✅ unchanged | GP loop knob 未動 |
| Search policy | ✅ unchanged | search policy / sampling weight 未動 |
| Real generation budget allocation | ✅ unchanged | allocator 不被 runtime 消費；`next_budget_weight_dry_run` 仍 dry-run only；`compute_dry_run_budget_weight(.., min_sample_size_met=False) == EXPLORATION_FLOOR` 保留 |
| Generation sampling weights | ✅ unchanged | 無 caller 把 allocator 輸出寫入 sampling weight |
| Thresholds（含 `A2_MIN_TRADES`、ATR/TRAIL/FIXED grids、A3 segments） | ✅ unchanged | 由 `test_a2_min_trades_still_pinned` / `test_a3_thresholds_still_pinned` source-text 檢核 |
| Arena pass/fail | ✅ unchanged | `arena_gates.py` 未動 |
| Rejection semantics | ✅ unchanged | `arena_rejection_taxonomy.py` 未動 |
| Champion promotion | ✅ unchanged | `arena45_orchestrator.maybe_promote_to_deployable` 未動；DEPLOYABLE 寫入路徑只此一處 |
| `deployable_count` semantics | ✅ unchanged | allocator 未持有 / 未產生 deployable_count；`'DEPLOYABLE'` 字串完全不存在於 allocator source |
| Execution / capital / risk | ✅ unchanged | `live/` / broker / risk 未動 |
| Service restart | ✅ not triggered | local PR；無 deploy |
| CANARY activation | ✅ not started | branch protection 不變 |
| Production rollout | ✅ not started | 屬 0-9T |
| Branch protection | ✅ unchanged | 未呼叫 governance edit |
| Signed PR-only flow | ✅ preserved | commit 走 ED25519 SSH |
| Controlled-diff strength | ✅ unchanged | 未修改 `diff_snapshots.py` |

## 2. Files modified

僅新增：

- `zangetsu/services/feedback_budget_allocator.py`（新模組）
- `zangetsu/tests/test_feedback_budget_allocator.py`（新測試）
- `docs/recovery/20260424-mod-7/0-9o-b/01..11*.md`（11 份證據）

零個 runtime SHA tracker 涵蓋的檔案被修改：

- `zangetsu_settings_sha`：unchanged
- `arena_pipeline_sha`：unchanged
- `arena23_orchestrator_sha`：unchanged
- `arena45_orchestrator_sha`：unchanged
- `calcifer_supervisor_sha`：unchanged
- `zangetsu_outcome_sha`：unchanged

## 3. Allocator 自身的不變式

| 項目 | 機制 |
| --- | --- |
| `mode = "DRY_RUN"` 不可變 | `__post_init__` + `to_event()` 雙層強制 |
| `applied = False` 不可變 | `__post_init__` + `to_event()` 雙層強制 |
| `allocator_version = "0-9O-B"` 不可變 | 同上 |
| 沒有 `apply()` method | `test_feedback_decision_record_has_no_apply_method` 透過 `dir()` 巡訪驗證 |
| 不被 runtime import | 6 個 isolation tests（見 `07_runtime_isolation_audit.md`） |
| 不寫 input | `test_weight_calculation_does_not_mutate_inputs` JSON snapshot |
| 不可能負權重 | `_normalize_with_floor` 多重 floor + scale 後再 clamp |
| 權重 sum=1.0 | `test_weights_sum_to_one` |
| Deterministic | `test_weight_calculation_is_deterministic` |
| UNKNOWN_PROFILE 不可壟斷 | `test_unknown_profile_does_not_dominate_allocation` |
| 任何 caller 嘗試 `applied=true` 被覆寫 | `test_allocator_invariants_resilient_to_caller_kwargs` / `test_allocator_invariants_resilient_to_post_construction_mutation` |

## 4. 結論

0-9O-B 完全符合 dry-run / analytics-only scope。零個 runtime SHA
變動；所有 forbidden item 維持原狀。
