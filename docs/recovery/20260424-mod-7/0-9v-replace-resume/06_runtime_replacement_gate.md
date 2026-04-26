# 06 — Runtime Replacement Gate (G1–G15)

## 1. Gate Evaluation

| ID | Criterion | Status | Evidence |
| --- | --- | --- | --- |
| G1 | Alaya repo clean and on latest governed main | **PASS** | `01_clean_state_verification.md`: HEAD=`41796663`, branch=`main`, ahead/behind=0/0 |
| G2 | 0-9V-CLEAN completed and residual WIP = NONE | **PASS** | PR #29 merged at `41796663`; only Calcifer regenerated state file documented as runtime churn (not WIP) |
| G3 | Rollback snapshot from 0-9V-REPLACE exists | **PASS** | `docs/recovery/20260424-mod-7/0-9v-replace/rollback_commands.sh` + `02_rollback_snapshot.md` (PR #28) |
| G4 | Old runtime process / launcher documented | **PASS** | cron `*/5 * * * * ~/j13-ops/zangetsu/watchdog.sh` (verified live in `crontab -l`); watchdog.sh manages `arena_pipeline_w0..w3`, `arena23_orchestrator`, `arena45_orchestrator` via lockfiles; HTTP APIs (`console-api`, `cp-api`, `dashboard-api`) preserved on systemd |
| G5 | Logs / env / secrets / runtime state preserved | **PASS** | No log deletion. `engine.jsonl` (37 MB, last write Apr 23) preserved. `~/.env.global` untouched. Calcifer state files preserved (regenerate naturally). |
| G6 | Tests pass or only non-blocking environment issue documented | **PASS** | `02_dependency_and_test_report.md`: 495 PASS / 0 fail / 0 skip on Alaya |
| G7 | Runtime safety audit PASS | **PASS** | `03_runtime_safety_audit.md`: no apply path, no APPLY mode, generation runtime imports clean |
| G8 | No apply path exists | **PASS** | Only pre-existing trading helpers (`apply_trailing_stop`, `apply_fixed_target`, `apply_tp_strategy`); allow-listed |
| G9 | No runtime-switchable APPLY mode exists | **PASS** | No env var / config flag for APPLY; rejection probes only |
| G10 | Consumer not connected to generation runtime | **PASS** | `arena_pipeline.py`, `arena23_orchestrator.py`, `arena45_orchestrator.py` do NOT import `feedback_budget_consumer` / `feedback_budget_allocator` / `sparse_canary_observer`; only the offline observer reads consumer events |
| G11 | A2_MIN_TRADES = 25 | **PASS** | `arena_gates.py:48 = 25`; `arena23_orchestrator.py:779,897 = 25`; `settings.py:29 = 25` |
| G12 | Telemetry source check complete | **PASS-WITH-NOTE** | `04_telemetry_source_check.md`: `arena_batch_metrics.jsonl` MISSING + `sparse_candidate_dry_run_plans.jsonl` MISSING (structurally expected pre-replacement state). Replacement IS the action that enables telemetry. |
| G13 | Shadow validation PASS or documented non-blocking missing telemetry | **PASS-WITH-NOTE** | `05_shadow_validation_report.md`: readiness 15/15 PASS; observer ran rc=0; status=`OBSERVING_NOT_COMPLETE`; classified as **SHADOW_BLOCKED_MISSING_TELEMETRY** (non-blocking per order §9) |
| G14 | Branch protection intact | **PASS** | enforce_admins=true, required_signatures=true, required_linear_history=true, allow_force_pushes=false, allow_deletions=false |
| G15 | Signed PR-only flow preserved | **PASS** | PRs #17–#29 all merged through signed PR-only flow with admin-squash; no force-push events on main |

## 2. Critical-Gate Verdict

| Critical gate | Result |
| --- | --- |
| G1 | PASS |
| G2 | PASS |
| G3 | PASS |
| G4 | PASS |
| G5 | PASS |
| G7 | PASS |
| G8 | PASS |
| G9 | PASS |
| G10 | PASS |
| G11 | PASS |
| G14 | PASS |
| G15 | PASS |

→ **All 12 critical gates PASS.** No `BLOCKED_REPLACEMENT_GATE`.

## 3. Soft-Note Gates

| Gate | Result | Why non-blocking |
| --- | --- | --- |
| G12 | PASS-with-note (telemetry MISSING) | The order itself notes this is the expected pre-replacement state and that replacement is the action to enable emission. |
| G13 | PASS-with-note (SHADOW_BLOCKED_MISSING_TELEMETRY) | Order §9 explicitly classifies this as non-blocking when replacement is needed to deploy emitters. |

## 4. Verdict

→ **GATE PASS.** Proceed to Phase G runtime switch.

## 5. Runtime Switch Constraints (carried into Phase G)

The switch must:

1. NOT touch HTTP APIs (`console-api`, `cp-api`, `dashboard-api`) — they preserve through replacement.
2. NOT manually start arena workers — the watchdog cron line is the documented launcher; let it relaunch them on the new code.
3. NOT modify any source file.
4. NOT modify any `.env*` or secret file.
5. NOT modify cron config.
6. NOT touch `engine.jsonl`, `data/funding/`, `data/ohlcv/`, or any historical telemetry file.
7. Document any worker startup failure honestly. Worker init failure caused by pre-existing environment configuration (e.g. missing env var) is NOT a code regression introduced by this order — document and recommend a separate environment-config order.

## 6. Phase F Verdict

→ **PASS.** All critical gates PASS. Soft-notes are explicitly authorized by the order. Phase G runtime switch authorized.
