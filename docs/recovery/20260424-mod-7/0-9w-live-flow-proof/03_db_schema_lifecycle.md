# 03 — DB Schema and Lifecycle Audit (read-only SQL)

## 1. champion_pipeline VIEW Verification

| Field | Value |
| --- | --- |
| public.champion_pipeline | EXISTS |
| Type | **VIEW** |
| Source | created by zangetsu/db/migrations/20260426_create_champion_pipeline.sql (PR #34) |
| Underlying | public.champion_pipeline_fresh (51 columns, 89 rows) |
| Row count via VIEW | 89 (== underlying count) |

## 2. champion_pipeline_fresh Status Distribution

```sql
SELECT status, count(*) FROM public.champion_pipeline_fresh GROUP BY status ORDER BY count(*) DESC;
```

| status | count |
| --- | --- |
| **ARENA2_REJECTED** | **89** |

→ **All 89 rows are at `ARENA2_REJECTED`. Zero rows in CANDIDATE / DEPLOYABLE / ARENA1_* / ARENA3_* / ARENA4_* / post-arena buckets.**

## 3. Lifecycle Buckets

| Bucket | Count |
| --- | --- |
| ARENA1_* (READY/PROCESSING/COMPLETE/REJECTED) | 0 |
| ARENA2_* (READY/PROCESSING/COMPLETE/REJECTED) | 89 (all REJECTED) |
| ARENA3_* (READY/PROCESSING/COMPLETE/REJECTED) | 0 |
| ARENA4_* (READY/PROCESSING/ELIMINATED) | 0 |
| post-arena (CANDIDATE/DEPLOYABLE/ELO_*/EVOLVING/EVOLVED/DEAD_LETTER) | 0 |

## 4. Timestamp Freshness

```sql
SELECT max(created_at), max(updated_at) FROM public.champion_pipeline_fresh;
```

| Field | Value |
| --- | --- |
| max(created_at) | **2026-04-21T04:34:21Z** |
| max(updated_at) | **2026-04-22T17:57:10Z** |
| Age of newest row at observation (12:04Z) | 5d 19h 30m |

## 5. Activity After PR #34 Merge (2026-04-26T11:36:04Z)

```sql
SELECT count(*) FROM public.champion_pipeline_fresh
WHERE updated_at > '2026-04-26T11:36:04Z'::timestamptz;
SELECT count(*) FROM public.champion_pipeline_fresh
WHERE created_at > '2026-04-26T11:36:04Z'::timestamptz;
```

| Metric | Count |
| --- | --- |
| rows updated after PR #34 merge | **0** |
| rows created after PR #34 merge | **0** |

## 6. Activity After A1 Workers Came Alive (2026-04-26T09:52Z, post-PR-#31)

```sql
SELECT count(*) FROM public.champion_pipeline_staging
WHERE created_at > '2026-04-26T09:52Z'::timestamptz;
```

| Metric | Count |
| --- | --- |
| staging rows created since A1 alive | **0** |

→ A1 has been actively cycling for **2h 12m+** but has not written **any** new row to either staging or fresh.

## 7. Staging + Rejected Tables

| Table | Count | Composition |
| --- | --- | --- |
| champion_pipeline_staging | 184 | admitted=89, admitted_duplicate=95 |
| champion_pipeline_rejected | 0 | (no rejection forensics) |
| Staging max created_ts | 2026-04-21T04:34:21Z | (pre-dates ALL the V/W repair orders) |

## 8. engine_telemetry Activity

| Metric | Value |
| --- | --- |
| max(ts) | NULL (table is empty) |
| count after A1 alive (09:52Z) | 0 |

## 9. Phase 3 Classification

Per order §16:

| Verdict | Match? |
| --- | --- |
| DB_FLOW_ACTIVE (fresh rows appearing, candidate-relevant status exists) | NO |
| DB_FLOW_COLD (tables exist, no new rows, no error) | partial — tables exist but the 89 existing rows pre-date the order |
| DB_FLOW_STALLED (no fresh rows despite A1 cycling) | **YES** |
| DB_FLOW_BLOCKED (schema/permission/query error) | NO (queries succeed) |
| DB_FLOW_DEGRADED (rows exist but only ERROR/rejected/malformed) | **YES** (89/89 = ARENA2_REJECTED) |

→ **Combined verdict: DB_FLOW_STALLED + DB_FLOW_DEGRADED.**

The system has historical (pre-Apr-22) failure evidence (89 rows that all rejected at Arena 2) and zero fresh activity for 5+ days despite A1 cycling for 2h+ today.
