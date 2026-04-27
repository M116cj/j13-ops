# 00 — State Lock + Alaya Baseline

| Field | Value |
| --- | --- |
| Timestamp (UTC) | 2026-04-26T18:21:33Z |
| Host | j13@100.123.49.102 |
| Repo | /home/j13/j13-ops |
| Branch | main |
| HEAD | `9f6dc60ac5350a2bf454394a47b1ebfc1b74f899` (post PR #42) |
| Mac sync | matches |
| Working tree | clean (excluding 3 runtime artifacts) |

## Pre-execution Snapshot

| Subsystem | State |
| --- | --- |
| A1 workers (×4) | ALIVE, actively rejecting at COUNTER_INCONSISTENCY/COST_NEGATIVE |
| A23 / A45 | ALIVE, idle (empty pipeline) |
| A13 cron | running every */5 min |
| watchdog cron | running every */5 min |
| `champion_pipeline` | TABLE (legacy schema, 14 cols, 0 rows) |
| `champion_pipeline_fresh / staging / rejected` | MISSING |
| `champion_legacy_archive` | MISSING |
| `engine_telemetry` | MISSING |
| `admission_validator()` function | MISSING |
| `fresh_insert_guard / archive_readonly_*` triggers | MISSING |
| `zangetsu.admission_active` session var | not registered |
| Deprecated guards (seed_101, factor_zoo, alpha_discovery) | ACTIVE per source code |
| CANARY active | NONE |
| Production rollout active | NONE |

## Migration Files Verified Present

| File | Lines |
| --- | --- |
| `zangetsu/migrations/postgres/v0.7.1_governance.sql` | 622 |
| `zangetsu/migrations/postgres/rollback_v0.7.1.sql` | 83 |

## Source-Code Reference Inventory

`grep` of v0.7.1 schema names across `services/`, `scripts/`, `dashboard/` returns **111 active references**. All are currently dead-code (target objects don't exist) but get masked by upstream rejection in A1.

→ **Phase 0 PASS.** Baseline locked. Migration script exists and matches the expected pre-state (legacy `champion_pipeline` only). Investigation/consolidation can proceed.
