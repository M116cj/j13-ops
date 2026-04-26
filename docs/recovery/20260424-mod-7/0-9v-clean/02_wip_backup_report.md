# 02 — WIP Backup Report

## 1. Backup Directory

| Field | Value |
| --- | --- |
| Backup path | `/home/j13/alaya-wip-backup-0-9v-clean-20260426T060553Z` |
| Backup timestamp (UTC) | `2026-04-26T06:05:53Z` |
| Total size | 200 KB |
| Mac repo copied | NO |
| Logs copied | NO (Calcifer logs treated as runtime state — backed up only the 3 expected blocker files; nothing under `zangetsu/logs/`) |
| `.env` / secrets copied | NO (no top-level `.env*` exists; backup operation enumerated explicit file list only) |

## 2. Files Backed Up

### Untracked (3)

| Source | Backup |
| --- | --- |
| `zangetsu/tests/test_a2_a3_arena_batch_metrics.py` | `<backup>/zangetsu/tests/test_a2_a3_arena_batch_metrics.py` |
| `docs/governance/snapshots/2026-04-24T221219Z-pre-p7-pr4b.json` | `<backup>/docs/governance/snapshots/2026-04-24T221219Z-pre-p7-pr4b.json` |
| `calcifer/deploy_block_state.json` | `<backup>/calcifer/deploy_block_state.json` |

### Modified tracked (6)

| Source | Backup |
| --- | --- |
| `zangetsu/services/arena23_orchestrator.py` | `<backup>/zangetsu/services/arena23_orchestrator.py` |
| `zangetsu/services/arena_pass_rate_telemetry.py` | `<backup>/zangetsu/services/arena_pass_rate_telemetry.py` |
| `zangetsu/services/generation_profile_metrics.py` | `<backup>/zangetsu/services/generation_profile_metrics.py` |
| `calcifer/maintenance.log` | `<backup>/calcifer/maintenance.log` |
| `calcifer/maintenance_last.json` | `<backup>/calcifer/maintenance_last.json` |
| `calcifer/report_state.json` | `<backup>/calcifer/report_state.json` |

Total: **9 files** (3 untracked + 6 modified-tracked).

## 3. Manifest

See `backed_up_files_manifest.txt` in this directory.

```
/home/j13/alaya-wip-backup-0-9v-clean-20260426T060553Z/calcifer/deploy_block_state.json
/home/j13/alaya-wip-backup-0-9v-clean-20260426T060553Z/calcifer/maintenance.log
/home/j13/alaya-wip-backup-0-9v-clean-20260426T060553Z/calcifer/maintenance_last.json
/home/j13/alaya-wip-backup-0-9v-clean-20260426T060553Z/calcifer/report_state.json
/home/j13/alaya-wip-backup-0-9v-clean-20260426T060553Z/docs/governance/snapshots/2026-04-24T221219Z-pre-p7-pr4b.json
/home/j13/alaya-wip-backup-0-9v-clean-20260426T060553Z/zangetsu/services/arena23_orchestrator.py
/home/j13/alaya-wip-backup-0-9v-clean-20260426T060553Z/zangetsu/services/arena_pass_rate_telemetry.py
/home/j13/alaya-wip-backup-0-9v-clean-20260426T060553Z/zangetsu/services/generation_profile_metrics.py
/home/j13/alaya-wip-backup-0-9v-clean-20260426T060553Z/zangetsu/tests/test_a2_a3_arena_batch_metrics.py
```

## 4. What Was NOT Touched

| Path | Status |
| --- | --- |
| `zangetsu/logs/engine.jsonl` (38 MB) | NOT copied, NOT moved |
| `zangetsu/logs/engine.jsonl.1` (2.5 MB) | NOT copied, NOT moved |
| `zangetsu/data/funding/` | NOT touched |
| `zangetsu/data/ohlcv/` | NOT touched |
| `.env*` / `secret/` | not present (as before) |
| Anything outside the explicit 9-file list | NOT touched |

## 5. Confirmation

- The backup is a `cp -a` snapshot (preserves mode, ownership, timestamps).
- No file content is printed in this report.
- No secret was read or transferred.
- No log was deleted.
- Backup retention: kept indefinitely on Alaya home dir until j13 explicitly removes.

→ **Phase C PASS.**
