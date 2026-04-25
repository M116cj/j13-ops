# 0-9S-CANARY — Controlled-Diff Report (Expected)

PR-CANARY following stack `0-9P/R-STACK-v2` — 在 PR-A `0-9P` 合併於
`a8a8ba9`、PR-B `0-9P-AUDIT` 合併於 `3219b805`、PR-C `0-9R-IMPL-DRY`
合併於 `fe3075f`、PR-D `0-9S-READY` 合併於 `0d7f67d` 之後。本 PR-E 交
付：

- `zangetsu/services/sparse_canary_observer.py`（新模組，~600 LOC）
- `zangetsu/tools/sparse_canary_readiness_check.py`（新離線工具，~300 LOC）
- 116 tests（observer 71 + readiness 45）
- 11 份 evidence docs

**本 PR 不修改任何 CODE_FROZEN runtime SHA 檔案**。

## 1. Snapshot capture（在 Alaya 執行）

```bash
ssh j13@100.123.49.102 \
  '/home/j13/j13-ops/scripts/governance/capture_snapshot.sh \
       pre-0-9s-canary j13@alaya'

ssh j13@100.123.49.102 \
  'cd /home/j13/j13-ops && \
   git fetch origin phase-7/0-9s-canary-dry-run-activation && \
   git checkout origin/phase-7/0-9s-canary-dry-run-activation'

ssh j13@100.123.49.102 \
  '/home/j13/j13-ops/scripts/governance/capture_snapshot.sh \
       post-0-9s-canary j13@alaya'

ssh j13@100.123.49.102 \
  'python3 /home/j13/j13-ops/scripts/governance/diff_snapshots.py \
       /home/j13/j13-ops/docs/governance/snapshots/<pre>.json \
       /home/j13/j13-ops/docs/governance/snapshots/<post>.json \
       --purpose 0-9s-canary'
```

**關鍵：本 PR 不需 `--authorize-trace-only` flag**。原因見 §11 — 無任
何 runtime SHA 變動，唯一 EXPLAINED diff 為
`repo.git_status_porcelain_lines`（branch 切換造成的 working tree 行數
變化）。其餘所有欄位 zero-diff（含 6 個 CODE_FROZEN runtime SHA + 全
部 hard-forbidden 欄位）。

## 2. Expected classification

```
Classification: EXPLAINED  (NOT EXPLAINED_TRACE_ONLY — no runtime SHA changed)

Zero diff:                   ~43 fields  (incl. all 6 CODE_FROZEN runtime SHAs)
Explained diff:              1 field   — repo.git_status_porcelain_lines
Explained TRACE_ONLY diff:   0 fields
Forbidden diff:              0 fields
```

EXPLAINED 而非 EXPLAINED_TRACE_ONLY 的關鍵：本 PR 沒有任何 runtime SHA
進入 trace-only 路徑。`sparse_canary_observer.py` 為新 service module
但不在 CODE_FROZEN tracker 清單；`sparse_canary_readiness_check.py` 為
新 offline tool 同樣不在 tracker 清單；tests / docs / allow-list 微調
皆 non-CODE_FROZEN。

## 3. Files added（皆 non-CODE_FROZEN）

| Path | Type | Notes |
| --- | --- | --- |
| `zangetsu/services/sparse_canary_observer.py` | new module (~600 LOC) | `SparseCanaryObservation` dataclass + `observe()` / `safe_observe()` / `serialize_observation()` + S1–S14 / F1–F9 evaluators + composite / density / diversity / collapse / stability helpers |
| `zangetsu/tools/sparse_canary_readiness_check.py` | new offline tool (~300 LOC) | CR1–CR15 readiness preflight；無 import side effect；CLI entry 為 read-only；`required_cr_ids()` 回傳鎖定 tuple |
| `zangetsu/tests/test_sparse_canary_observer.py` | new test file | 71 tests |
| `zangetsu/tests/test_sparse_canary_readiness.py` | new test file | 45 tests |
| `docs/recovery/20260424-mod-7/0-9s-canary/01..11*.md` | evidence docs | 11 markdown artifacts |

## 4. Files modified（皆 non-CODE_FROZEN，allow-list extension only）

| Path | Type | Diff scope |
| --- | --- | --- |
| `zangetsu/tests/test_feedback_budget_allocator.py` | allow-list extension | 1-line `set` 新增：把 `sparse_canary_observer.py` 加入 `allocate_dry_run_budget` symbol 的 legitimate-downstream 名單 |
| `zangetsu/tests/test_feedback_budget_consumer.py` | allow-list extension | 1-line `set` 新增：把 `sparse_canary_observer.py` 加入 `SparseCandidateDryRunPlan` symbol 的 legitimate-downstream 名單 |

兩個 allow-list 修改：

- **是測試檔，不是 runtime**（CODE_FROZEN tracker 不收測試檔）
- **不放行 runtime caller** — 這兩個放行的是「observer 可以 read-only
  import allocator output / consumer plan output 作為觀察輸入」，
  並沒有把 observer 自身放進任何 runtime 的 import 路徑
- **不改測試邏輯** — 僅在現有 allow-list 集合裡多加一個 module path
  字串，斷言邏輯完全不變
- **無新增測試讓 observer 進入 runtime 路徑** — §12.5 七條 isolation
  tests 主動 grep 並斷言 observer 不在 generation / Arena / execution
  runtime 任何 source 中被 import

## 5. Files NOT modified — 完全 zero-diff

以下檔案 zero-diff（本 PR 為 dry-run-CANARY observer，不觸動 runtime
／engine／live／config／generation／Arena pass-fail／champion／
execution）：

- `zangetsu/services/arena_pipeline.py`
- `zangetsu/services/arena23_orchestrator.py`
- `zangetsu/services/arena45_orchestrator.py`
- `zangetsu/services/arena_gates.py`
- `zangetsu/services/feedback_budget_allocator.py`
- `zangetsu/services/feedback_budget_consumer.py`
- `zangetsu/services/feedback_decision_record.py`
- `zangetsu/services/generation_profile_metrics.py`
- `zangetsu/services/generation_profile_identity.py`
- `zangetsu/services/arena_pass_rate_telemetry.py`
- `zangetsu/services/arena_rejection_taxonomy.py`
- `zangetsu/tools/profile_attribution_audit.py`
- `zangetsu/config/`（含 `zangetsu_settings.py` 等所有 config 檔）
- `zangetsu/engine/`
- `zangetsu/live/`
- `scripts/governance/diff_snapshots.py`

## 6. CODE_FROZEN runtime SHA preservation

以下 6 個 runtime SHA 一律 zero-diff（本 PR 沒有修改任何 CODE_FROZEN
runtime 檔案）：

| Field | Pre | Post | Diff |
| --- | --- | --- | --- |
| `config.zangetsu_settings_sha` | `<frozen>` | `<frozen>` | 0 |
| `config.arena_pipeline_sha` | `<frozen>` | `<frozen>` | 0 |
| `config.arena23_orchestrator_sha` | `<frozen>` | `<frozen>` | 0 |
| `config.arena45_orchestrator_sha` | `<frozen>` | `<frozen>` | 0 |
| `config.calcifer_supervisor_sha` | `<frozen>` | `<frozen>` | 0 |
| `config.zangetsu_outcome_sha` | `<frozen>` | `<frozen>` | 0 |

`sparse_canary_observer.py` 為新檔且不在 CODE_FROZEN 清單；
`sparse_canary_readiness_check.py` 為新檔且不在 CODE_FROZEN 清單。
SHA tracker 不會將其新增標記為 runtime SHA change。

## 7. Hard-forbidden 守恆

`HARD_FORBIDDEN_NONZERO`：

- `runtime.arena_processes.count` 仍 0
- `runtime.engine_jsonl_mtime_iso` 仍 static
- `runtime.engine_jsonl_size_bytes` 仍 static

本 PR 不啟動 service / 不觸發 Arena loop / 不寫 `engine.jsonl` / 不觸
碰 sparse-candidate live 路徑 / 不啟動 systemd unit / 不開啟 Docker
container / 不發 Telegram alert 至 production chat。observer 為 dry-
run-CANARY only — 觀察輸入為 read-only allocator output + consumer
plan + Arena telemetry，輸出為 evidence record（diagnostic only）。

## 8. Branch protection

本 PR 不修改 governance config / branch protection rules / CI workflow
／signed-PR-only flow。`enforce_admins=true` / `required_signatures=true`
／`linear_history=true` / `allow_force_pushes=false` /
`allow_deletions=false` 全部維持。

## 9. 簽章

簽名 commit 用 ED25519 SSH key
`SHA256:vzKybH9THchzB17tZOfkJZPRI/WGkTcXxd/+a7NciC8`（與 0-9P /
0-9P-AUDIT / 0-9O-B / 0-9R-IMPL-DRY / 0-9S-READY 同一把私鑰）。
GitHub-side `verified=true` 由 GitHub squash merge 階段以 GitHub 自身
PGP key 重新簽署 merge commit 完成。

## 10. Diff exit code 預期

```
exit code 0  ⇐ ZERO / EXPLAINED
```

`diff_snapshots.py` 應回傳 exit 0：唯一 EXPLAINED diff 為
`repo.git_status_porcelain_lines`（branch 切換造成的 working tree 行數
變化），無 forbidden 欄位、無 trace-only 欄位、6 個 CODE_FROZEN SHA
皆 zero-diff、3 個 hard-forbidden runtime 欄位皆 zero-diff。

## 11. No `--authorize-trace-only` flag needed

本 PR 不需傳遞 `--authorize-trace-only` flag。原因：

1. 無任何 CODE_FROZEN runtime SHA 變動 → 不會進入 trace-only 路徑
2. 兩個 allow-list 修改的檔案均為測試檔（`zangetsu/tests/*`），不在
   CODE_FROZEN tracker 集合
3. 新增 modules（`sparse_canary_observer.py` /
   `sparse_canary_readiness_check.py`）為新檔，tracker 對「新增非
   CODE_FROZEN module」的分類為 EXPLAINED（檔案存在 + git 可追溯）
4. tests / evidence docs 屬 EXPLAINED 範疇（per order §16）

如未來合併後 controlled-diff 報告 trace-only field non-zero — 表示有
非預期路徑。應 STOP 並回報具體欄位 + 原因，不可 bypass。

## 12. Local Mac 限制

`capture_snapshot.sh` 使用 `pgrep` / `systemctl` / `stat`（Linux 專用），
需 Alaya runtime。Local Mac 端僅做 source 靜態 review；實際 controlled-
diff 由 Gate-A / Gate-B 在 Alaya 端執行，並產出 `docs/governance/
snapshots/<pre|post>-0-9s-canary-*.json` 兩份 snapshot 作為合併前最終
證據。本 PR 提交時 evidence path 為 placeholder（`<pre>` / `<post>`），
合併後 CI 將自動填入實際 snapshot 檔名。
