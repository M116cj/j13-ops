# Controlled-Diff Report

- **Pre snapshot**: `/home/j13/j13-ops/docs/governance/snapshots/2026-04-24T014039Z-rollback-rehearsal-pre-claude_mod6.json`
  - sha256_manifest: `cc909a90d66f72aed203d603e3da1e99ed8c2fd272906d4688a23db9443b4740`
- **Post snapshot**: `/home/j13/j13-ops/docs/governance/snapshots/2026-04-24T014343Z-rollback-rehearsal-post-claude_mod6.json`
  - sha256_manifest: `9f38461c64ede7aec0d804b46b05b20cd518cafb07ef588e4e6e4673f4fe7fe1`
- **Manifest match**: False

## Classification: **EXPLAINED**

- Zero diff: 39 fields
- Explained diff: 5 fields
- Forbidden diff: 0 fields

## Explained diffs

- `config.calcifer_deploy_block_file_sha`: `4bb727861bbcbdfb63da4efab99cd1185a84519bf8d843136cfcdbabdf95e33f` → `20b8be2de57bdedc51fc4c5f4b535519dc03c022c04550129d644126a99a41d5`
- `config.calcifer_state_file_sha`: `4bb727861bbcbdfb63da4efab99cd1185a84519bf8d843136cfcdbabdf95e33f` → `20b8be2de57bdedc51fc4c5f4b535519dc03c022c04550129d644126a99a41d5`
- `runtime.calcifer_deploy_block_ts_iso`: `2026-04-24T01:35:41.643872+00:00` → `2026-04-24T01:42:44.406683+00:00`
- `runtime.systemd_units.calcifer-supervisor.active_since`: `Thu 2026-04-23 06:19:51 UTC` → `Fri 2026-04-24 01:42:40 UTC`
- `runtime.systemd_units.calcifer-supervisor.main_pid`: `3871492` → `1960230`

✅ EXPLAINED — all changes trace to allowed catalog entries.

