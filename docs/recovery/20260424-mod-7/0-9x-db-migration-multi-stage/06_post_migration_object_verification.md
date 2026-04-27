# 06 — Post-Migration Object Verification

## Verdict
**OBJECT_VERIFICATION_PASS**

## Required Objects

| Check | SQL | Result |
| --- | --- | --- |
| `to_regclass('public.champion_pipeline')` | resolves | `champion_pipeline` (VIEW) |
| `to_regclass('public.champion_pipeline_staging')` | resolves | `champion_pipeline_staging` (TABLE) |
| `to_regclass('public.champion_pipeline_fresh')` | resolves | `champion_pipeline_fresh` (TABLE) |
| `to_regclass('public.champion_pipeline_rejected')` | resolves | `champion_pipeline_rejected` (TABLE) |
| `to_regclass('public.champion_legacy_archive')` | resolves | `champion_legacy_archive` (TABLE) |
| `to_regclass('public.engine_telemetry')` | resolves | `engine_telemetry` (TABLE) |

## Required Function

| Function | Result |
| --- | --- |
| `admission_validator(BIGINT)` | EXISTS (returns TEXT — admitted/rejected/error/not_found) |
| `admission_validator(0)` test call | returns `not_found_or_already_processed` (correct — staging row 0 doesn't exist) |
| `archive_readonly_trigger()` | EXISTS (raises EXCEPTION on any modification) |
| `fresh_insert_guard()` | EXISTS (raises EXCEPTION unless `zangetsu.admission_active='true'`) |

## Required Triggers

```
archive_readonly_delete   → champion_legacy_archive
archive_readonly_insert   → champion_legacy_archive
archive_readonly_update   → champion_legacy_archive
fresh_insert_gated        → champion_pipeline_fresh
```

→ All 4 triggers present and `not tgisinternal`.

## Row Preservation

| Table | Row count |
| --- | --- |
| `champion_legacy_archive` | 0 (preserved from `champion_pipeline` pre-migration) |
| `champion_pipeline_staging` | 0 (newly created) |
| `champion_pipeline_fresh` | 0 (newly created) |
| `champion_pipeline_rejected` | 0 |
| `engine_telemetry` | 0 |

→ Conservation: 0 row before, 0 + 0 + 0 + 0 + 0 = 0 row after (in migration-scope tables). No row loss possible since source had 0 rows.

## Foreign Key Integrity

```
pipeline_audit_log_champion_id_fkey | pipeline_audit_log
  FOREIGN KEY (champion_id) REFERENCES champion_legacy_archive(id)
```

PG auto-updated FK target to follow RENAME. FK still functional. (No new audit log rows expected since archive is read-only via triggers.)

## Verification Verdict

→ **OBJECT_VERIFICATION_PASS** — all 6 required tables exist, all 3 functions callable, all 4 triggers active, row preservation confirmed.
