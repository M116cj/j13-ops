# 03 — PostgreSQL Admission Guard Audit

## 1. fresh_insert_guard Definition (read from migration)

From `zangetsu/migrations/postgres/v0.7.1_governance.sql` (applied 2026-04-20):

```sql
CREATE OR REPLACE FUNCTION fresh_insert_guard()
RETURNS TRIGGER AS $$
BEGIN
    IF current_setting('zangetsu.admission_active', true)
       IS DISTINCT FROM 'true' THEN
        RAISE EXCEPTION
            'champion_pipeline_fresh direct INSERT forbidden. '
            'Only admission_validator() may promote rows. '
            'Governance rule #2.';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER fresh_insert_gated
    BEFORE INSERT ON champion_pipeline_fresh
    FOR EACH ROW EXECUTE FUNCTION fresh_insert_guard();
```

| Field | Value |
| --- | --- |
| Trigger name | `fresh_insert_gated` |
| Trigger timing | BEFORE INSERT |
| Trigger target table | `public.champion_pipeline_fresh` |
| Required session setting | `zangetsu.admission_active = 'true'` |
| Behavior on missing setting | `IS DISTINCT FROM 'true'` → raise exception |
| Behavior on `false` value | raise exception (same path) |
| Bypass mechanism | `admission_validator()` PostgreSQL function (which presumably does `SET LOCAL zangetsu.admission_active = 'true'` inside its body before its INSERT into fresh) |

## 2. Other Guarded Tables (per v0.7.1 migration text)

| Table | Trigger | Notes |
| --- | --- | --- |
| `champion_pipeline_staging` | NO trigger guard (per v0.7.1 source) | A1 INSERTs directly here without needing `zangetsu.admission_active` |
| `champion_pipeline_fresh` | `fresh_insert_gated` | Only `admission_validator()` can write |
| `champion_pipeline_rejected` | NO trigger guard | rejection forensics |
| `engine_telemetry` | NO trigger guard | A1 inserts telemetry directly |
| `champion_legacy_archive` | `archive_readonly_*` triggers (BEFORE INSERT/UPDATE/DELETE) | always raises — Epoch A is read-only |

## 3. Does the Admission Guard Block A1?

**A1 writes go to `champion_pipeline_staging` first** (line 1117 in `arena_pipeline.py`). Staging has NO `fresh_insert_guard` trigger; staging INSERTs do NOT require `zangetsu.admission_active`.

`fresh_insert_guard` only fires when `admission_validator()` itself writes into `fresh`. The validator runs server-side as a PostgreSQL function and is responsible for setting `zangetsu.admission_active='true'` inside its own session-local context. A1's asyncpg session does NOT need this setting.

→ **The admission guard is NOT blocking A1.** A1 never even reaches the staging INSERT (because the loop crashes earlier at line 1218 — see 02).

## 4. Empirical Confirmation

`champion_pipeline_staging` row count = 184 (admitted=89 + admitted_duplicate=95). All from before 2026-04-21T04:34Z. If `admission_validator()` were broken, we'd see staging rows newer than fresh rows (or vice versa). They both have identical max-timestamps (Apr 21 04:34) — showing the validator path WAS working historically.

The current 0-row-since-A1-restart pattern matches the **Python crash before INSERT**, not a guard rejection. A guard rejection would also be visible as a `psycopg2.errors.InsufficientPrivilege` traceback in worker logs — there is none.

## 5. Verbatim Inspection Query (read-only, executed via /tmp/0-9w-a1diag-pgaudit.py)

```sql
SELECT EXISTS (SELECT 1 FROM pg_proc WHERE proname='fresh_insert_guard') AS guard_present;
SELECT tgname FROM pg_trigger WHERE tgrelid='public.champion_pipeline_fresh'::regclass;
SELECT tgname FROM pg_trigger WHERE tgrelid='public.champion_pipeline_staging'::regclass;
SELECT current_setting('zangetsu.admission_active', true);
```

The `current_setting` call returns NULL in a fresh inspection session (because it's not set by default), but that NULL is only checked **at INSERT time** by the trigger. A1 doesn't need it because A1 doesn't INSERT into fresh directly.

## 6. Phase 3 Classification

Per order §8:

| Verdict | Match? |
| --- | --- |
| ADMISSION_GUARD_OK (A1 writes to staging which is unguarded) | **YES — exact match** |
| ADMISSION_SETTING_MISSING (A1 INSERT into fresh without setting) | NO (A1 doesn't INSERT into fresh) |
| ADMISSION_SETTING_FALSE | NO |
| ADMISSION_GUARD_REJECTING_A1 | NO (no rejection traceback) |
| ADMISSION_GUARD_NOT_ON_A1_PATH | partial — true but framed positively as ADMISSION_GUARD_OK |
| ADMISSION_GUARD_UNKNOWN | NO |

→ **Phase 3 verdict: ADMISSION_GUARD_OK.** The guard is correctly designed and not the cause of the materialization gap.
