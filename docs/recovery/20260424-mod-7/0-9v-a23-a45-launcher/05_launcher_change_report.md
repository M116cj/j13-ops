# 05 — Launcher Change Report

## 1. Outcome Selected

**Outcome A — no source change needed; existing watchdog launcher logic is sufficient once a placeholder lockfile bootstraps the watchdog loop.**

## 2. Files Changed in This PR

| Path | Class | Change |
| --- | --- | --- |
| `docs/recovery/20260424-mod-7/0-9v-a23-a45-launcher/01_preflight_state.md` | evidence | new |
| `docs/recovery/20260424-mod-7/0-9v-a23-a45-launcher/02_launcher_inventory.md` | evidence | new |
| `docs/recovery/20260424-mod-7/0-9v-a23-a45-launcher/03_env_and_secret_safety.md` | evidence | new |
| `docs/recovery/20260424-mod-7/0-9v-a23-a45-launcher/04_a23_a45_launcher_plan.md` | evidence | new |
| `docs/recovery/20260424-mod-7/0-9v-a23-a45-launcher/05_launcher_change_report.md` | evidence | new (this doc) |
| `docs/recovery/20260424-mod-7/0-9v-a23-a45-launcher/06_process_start_report.md` | evidence | new |
| `docs/recovery/20260424-mod-7/0-9v-a23-a45-launcher/07_runtime_health_check.md` | evidence | new |
| `docs/recovery/20260424-mod-7/0-9v-a23-a45-launcher/08_telemetry_emission_check.md` | evidence | new |
| `docs/recovery/20260424-mod-7/0-9v-a23-a45-launcher/09_runtime_safety_audit.md` | evidence | new |
| `docs/recovery/20260424-mod-7/0-9v-a23-a45-launcher/10_controlled_diff_report.md` | evidence | new |
| `docs/recovery/20260424-mod-7/0-9v-a23-a45-launcher/11_final_report.md` | evidence | new |
| `zangetsu/services/arena23_orchestrator.py` | runtime | UNCHANGED |
| `zangetsu/services/arena45_orchestrator.py` | runtime | UNCHANGED |
| `zangetsu/services/arena_gates.py` | runtime | UNCHANGED |
| `zangetsu/services/arena_pipeline.py` | runtime | UNCHANGED |
| `zangetsu/config/settings.py` | runtime | UNCHANGED |
| `zangetsu/watchdog.sh` | launcher | UNCHANGED in this order (already had A23/A45 cases + env preamble from PR #31) |
| Cron config | scheduler | UNCHANGED |
| `~/.env.global` | secret env | UNCHANGED in this order (set in PR #31; same content reused) |

## 3. Reason for Smallest-Change Outcome

The watchdog already has all three required pieces:

1. The `for lock in $LOCK_DIR/*.lock` loop iterates discovered services.
2. The `restart_service "arena23_orchestrator"` / `restart_service "arena45_orchestrator"` case branches construct the correct launch commands.
3. The env-loading preamble (PR #31) exports `ZV5_DB_PASSWORD` to all spawned children.

The only missing step is the **first lockfile** that triggers iteration. A bootstrap `: > /tmp/zangetsu/arenaXX_orchestrator.lock` (touch with empty contents) is a transient filesystem operation outside the repo. Within the watchdog's first relevant cycle the empty file is replaced by an `acquire_lock`-managed lockfile holding the orchestrator's real PID.

## 4. Diff Summary

| Diff scope | Bytes |
| --- | --- |
| Tracked source files | **0** changed |
| Tracked launcher / shell files | **0** changed |
| Tracked governance files | **0** changed |
| Tracked tests | **0** changed |
| New tracked evidence docs | 11 files (~1100 LOC; this file alone is ~80 LOC) |
| Filesystem outside repo | 2 transient empty lockfiles (`/tmp/zangetsu/arena{23,45}_orchestrator.lock`, replaced by `acquire_lock` within seconds) |

## 5. Strategy / Threshold Audit

| Item | Diff |
| --- | --- |
| Strategy logic | UNCHANGED |
| Thresholds | UNCHANGED |
| `A2_MIN_TRADES` | 25 (UNCHANGED) |
| Arena pass/fail | UNCHANGED |
| Champion promotion | UNCHANGED |
| `deployable_count` semantics | UNCHANGED |
| Execution / capital / risk | UNCHANGED |
| CANARY | NOT STARTED |
| Production rollout | NOT STARTED |
| Secret committed | NO |

## 6. Phase E Verdict

→ **PASS.** Smallest possible launcher restoration. No source code or launcher script change.
