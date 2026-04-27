# 02 — Pre-Migration Schema Inventory

## Tables (5 total in public schema)

| Table | Type |
| --- | --- |
| `champion_pipeline` | TABLE (14 cols, 0 rows) |
| `paper_trades` | TABLE |
| `pipeline_audit_log` | TABLE (FK references `champion_pipeline.id`) |
| `pipeline_state` | TABLE |
| `trade_journal` | TABLE |

## `champion_pipeline` Columns (Original v0.0 Schema)

```
id, indicator_hash, regime, status, passport, retry_count,
processing_started_at, engine_hash, created_at, updated_at,
is_active_card, accepting_new_entries, elo, quant_class
```

→ **14 cols.** This is the bootstrap schema, NOT v0.4 or later.

## Functions: 0 (none in public schema)
## Triggers: 0
## Views: 0
## Session vars: 0 (zangetsu.admission_active not registered)
## Row counts: champion_pipeline = 0

## Schema Level Classification

`current_schema_level = pre-v0.4`

## Missing Objects (Per v0.7.1 Contract)

| Tables | Functions | Triggers | Session vars |
| --- | --- | --- | --- |
| champion_pipeline_staging | admission_validator(BIGINT) | fresh_insert_guard | zangetsu.admission_active |
| champion_pipeline_fresh | archive_readonly_trigger | archive_readonly_insert | |
| champion_pipeline_rejected | fresh_insert_guard | archive_readonly_update | |
| champion_legacy_archive | | archive_readonly_delete | |
| engine_telemetry | | fresh_insert_gated | |

Plus 9 expected views (j01_status, j02_status, zangetsu_status, fresh_pool_*, etc.)

## Missing Columns vs v0.7.1 Expected Schema

For `champion_pipeline_fresh` (the post-RENAME canonical table), v0.7.1 expects 50+ columns including:
- `alpha_hash`, `n_indicators`, `arena1_*`, `arena2_*`, `arena3_*`, `arena4_*`, `arena5_*` columns
- `elo_rating`, `elo_consecutive_first`, `card_status`, `parent_hash`, `generation`, `evolution_operator`
- `family_id`, `family_tag`, `lease_until`, `worker_id_str`, `deployable_tier`, `strategy_id`
- 11 provenance fields: `engine_version`, `git_commit`, `config_hash`, `grammar_hash`, `fitness_version`, `patches_applied`, `run_id`, `worker_id`, `seed`, `epoch`, `created_ts`

Only 14 of those columns exist in the current `champion_pipeline`. **Bootstrap migration needed before v0.4 can apply.**
