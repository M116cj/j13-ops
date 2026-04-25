# 0-9R-IMPL-DRY — Controlled-Diff Report (Expected)

PR-C of stack `0-9P/R-STACK-v2`（在 `0-9P` 合併於 `a8a8ba9`、
`0-9P-AUDIT` 合併於 `3219b805` 之後）。本 PR 交付
`zangetsu/services/feedback_budget_consumer.py` —— sparse-candidate
dry-run consumer。**本 PR 不修改任何 CODE_FROZEN runtime SHA 檔案**。

## 1. Snapshot capture（在 Alaya 執行）

```
ssh j13@100.123.49.102 \
  '/home/j13/j13-ops/scripts/governance/capture_snapshot.sh \
       pre-0-9r-impl-dry j13@alaya'
ssh j13@100.123.49.102 \
  'cd /home/j13/j13-ops && \
   git fetch origin phase-7/0-9r-impl-dry-feedback-budget-consumer && \
   git checkout origin/phase-7/0-9r-impl-dry-feedback-budget-consumer'
ssh j13@100.123.49.102 \
  '/home/j13/j13-ops/scripts/governance/capture_snapshot.sh \
       post-0-9r-impl-dry j13@alaya'
ssh j13@100.123.49.102 \
  'python3 /home/j13/j13-ops/scripts/governance/diff_snapshots.py \
       /home/j13/j13-ops/docs/governance/snapshots/<pre>.json \
       /home/j13/j13-ops/docs/governance/snapshots/<post>.json \
       --purpose 0-9r-impl-dry'
```

**關鍵：本 PR 不需 `--authorize-trace-only` flag**。原因見下節 —
無任何 runtime SHA 變動，僅 `repo.git_status_porcelain_lines` 為
EXPLAINED diff。

## 2. Expected classification

```
Classification: EXPLAINED  (NOT EXPLAINED_TRACE_ONLY — no runtime SHA changed)

Zero diff:                    ~43 fields  (incl. all 6 CODE_FROZEN runtime SHAs)
Explained diff:               1 field    — repo.git_status_porcelain_lines
Explained TRACE_ONLY diff:    0 fields
Forbidden diff:               0 fields
```

## 3. Files added / modified（皆 non-CODE_FROZEN）

| Category | Path | Notes |
|----------|------|-------|
| New consumer module | `zangetsu/services/feedback_budget_consumer.py` | 新檔，未列入 CODE_FROZEN SHA tracker |
| New test suite | `zangetsu/tests/test_feedback_budget_consumer.py` | 81 tests（dry-run，無副作用）|
| Evidence docs | `docs/recovery/20260424-mod-7/0-9r-impl-dry/01..09*.md` | 9 份 PR-C evidence |
| Allow-list 微調 | 2 existing test files | legitimate downstream，僅放行 consumer module import |

## 4. Files NOT modified

以下檔案 **完全 zero-diff**（本 PR 為 dry-run consumer，不觸動 runtime
／engine／live／config）：

- `zangetsu/services/arena_pipeline.py`
- `zangetsu/services/arena23_orchestrator.py`
- `zangetsu/services/arena45_orchestrator.py`
- `zangetsu/services/arena_gates.py`
- `zangetsu/services/arena_pass_rate_telemetry.py`
- `zangetsu/services/arena_rejection_taxonomy.py`
- `zangetsu/services/feedback_budget_allocator.py`（PR-B 之 producer，本 PR 為其 consumer，僅 import）
- `zangetsu/services/feedback_decision_record.py`
- `zangetsu/services/generation_profile_metrics.py`
- `zangetsu/services/generation_profile_identity.py`
- `zangetsu/services/calcifer_supervisor.py`
- `zangetsu/services/zangetsu_outcome.py`
- `zangetsu/tools/profile_attribution_audit.py`（PR-AUDIT 交付物）
- `zangetsu/config/`（含 `zangetsu_settings.py` 等所有 config 檔）
- `zangetsu/engine/`
- `zangetsu/live/`

## 5. CODE_FROZEN SHA preservation

以下 6 個 runtime SHA 一律 zero-diff（本 PR 沒有修改任何 CODE_FROZEN
runtime 檔案）：

| Field | Pre | Post | Diff |
|-------|-----|------|------|
| `config.zangetsu_settings_sha` | `<frozen>` | `<frozen>` | 0 |
| `config.arena_pipeline_sha` | `<frozen>` | `<frozen>` | 0 |
| `config.arena23_orchestrator_sha` | `<frozen>` | `<frozen>` | 0 |
| `config.arena45_orchestrator_sha` | `<frozen>` | `<frozen>` | 0 |
| `config.calcifer_supervisor_sha` | `<frozen>` | `<frozen>` | 0 |
| `config.zangetsu_outcome_sha` | `<frozen>` | `<frozen>` | 0 |

`feedback_budget_consumer.py` 為新檔且不在 CODE_FROZEN 清單，因此
SHA tracker 不會將其新增標記為 runtime SHA change。

## 6. Hard-forbidden 守恆

`HARD_FORBIDDEN_NONZERO`：

- `runtime.arena_processes.count` 仍 0
- `runtime.engine_jsonl_mtime_iso` 仍 static
- `runtime.engine_jsonl_size_bytes` 仍 static

本 PR 不啟動 service / 不觸發 Arena loop / 不寫 `engine.jsonl` /
不觸碰 sparse-candidate live 路徑。consumer 為 dry-run only。

## 7. Branch protection

`enforce_admins=true` / `required_signatures=true` / `linear_history=true`
/ `allow_force_pushes=false` / `allow_deletions=false` 全部維持。
本 PR 不修改 governance config / branch protection rules / CI workflow。

## 8. 簽章

簽名 commit 用 ED25519 SSH key
`SHA256:vzKybH9THchzB17tZOfkJZPRI/WGkTcXxd/+a7NciC8`（與 0-9P /
0-9P-AUDIT / 0-9O-B 同一把私鑰）。GitHub-side `verified=true` 由
GitHub squash merge 階段以 GitHub 自身 PGP key 重新簽署 merge commit
完成。

## 9. Diff exit code 預期

```
exit code 0  ⇐ ZERO / EXPLAINED
```

`diff_snapshots.py` 應回傳 exit 0：唯一 EXPLAINED diff 為
`repo.git_status_porcelain_lines`（branch 切換造成的 working tree 行數
變化），無 forbidden 欄位、無 trace-only 欄位、6 個 CODE_FROZEN SHA
皆 zero-diff。

## 10. Local Mac 限制

`capture_snapshot.sh` 使用 `pgrep` / `systemctl` / `stat`，需
Linux/Alaya runtime。Local Mac 端僅做 source 靜態 review；實際
controlled-diff 由 Gate-A / Gate-B 在 Alaya 端執行，並產出
`docs/governance/snapshots/<pre|post>-0-9r-impl-dry-*.json` 兩份
snapshot 作為 PR-C 合併前的最終證據。
