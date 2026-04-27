# 12 — Monitoring Plan + First Snapshot

## First Monitoring Snapshot (post-migration)

Timestamp: `2026-04-27T06:44:28Z`

### DB Object Status & Row Counts

```json
{
  "champion_pipeline": 0,
  "champion_pipeline_staging": 0,
  "champion_pipeline_fresh": 0,
  "champion_pipeline_rejected": 0,
  "champion_legacy_archive": 0,
  "engine_telemetry": 0,
  "snapshot_ts_utc": "2026-04-27T06:44:28Z"
}
```

### Engine Log Latest Entries
```
{"ts": "2026-04-27T06:40:01", "level": "INFO", "msg": "Arena 13 Feedback complete (single-shot)"}
{"ts": "2026-04-27T06:40:01", "level": "INFO", "msg": "A13 guidance MODE=observe | survivors=0 failures=0 cool_off=0"}
```

### A1/A23/A45 Process Status
- 0 arena worker processes alive (cold-boot gap, documented in Phase J)

### arena_batch_metrics Existence
- File: `/home/j13/j13-ops/zangetsu/logs/engine.jsonl` (active write — A13 cron)
- No A1 batch metrics since reboot (workers not running)

### Schema-Related Errors
- 0 schema errors observed in engine.jsonl post-migration

## 24h Monitoring Metrics

| Metric | Source | Threshold |
| --- | --- | --- |
| `champion_pipeline.count` (VIEW over fresh) | `SELECT count(*) FROM champion_pipeline` | growing > 0 once cold-boot resolved |
| `champion_pipeline_staging.count` | direct table | > 0 once A1 produces valid candidates |
| `champion_pipeline_fresh.count` | direct table | > 0 once admission_validator promotes |
| `champion_pipeline_rejected.count` | direct table | > 0 if any candidate fails 3 gates (expected normal) |
| schema errors per hour | grep `schema|relation does not exist` from engine.jsonl | ≤ 1 (transient noise OK) |
| admission guard errors per hour | grep `fresh_insert_guard|admission_active` | 0 (any > 0 is bug) |
| A1 crash count | grep `Traceback|UnboundLocalError|RaiseError` | 0 (any > 0 is regression) |
| A23/A45 idle vs active | log mtime delta | active when fresh.count > 0 |
| arena_batch_metrics lines per hour | engine.jsonl event_type='arena_batch_metrics' | growing once A1 alive |

## Monitoring Cadence
- T+5min, T+15min, T+1h, T+4h, T+12h, T+24h post-cold-boot-recovery

## Action Triggers

| Observation | Action |
| --- | --- |
| 0 schema errors after cold-boot | GREEN — migration successful in production |
| ≥ 1 admission guard error after cold-boot | RED — investigate; potential rollback |
| ≥ 1 A1 crash after cold-boot | RED — investigate; potential rollback |
| `champion_legacy_archive` row count changes | RED — should be permanently 0 (read-only triggers active) |
| Engine.jsonl growth rate stable | GREEN |

## First Snapshot Verdict

→ **MONITORING_BASELINE_ESTABLISHED.** Schema is clean, all tables zero-row, no errors. Awaiting cold-boot recovery (separate order) to begin observing live A1 candidate flow through staging → admission_validator → fresh.
