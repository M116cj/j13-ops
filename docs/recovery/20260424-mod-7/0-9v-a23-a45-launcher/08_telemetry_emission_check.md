# 08 — Telemetry Emission Check

## 1. Files at Observation Time

| File | Status | Detail |
| --- | --- | --- |
| `zangetsu/logs/engine.jsonl` | WRITING | last `2026-04-26T09:57:17Z`, advancing on each A1 cron cycle |
| `zangetsu/logs/arena_batch_metrics.jsonl` | MISSING | A23 / A45 alive but waiting for upstream A1 candidates |
| `zangetsu/logs/sparse_candidate_dry_run_plans.jsonl` | MISSING | offline by design (PR #23) |

## 2. Why `arena_batch_metrics.jsonl` Is Still Missing

PR #18's emitter (`safe_emit_a2_batch_metrics` / `safe_emit_a3_batch_metrics` in `zangetsu/services/arena_pass_rate_telemetry.py`) is invoked from `arena23_orchestrator.py` at every 20-iteration window boundary of A2/A3 work. A2/A3 work happens only when A1 promotes candidates upstream.

Current A1 / A23 / A45 chain state:

| Stage | State | Output |
| --- | --- | --- |
| A1 (`arena_pipeline_w0..w3`) | cycling on cron `*/5`, ~30 s per cycle | regime classifications + alpha generation (event_queue) |
| `arena13_feedback.py` (cron) | crash-loop (out of scope env issue, separate order needed) | feedback events not landing |
| A23 (`arena23_orchestrator`) | alive, idle, waiting for events | none yet (no candidates promoted) |
| A45 (`arena45_orchestrator`) | alive, idle, waiting for events | "Daily reset complete: kept=0 retired=0" |
| A23 emit window | not yet reached (needs ≥ 20 A2/A3 iterations) | `arena_batch_metrics.jsonl` MISSING |

→ **A23 / A45 are correctly idle**, not crashing — but the upstream A1→A23 candidate flow is throttled by the `arena13_feedback.py` env issue (separate scope). A23 will emit the first `arena_batch_metrics.jsonl` line only after either:

1. The arena13_feedback env is also fixed (next order), OR
2. A1 directly publishes to the event queue and A23 reads ≥ 20 candidates from there.

## 3. Watch-Loop Evidence (5 × 30 s sampling)

```
09:53:39Z  arena_batch_metrics.jsonl: still missing
09:54:09Z  arena_batch_metrics.jsonl: still missing
09:54:39Z  arena_batch_metrics.jsonl: still missing
09:55:09Z  arena_batch_metrics.jsonl: still missing
09:55:39Z  arena_batch_metrics.jsonl: still missing

A23 (PID 207186): alive throughout
A45 (PID 207195): alive throughout
A23 last log:  "Service loop started"
A45 last log:  "Daily reset complete: kept=0 retired=0 across 0 regimes"
```

→ Orchestrators stay alive, no errors, no telemetry yet — exactly the documented `A23_A45_LAUNCHED_NO_TELEMETRY_YET` state.

## 4. `sparse_candidate_dry_run_plans.jsonl` — by design

PR #23's `feedback_budget_consumer` is offline-only (3-layer dry-run invariant). It is not imported by any of A1, A23, A45. It will produce this file only when a future dedicated dry-run consumer order runs the consumer offline against `arena_batch_metrics.jsonl`.

→ Missing is **the intended pre-CANARY state**, not a regression.

## 5. Telemetry Status Per Order §14

| Verdict | Match? |
| --- | --- |
| `READY_FOR_LIVE_OBSERVATION` (arena_batch_metrics.jsonl exists with real records) | NO |
| `ENGINE_RECOVERED_WAITING_FOR_ARENA_BATCH` (A1/A23/A45 alive, no batch yet) | YES |
| `A23_A45_LAUNCHED_NO_TELEMETRY_YET` (orchestrators alive, waiting for candidates) | **YES** ← exact match |
| `BLOCKED_NO_A23_A45` | NO (A23/A45 are alive) |
| `BLOCKED_RUNTIME_ERROR` | NO |

→ Status = **`A23_A45_LAUNCHED_NO_TELEMETRY_YET`** which maps to the order's allowed final status `COMPLETE_LAUNCHER_RESTORED_WAITING_FOR_BATCH`.

## 6. Phase I Verdict

→ **PASS-WITH-NOTE.** Launcher is restored. Telemetry waits on either next-order arena13_feedback env fix or upstream A1 candidate flow. No `BLOCKED_NO_A23_A45`, no `BLOCKED_RUNTIME_ERROR`.
