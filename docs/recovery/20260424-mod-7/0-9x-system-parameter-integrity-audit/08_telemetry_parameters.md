# 08 — Telemetry and Evidence Parameter Audit

## 1. File-Based Telemetry Inventory

| Source | Path | Size | Latest mtime | Status |
| --- | --- | --- | --- | --- |
| `engine.jsonl` | `zangetsu/logs/engine.jsonl` | 3.2 MB | 2026-04-26T17:32Z | **WRITING** (active) |
| A1 worker 0 log | `/tmp/zangetsu_a1_w0.log` | 11.5 MB | 2026-04-26T17:32Z | WRITING |
| A1 worker 1 log | `/tmp/zangetsu_a1_w1.log` | 11.4 MB | 2026-04-26T17:32Z | WRITING |
| A1 worker 2 log | `/tmp/zangetsu_a1_w2.log` | 11.3 MB | 2026-04-26T17:32Z | WRITING |
| A1 worker 3 log | `/tmp/zangetsu_a1_w3.log` | 11.6 MB | 2026-04-26T17:32Z | WRITING |
| A23 log | `/tmp/zangetsu_a23.log` | 4.1 KB | 2026-04-26T09:53Z | **STALE** (8h since last write) |
| A45 log | `/tmp/zangetsu_a45.log` | 4.2 KB | 2026-04-26T09:53Z | **STALE** (8h since last write) |
| A13 feedback log | `/tmp/zangetsu_arena13_feedback.log` | (not sized) | continuously | WRITING (every */5 min cron) |
| v9 metrics report | `/tmp/v10_factor_zoo_latest.md` | 246 B | 2026-04-26T17:15Z | tiny — likely empty stats |
| v10 alpha IC report | `/tmp/v10_alpha_ic_latest.md` | 246 B | 2026-04-26T16:45Z | tiny |

A23/A45 staleness is consistent with empty `champion_pipeline` (no candidates to process). Not a defect, but indicates the pipeline is not flowing end-to-end.

## 2. Database-Backed Telemetry

| Telemetry sink | Status |
| --- | --- |
| `engine_telemetry` table | **MISSING** (Phase 7); inserts silently fail at `arena_pipeline.py:329` |
| `arena_batch_metrics` events | emitted to `/tmp/zangetsu_a1_*.log` only (file-based fallback, not DB-persisted) |

## 3. A1 Stats Line Format

Per recent log sample:

```json
{
  "arena_stage": "A1",
  "batch_id": "R50384-XRPUSDT-CONSOLIDATION",
  "deployable_count": null,
  "entered_count": 10,
  "error_count": 0,
  "event_type": "arena_batch_metrics",
  "generation_profile_fingerprint": "sha256:26f478846fd0f72913ffb27a9fe6c4622d1fc5d25e7ae50e38ad4e88d707e4d2",
  "generation_profile_id": "gp_26f478846fd0f729",
  "in_flight_count": 0,
  "pass_rate": 0.0,
  "passed_count": 0,
  "reject_rate": 1.0,
  "reject_reason_distribution": {
    "COST_NEGATIVE": 9319,
    "COUNTER_INCONSISTENCY": 9330,
    "INVALID_FORMULA": 1,
    "SIGNAL_TOO_SPARSE": 20
  },
  "rejected_count": 18670,
  "run_id": "",
  "skipped_count": 0,
  "source": "arena_pipeline",
  "telemetry_version": "1",
  "timestamp_end": "2026-04-26T17:31:34Z",
  "timestamp_start": "2026-04-26T17:31:34Z",
  "top_reject_reason": "COUNTER_INCONSISTENCY"
}
```

Schema is parseable. `generation_profile_id` and `generation_profile_fingerprint` are populated. `run_id` is empty (suggests provenance stub not fully wired or strict-mode disabled).

## 4. A13 Feedback Log Format

```json
{"ts": "2026-04-26T17:30:02", "level": "INFO", "msg": "A13 guidance MODE=observe | survivors=0 failures=0 cool_off=0 | top: tsi=2.0, macd=2.0, zscore=1.8 | bot: rsi=1.0, stochastic_k=1.0, obv=1.0"}
```

A13 reports 0 survivor indicator-uses → falls back to BASE_WEIGHTS. Mode is observe (no live mutation of generation).

## 5. Required for Cold-Start

| Telemetry | Required for cold-start | Available? |
| --- | --- | --- |
| `arena_batch_metrics` reject_reason_distribution | YES | YES (file-based) |
| `engine_telemetry` per-metric counters | YES (deployable_count provenance) | **NO — table missing** |
| `generation_profile_fingerprint` | YES (genealogy) | YES |
| A1 candidate lifecycle events | YES | YES (file-based) |
| Provenance bundle (engine_version, git_commit, config_hash, etc.) | YES per v0.7.1 | partially — code computes these but cannot persist (table missing) |

## 6. Required for CANARY

| Telemetry | Required for CANARY | Available? |
| --- | --- | --- |
| Per-trade execution log | YES | not assessed (out of scope for this audit) |
| Live PnL telemetry | YES | not assessed |
| `paper_trades` and `trade_journal` tables | YES | both present |

## 7. Malformed Line Handling

A1 logs intersperse `INFO` python logging output and JSON envelope `{"ts": ..., "msg": "..."}` — both forms parseable but require different parsers. No malformed lines observed in sampled output.

## 8. Classification

| Verdict | Match? |
| --- | --- |
| TELEMETRY_OK | partial — file-based telemetry intact |
| **TELEMETRY_MISSING_EXPECTED** | **YES** — `engine_telemetry` DB table missing; provenance bundle cannot persist |
| TELEMETRY_SCHEMA_GAP | partial — `run_id` field empty in A1 stats; signals provenance not fully wired |
| TELEMETRY_STALE | partial — A23/A45 logs stale (consistent with empty pipeline, not stale telemetry per se) |
| TELEMETRY_UNKNOWN | NO |

→ **Phase 8 verdict: TELEMETRY_MISSING_EXPECTED.** File-based telemetry covers most needs but the DB-backed `engine_telemetry` is missing. This compounds the Phase 7 schema gap — both finding require the v0.7.1 migration to be applied before cold-start is safe.
