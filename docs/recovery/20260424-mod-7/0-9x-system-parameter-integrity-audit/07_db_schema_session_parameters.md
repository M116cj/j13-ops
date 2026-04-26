# 07 — DB Schema and Session Parameter Audit

## 1. Postgres Container

| Field | Value |
| --- | --- |
| Container | `deploy-postgres-1` (from `docker ps`) |
| DB | `zangetsu_v5` |
| User | `zangetsu` |
| Auth | `ZV5_DB_PASSWORD` env var |

## 2. Tables Present in `zangetsu_v5.public`

```
                List of relations
 Schema |        Name        | Type  |  Owner   
--------+--------------------+-------+----------
 public | champion_pipeline  | table | zangetsu
 public | paper_trades       | table | zangetsu
 public | pipeline_audit_log | table | zangetsu
 public | pipeline_state     | table | zangetsu
 public | trade_journal      | table | zangetsu
(5 rows)
```

## 3. Tables / Views EXPECTED BY VERSION_LOG v0.7.1 vs Current State

| Object | Type expected | Current state |
| --- | --- | --- |
| `champion_pipeline` | renamed to `champion_legacy_archive` | **STILL EXISTS as a TABLE** (not VIEW); 0 rows |
| `champion_pipeline_fresh` | new TABLE | **DOES NOT EXIST** |
| `champion_pipeline_staging` | new TABLE | **DOES NOT EXIST** |
| `champion_pipeline_rejected` | new TABLE | **DOES NOT EXIST** |
| `champion_legacy_archive` | renamed table | **DOES NOT EXIST** |
| `engine_telemetry` | new TABLE | **DOES NOT EXIST** |
| `champion_pipeline_v9` | (per order's checklist) | **DOES NOT EXIST** |
| `admission_validator(BIGINT)` plpgsql function | new | **DOES NOT EXIST** |
| `fresh_insert_guard` trigger | new | **DOES NOT EXIST** |
| `fresh_pool_outcome_health` view | new | **DOES NOT EXIST** |
| `fresh_pool_process_health` view | new | **DOES NOT EXIST** |

→ **Massive schema gap.** The `migrations/postgres/v0.7.1_governance.sql` migration appears NOT to have been applied to the live database.

## 4. Triggers

```
\dt+ (triggers)
 tgname | tgrelid 
--------+---------
(0 rows)
```

→ **No triggers.** Expected `archive_readonly_triggers` and `fresh_insert_guard` are absent.

## 5. Session Variables

```
SELECT name, setting FROM pg_settings WHERE name LIKE 'zangetsu%' OR name LIKE 'admission%';
 name | setting 
------+---------
(0 rows)
```

→ **No `zangetsu.admission_active` session variable.** The admission gating mechanism described in v0.7.1 is not present.

## 6. Row Counts

| Table | Rows | Newest timestamp |
| --- | --- | --- |
| `champion_pipeline` | **0** | (none — table empty) |
| `paper_trades` | not queried | n/a |
| `pipeline_audit_log` | not queried | n/a |
| `pipeline_state` | not queried | n/a |
| `trade_journal` | not queried | n/a |

## 7. Code Paths That Reference Non-Existent Objects

| Code line | Target | Failure mode |
| --- | --- | --- |
| `arena_pipeline.py:329` | `INSERT INTO engine_telemetry ...` | wrapped in `try/except ... pass` — **silently swallows error** |
| `arena_pipeline.py:685` | `FROM champion_pipeline_fresh` | error would raise; not currently reached (no candidates) |
| `arena_pipeline.py:821` | `FROM champion_pipeline_fresh` | same |
| `arena_pipeline.py:1127` | `INSERT INTO champion_pipeline_staging ...` | wrapped in `try/except: log + continue` — error logged + candidate skipped |
| `arena_pipeline.py:1167` | `SELECT admission_validator($1)` | same try/except |

→ **The full v0.7.1 governance pipeline is wired in code but the underlying DB objects do not exist.** Currently this has no observable user-facing failure because:
1. A1 candidates fail at `COUNTER_INCONSISTENCY` / `COST_NEGATIVE` before ever reaching the staging insert path
2. The `engine_telemetry` insert silently swallows exceptions
3. SELECTs from `champion_pipeline_fresh` happen during cron-driven dashboard scripts that may run with stderr redirection

This is **a hidden time bomb**: if the alpha generation suddenly produces valid candidates again, the pipeline will fail at the staging stage and they will all be lost.

## 8. Special Checks Per Order

| Check | Result |
| --- | --- |
| `champion_pipeline` is a VIEW | **NO — it is still a TABLE** (legacy state) |
| `champion_pipeline_staging` is correct write target | TABLE DOES NOT EXIST |
| `champion_pipeline_fresh` not directly injected | n/a — table doesn't exist |
| `admission_validator()` would not block staging incorrectly | n/a — function doesn't exist |
| No stale migration conflict | partial — v0.7.1 migration not applied; downstream code expects it applied |

## 9. Classification

| Verdict | Match? |
| --- | --- |
| DB_PARAMS_OK | NO |
| **DB_VIEW_RISK** | **YES** — `champion_pipeline_fresh` view (or table) is missing; code SELECTs reference it |
| DB_TRIGGER_RISK | YES — fresh_insert_guard trigger missing; admission_validator function missing |
| **ADMISSION_SETTING_RISK** | **YES** — `zangetsu.admission_active` session var absent; admission-active mechanism unenforceable |
| **DB_STALE_STATE** | **YES** — schema is at pre-v0.7.1; code expects post-v0.7.1 |
| DB_UNKNOWN | NO |

→ **Phase 7 verdict: DB_STALE_STATE + DB_VIEW_RISK + ADMISSION_SETTING_RISK.** Critical finding. The v0.7.1 governance migration was not applied to the live Postgres. Code references non-existent tables/functions; failures are currently masked by upstream rejection. **This is a primary cold-start blocker** — even if alpha generation produced valid candidates, none could be persisted.
