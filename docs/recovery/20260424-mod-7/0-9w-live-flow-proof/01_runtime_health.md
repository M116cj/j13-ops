# 01 — Runtime Health Proof

## 1. Process Snapshot

```
ps -ef | grep -E '(arena_pipeline|arena23_orchestrator|arena45_orchestrator|arena13_feedback)' | grep -v grep
```

| Service | PID | Wall time at observation | CPU | State |
| --- | --- | --- | --- | --- |
| arena23_orchestrator | 207186 | 2h 12m+ | low (idle daemon) | ALIVE_IDLE |
| arena45_orchestrator | 207195 | 2h 12m+ | low (idle daemon) | ALIVE_IDLE |
| arena_pipeline_w0..w3 | 482426 / 482435 / 482447 / 482461 | ~14 s into current cycle | 99% | ALIVE (cycling) |
| HTTP APIs | unchanged from prior orders | days | low | ALIVE (UNTOUCHED) |
| arena13_feedback | exits cleanly per cycle | n/a | n/a | working |

## 2. engine.jsonl Freshness

| Field | Value |
| --- | --- |
| Last write | 2026-04-26T12:05:06Z (just before this snapshot) |
| Size | 40 130 600 B |
| Status | **WRITING** |

## 3. A1 Worker Logs (latest activity)

| Worker | Log mtime | Latest line excerpt |
| --- | --- | --- |
| /tmp/zangetsu_a1_w0.log | 2026-04-26T12:06:26Z | "Indicator cache built for XRPUSDT: 110 arrays (holdout)" |
| /tmp/zangetsu_a1_w1.log | 2026-04-26T12:06:25Z | "Indicator cache built for DOGEUSDT: 110 arrays (holdout)" |
| /tmp/zangetsu_a1_w2.log | 2026-04-26T12:06:28Z | RuntimeWarning: overflow encountered in numpy reduce |
| /tmp/zangetsu_a1_w3.log | 2026-04-26T12:06:28Z | RuntimeWarning: overflow encountered in numpy reduce |

→ A1 workers are actively building indicator caches and running regime classification. No KeyError, no missing-table error. Two workers (w2, w3) emit numpy overflow RuntimeWarnings — these are non-fatal and do not block A1's main loop.

## 4. A13 Feedback Cron Activity (latest 4 cycles)

```
2026-04-26T11:55:01  Arena 13 Feedback complete (single-shot)
2026-04-26T12:00:01  Arena 13 Feedback complete (single-shot)
2026-04-26T12:05:02  Arena 13 Feedback complete (single-shot)
```

→ feedback log is CLEAN.

## 5. Recent Runtime Errors

| Source | Error pattern (post-PR-#34) | Count |
| --- | --- | --- |
| /tmp/zangetsu_arena13_feedback.log | KeyError ZV5_DB_PASSWORD | 0 |
| /tmp/zangetsu_arena13_feedback.log | relation does not exist | 0 |
| /tmp/zangetsu_a1_w*.log | KeyError ZV5_DB_PASSWORD | 0 |
| /tmp/zangetsu_a1_w2/w3.log | numpy RuntimeWarning (overflow in reduce) | non-zero (non-fatal) |
| /tmp/zangetsu_a23.log | KeyError | 0 since 09:52Z |
| /tmp/zangetsu_a45.log | KeyError | 0 since 09:52Z |

## 6. Phase 1 Classifications

| Field | Value |
| --- | --- |
| A1 status | **ACTIVE** (cycling, building caches, processing regimes) |
| A23 status | **ALIVE_IDLE** |
| A45 status | **ALIVE_IDLE** |
| engine.jsonl | **WRITING** |
| feedback log | **CLEAN** |

## 7. Phase 1 Verdict

PASS. No STOP conditions triggered (no A1 dead, no KeyError recurrence, no missing-table recurrence, no A23/A45 crash-loop, no secret exposure). Daemons are alive; A1 is actively cycling.
