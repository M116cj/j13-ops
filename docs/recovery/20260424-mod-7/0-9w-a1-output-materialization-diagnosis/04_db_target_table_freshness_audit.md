# 04 — DB Target Table Freshness Audit

## 1. Read-Only SQL Probe Results

| Table | Row count | max(created_at) or max(ts) |
| --- | --- | --- |
| `public.champion_pipeline_staging` | 184 | 2026-04-21T04:34:21Z |
| `public.champion_pipeline_fresh` | 89 | created_at 2026-04-21T04:34:21Z; updated_at 2026-04-22T17:57:10Z |
| `public.champion_pipeline_rejected` | 0 | n/a |
| `public.champion_pipeline_v9` | (VIEW; not counted independently) | n/a |
| `public.champion_legacy_archive` | 1564 | (read-only Epoch A archive) |
| `public.engine_telemetry` | **0 (empty)** | NULL |

## 2. Activity After A1 Workers Came Alive (PR #31, 2026-04-26T09:42:45Z)

| Metric | Count |
| --- | --- |
| `champion_pipeline_staging` rows created after 09:52Z | **0** |
| `champion_pipeline_fresh` rows created after 09:52Z | **0** |
| `champion_pipeline_fresh` rows updated after 09:52Z | **0** |
| `champion_pipeline_rejected` rows created after 09:52Z | **0** |
| `engine_telemetry` rows after 09:52Z | **0** |

→ **Zero materialization in any target table since A1 restart 2h 35m+ ago.**

## 3. Where Should A1 Write First?

Per `arena_pipeline.py:1117-1158`: A1 writes first to **`champion_pipeline_staging`** with `status='ARENA1_COMPLETE'`. Then `admission_validator(staging_id)` decides whether the row is also inserted into `champion_pipeline_fresh`.

→ Expected first-write target: `champion_pipeline_staging`.

## 4. Where Is A1 Actually Writing?

| Target | A1 wrote there since 09:52Z? |
| --- | --- |
| `champion_pipeline_staging` | NO |
| `champion_pipeline_fresh` | NO (and would be guarded anyway) |
| `champion_pipeline_rejected` | NO |
| `champion_pipeline_v9` | (it's a VIEW; not directly writable) |
| `champion_legacy_archive` | NO (read-only triggers raise) |
| `engine_telemetry` | NO |
| Any other table | none observed |

→ **A1 is writing nowhere.** Consistent with the line-1218 crash documented in 02 — the loop terminates before any INSERT runs.

## 5. Cross-Check: engine.jsonl IS Writing

`zangetsu/logs/engine.jsonl` last write at 2026-04-26T12:27:14Z (40 MB). This is the file-based emit (e.g. ENTRY events from `_emit_a1_lifecycle_safe` at line 944, which fires BEFORE the line-1218 crash). So filesystem writes work; only DB writes are missing.

## 6. Phase 4 Classification

Per order §9:

| Verdict | Match? |
| --- | --- |
| **DB_TARGET_STAGING_EMPTY** (no fresh writes to staging despite A1 cycling) | **YES — exact match** |
| DB_TARGET_NO_RECENT_WRITES_ANYWHERE | YES (also true) |
| DB_TARGET_WRITING_TO_UNEXPECTED_TABLE | NO (A1 writes nowhere; not redirected) |
| DB_TARGET_REJECTED_ONLY | NO (rejected table is empty) |
| DB_TARGET_PERMISSION_BLOCK | NO (no permission errors in log) |
| DB_TARGET_UNKNOWN | NO |

→ **Phase 4 verdict: DB_TARGET_STAGING_EMPTY** (closest single match; secondary truth: no recent writes anywhere).
