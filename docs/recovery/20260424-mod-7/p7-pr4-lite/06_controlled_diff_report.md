# Controlled-Diff Report

- **Pre snapshot**: `docs/governance/snapshots/2026-04-24T131935Z-pre-p7-pr4-lite.json`
  - sha256_manifest: `67025e27ece310dd1ac0484a143d59e4d5203dff77ba1d13be458ca4ac9d5d64`
- **Post snapshot**: `docs/governance/snapshots/2026-04-24T133337Z-post-p7-pr4-lite.json`
  - sha256_manifest: `cc69952dfd8cc588fc83f411dbdd1c68ad521643f71a9fe8042793943c3d7959`
- **Manifest match**: False

## Classification: **EXPLAINED_TRACE_ONLY**

- Zero diff: 42 fields
- Explained diff: 1 fields
- Explained TRACE_ONLY diff: 1 fields
- Forbidden diff: 0 fields

## Explained TRACE_ONLY diffs (authorized runtime SHA changes)

- `config.arena_pipeline_sha`: `888e2fdd4b4af5f6f6523256462d02ba012dafa64c968663fd6d8225bc749142` → `30e66a9d4a14f248e7dde9d2512ec4c577b43667c22a3e08a222fc2c93cd980f`

## Explained diffs

- `repo.git_status_porcelain_lines`: `1` → `5`

✅ EXPLAINED_TRACE_ONLY — authorized Phase 7 trace-only runtime SHA change(s); non-trace protections remain intact.

