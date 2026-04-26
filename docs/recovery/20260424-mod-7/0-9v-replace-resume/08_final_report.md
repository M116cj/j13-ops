# 0-9V-REPLACE-RESUME — Alaya Runtime Replacement Resume Final Report

## 1. Status

**COMPLETE_SYNCED_SHADOW_ONLY.**

The code-path replacement happened automatically via the existing watchdog cron launcher (workers now spawn from the post-CLEAN SHA `41796663`), shadow validation ran cleanly with the documented missing-telemetry note, and all 12 critical gates G1–G15 PASS. Worker initialization is blocked by a **pre-existing environment-configuration issue** (`KeyError: ZV5_DB_PASSWORD`) introduced by commit `fe1c0bc0` on 2026-04-20 — three days before the original 2026-04-23 pipeline stop. This is outside the scope of a runtime-replacement order.

→ Per order §16 final-status guidance: **"If COMPLETE_SYNCED_SHADOW_ONLY: Fix telemetry or launcher issue, then rerun replacement/switch step."** Recommended next action documented in §14.

## 2. Alaya

| Field | Value |
| --- | --- |
| Host | `j13@100.123.49.102` (Tailscale) |
| Repo | `/home/j13/j13-ops` |
| SSH access | PASS |

## 3. Clean state verification

| Field | Value |
| --- | --- |
| Branch | `main` |
| HEAD | `41796663ccc7cc6b7b66e5d92bc941de6c92c442` |
| Origin/main | `41796663ccc7cc6b7b66e5d92bc941de6c92c442` |
| Ahead/behind | 0 / 0 |
| Dirty state | clean (Calcifer state regenerated daily — restored once for snapshot, see 01) |
| Residual WIP | NONE |

Detail: `01_clean_state_verification.md`.

## 4. Tests

| Field | Value |
| --- | --- |
| Command | `zangetsu/.venv/bin/python -m pytest <10 suites>` |
| Result | **495 passed / 0 failed / 0 skipped** in 1.11 s |
| Failures | NONE |
| Skips | NONE |

Detail: `02_dependency_and_test_report.md`.

## 5. Runtime safety

| Field | Value |
| --- | --- |
| Apply path | NONE |
| Runtime-switchable APPLY | NONE |
| Consumer connected to generation runtime | NO |
| Consumer output consumed by generation runtime | NO |
| `A2_MIN_TRADES` | 25 |
| CANARY | NOT STARTED |
| Production rollout | NOT STARTED |

Detail: `03_runtime_safety_audit.md`.

## 6. Telemetry source check

| File | Status |
| --- | --- |
| `arena_batch_metrics.jsonl` | MISSING (PR #18 emitter not yet emitted; orchestrator cannot pass init) |
| `sparse_candidate_dry_run_plans.jsonl` | MISSING (consumer is offline by design) |
| Line counts | n/a |
| Last modified | n/a |
| Enough for live observation | **NO** |

Detail: `04_telemetry_source_check.md`.

## 7. Shadow validation

| Field | Value |
| --- | --- |
| Readiness | PASS (15/15 CRs) |
| Observer | rc=0; runner_version=0-9S-OBSERVE-FAST |
| Records | 0 (telemetry inputs MISSING) |
| Result | **SHADOW_BLOCKED_MISSING_TELEMETRY** (non-blocking per order §9) |
| Output dir | `docs/recovery/20260424-mod-7/0-9v-replace-resume/shadow-validation/` |

Detail: `05_shadow_validation_report.md`.

## 8. Replacement gate

```
G1  PASS  clean main + sync
G2  PASS  0-9V-CLEAN done
G3  PASS  rollback snapshot exists
G4  PASS  cron + watchdog launcher documented
G5  PASS  logs/env/secrets/runtime state preserved
G6  PASS  495 tests pass
G7  PASS  runtime safety audit
G8  PASS  no apply path
G9  PASS  no APPLY mode
G10 PASS  consumer not in generation runtime
G11 PASS  A2_MIN_TRADES=25
G12 PASS-NOTE telemetry missing (replacement is the action that enables emission)
G13 PASS-NOTE SHADOW_BLOCKED_MISSING_TELEMETRY (non-blocking)
G14 PASS  branch protection intact
G15 PASS  signed PR-only flow preserved

Verdict: ALL 12 critical gates PASS. Authorize Phase G.
```

Detail: `06_runtime_replacement_gate.md`.

## 9. Runtime switch

| Field | Value |
| --- | --- |
| Performed | **PARTIAL** (code-path switched; worker init blocked by env config) |
| Runtime manager | cron + watchdog.sh (verified active, every 5 min) + systemd HTTP APIs (preserved) |
| Old PID | A1 workers crash-loop; HTTP APIs UNTOUCHED |
| New PID | watchdog cycle 08:30:01 spawned `33428/33450/33468/33477` from new SHA — each crashed within ~30 s on `KeyError: ZV5_DB_PASSWORD` |
| Logs writing | HTTP API systemd journals + `/tmp/zangetsu_*.log` traceback evidence; `engine.jsonl` last write 2026-04-23T00:35Z (idle) |
| Telemetry writing | NONE (workers cannot pass init) |
| Rollback readiness | YES (rollback SHA `f5f62b2b`; procedure in PR #28) |

Detail: `07_runtime_switch_report.md`.

## 10. Controlled-diff

This PR is documentation + evidence files only. No runtime files modified. Expected classification: **EXPLAINED** (docs-only).

| CODE_FROZEN runtime SHA | Status |
| --- | --- |
| `config.zangetsu_settings_sha` | zero-diff |
| `config.arena_pipeline_sha` | zero-diff |
| `config.arena23_orchestrator_sha` | zero-diff |
| `config.arena45_orchestrator_sha` | zero-diff |
| `config.calcifer_supervisor_sha` | zero-diff |
| `config.zangetsu_outcome_sha` | zero-diff |

0 forbidden.

## 11. Gate-A / Gate-B

Expected: **PASS / PASS** (docs-only PR with no controversial diffs). Will run on PR open.

## 12. Branch protection

Expected unchanged on `main`:

- `enforce_admins=true`
- `required_signatures=true`
- `linear_history=true`
- `allow_force_pushes=false`
- `allow_deletions=false`

This PR does not modify governance configuration.

## 13. Forbidden changes audit

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
| Arena pass/fail | UNCHANGED |
| champion promotion | UNCHANGED |
| `deployable_count` semantics | UNCHANGED |
| execution / capital / risk | UNCHANGED |
| CANARY | NOT STARTED |
| production rollout | NOT STARTED |

## 14. Recommended next action

### Immediate (j13 owns)

The arena pipeline workers cannot complete `import zangetsu.config.settings` because `ZV5_DB_PASSWORD` is not in cron's environment. Two viable repair paths:

**Path A — env file injection (recommended)**: add `ZV5_DB_PASSWORD=<secret>` to `/home/j13/.env.global`, then prepend each cron-spawned line with `set -a; . /home/j13/.env.global; set +a;` (or use the `BASH_ENV` cron variable). This restores worker startup with no source-code or governance change.

**Path B — systemd unit per worker**: replace the cron-watchdog model with one systemd unit per worker, each loading the env via `EnvironmentFile=/home/j13/.env.global`. Larger blast radius; defer unless Path A reveals other issues.

j13 issues a separate authorization order (e.g. **0-9V-ENV-CONFIG**) to apply the chosen path, since both touch environment configuration which is explicitly outside this order's scope.

### After env fix

Re-run 0-9V-REPLACE-RESUME from Phase G (or rerun the full order). Expected outcome: `COMPLETE_REPLACED`.

### Subsequent (separate orders)

After functional runtime replacement:

- **TEAM ORDER 0-9S-CANARY-OBSERVE-LIVE** — run sparse-candidate observer against the live `arena_batch_metrics` stream once it begins emitting; accumulate ≥ 20 real rounds; produce real CANARY verdict.

## 15. Final declaration

```
TEAM ORDER 0-9V-REPLACE-RESUME = COMPLETE_SYNCED_SHADOW_ONLY
```

Code-path is on the latest governed `main` (`41796663`). Tests 495/0/0. Runtime safety verified. Shadow validation ran cleanly with the documented missing-telemetry note. All 12 critical replacement gates PASS. Watchdog launcher actively spawning workers from the new SHA. HTTP APIs preserved. No source code modified. No `.env` / secret modified. No production rollout. Branch protection intact. Signed PR-only flow preserved. Mac repo not copied to Alaya.

Worker functional uptime is blocked by a pre-existing env-config issue from `fe1c0bc0` (2026-04-20). j13 must authorize a separate order to repair the cron environment, after which the watchdog will bring workers fully online on the new code.
