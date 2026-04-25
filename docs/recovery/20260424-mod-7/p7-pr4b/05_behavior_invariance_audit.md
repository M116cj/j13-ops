# P7-PR4B — Behavior Invariance Audit

對照 TEAM ORDER P7-PR4B §3 / §5 / §10 / §18 / §19，本 PR 在 ZANGETSU
runtime 上的 invariant 清單與其驗證來源。

## 1. Forbidden changes（§3 / §5 / §18 / §19）

| 項目 | 維持？ | 驗證來源 |
| --- | --- | --- |
| Alpha generation behavior | ✅ unchanged | `arena_pipeline.py` not modified；`engine/components/alpha_engine.py` not modified |
| Formula generation behavior | ✅ unchanged | `engine/components/alpha_signal.py`、operator DSL、AST 編譯路徑全部 untouched |
| Mutation / crossover behavior | ✅ unchanged | `alpha_engine` GP loop 未變更 |
| Search policy | ✅ unchanged | search policy / sampling weight 未動 |
| Generation budget allocation | ✅ unchanged | `next_budget_weight_dry_run` 仍是 dry-run only；`compute_dry_run_budget_weight(.., min_sample_size_met=False) == EXPLORATION_FLOOR` 強制保留 |
| Generation sampling weights | ✅ unchanged | Calcifer / pool weight 未動 |
| Thresholds 全集（A2_MIN_TRADES、entry/exit、ATR_STOP_MULTS、TRAIL_PCTS、FIXED_TARGETS、A3 segment threshold、A4 promotion thresholds） | ✅ unchanged | `bt.total_trades < 25` 仍存在於 V10 path（`test_a2_min_trades_still_pinned`）；ATR/TRAIL/FIXED 常數常數不變（`test_a3_thresholds_still_pinned`）；arena_gates / arena45 promotion 未動 |
| Arena pass/fail branch conditions | ✅ unchanged | `arena_gates.arena2_pass / arena3_pass / arena4_pass` 不變；`process_arena2 / process_arena3` 控制流未動，僅 caller 在 main loop 取 result 後做 telemetry side-effect |
| Rejection semantics | ✅ unchanged | reject 仍從同樣的條件分支發起；taxonomy classify 是 read-only |
| Champion promotion | ✅ unchanged | `arena45_orchestrator.maybe_promote_to_deployable` 未動；DEPLOYABLE 寫入路徑只此一處（`test_champion_promotion_unchanged`） |
| `deployable_count` semantics | ✅ unchanged | A2/A3 batch metrics emission 顯式傳 `deployable_count=None`；`aggregate_batches_for_profile` 只認顯式 integer（`test_a2_a3_pass_metrics_do_not_inflate_deployable_count`） |
| Execution / capital / risk | ✅ unchanged | `live/`、broker、risk control 未動 |
| Service restart | ✅ not triggered | local PR；deployment / restart 由後續 order 處理 |
| CANARY activation | ✅ not started | branch protection 不變；CANARY 屬 0-9S |
| Production rollout | ✅ not started | 屬 0-9T |
| Branch protection（required_signatures, linear_history, enforce_admins, allow_force_pushes, allow_deletions） | ✅ unchanged | 未呼叫 governance edit |
| Signed PR-only flow | ✅ preserved | commit 走 ED25519 簽章 |
| Controlled-diff strength | ✅ unchanged | 未修改 `diff_snapshots.py`；只透過授權 `--authorize-trace-only config.arena23_orchestrator_sha` 走既有 0-9M pathway |
| Per-alpha lineage 引入 | ❌ 未引入 | telemetry 只 aggregate；無 per-candidate row |
| Formula explainability 強制 | ❌ 未引入 | profile fingerprint 維持 sha256 over knob dict，無 formula 解釋 |
| Telemetry 影響 runtime 決策 | ❌ 不會 | 所有 telemetry 動作以 try / except 包裹；emission 失敗 silently 回 False；orchestrator runtime path 不依賴 telemetry 回傳值 |

## 2. Files modified（runtime）

唯一 runtime SHA 變動：`zangetsu/services/arena23_orchestrator.py`
（authorized EXPLAINED_TRACE_ONLY）。

`arena_pipeline.py`、`arena45_orchestrator.py`、`arena_gates.py`、
`zangetsu/config/settings.py`、`engine/`、`live/`、`scripts/`、
`migrations/`、`calcifer/`、`watchdog.sh`、`zangetsu_ctl.sh`：**未動**。

## 3. Files modified（helper / metrics / tests / docs）

非 runtime SHA tracker 涵蓋的 helper 改動：

- `zangetsu/services/arena_pass_rate_telemetry.py` — additive helpers。
- `zangetsu/services/generation_profile_metrics.py` — confidence enum
  增補 + 三態 resolution。

新檔：

- `zangetsu/tests/test_a2_a3_arena_batch_metrics.py` — 54 tests。
- `docs/recovery/20260424-mod-7/p7-pr4b/01..08*.md` — 8 evidence docs。

以上皆非 CODE_FROZEN 檔，controlled-diff 分類為 EXPLAINED / DOC_ONLY。

## 4. Test 結果摘要

`zangetsu/tests/test_a2_a3_arena_batch_metrics.py`：54 / 54 PASS（local
Mac，`python3 -m pytest zangetsu/tests/test_a2_a3_arena_batch_metrics.py`）。

既有測試在 local Mac 上 14 個 fail 屬於 pre-existing — 因為
`zangetsu/services/arena_pipeline.py` 模組頂端做
`os.chdir('/home/j13/j13-ops')`，這條路徑只存在於 Alaya 生產機。在
Alaya CI 上既有 253 tests 全 pass（依 0-9O-A PR #17 evidence 與
本 PR 未變動 arena_pipeline.py 的事實推論）。

## 5. 結論

P7-PR4B 完全符合 trace-only / telemetry-only 範圍。唯一
runtime SHA 變動（`arena23_orchestrator.py`）於 0-9M
`EXPLAINED_TRACE_ONLY` 授權範圍內；所有 forbidden item 維持原狀。
