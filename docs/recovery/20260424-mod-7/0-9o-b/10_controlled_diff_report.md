# 0-9O-B — Controlled-Diff Report (Expected)

## 1. Snapshot capture（在 Alaya 執行）

```
ssh j13@100.123.49.102 \
  '/home/j13/j13-ops/scripts/governance/capture_snapshot.sh \
       pre-0-9o-b j13@alaya'
ssh j13@100.123.49.102 \
  'cd /home/j13/j13-ops && \
   git fetch origin phase-7/0-9o-b-dry-run-feedback-budget-allocator && \
   git checkout origin/phase-7/0-9o-b-dry-run-feedback-budget-allocator'
ssh j13@100.123.49.102 \
  '/home/j13/j13-ops/scripts/governance/capture_snapshot.sh \
       post-0-9o-b j13@alaya'
ssh j13@100.123.49.102 \
  'python3 /home/j13/j13-ops/scripts/governance/diff_snapshots.py \
       /home/j13/j13-ops/docs/governance/snapshots/<pre>.json \
       /home/j13/j13-ops/docs/governance/snapshots/<post>.json \
       --purpose 0-9o-b'
```

**關鍵：本 PR 不需 `--authorize-trace-only` flag**。原因見下節。

## 2. Expected classification

```
Classification: EXPLAINED  (NOT EXPLAINED_TRACE_ONLY — no runtime SHA changed)

Zero diff:                    ~43 fields  (incl. all CODE_FROZEN runtime SHAs)
Explained diff:               1 field    — repo.git_status_porcelain_lines
Explained TRACE_ONLY diff:    0 fields
Forbidden diff:               0 fields
```

## 3. Untouched CODE_FROZEN SHAs

以下 SHA 一律 zero-diff（本 PR 沒有修改任何 runtime 檔案）：

- `config.zangetsu_settings_sha`
- `config.arena_pipeline_sha`
- `config.arena23_orchestrator_sha`
- `config.arena45_orchestrator_sha`
- `config.calcifer_supervisor_sha`
- `config.zangetsu_outcome_sha`

只有以下 **non-CODE_FROZEN** 檔案被新增 / 改動：

- `zangetsu/services/feedback_budget_allocator.py`（新增）
- `zangetsu/tests/test_feedback_budget_allocator.py`（新增）
- `docs/recovery/20260424-mod-7/0-9o-b/01..11*.md`（新增）

allocator 模組不在 CODE_FROZEN 清單，因此 SHA tracker 不會將其變動
標記為 runtime SHA change。

## 4. Hard-forbidden 守恆

`HARD_FORBIDDEN_NONZERO`：

- `runtime.arena_processes.count` 仍 0
- `runtime.engine_jsonl_mtime_iso` 仍 static
- `runtime.engine_jsonl_size_bytes` 仍 static

本 PR 不啟動 service / 不觸發 Arena loop / 不寫 engine.jsonl。

## 5. Branch protection

`enforce_admins=true` / `required_signatures=true` / `linear_history=true`
/ `allow_force_pushes=false` / `allow_deletions=false` 全部維持。
本 PR 不修改 governance config。

## 6. 簽章

簽名 commit 用 ED25519 SSH key
`SHA256:vzKybH9THchzB17tZOfkJZPRI/WGkTcXxd/+a7NciC8`（與 P7-PR4B
PR #18 相同）。GitHub-side `verified=true` 由 GitHub squash merge
階段以 GitHub 自身 PGP key 重新簽署 merge commit 完成。

## 7. Diff exit code 預期

```
exit code 0  ⇐ ZERO / EXPLAINED
```

## 8. Local Mac 限制

`capture_snapshot.sh` 使用 `pgrep` / `systemctl` / `stat`，需
Linux/Alaya runtime。Local Mac 端僅做 source 靜態 review；實際
controlled-diff 由 Gate-A / Gate-B 在 Alaya 端執行。
