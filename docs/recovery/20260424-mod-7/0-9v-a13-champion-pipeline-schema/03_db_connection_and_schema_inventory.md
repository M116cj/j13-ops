# 03 — DB Connection and Schema Inventory

## 1. DB Drivers Available in zangetsu venv

| Driver | Version |
| --- | --- |
| psycopg (v3) | NOT INSTALLED |
| psycopg2 | 2.9.11 (selected for this order) |
| asyncpg | 0.31.0 (used by orchestrators; not used here) |

## 2. DB Connection Env (no value printed)

```
DB_ENV_STATUS={"host": "PRESENT", "port": "PRESENT", "dbname": "PRESENT", "user": "PRESENT", "password": "PRESENT"}
```

| Source | Variable |
| --- | --- |
| ZV5_DB_HOST | from `zangetsu/secret/.env` (also defaulted to localhost in `settings.py`) |
| ZV5_DB_PORT | from secret/.env (defaulted to 5432 in settings.py) |
| ZV5_DB_NAME | from secret/.env (defaulted to zangetsu) |
| ZV5_DB_USER | from secret/.env (defaulted to zangetsu) |
| ZV5_DB_PASSWORD | from `~/.env.global` (placed there by PR #31 0-9V-ENV-CONFIG, mode 600) |

For this order's migration we source `~/.env.global` (which provides ZV5_DB_PASSWORD); the rest fall back to settings.py defaults — same path A1/A23/A45 workers successfully use.

## 3. Connection Result

| Field | Value |
| --- | --- |
| psycopg2.connect | PASS |
| Total user-schema tables | 36 |
| Connection timeouts / errors | none |

## 4. Champion-Family Object Inventory

```
public.champion_legacy_archive    BASE TABLE   (1564 rows)
public.champion_pipeline_fresh    BASE TABLE   (89 rows)
public.champion_pipeline_rejected BASE TABLE
public.champion_pipeline_staging  BASE TABLE
public.champion_pipeline_v9       VIEW
```

**No object named `public.champion_pipeline` exists** — neither table nor view. This matches the failure mode in §02.

## 5. Historical Context

The migration `zangetsu/migrations/postgres/v0.7.1_governance.sql` (applied 2026-04-20) performed:

```sql
ALTER TABLE champion_pipeline RENAME TO champion_legacy_archive;
```

…then created `champion_pipeline_fresh`, `champion_pipeline_staging`, `champion_pipeline_rejected`. It did NOT create a compatibility VIEW named `champion_pipeline`. That gap is what arena13_feedback (and any other reader still using the bare name) now hits.

## 6. arena23_orchestrator.py:336 Design Intent

```
# Trace-only A2/A3 pass events MUST NOT inflate
# deployable_count (P7-PR4B §9). Pass None so the
# authoritative source remains champion_pipeline VIEW.
```

→ The architecture explicitly references `champion_pipeline` as a VIEW. This order finally creates it.

## 7. Required Migration Shape

A non-destructive idempotent VIEW that aliases `champion_pipeline_fresh` (the active 89-row table). `champion_legacy_archive` is left out per v0.7.1 governance rule #1 ("Epoch A rows are read-only and never promoted / ranked / deployed") — a separate enhancement order can extend the VIEW to UNION legacy data if A13 guidance later needs it.

## 8. Phase C Verdict

PASS. DB connect works. Inventory confirms: `champion_pipeline` is the only missing piece. `champion_pipeline_fresh` already has every column arena13_feedback queries reference.
