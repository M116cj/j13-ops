# 13 — Controlled Diff Report

## Classification: **EXPLAINED_DOCS_AND_MIGRATION_ASSET**

## Changed Files

| Path | Class | Reason |
| --- | --- | --- |
| `docs/recovery/20260424-mod-7/0-9x-db-migration-multi-stage/00_state_lock.md` | EXPLAINED_DOCS_ONLY | new evidence file |
| `docs/recovery/20260424-mod-7/0-9x-db-migration-multi-stage/01_backup_report.md` | EXPLAINED_DOCS_ONLY | new |
| `docs/recovery/20260424-mod-7/0-9x-db-migration-multi-stage/02_pre_migration_schema_inventory.md` | EXPLAINED_DOCS_ONLY | new |
| `docs/recovery/20260424-mod-7/0-9x-db-migration-multi-stage/03_migration_plan_reconstruction.md` | EXPLAINED_DOCS_ONLY | new |
| `docs/recovery/20260424-mod-7/0-9x-db-migration-multi-stage/04_dry_run_migration_report.md` | EXPLAINED_DOCS_ONLY | new |
| `docs/recovery/20260424-mod-7/0-9x-db-migration-multi-stage/05_live_migration_execution.md` | EXPLAINED_DOCS_ONLY | new |
| `docs/recovery/20260424-mod-7/0-9x-db-migration-multi-stage/06_post_migration_object_verification.md` | EXPLAINED_DOCS_ONLY | new |
| `docs/recovery/20260424-mod-7/0-9x-db-migration-multi-stage/07_admission_guard_verification.md` | EXPLAINED_DOCS_ONLY | new |
| `docs/recovery/20260424-mod-7/0-9x-db-migration-multi-stage/08_runtime_boundary_audit.md` | EXPLAINED_DOCS_ONLY | new |
| `docs/recovery/20260424-mod-7/0-9x-db-migration-multi-stage/09_test_report.md` | EXPLAINED_DOCS_ONLY | new |
| `docs/recovery/20260424-mod-7/0-9x-db-migration-multi-stage/10_a1_pipeline_reverification.md` | EXPLAINED_DOCS_ONLY | new |
| `docs/recovery/20260424-mod-7/0-9x-db-migration-multi-stage/11_rollback_plan.md` | EXPLAINED_DOCS_ONLY | new |
| `docs/recovery/20260424-mod-7/0-9x-db-migration-multi-stage/12_monitoring_plan.md` | EXPLAINED_DOCS_ONLY | new |
| `docs/recovery/20260424-mod-7/0-9x-db-migration-multi-stage/13_controlled_diff_report.md` | this file | new |
| `docs/recovery/20260424-mod-7/0-9x-db-migration-multi-stage/14_red_team_review.md` | EXPLAINED_DOCS_ONLY | new |
| `docs/recovery/20260424-mod-7/0-9x-db-migration-multi-stage/15_final_report.md` | EXPLAINED_DOCS_ONLY | new |
| `docs/recovery/20260424-mod-7/0-9x-db-migration-multi-stage/bootstrap_pre_v04.sql` | EXPLAINED_SCHEMA_ONLY | bootstrap migration that adds 28 columns to `champion_pipeline` (all `IF NOT EXISTS`, idempotent, additive). Required prerequisite for v0.4.0_v2_constraints.sql to apply. NOT runtime/threshold change. |
| `docs/recovery/20260424-mod-7/0-9x-db-migration-multi-stage/rollback_commands.sh` | EXPLAINED_DOCS_ONLY | NOT executable by default (chmod 644). j13 must explicitly chmod +x to run. |
| `docs/recovery/20260424-mod-7/0-9x-db-migration-multi-stage/*.json` | EXPLAINED_DOCS_ONLY | data artifacts |

## Changes Outside docs/recovery/

**ZERO**.

| Category | Changes |
| --- | --- |
| Source code (`zangetsu/services/`, `zangetsu/scripts/`, `zangetsu/engine/`, `zangetsu/dashboard/`) | 0 |
| Configuration (`zangetsu/config/`) | 0 |
| Migrations (`zangetsu/migrations/postgres/*.sql`) | 0 (existing files unchanged; bootstrap is in evidence dir, not migrations dir) |
| Tests (`zangetsu/tests/`) | 0 |
| Cron (`crontab`, wrapper scripts) | 0 |
| Workflows (`.github/workflows/`) | 0 |
| Hooks (`.githooks/`) | 0 |
| Secrets / env files | 0 |

## DB Changes (out of source-tree, but documented)

| Object | Before | After |
| --- | --- | --- |
| `champion_pipeline` (table) | TABLE 14 cols 0 rows | RENAMED to `champion_legacy_archive` |
| `champion_pipeline` (view) | absent | VIEW over `champion_pipeline_fresh` |
| 5 new tables | absent | created (staging, fresh, rejected, legacy_archive, engine_telemetry) |
| 3 new functions | absent | created (admission_validator, archive_readonly_trigger, fresh_insert_guard) |
| 4 new triggers | absent | created (3 archive_readonly + fresh_insert_gated) |
| 9 new views | absent | created (status views + dual-evidence health views) |

→ **All DB changes are SCHEMA additions or RENAMEs. ZERO row deletion, ZERO row mutation, ZERO data loss.**

## Forbidden Diff Audit

| Category | Result |
| --- | --- |
| Source patch | NONE |
| Threshold change | NONE (A2_MIN_TRADES=25 verified unchanged) |
| Alpha behavior change | NONE |
| Runtime pass/fail change | NONE |
| Champion promotion semantic change | NONE |
| deployable_count semantic change | NONE |
| APPLY mode add | NONE |
| CANARY start | NONE |
| Production rollout | NONE |
| Execution / capital / risk change | NONE |
| Branch protection change | NONE |
| Force push | NONE |
| Unsigned commit | NONE (this commit signed ED25519) |
| Secret commit | NONE |

→ **Total forbidden diffs: 0.**

## Verdict
**CONTROLLED_DIFF_PASS.** All changes are docs/evidence + 1 schema-only bootstrap migration (idempotent, additive). Zero source/runtime/threshold/secret changes.
