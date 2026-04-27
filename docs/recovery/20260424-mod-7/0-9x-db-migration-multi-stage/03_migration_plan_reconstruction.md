# 03 — Migration Plan Reconstruction

## Migration Files Inventory

| File | Lines | Purpose |
| --- | --- | --- |
| `v0.3.0_v9_view.sql` | 5 | Creates `champion_pipeline_v9` VIEW |
| `v0.4.0_v2_constraints.sql` | 27 | Adds UNIQUE indexes + `chk_sane_metrics` CHECK constraint (references columns alpha_hash, arena1_*, n_indicators, elo_rating) |
| `v0.6.0_deployable_tier.sql` | 84 | Adds `deployable_tier` column + `zangetsu_status` VIEW |
| `v0.7.0_strategy_id.sql` | 215 | Adds `strategy_id` column + creates 4 status views (zangetsu_engine_status, j01_status, j02_status, zangetsu_status) |
| `v0.7.1_governance.sql` | 622 | Major restructure: RENAMEs `champion_pipeline` → `champion_legacy_archive`, creates fresh/staging/rejected/engine_telemetry tables, admission_validator function, triggers, 9 views |
| `rollback_v0.7.1.sql` | 83 | Reverses v0.7.1 |

## Required Bootstrap Migration

The current `champion_pipeline` (14 cols) lacks columns that v0.4's CHECK constraint references. A bootstrap migration must add these columns BEFORE v0.4 applies:
- `alpha_hash`, `n_indicators`, `arena1_*`, `arena2_*`, `arena3_*`, `arena4_*`, `arena5_*`
- `elo_rating`, `elo_consecutive_first`, `card_status`, `parent_hash`, `generation`, `evolution_operator`
- `family_id`, `family_tag`, `lease_until`, `worker_id_str`

**Bootstrap migration file**: `/tmp/bootstrap_pre_v04.sql` (committed to PR with this evidence)

Properties: schema-additive, idempotent (`IF NOT EXISTS`), row-preserving, version-explicit, fully documented.

## Migration Execution Order

1. **Bootstrap** (`/tmp/bootstrap_pre_v04.sql`) — adds ~28 columns to `champion_pipeline`
2. **v0.3.0** — creates `champion_pipeline_v9` view
3. **v0.4.0** — UNIQUE indexes + `chk_sane_metrics` CHECK
4. **v0.6.0** — `deployable_tier` column + `zangetsu_status` view
5. **v0.7.0** — `strategy_id` column + 3 strategy views
6. **v0.7.1** — RENAME + 5 new tables + 3 functions + 4 triggers + 9 views

## Special Attention Items

| Item | Notes |
| --- | --- |
| `strategy_id` | added by v0.7.0 with DEFAULT 'j01' (safe for empty table) |
| `champion_pipeline_staging` | created by v0.7.1 |
| `champion_pipeline_fresh` | created by v0.7.1 with 50+ columns including 11 provenance fields NOT NULL |
| `admission_validator()` | created by v0.7.1; only path from staging to fresh |
| `fresh_insert_guard` | trigger created by v0.7.1; blocks direct INSERT to fresh |
| `zangetsu.admission_active` session setting | manipulated by `admission_validator()` via `set_config(..., 'true', true)` |

## Dependencies

- v0.4 depends on bootstrap (column refs)
- v0.6 depends on v0.4 (no new dep, but cumulative)
- v0.7.0 depends on v0.6 (`deployable_tier` referenced in views)
- v0.7.1 depends on v0.7.0 (`strategy_id` referenced in archive views)
- `champion_pipeline` backward-compat VIEW must be created post-v0.7.1 to satisfy Phase 1 boundary contract

## Risk Assessment

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Multi-stage migration interleaves BEGIN/COMMIT | MEDIUM | each migration's inner BEGIN/COMMIT actually commits its changes; this is normal PG behavior, not a bug |
| 0 rows means data loss is impossible | n/a | n/a |
| FK on `pipeline_audit_log.champion_id` | LOW | PG auto-updates FK target on RENAME (verified post-migration: now references `champion_legacy_archive(id)`) |
| Test fixtures may reference old schema | LOW | `test_integration.py::test_db` is a known pre-existing failure independent of this migration |
| Workers might already be running and write during migration | NONE | A1/A23/A45 workers are 0 alive (post-reboot watchdog gap) — perfect time to migrate |

→ Plan is reconstructable, idempotent, and safe.
