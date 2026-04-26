# 0-9V-A23-A45-LAUNCHER — Final Report

## 1. Status

**COMPLETE_LAUNCHER_RESTORED_WAITING_FOR_BATCH.**

Lockfile-bootstrap of `arena23_orchestrator.lock` and `arena45_orchestrator.lock` allowed the existing watchdog launcher to discover and spawn both orchestrators. A23 (PID 207186) and A45 (PID 207195) reached "Service loop started" / "Arena 4+5 Orchestrator running" with no `KeyError`. `arena_batch_metrics.jsonl` is still missing because A23's emit window requires upstream A1→A23 candidate flow that is currently throttled by an unrelated `arena13_feedback.py` env issue (separate-order scope).

## 2. Alaya

| Field | Value |
| --- | --- |
| Host | `j13@100.123.49.102` (Tailscale) |
| Repo | `/home/j13/j13-ops` |
| Access | PASS |
| HEAD | `f50e8cba7b5180605abcc08306446f79686aef60` |
| origin/main | matches |

## 3. Preflight

| Field | Value |
| --- | --- |
| Branch | `main` |
| Dirty state | clean |
| A1 status | ACTIVE (cycling per cron `*/5`) |
| `engine.jsonl` last write at observation | `2026-04-26T09:57:17Z` |

Detail: `01_preflight_state.md`.

## 4. Launcher inventory

| Field | Value |
| --- | --- |
| A23 process (pre-trigger) | STOPPED |
| A45 process (pre-trigger) | STOPPED |
| Cron | `*/5 * * * *` watchdog.sh |
| Watchdog | `zangetsu/watchdog.sh` (PR #31 env preamble already loaded) |
| Systemd | only HTTP APIs + Calcifer (no arena services) |
| Tmux | none |
| Manual launcher | none discovered |
| Lockfile bootstrap pattern | identified |

Detail: `02_launcher_inventory.md`.

## 5. Env safety

| Field | Value |
| --- | --- |
| Env source | `~/.env.global` (mode 600, j13:j13) |
| `ZV5_DB_PASSWORD` reachable in subshell-via-preamble | YES |
| Secret printed | NO |
| Secret committed | NO |

Detail: `03_env_and_secret_safety.md`.

## 6. Launcher plan

| Field | Value |
| --- | --- |
| Method | lockfile bootstrap (`: > /tmp/zangetsu/arena{23,45}_orchestrator.lock`) + manual one-shot watchdog trigger |
| A23 command (run by watchdog) | `python3 zangetsu/services/arena23_orchestrator.py` (cwd `~/j13-ops/zangetsu`, env loaded by watchdog preamble) |
| A45 command | same shape |
| Working directory | `~/j13-ops/zangetsu` |
| Python / venv | `~/j13-ops/zangetsu/.venv/bin/python3` (3.12.3) |
| Logs | `/tmp/zangetsu_a23.log`, `/tmp/zangetsu_a45.log` |
| Rollback | `kill -TERM` PIDs + `rm -f` lockfiles; cron / repo / source unchanged |

Detail: `04_a23_a45_launcher_plan.md`.

## 7. Launcher change

| Field | Value |
| --- | --- |
| Files changed (tracked) | 11 evidence docs only |
| Source code changed | NONE |
| `watchdog.sh` changed | NO (PR #31 already added env preamble) |
| Cron changed | NO |
| `~/.env.global` changed | NO (set in PR #31) |
| Strategy logic changed | NO |
| Thresholds changed | NO |

Detail: `05_launcher_change_report.md`.

## 8. Process start

| Field | Value |
| --- | --- |
| A23 started | YES — PID 207186 at `2026-04-26T09:52:52Z` |
| A45 started | YES — PID 207195 at `2026-04-26T09:52:52Z` |
| Old PIDs | none (services were stopped pre-trigger) |
| New PIDs | A23 207186, A45 207195, A1 207204/207213/207222/207231 |
| HTTP APIs touched | NO |
| A1 preserved | YES (workers cycling normally) |

Detail: `06_process_start_report.md`.

## 9. Runtime health

| Field | Value |
| --- | --- |
| A1 | CYCLING (engine.jsonl advancing) |
| A23 | ALIVE (idle, "Service loop started") |
| A45 | ALIVE (idle, "Arena 4+5 Orchestrator running") |
| Engine log | advancing |
| Errors | none in A23/A45/A1 logs |
| Side note | `arena13_feedback.py` (separate cron line, not via watchdog) still hits `KeyError: ZV5_DB_PASSWORD` — out of scope; documented for follow-up order |
| Result | **PASS** |

Detail: `07_runtime_health_check.md`.

## 10. Telemetry

| File | Status |
| --- | --- |
| `arena_batch_metrics.jsonl` | MISSING |
| Line count | 0 |
| Mtime | n/a |
| Sample record | n/a |
| `sparse_candidate_dry_run_plans.jsonl` | MISSING (offline by design — PR #23) |
| Verdict (per order §14) | **`A23_A45_LAUNCHED_NO_TELEMETRY_YET`** → maps to allowed final status `COMPLETE_LAUNCHER_RESTORED_WAITING_FOR_BATCH` |

Detail: `08_telemetry_emission_check.md`.

## 11. Runtime safety

| Field | Value |
| --- | --- |
| Apply path | NONE |
| Runtime-switchable APPLY | NONE |
| Consumer connected | NO |
| `A2_MIN_TRADES` | 25 |
| CANARY | NOT STARTED |
| Production rollout | NOT STARTED |

Detail: `09_runtime_safety_audit.md`.

## 12. Tests

| Field | Value |
| --- | --- |
| Suites | `test_a2_a3_arena_batch_metrics.py`, `test_sparse_canary_observer.py`, `test_sparse_canary_readiness.py`, `test_sparse_canary_observation_runner.py` |
| Result | **189 passed / 0 failed / 0 skipped** in 0.29 s |

## 13. Controlled-diff

| Field | Value |
| --- | --- |
| Classification | EXPLAINED (docs-only) |
| Forbidden | 0 |
| CODE_FROZEN runtime SHAs | zero-diff for all 6 |

Detail: `10_controlled_diff_report.md`.

## 14. Gate-A / Gate-B

Expected: **PASS / PASS** (will run on PR open).

## 15. Branch protection

Expected unchanged on `main`:

- `enforce_admins=true`
- `required_signatures=true`
- `linear_history=true`
- `allow_force_pushes=false`
- `allow_deletions=false`

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

### Immediate (separate orders)

**TEAM ORDER 0-9V-FEEDBACK-LOOP-ENV-CONFIG** (recommended) — apply the same env-loading pattern from PR #31 to the bare-cron `arena13_feedback.py` line, so feedback events flow back into the A1→A23 pipeline. This will unblock A23's first 20-iteration window and allow `arena_batch_metrics.jsonl` to begin writing.

### After arena_batch_metrics emission

**TEAM ORDER 0-9S-CANARY-OBSERVE-LIVE** — run the sparse-candidate canary observer against live `arena_batch_metrics.jsonl`; accumulate ≥ 20 real rounds; produce real CANARY verdict.

## 18. Final declaration

```
TEAM ORDER 0-9V-A23-A45-LAUNCHER = COMPLETE_LAUNCHER_RESTORED_WAITING_FOR_BATCH
```

A23 (PID 207186) and A45 (PID 207195) are alive and waiting for upstream candidates. Launcher restoration is **lockfile-bootstrap-only**: no source code changed, no watchdog change, no cron change, no `.env.global` change, no secret printed or committed. HTTP APIs preserved. A1 cycling normally. `engine.jsonl` advancing. `arena_batch_metrics.jsonl` waits on a separate-scope `arena13_feedback.py` env-config follow-up. Branch protection intact. Signed PR-only flow preserved. No CANARY. No production rollout. Forbidden changes count = 0.
