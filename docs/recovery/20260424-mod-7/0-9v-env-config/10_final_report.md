# 0-9V-ENV-CONFIG — Alaya Runtime Environment Configuration Repair Final Report

## 1. Status

**COMPLETE_ENV_REPAIRED.**

Watchdog-launched A1 workers no longer crash on `KeyError: ZV5_DB_PASSWORD`. `engine.jsonl` has cleared three days of staleness and is actively writing. Runtime safety unchanged. No secret value printed, committed, or written to docs.

## 2. Alaya

| Field | Value |
| --- | --- |
| Host | `j13@100.123.49.102` (Tailscale) |
| Repo | `/home/j13/j13-ops` |
| SSH access | PASS |

## 3. Baseline

| Field | Value |
| --- | --- |
| HEAD | `6fdb4c93e4a61c712e564b950dafde2039ec3dc6` (PR #30 squash) |
| origin/main | matches |
| Dirty state (pre-order) | clean |
| Previous blocker | `KeyError: ZV5_DB_PASSWORD` from commit `fe1c0bc0` (2026-04-20 security purge), broke arena pipeline since 2026-04-23 |

Detail: `01_preflight_state.md`.

## 4. Launcher inventory

| Field | Value |
| --- | --- |
| Cron line | `*/5 * * * * ~/j13-ops/zangetsu/watchdog.sh >> /tmp/zangetsu_watchdog.log 2>&1` |
| Watchdog | `/home/j13/j13-ops/zangetsu/watchdog.sh` (tracked in repo) |
| Worker (A1) | `python3 zangetsu/services/arena_pipeline.py` × 4 (`w0..w3`) |
| Worker (A2/A3) | `arena23_orchestrator.py` (NOT currently launched — no lockfile; separate launcher question, out of scope) |
| Worker (A4/A5) | `arena45_orchestrator.py` (same) |
| Working directory | `/home/j13/j13-ops/zangetsu` |
| Python / venv | `/home/j13/j13-ops/zangetsu/.venv/bin/python3` (3.12.3) |
| Logs | `/tmp/zangetsu_a1_w0..w3.log`, `/tmp/zangetsu_watchdog.log`, `zangetsu/logs/engine.jsonl` |

Detail: `02_launcher_inventory.md`.

## 5. Root cause confirmation

| Field | Value |
| --- | --- |
| `ZV5_DB_PASSWORD` missing from cron worker env | YES (confirmed in pre-repair worker logs) |
| `KeyError` recurrence in pre-repair logs | YES (every cron cycle since 2026-04-23) |
| Secret printed during root-cause check | NO |

Detail: `02_launcher_inventory.md` §7-8.

## 6. Env source

| Field | Value |
| --- | --- |
| Method | `~/.env.global` preamble loaded by `watchdog.sh` (Option A per order §9) |
| File | `/home/j13/.env.global` |
| Permission | `600` (re-asserted via `chmod 600`) |
| Owner | `j13:j13` |
| Tracked / committed | NO |
| Secret value committed | NO |
| Secret value printed | NO |
| Backup | `/home/j13/.env.global.bak.0-9v-env-config` (created via `cp -a` before append) |

Source line was appended via silent redirect from `zangetsu/secret/.env` (the existing authoritative source for the running HTTP APIs). No new secret value introduced — the same string is now visible to the cron-spawned workers via the preamble.

Detail: `03_env_source_plan.md`, `04_env_injection_change_report.md`.

## 7. Env injection change

| Field | Value |
| --- | --- |
| `watchdog.sh` preamble | added (8 lines, immediately after `#!/bin/bash`) |
| Tracked file changed | `zangetsu/watchdog.sh` (+8 / -0) |
| Bash syntax check | PASS |
| Strategy / threshold / Arena logic touched | NO |
| Diff classification | EXPLAINED (env-loading only) |

Detail: `04_env_injection_change_report.md` §2.

## 8. Worker restart

| Field | Value |
| --- | --- |
| Method | manual one-shot `bash zangetsu/watchdog.sh` (the watchdog is the documented launcher; cron will continue running the patched script every 5 min) |
| Old PIDs | `94122` / `94147` / `94156` / `94165` (pre-repair, all crashed on `KeyError`) |
| New PIDs | `103233` / `103242` / `103251` / `103260` (post-repair, all alive ≥ 58 s, 99% CPU) |
| Worker alive after 45 s | YES (4 / 4 A1 workers) |
| `KeyError` recurrence on new PIDs | NO |
| HTTP APIs touched | NO (`cp-api` 2537810, `dashboard-api` 3871446, `console-api` 3871449 unchanged) |

Detail: `05_worker_restart_report.md`.

## 9. Runtime health

| Field | Value |
| --- | --- |
| `engine.jsonl` last write (pre) | `2026-04-23T00:35:54Z` |
| `engine.jsonl` last write (post) | `2026-04-26T09:04:52Z` |
| Engine loop | ALIVE (3-day staleness cleared, regime classifications writing) |
| Worker status | 4 / 4 A1 workers alive at 99% CPU |
| Result | **PASS** per order §14 health criteria |

Detail: `06_runtime_health_check.md`.

## 10. Telemetry emission

| File | Status |
| --- | --- |
| `engine.jsonl` | WRITING (advancing) |
| `arena_batch_metrics.jsonl` | MISSING (requires A23 orchestrator; A23 not currently launched — separate launcher scope) |
| `sparse_candidate_dry_run_plans.jsonl` | MISSING (offline by design — PR #23 dry-run consumer) |
| Telemetry status (per order §15) | `ENGINE_RECOVERED_WAITING_FOR_ARENA_BATCH` |

Detail: `07_telemetry_emission_check.md`.

## 11. Security audit

| Field | Value |
| --- | --- |
| Secret value in evidence docs | NO (every `ZV5_DB_PASSWORD=` in docs is followed by a status string, a quote, or an end-of-line in a command example) |
| Secret value in tracked git files | NO (only `*.env.example` template files are tracked) |
| `~/.env.global` committed | NO |
| `zangetsu/secret/.env` committed | NO (gitignored via `**/secret/`) |
| Env file permissions | `600` |
| Result | PASS |

Detail: `08_security_and_secret_audit.md`.

## 12. Runtime safety

| Field | Value |
| --- | --- |
| Apply path | NONE |
| Runtime-switchable APPLY | NONE |
| Consumer connected to generation runtime | NO (only the offline observer reads it, read-only) |
| `A2_MIN_TRADES` | 25 |
| CANARY | NOT STARTED |
| Production rollout | NOT STARTED |

Detail: `06_runtime_health_check.md` §6.

## 13. Controlled-diff

| Field | Value |
| --- | --- |
| Classification | EXPLAINED (env-loading preamble + docs-only) |
| Forbidden | 0 |
| CODE_FROZEN runtime SHA | zero-diff for all 6 (settings / arena_pipeline / arena23_orchestrator / arena45_orchestrator / calcifer_supervisor / zangetsu_outcome) |

Detail: `09_controlled_diff_report.md`.

## 14. Gate-A / Gate-B

Expected: **PASS / PASS**. Will run on PR open. The `watchdog.sh` change is a launcher-script env-loading preamble outside the CODE_FROZEN runtime SHA list and outside any strategy module, so Gate-B should classify it as a non-strategic launcher patch.

## 15. Branch protection

Expected unchanged on `main`:

- `enforce_admins=true`
- `required_signatures=true`
- `linear_history=true`
- `allow_force_pushes=false`
- `allow_deletions=false`

This PR does not modify governance configuration.

## 16. Forbidden changes audit

| Item | Status |
| --- | --- |
| alpha generation | UNCHANGED |
| formula generation | UNCHANGED |
| mutation / crossover | UNCHANGED |
| search policy | UNCHANGED |
| generation budget | UNCHANGED |
| sampling weights | UNCHANGED |
| thresholds | UNCHANGED |
| `A2_MIN_TRADES` | PINNED at 25 |
| Arena pass / fail | UNCHANGED |
| champion promotion | UNCHANGED |
| `deployable_count` semantics | UNCHANGED |
| execution / capital / risk | UNCHANGED |
| CANARY | NOT STARTED |
| production rollout | NOT STARTED |

## 17. Recommended next action

### A. Bring A2/A3 + A4/A5 orchestrators back online

`arena_batch_metrics.jsonl` will not appear until `arena23_orchestrator.py` is being launched. The watchdog manages it via lockfile, but no lockfile exists. Two viable paths:

- **Path A — manual lockfile bootstrap**: `touch /tmp/zangetsu/arena23_orchestrator.lock` (with a stale PID inside) so the next watchdog cycle detects it as DEAD and respawns. Lowest blast radius.
- **Path B — add an explicit cron line**: a separate cron entry that supervises A23 / A45. Requires more careful systemd / cron design.

This is a separate launcher-orchestration order (e.g. **0-9V-A23-A45-LAUNCHER**), not env-config.

### B. After arena_batch_metrics begins writing

- Re-run **TEAM ORDER 0-9V-REPLACE-RESUME** Phase G verification (G12 / G13 will upgrade from PASS-with-note to clean PASS once telemetry exists).
- Then run **TEAM ORDER 0-9S-CANARY-OBSERVE-LIVE** for the real CANARY verdict against ≥ 20 live arena batches.

## 18. Final declaration

```
TEAM ORDER 0-9V-ENV-CONFIG = COMPLETE_ENV_REPAIRED
```

Cron-launched A1 workers can now reach the engine loop. Engine.jsonl is advancing. Runtime safety unchanged. No secret printed, committed, or documented. HTTP APIs preserved. Watchdog cron line untouched (the script it points to gained an 8-line env-loading preamble; cron schedule unchanged). Branch protection intact. Signed PR-only flow preserved. No CANARY. No production rollout.
