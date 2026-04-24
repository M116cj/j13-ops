# Controlled-Diff Report

- **Pre snapshot**: `docs/governance/snapshots/2026-04-24T140738Z-pre-0-9o-a.json`
  - sha256_manifest: `738fb04544af8e2d71ca4eeca31588fa2c3a24e806dd8418c4e43de575286f48`
- **Post snapshot**: `docs/governance/snapshots/2026-04-24T141442Z-post-0-9o-a.json`
  - sha256_manifest: `35fa60e9f629cab1321fc6b5f090e96507022a27dda553e0b5a22be24fa111db`
- **Manifest match**: False

## Classification: **EXPLAINED_TRACE_ONLY**

- Zero diff: 42 fields
- Explained diff: 1 fields
- Explained TRACE_ONLY diff: 1 fields
- Forbidden diff: 0 fields

## Explained TRACE_ONLY diffs (authorized runtime SHA changes)

- `config.arena_pipeline_sha`: `30e66a9d4a14f248e7dde9d2512ec4c577b43667c22a3e08a222fc2c93cd980f` → `e37afbe048f6d4041acdf938267a3f32648fd6e5e8a5ceb134a12a33035f1e0d`

## Explained diffs

- `repo.git_status_porcelain_lines`: `1` → `7`

✅ EXPLAINED_TRACE_ONLY — authorized Phase 7 trace-only runtime SHA change(s); non-trace protections remain intact.

