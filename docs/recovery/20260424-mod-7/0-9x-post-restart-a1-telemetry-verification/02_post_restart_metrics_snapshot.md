# 02 — Post-Restart Metrics Snapshot (Phase 3)

**Phase 3 Verdict:** `NEW_METRICS_COLLECTED`

## Window

| Field | Value |
|---|---|
| Worker boot (UTC) | 2026-04-27T17:02:16Z |
| First arena_batch_metrics | 2026-04-27T17:04:02Z |
| Snapshot end (parser run) | 2026-04-27T17:09:50Z |
| Window length | ~5 min 48 s |
| Threshold (order) | ≥ 20 batches OR 15 min |
| Threshold reached | **Batches** (`96 ≥ 20`) |

## Cursor / source

- Log file: `/home/j13/j13-ops/zangetsu/logs/engine.jsonl` (rotated at 17:02 restart, so the entire file is post-restart)
- Snapshot copy: `/tmp/0_9x_post_restart_new_engine.jsonl` (2191 lines, 755 KB)
- Cursor recorded: `/tmp/0_9x_post_restart_start_lines.txt` = 1960 (mid-window — **not** the parsing baseline because the file rotated post-restart and all lines are already post-restart; entire file consumed by parser)
- Cursor timestamp: `/tmp/0_9x_post_restart_start_time.txt` = `2026-04-27T17:09:11Z`

> Why entire file is used as window: `engine.jsonl.1` (the previous rotation) has mtime `2026-04-27 17:02`, matching the restart instant — confirming the live `engine.jsonl` was created at workers' boot and contains only post-restart events.

## New batch count

`grep -c arena_batch_metrics engine.jsonl` → **96** events at parse time (88 at first observation 30 s earlier; rate ≈ 16 batches/min).

## Aggregate reject distribution

```json
{
  "COST_NEGATIVE":      936,
  "SIGNAL_TOO_SPARSE":   20,
  "LOW_BACKTEST_SCORE":   4
}
```

Sum = 960 = 96 batches × 10 alphas/batch (every batch `entered_count = 10`).

| Bucket | Count | Notes |
|---|---|---|
| **COUNTER_INCONSISTENCY** | **0** | Pre-fix this would have absorbed ≈50% of the distribution |
| **UNKNOWN_REJECT** | **0** | PR #49 taxonomy maps every observed reason to a canonical bucket |
| Canonical buckets visible | 3 (`COST_NEGATIVE`, `SIGNAL_TOO_SPARSE`, `LOW_BACKTEST_SCORE`) | All from `RejectionReason` enum |

## Sample events

### First observed batch (17:04:02Z)

```json
{"arena_stage": "A1", "batch_id": "R271801-LINKUSDT-BULL_TREND",
 "entered_count": 10, "passed_count": 0, "rejected_count": 10, "skipped_count": 0,
 "reject_reason_distribution": {"COST_NEGATIVE": 10},
 "top_reject_reason": "COST_NEGATIVE",
 "event_type": "arena_batch_metrics",
 "generation_profile_id": "gp_541a313e770c4424",
 "telemetry_version": "1"}
```

### Latest observed batch (17:09:50Z)

```json
{"arena_stage": "A1", "batch_id": "R328723-DOTUSDT-BEAR_RALLY",
 "entered_count": 10, "passed_count": 0, "rejected_count": 10, "skipped_count": 0,
 "reject_reason_distribution": {"COST_NEGATIVE": 10},
 "top_reject_reason": "COST_NEGATIVE",
 "event_type": "arena_batch_metrics",
 "generation_profile_id": "gp_26f478846fd0f729",
 "telemetry_version": "1"}
```

Two distinct `generation_profile_id` values observed (`gp_541a313e770c4424`, `gp_26f478846fd0f729`) corresponding to the two strategy lanes (j01 baseline vs j02 exploration).

## Phase 3 Classification

```
NEW_METRICS_COLLECTED
```

| Required field | Recorded |
|---|---|
| start time | 17:02:16Z (worker boot) |
| end time | 17:09:50Z (parser run) |
| log line cursor | engine.jsonl whole-file (rotated at restart) |
| number of new batches | 96 |
| aggregate reject distribution | `{COST_NEGATIVE: 936, SIGNAL_TOO_SPARSE: 20, LOW_BACKTEST_SCORE: 4}` |
| COUNTER_INCONSISTENCY count | 0 |
| UNKNOWN_REJECT count | 0 |
| canonical bucket counts | 3 distinct canonical buckets |
| sample events | first + last shown above |
