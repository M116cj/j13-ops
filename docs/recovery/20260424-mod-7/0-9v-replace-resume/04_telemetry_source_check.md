# 04 — Telemetry Source Check

## 1. Telemetry Files

| File | Status | Size | Lines | Last write |
| --- | --- | --- | --- | --- |
| `zangetsu/logs/arena_batch_metrics.jsonl` | **MISSING** | — | — | — |
| `zangetsu/logs/sparse_candidate_dry_run_plans.jsonl` | **MISSING** | — | — | — |
| `zangetsu/logs/engine.jsonl` | present | 37 MB | (308579 prior) | `2026-04-23T00:35Z` (arena pipeline stopped) |
| `zangetsu/logs/engine.jsonl.1` | present | 2.5 MB | (14213 prior) | `2026-04-16T04:25Z` (rotated) |
| `zangetsu/logs/dashboard.log` | present | 316 B | — | `2026-04-11T06:01Z` |
| `zangetsu/logs/pipeline-v2.log` | present | 8.9 KB | — | `2026-04-16T14:45Z` |
| `zangetsu/logs/r2_n4_watchdog.stdout` | present | 4.5 KB | — | `2026-04-22T19:56Z` |

## 2. Diagnosis

### `arena_batch_metrics.jsonl` (MISSING)

PR #18 introduced the `ArenaBatchMetrics` dataclass and emission helpers (`safe_emit_a2_batch_metrics` / `safe_emit_a3_batch_metrics`) in `zangetsu/services/arena_pass_rate_telemetry.py`. The orchestrator (`arena23_orchestrator.py`) calls these at every 20-iteration window boundary.

The file does not yet exist because:

1. The arena pipeline (`arena_pipeline.py` + `arena23_orchestrator`) **stopped at 2026-04-23T00:35Z** — before PR #18 was deployed.
2. The post-PR-#18 code is now on disk (since 0-9V-CLEAN fast-forward to `5ab95bfe` → squash to `41796663`), but the running process never started under the new code.
3. The emitter is invoked only on a 20-iteration boundary — so even after a restart, the first arena_batch_metrics line will land only when the pipeline finishes its first window of A2/A3 work.

→ **MISSING is the expected pre-replacement state.** Replacement (Phase G) is the action that enables telemetry emission going forward.

### `sparse_candidate_dry_run_plans.jsonl` (MISSING)

PR #23 introduced `feedback_budget_consumer.py` which produces `SparseCandidateDryRunPlan` events. The consumer is:

- Not imported by any generation-runtime entry point (verified in 03 §4).
- Invoked only via the future 0-9R-IMPL run script (which was deferred to a separate order).

→ **MISSING is structurally expected** — no consumer is wired into the runtime, so no plans are emitted. This will remain MISSING until a separate dedicated dry-run consumer order is run.

## 3. Will Replacement Resolve This?

| Question | Answer |
| --- | --- |
| Will runtime replacement (Phase G watchdog restart) start emitting `arena_batch_metrics.jsonl`? | **YES** (within ~20 iterations of the first arena window after the pipeline restarts on `41796663` code) |
| Will runtime replacement start emitting `sparse_candidate_dry_run_plans.jsonl`? | **NO** (consumer is not in the generation runtime; that's by design. Plans are only produced by the offline consumer tool. A separate order is required to start that.) |

## 4. Enough Telemetry for Live Observation Now?

| Field | Value |
| --- | --- |
| Enough for shadow observer dry-run with real Alaya data | **NO** (both inputs missing) |
| Enough for `0-9S-CANARY-OBSERVE-LIVE` | **NO** (still requires `arena_batch_metrics.jsonl` to be written by the running pipeline first) |
| Replacement still safe to proceed | YES — replacement is the **prerequisite** for telemetry, not the consequence |

## 5. Phase D Verdict

→ **PASS-WITH-NOTE.** Telemetry sources are documented MISSING. This is a known structural state (pipeline stopped, consumer not in runtime) — not a regression. Shadow validation will be SHADOW_BLOCKED_MISSING_TELEMETRY (non-blocking per order §9). Replacement may proceed.
