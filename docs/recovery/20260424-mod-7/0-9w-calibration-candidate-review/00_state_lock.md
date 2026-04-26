# 00 — State Lock (0-9W-CALIBRATION-CANDIDATE-REVIEW)

| Field | Value |
| --- | --- |
| Timestamp (UTC) | 2026-04-26T16:30:45Z |
| Host | j13@100.123.49.102 |
| Repo | /home/j13/j13-ops |
| Branch | main |
| HEAD | `6aba9efba0e0917ac1f3942a416cbb20eca3fed4` |
| origin/main | matches |

## Precondition Checks

| Check | Result |
| --- | --- |
| Alaya access | OK |
| Repo path | `/home/j13/j13-ops` (confirmed) |
| Branch is main | YES |
| PR #40 merged into main | YES (squash commit `6aba9ef`) |
| Mac + Alaya main synced | YES (both at `6aba9ef`) |
| Prior evidence dir exists | YES — `docs/recovery/20260424-mod-7/0-9w-cost-threshold-horizon-calibration-diagnosis/` (19 files) |
| No CANARY process | NONE (`ps aux | grep canary` returns 0) |
| No production rollout active | NONE |
| No runtime config changes since PR #40 | confirmed (`git log` shows merge as latest commit) |

## Working Tree

Three modified files in tracked tree:
- `calcifer/maintenance.log`
- `calcifer/maintenance_last.json`
- `zangetsu/logs/engine.jsonl.1`

These are **runtime artifacts continuously written by live services** (calcifer maintenance loop, zangetsu engine logger). They are not user-staged changes and have been observed across all prior governance orders. Excluded from staging during this investigation.

## Service State

| Service | State |
| --- | --- |
| 6 arena/champion processes | ALIVE (4 A1 + A23 + A45) |
| engine.jsonl writer | WRITING |
| HTTP APIs | UNTOUCHED |
| CANARY | NOT STARTED |
| production rollout | NOT STARTED |
| DB write planned | NO |

→ **Phase 0 PASS.** Preconditions satisfied. PR #40 merged. Prior evidence intact. No runtime changes. Investigation can proceed.
