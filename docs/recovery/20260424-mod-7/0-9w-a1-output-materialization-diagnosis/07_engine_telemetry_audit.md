# 07 — Engine Telemetry Audit

## 1. engine.jsonl Writer Path

| Field | Value |
| --- | --- |
| Path | `zangetsu/logs/engine.jsonl` |
| Writer | `_emit_a1_lifecycle_safe` and other engine-event emit helpers in `arena_pipeline.py` |
| Status | **WRITING** (40+ MB, last write 2026-04-26T12:27:14Z) |
| Trigger | per-candidate ENTRY events fire BEFORE the line-1218 crash, so they reach disk |

## 2. engine_telemetry DB Writer Path

| Field | Value |
| --- | --- |
| SQL | `INSERT INTO engine_telemetry (run_id, worker_id, strategy_id, metric_name, value) VALUES ($1, $2, $3, $4, $5)` (line 329 of arena_pipeline.py) |
| Caller | `_flush_telemetry(db)` |
| Invocation point | line 1167 of arena_pipeline.py — **inside the per-candidate INSERT try-block** (after admission_validator returns) |
| Status | **EMPTY** (0 rows since A1 alive at 09:52Z; table is completely empty per Phase 4) |

## 3. Why engine_telemetry Is Empty

`_flush_telemetry` runs at line 1167, immediately AFTER:

1. line 1117 — INSERT INTO champion_pipeline_staging (succeeds → returns staging_id)
2. line 1160 — SELECT admission_validator(staging_id) (returns 'admitted' or 'rejected:...')
3. line 1162-1166 — `_telemetry_counters['admitted_count' / 'rejected_count'] += 1`
4. line 1167 — `await _flush_telemetry(db)`

Because **no candidate passes all 9 val gates** (per Phases 1-5), the inner block at lines 1117+ is never entered, so `_flush_telemetry` is never called. As a consequence, `engine_telemetry` stays empty.

## 4. Are engine.jsonl and engine_telemetry the Same Path?

NO — they are **separate emission paths**:

| Layer | engine.jsonl | engine_telemetry table |
| --- | --- | --- |
| Sink | filesystem (JSONL append) | PostgreSQL row INSERT |
| Trigger | per-candidate lifecycle events (ENTRY, EXIT, etc.) | per-batch metric counters (admitted_count, rejected_count, etc.) |
| Position in main loop | BEFORE the val-filter chain (line 944 ENTRY emit) | AFTER successful staging INSERT (line 1167) |
| Crash impact | unaffected by line-1218 crash (already wrote ENTRY) | never reached when no candidate passes val gates |

→ engine.jsonl writes ENTRY events, then the loop crashes, then the worker dies. engine_telemetry never gets written because it lives downstream of the unreached INSERT.

## 5. Is engine_telemetry Emptiness Root Cause or Symptom?

**Symptom.** It is downstream of the same ROOT CAUSE that prevents staging INSERTs (per 02 and 04). Repairing the line-1218 `_pb` bug AND ensuring at least one candidate passes val gates would unblock both staging writes AND engine_telemetry writes simultaneously.

## 6. Phase 7 Classification

Per order §12:

| Verdict | Match? |
| --- | --- |
| ENGINE_TELEMETRY_EXPECTED_EMPTY (legacy/deprecated and intentionally unused) | NO (it's actively written by `_flush_telemetry` per source) |
| ENGINE_TELEMETRY_DISABLED | NO |
| ENGINE_TELEMETRY_WRITE_PATH_BROKEN | NO (the path is intact; just never reached) |
| ENGINE_TELEMETRY_BLOCKED_BY_DB_SETTING | NO (no admission guard on engine_telemetry table) |
| ENGINE_TELEMETRY_EXCEPTION_SWALLOWED | NO (no exception traceback in worker logs concerning engine_telemetry) |
| **ENGINE_TELEMETRY_SECONDARY_SYMPTOM** | **YES — exact match** (empty because the upstream INSERT never runs) |
| ENGINE_TELEMETRY_UNKNOWN | NO |

→ **Phase 7 verdict: ENGINE_TELEMETRY_SECONDARY_SYMPTOM.** Empty engine_telemetry is a downstream consequence of the line-1218 source bug; not an independent issue.
