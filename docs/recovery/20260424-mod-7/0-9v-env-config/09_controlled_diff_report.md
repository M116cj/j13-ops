# 09 — Controlled-Diff Report

## 1. Files Changed in This PR

| Path | Class | Size | Lines | Notes |
| --- | --- | --- | --- | --- |
| `zangetsu/watchdog.sh` | tracked shell launcher | +8 / -0 | preamble only | env-loading only; no strategy / threshold / Arena pass-fail / budget / weight / sampling change |
| `docs/recovery/20260424-mod-7/0-9v-env-config/01_preflight_state.md` | evidence | new | 49 | docs |
| `docs/recovery/20260424-mod-7/0-9v-env-config/02_launcher_inventory.md` | evidence | new | 93 | docs |
| `docs/recovery/20260424-mod-7/0-9v-env-config/03_env_source_plan.md` | evidence | new | 66 | docs |
| `docs/recovery/20260424-mod-7/0-9v-env-config/04_env_injection_change_report.md` | evidence | new | 124 | docs |
| `docs/recovery/20260424-mod-7/0-9v-env-config/05_worker_restart_report.md` | evidence | new | 101 | docs |
| `docs/recovery/20260424-mod-7/0-9v-env-config/06_runtime_health_check.md` | evidence | new | 96 | docs |
| `docs/recovery/20260424-mod-7/0-9v-env-config/07_telemetry_emission_check.md` | evidence | new | 48 | docs |
| `docs/recovery/20260424-mod-7/0-9v-env-config/08_security_and_secret_audit.md` | evidence | new | (this doc) | docs |
| `docs/recovery/20260424-mod-7/0-9v-env-config/09_controlled_diff_report.md` | evidence | new | (this doc) | docs |
| `docs/recovery/20260424-mod-7/0-9v-env-config/10_final_report.md` | evidence | new | TBD | docs |

## 2. CODE_FROZEN Runtime SHA Audit

| Field | Status |
| --- | --- |
| `config.zangetsu_settings_sha` | zero-diff |
| `config.arena_pipeline_sha` | zero-diff |
| `config.arena23_orchestrator_sha` | zero-diff |
| `config.arena45_orchestrator_sha` | zero-diff |
| `config.calcifer_supervisor_sha` | zero-diff |
| `config.zangetsu_outcome_sha` | zero-diff |

→ All CODE_FROZEN runtime modules unchanged. The single non-doc change is `zangetsu/watchdog.sh` — a launcher script outside the CODE_FROZEN runtime SHA list.

## 3. Strategy / Behavior Audit

| Item | Diff in this PR? |
| --- | --- |
| alpha generation | NO |
| formula generation | NO |
| mutation / crossover | NO |
| search policy | NO |
| generation budget | NO |
| sampling weights | NO |
| thresholds | NO |
| `A2_MIN_TRADES` | NO (still 25) |
| Arena pass / fail | NO |
| rejection semantics | NO |
| champion promotion | NO |
| `deployable_count` semantics | NO |
| execution / capital / risk | NO |
| CANARY enable | NO |
| production rollout enable | NO |
| optimizer apply | NO |
| Consumer connected to runtime | NO |

## 4. Watchdog Diff Classification

```
diff --git a/zangetsu/watchdog.sh b/zangetsu/watchdog.sh
@@ -1,4 +1,12 @@
 #!/bin/bash
+# Load local runtime secrets for cron-launched workers.
+# File is local-only, not committed, and must not be printed.
+if [ -f "$HOME/.env.global" ]; then
+  set -a
+  . "$HOME/.env.global"
+  set +a
+fi
+
 # Watchdog — checks each service independently, restarts only the dead one
```

→ Classification: **EXPLAINED — env-loading preamble only**, matches order §11 / §18 explicit allowance. Does not touch `restart_service()`, `reclaim_lock()`, `check_log_activity()`, the lockfile loop, or any worker-spawn `eval` line.

## 5. Forbidden Count

| Forbidden category | Count |
| --- | --- |
| Strategy logic changes | 0 |
| Threshold changes | 0 |
| Arena pass/fail changes | 0 |
| Generation budget changes | 0 |
| Sampling weight changes | 0 |
| Execution / capital / risk changes | 0 |
| Committed secrets | 0 |
| Apply path additions | 0 |
| APPLY mode additions | 0 |
| **Total forbidden** | **0** |

## 6. Phase M Verdict

→ **PASS.** Classification: EXPLAINED. 0 forbidden. No `BLOCKED_CONTROLLED_DIFF`.
