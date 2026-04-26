# 07 — Telemetry Emission Check

## 1. Files

| File | Status (post-repair) | Notes |
| --- | --- | --- |
| `zangetsu/logs/engine.jsonl` | **WRITING** (last write `2026-04-26T09:04:52Z`, advancing) | A1 engine producer running |
| `zangetsu/logs/arena_batch_metrics.jsonl` | MISSING | requires A23 orchestrator (separate launcher question; out of scope of this order) |
| `zangetsu/logs/sparse_candidate_dry_run_plans.jsonl` | MISSING | offline consumer by design (PR #23); requires a separate dry-run orchestrator order |

## 2. Diagnosis

### `engine.jsonl` advancing — PR-relevant outcome

The A1 generation pipeline (`arena_pipeline.py`) is the engine's primary writer. With env injection repaired, A1 reaches the engine loop and writes JSONL events. This is the direct, measurable outcome of the env-config repair.

### `arena_batch_metrics.jsonl` still missing — separate scope

PR #18's `arena_batch_metrics` emitter lives in `arena23_orchestrator.py`. The watchdog manages A23 only when `/tmp/zangetsu/arena23_orchestrator.lock` exists, which is not the case currently:

```
$ ls /tmp/zangetsu/*.lock
/tmp/zangetsu/arena_pipeline_w0.lock
/tmp/zangetsu/arena_pipeline_w1.lock
/tmp/zangetsu/arena_pipeline_w2.lock
/tmp/zangetsu/arena_pipeline_w3.lock
/tmp/zangetsu/calcifer_supervisor.lock
```

A23 / A45 orchestrators were noted as STOPPED with "unknown launcher" in PR #28 evidence. Restoring their launch path is a launcher-orchestration question (e.g. add cron line, manual lockfile creation, or systemd unit), which is **separate** from environment-config repair and outside this order's mission.

### `sparse_candidate_dry_run_plans.jsonl` still missing — by design

PR #23's `feedback_budget_consumer` is offline-only by design (3-layer dry-run invariant: never imported by generation runtime). This file will only appear when a future dedicated dry-run consumer order runs the consumer offline against `arena_batch_metrics.jsonl`.

## 3. Telemetry Status

Per order §15 classification:

> "arena_batch_metrics missing but engine loop now alive: telemetry_status = `ENGINE_RECOVERED_WAITING_FOR_ARENA_BATCH`"

Engine loop is alive (engine.jsonl advancing). `arena_batch_metrics.jsonl` is missing. This matches the order's defined intermediate status:

→ **`ENGINE_RECOVERED_WAITING_FOR_ARENA_BATCH`** (with sub-condition: A23 orchestrator is not currently being launched; needs a separate launcher order).

## 4. Phase J Verdict

→ **PASS-WITH-NOTE.** Engine loop recovered (the order's primary success criterion). `arena_batch_metrics.jsonl` missing is documented and traced to A23 launcher path, not an env-config issue. Sparse-candidate consumer file missing is by design.
