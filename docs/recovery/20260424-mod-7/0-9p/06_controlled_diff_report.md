# 06 — Controlled-Diff Report (Expected)

## 1. Snapshot capture（在 Alaya 執行）

```
ssh j13@100.123.49.102 \
  '/home/j13/j13-ops/scripts/governance/capture_snapshot.sh \
       pre-0-9p j13@alaya'
ssh j13@100.123.49.102 \
  'cd /home/j13/j13-ops && \
   git fetch origin phase-7/0-9p-generation-profile-passport-persistence && \
   git checkout origin/phase-7/0-9p-generation-profile-passport-persistence'
ssh j13@100.123.49.102 \
  '/home/j13/j13-ops/scripts/governance/capture_snapshot.sh \
       post-0-9p j13@alaya'
ssh j13@100.123.49.102 \
  'python3 /home/j13/j13-ops/scripts/governance/diff_snapshots.py \
       /home/j13/j13-ops/docs/governance/snapshots/<pre>.json \
       /home/j13/j13-ops/docs/governance/snapshots/<post>.json \
       --purpose 0-9p \
       --authorize-trace-only config.arena_pipeline_sha'
```

## 2. Expected classification

```
Classification: EXPLAINED_TRACE_ONLY

Zero diff:                   ~42 fields
Explained diff:              1 field   — repo.git_status_porcelain_lines
Explained TRACE_ONLY diff:   1 field   — config.arena_pipeline_sha
Forbidden diff:              0 fields
```

## 3. Authorized runtime SHA change

| Field | Reason | Authorization |
| --- | --- | --- |
| `config.arena_pipeline_sha` | Metadata-only `passport.arena1.generation_profile_id` / `generation_profile_fingerprint` persistence + try/except guard | `--authorize-trace-only config.arena_pipeline_sha` per 0-9M EXPLAINED_TRACE_ONLY pathway |

Runtime SHA change 不涉 Arena 決策、threshold、champion promotion、
deployable_count semantics — 僅是 JSONB blob 內 metadata 增補與
identity 解析的 try/except 包裹。

## 4. Untouched CODE_FROZEN SHAs

- `config.zangetsu_settings_sha` — thresholds 不可 trace-only authorize
- `config.arena23_orchestrator_sha`
- `config.arena45_orchestrator_sha`
- `config.calcifer_supervisor_sha`
- `config.zangetsu_outcome_sha`

## 5. Hard-forbidden 守恆

- `runtime.arena_processes.count` 仍 0
- `runtime.engine_jsonl_mtime_iso` 仍 static
- `runtime.engine_jsonl_size_bytes` 仍 static

本 PR 不啟動 service / 不觸發 GP loop / 不寫 engine.jsonl。

## 6. Branch protection

`enforce_admins=true` / `required_signatures=true` / `linear_history=true`
/ `allow_force_pushes=false` / `allow_deletions=false` 全部維持。

## 7. 簽章

ED25519 SSH `SHA256:vzKybH9THchzB17tZOfkJZPRI/WGkTcXxd/+a7NciC8`。
GitHub-side `verified=true` 由 GitHub squash merge 階段以 GitHub 自身
PGP key 重新簽署 merge commit 完成。

## 8. Diff exit code 預期

```
exit code 0  ⇐ ZERO / EXPLAINED / EXPLAINED_TRACE_ONLY
```

## 9. Local Mac 限制

`capture_snapshot.sh` 用 `pgrep` / `systemctl` / `stat`，需 Linux/Alaya
runtime。本 PR 之 controlled-diff 由 Gate-A / Gate-B 在 Alaya 執行。
