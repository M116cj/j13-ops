# 04 — Behavior Invariance Audit

## 1. 規則對照（per TEAM ORDER 0-9P §3 / §6）

| 項目 | 維持 | 驗證 |
| --- | --- | --- |
| Alpha generation behavior | ✅ | `_gen_profile_identity` 是 startup-once 的 read-only metadata；passport 寫入是 metadata 增補，不觸 alpha 生成路徑 |
| Formula generation behavior | ✅ | DSL / AST / `alpha_engine` 完全未動 |
| Mutation / crossover behavior | ✅ | GP loop knobs 未動 |
| Search policy | ✅ | 未動 |
| Real generation budget | ✅ | budget knobs (N_GEN / POP_SIZE / TOP_K) 未動 |
| Sampling weights | ✅ | 未引入 sampling-weight 機械 |
| Candidate scoring semantics | ✅ | `score = float(val_wilson) * _pnl_component` 未動 |
| Thresholds（含 `A2_MIN_TRADES`、ATR/TRAIL/FIXED grids、A3 segment thresholds） | ✅ | 字面 unchanged；source-text 測試強制驗證 |
| Arena pass/fail（`arena_gates.arena2_pass` / `arena3_pass` / `arena4_pass`） | ✅ | `arena_gates.py` 未動；`generation_profile_id` 字串完全不存在於該檔 |
| Rejection semantics（`arena_rejection_taxonomy`） | ✅ | enum / RAW_TO_REASON 未動；`generation_profile_id` 不存在於該檔 |
| Champion promotion | ✅ | `arena45_orchestrator.maybe_promote_to_deployable` 未動；UPDATE 子句不含 profile id 條件 |
| `deployable_count` semantics | ✅ | DEPLOYABLE 字串不存在於 modified files 之內 |
| Execution / capital / risk | ✅ | `live/` / broker / risk 未動 |
| Service restart | ✅ | local PR；無 deploy |
| CANARY activation | ✅ | 未啟動 |
| Production rollout | ✅ | 未啟動 |
| Branch protection | ✅ | governance 未編輯 |
| Signed PR-only flow | ✅ | ED25519 SSH commit 簽章 |
| Controlled-diff strength | ✅ | 未修改 `diff_snapshots.py` |
| 不引入 per-alpha lineage | ✅ | 未引入 `alpha_lineage` / `parent_alpha` / `ancestor_chain` 等 |
| 不要求 formula explainability | ✅ | profile fingerprint 仍是 sha256-over-knobs |
| Telemetry 失敗不影響 Arena | ✅ | passport 寫入路徑用 try/except 包裹；fallback to UNKNOWN |

## 2. Files modified

唯一 runtime SHA 變動：
- `zangetsu/services/arena_pipeline.py`（authorized EXPLAINED_TRACE_ONLY，metadata-only）

非 runtime SHA tracker 涵蓋：
- `zangetsu/services/generation_profile_identity.py`（新增
  `resolve_attribution_chain` 純 Python helper）

新檔：
- `zangetsu/tests/test_passport_profile_attribution.py`（40 tests）
- `docs/recovery/20260424-mod-7/0-9p/01..07*.md`（7 evidence docs）

零 runtime 檔案被增刪欄位。`admission_validator` 的 SQL INSERT
column list **未動**；profile_id 僅存在 `passport` JSONB blob 內，
不影響 staging schema。

## 3. SQL 影響

`champion_pipeline_staging.passport` 為 JSONB；新增兩個欄位是
JSONB 內部結構變更，不需 schema migration。

下游讀取者：
- `arena23_orchestrator.py` 透過 `json.loads(champion["passport"])`
  讀整個 blob，已能拾取新欄位。
- `arena45_orchestrator.py` 不關心 profile id。
- `candidate_lifecycle_reconstruction.py` 不關心 profile id（只看
  `arena1` 內既有 alpha_hash / hash 等）。
- `dashboard/`、`console/` 不解析 profile id。

## 4. Tests for behavior invariance

`test_passport_profile_attribution.py`：

- `test_no_threshold_constants_changed`
- `test_a2_min_trades_still_pinned`
- `test_a3_thresholds_still_pinned`
- `test_arena_pass_fail_behavior_unchanged`
- `test_champion_promotion_unchanged`
- `test_generation_budget_unchanged`
- `test_sampling_weights_unchanged`
- `test_no_formula_lineage_added`
- `test_no_parent_child_ancestry_added`
- `test_passport_identity_does_not_change_arena_decisions`
- `test_passport_identity_does_not_change_candidate_admission`
- `test_passport_identity_does_not_change_rejection_semantics`
- `test_passport_identity_does_not_change_deployable_count`
- `test_passport_identity_failure_does_not_block_telemetry`
- `test_no_runtime_apply_path_introduced`

全部 PASS（local Mac）。詳見 `05_test_results.md`。

## 5. 結論

0-9P 純粹是 metadata persistence；零 Arena 決策語意改動。
唯一 runtime SHA 變動透過 0-9M EXPLAINED_TRACE_ONLY 路徑授權；
所有 forbidden item 維持原狀。
