# 04 — DB Schema Implementation and Reference Alignment

## 1. Live DB Inventory (pre-PR #43)

```
List of relations
 Schema |        Name        | Type
--------+--------------------+-------
 public | champion_pipeline  | table   (14 cols, 0 rows)
 public | paper_trades       | table
 public | pipeline_audit_log | table   (FK references champion_pipeline.id)
 public | pipeline_state     | table
 public | trade_journal      | table
```

Functions: 0 (none in public schema)
Triggers: 0
Views: 0
Session vars: 0 (zangetsu.admission_active not registered)

## 2. Current `champion_pipeline` Schema (Pre-v0.4)

```
id, indicator_hash, regime, status, passport, retry_count,
processing_started_at, engine_hash, created_at, updated_at,
is_active_card, accepting_new_entries, elo, quant_class
```

→ **14 columns. This is the original v0.0 schema.** The codebase expects 60+ columns including provenance fields (`engine_version`, `git_commit`, `config_hash`, `grammar_hash`, `fitness_version`, `patches_applied`, `run_id`, `worker_id`, `seed`, `epoch`, `created_ts`), strategy_id, deployable_tier, alpha_hash, arena1_*, arena2_*, etc.

## 3. Migration Inventory in Repo

| File | Lines | Applied? |
| --- | --- | --- |
| `v0.3.0_v9_view.sql` | 5 | NO (creates VIEW that doesn't exist in live) |
| `v0.4.0_v2_constraints.sql` | 27 | **NO** (references columns missing from current schema: `alpha_hash`, `arena1_*`, `n_indicators`, `elo_rating`) |
| `v0.6.0_deployable_tier.sql` | 84 | **NO** (adds `deployable_tier` column, missing) |
| `v0.7.0_strategy_id.sql` | 215 | **NO** (adds `strategy_id` column, missing) |
| `v0.7.1_governance.sql` | 622 | **NO** (creates fresh/staging/rejected/archive/telemetry + admission_validator + triggers — none of which exist) |
| `rollback_v0.7.1.sql` | 83 | n/a |

## 4. Migration Application Attempt (Phase 4)

I attempted to apply `v0.7.1_governance.sql` directly. The migration is wrapped in `BEGIN/COMMIT`. With `-v ON_ERROR_STOP=1`:

```
psql:/tmp/v071.sql:456: ERROR:  column "strategy_id" does not exist
LINE 4:      WHERE strategy_id = 'j01') AS total_count,
                   ^
```

The migration ran ~27 successful DDL statements (creating fresh/staging/rejected/telemetry tables, indexes, archive_readonly_trigger function, fresh_insert_guard function, admission_validator function, triggers, j01_status + j02_status views), then failed at the `j01_status_archive` view because `champion_legacy_archive` (= renamed `champion_pipeline`) lacks `strategy_id` column.

The transaction rolled back cleanly — **post-attempt DB state matches pre-attempt** (verified). 

## 5. Why Migration Cannot Proceed Autonomously

| Requirement | Status |
| --- | --- |
| Pre-v0.7.1 migrations (v0.4, v0.6, v0.7.0) must be applied first | **NOT APPLIED** |
| v0.4 migration assumes columns from earlier (alpha_hash, arena1_*) that current schema lacks | **PRE-v0.4 SCHEMA INCOMPLETE** |
| Multi-step migration would require: (a) reconstructing intermediate schemas, OR (b) drop+recreate of `champion_pipeline` skipping all intermediate states | autonomous decision, high impact |
| 0 rows in champion_pipeline ⇒ no data loss risk on drop+recreate | YES |
| FK reference: `pipeline_audit_log.champion_id` references `champion_pipeline.id` | exists; would need ON DELETE handling for drop+recreate |

**Decision**: BLOCK migration autonomously. Recommend a separate, dedicated `TEAM ORDER 0-9X-DB-MIGRATION-MULTI-STAGE` that:
1. Authorizes the multi-migration sequence (v0.4 → v0.6 → v0.7.0 → v0.7.1) OR drop+recreate
2. Includes explicit governance review of each step
3. Includes post-migration verification + rollback plan

## 6. Reference Alignment Status

| Source reference | Target object | Resolves? |
| --- | --- | --- |
| 11 v0.7.1 schema names | tables/functions/triggers in live DB | NO (all blocked) |
| Code paths gated by try/except (telemetry insert, staging insert) | live DB | silently fail on schema gap |
| Active runtime SELECT from `champion_pipeline_fresh` | live DB | would error if reached (currently no candidate reaches them due to upstream rejection) |

→ **Phase 4 verdict: DB_MIGRATION_BLOCKED.**

## 7. Phase 4 Classification

```
Result: SCHEMA_GAP_TOO_DEEP_FOR_AUTONOMOUS_MIGRATION
Block status: BLOCKED — requires dedicated multi-stage migration order
Rollback: not needed (no migration applied)
Pre-state preserved: YES (transaction rollback verified)
```
