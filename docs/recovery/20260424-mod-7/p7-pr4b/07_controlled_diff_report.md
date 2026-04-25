# P7-PR4B — Controlled-Diff Report (Expected)

## 1. Snapshot capture（在 Alaya 執行）

```
ssh j13@100.123.49.102 \
  '/home/j13/j13-ops/scripts/governance/capture_snapshot.sh \
       pre-p7-pr4b j13@alaya'
ssh j13@100.123.49.102 \
  'cd /home/j13/j13-ops && \
   git fetch origin phase-7/p7-pr4b-a2-a3-arena-batch-metrics && \
   git checkout origin/phase-7/p7-pr4b-a2-a3-arena-batch-metrics'
ssh j13@100.123.49.102 \
  '/home/j13/j13-ops/scripts/governance/capture_snapshot.sh \
       post-p7-pr4b j13@alaya'
```

```
ssh j13@100.123.49.102 \
  'python3 /home/j13/j13-ops/scripts/governance/diff_snapshots.py \
       /home/j13/j13-ops/docs/governance/snapshots/<pre>.json \
       /home/j13/j13-ops/docs/governance/snapshots/<post>.json \
       --purpose p7-pr4b \
       --authorize-trace-only config.arena23_orchestrator_sha'
```

## 2. Expected classification

```
Classification: EXPLAINED_TRACE_ONLY

Zero diff:                      ~42 fields
Explained diff:                 1 field   — repo.git_status_porcelain_lines
Explained TRACE_ONLY diff:      1 field   — config.arena23_orchestrator_sha
Forbidden diff:                 0 fields
```

## 3. Authorized runtime SHA change

| Field | Reason | Authorization |
| --- | --- | --- |
| `config.arena23_orchestrator_sha` | A2 / A3 aggregate batch telemetry wiring（trace-only / non-blocking / additive helpers + `_p7pr4b_*` 變數 + log capture wrapper + accumulator state inside `main()`） | `--authorize-trace-only config.arena23_orchestrator_sha` per 0-9M `EXPLAINED_TRACE_ONLY` pathway |

## 4. Untouched CODE_FROZEN SHAs

以下 SHA 一律 zero-diff：

- `config.zangetsu_settings_sha` — thresholds 不可 trace-only
  authorize（`NEVER_TRACE_ONLY_AUTHORIZABLE` 防禦）
- `config.arena_pipeline_sha`
- `config.arena45_orchestrator_sha`
- `config.calcifer_supervisor_sha`
- `config.zangetsu_outcome_sha`

## 5. Hard-forbidden 守恆

`HARD_FORBIDDEN_NONZERO`：

- `runtime.arena_processes.count` 仍 0（freeze）
- `runtime.engine_jsonl_mtime_iso` 仍 static
- `runtime.engine_jsonl_size_bytes` 仍 static

P7-PR4B 不啟動 service / 不觸發 GP loop，因此 engine.jsonl 不增長。

## 6. Branch protection

`enforce_admins=true`、`required_signatures=true`、
`linear_history=true`、`allow_force_pushes=false`、
`allow_deletions=false` 全部維持。本 PR 不修改 governance config。

## 7. 簽章

簽名 commit 用 ED25519 key
`SHA256:jOIkKEJ3FntF2SIZyThPGVgZdd+sMxeii6Vjsj90+jk`（與 0-9O-A
PR #17 相同）。GitHub-side `verified=true` 將於 PR open 後由 GitHub
驗證；merge commit 預期 `verified=true`。

## 8. Diff exit code 預期

```
exit code 0  ⇐ ZERO / EXPLAINED / EXPLAINED_TRACE_ONLY
```

## 9. Local Mac 限制

`capture_snapshot.sh` 使用 `pgrep`、`systemctl`、`stat`，需 Linux/Alaya
runtime 才能跑。Local Mac 端僅完成靜態 source code review；實際
controlled-diff 由 Gate-A / Gate-B 在 Alaya 端執行。
