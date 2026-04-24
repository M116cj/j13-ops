# 02 — Arena Pass-Rate Telemetry Contract

TEAM ORDER 0-9N §9.2 + §12 deliverable.

## 1. Purpose

Define the minimal aggregate telemetry the black-box Alpha Engine needs to optimize
against. This contract replaces the previous P7-PR2/P7-PR3 goal of FULL per-candidate
provenance with **Arena-level pass-rate provenance**. j13 explicitly accepts that
alpha internals remain black-box; only Arena pass/reject aggregates are required
to be observable.

## 2. Non-negotiable contract properties

- **Additive-only** — must not change Arena decision logic.
- **Aggregate** — emitted per batch + per stage, NOT per-candidate in the primary path.
- **Exception-safe** — emission failure must never alter Arena pass/fail behavior.
- **Deterministic** — same input → same counters (modulo real-time clock skew).
- **JSON-serializable** — consumable by existing LifecycleTraceEvent stream OR a
  parallel ArenaBatchMetric stream.
- **Reuses canonical rejection vocabulary** from `arena_rejection_taxonomy.py` (P7-PR1).
- **Not lineage** — does not require candidate_id → parent mapping.

## 3. Schema — `arena_batch_metrics` (per batch, per stage)

```json
{
  "event_type": "arena_batch_metrics",
  "run_id": "zangetsu-run-2026-05-01T00:00:00Z",
  "batch_id": "batch-42",
  "generation_profile_id": "gp_v10_volume_l9",
  "arena_stage": "A2",
  "entered_count": 120,
  "passed_count": 8,
  "rejected_count": 112,
  "pass_rate": 0.0667,
  "reject_rate": 0.9333,
  "top_reject_reason": "SIGNAL_TOO_SPARSE",
  "reject_reason_distribution": {
    "SIGNAL_TOO_SPARSE": 98,
    "COST_NEGATIVE": 8,
    "OOS_FAIL": 6
  },
  "deployable_count": 2,
  "timestamp_start_utc": "2026-05-01T00:00:00Z",
  "timestamp_end_utc":   "2026-05-01T00:05:00Z",
  "telemetry_version": "1"
}
```

### 3.1 Required fields

| Field | Type | Semantics |
|---|---|---|
| `event_type` | string | Always `"arena_batch_metrics"`. Consumer-discriminator. |
| `run_id` | string | Identifies a single arena_pipeline invocation. |
| `batch_id` | string | A sub-run unit — e.g., a (symbol, regime) pass. |
| `generation_profile_id` | string | See §03 — identifies which GP profile produced these candidates. |
| `arena_stage` | string | One of `"A0"`, `"A1"`, `"A2"`, `"A3"`, `"A4"`, `"A5"`. |
| `entered_count` | int | Candidates that reached this stage in this batch. |
| `passed_count` | int | Candidates that passed this stage. |
| `rejected_count` | int | `entered_count - passed_count - skipped_count`. |
| `pass_rate` | float | `passed_count / entered_count` (0 if entered_count == 0). |
| `reject_rate` | float | `rejected_count / entered_count` (0 if entered_count == 0). |
| `top_reject_reason` | string | Most frequent canonical reason; `"UNKNOWN_REJECT"` as fallback. |
| `reject_reason_distribution` | dict[str,int] | Canonical-reason → count map. |
| `deployable_count` | int | Candidates that satisfy `is_deployable_through("A3")` at batch close (only meaningful on A3+ events). |
| `timestamp_start_utc`, `timestamp_end_utc` | RFC3339 string | Batch wall-clock bounds. |
| `telemetry_version` | string | Currently `"1"`. Future schema changes bump this. |

### 3.2 Optional fields

| Field | Type | Use |
|---|---|---|
| `skipped_count` | int | For stages that emit skip events (e.g., `A3 PREFILTER SKIP`). |
| `stage_latency_ms_p50`, `_p95`, `_p99` | int | If trace emitter can cheaply track per-candidate stage duration. |
| `top_3_reject_reasons` | list[str] | For fast UI rendering. |
| `notes` | string | Free-form operator notes. |

## 4. Schema — `arena_stage_summary` (per run, per stage — run-close rollup)

```json
{
  "event_type": "arena_stage_summary",
  "run_id": "...",
  "arena_stage": "A2",
  "entered_count": 1500,
  "passed_count": 90,
  "rejected_count": 1410,
  "pass_rate": 0.06,
  "reject_rate": 0.94,
  "top_3_reject_reasons": ["SIGNAL_TOO_SPARSE", "COST_NEGATIVE", "OOS_FAIL"],
  "bottleneck_score": 0.94,
  "timestamp_utc": "2026-05-01T03:00:00Z"
}
```

`bottleneck_score = reject_rate` (aggregate). Higher → more of a bottleneck.

## 5. Counter conservation rules

For any (run_id, batch_id, arena_stage):

```
entered_count >= 0
passed_count >= 0
rejected_count >= 0
skipped_count >= 0
entered_count == passed_count + rejected_count + skipped_count
```

Any violation is a **TELEMETRY BUG, not a runtime bug**. The emission path must log the discrepancy as a warning metadata but MUST NOT retroactively adjust Arena decisions.

## 6. Emission points (design — not implemented in 0-9N)

Future P7-PR4-LITE inserts these emissions using the existing
`_emit_a1_lifecycle_safe()`-style exception-safe helper:

| Stage | Emission site | Event |
|---|---|---|
| A1 | end of per-batch (symbol, regime) loop in `arena_pipeline.py` | `arena_batch_metrics` with arena_stage="A1", using existing `stats["reject_*"]` counters as the rejection distribution source |
| A2 | end of A2 processing in `arena23_orchestrator.py` | `arena_batch_metrics` with arena_stage="A2" |
| A3 | end of A3 processing in `arena23_orchestrator.py` | `arena_batch_metrics` with arena_stage="A3" |
| Run-close | end of `arena_pipeline.main()` | `arena_stage_summary` × 3 (A1/A2/A3) |

All emissions are wrapped in try/except; failure MUST NOT raise.

## 7. Reconstruction compatibility

Consumer (`candidate_lifecycle_reconstruction.py` or a future
`arena_batch_metrics_reader.py`) reads the JSONL stream and:

- Filters on `event_type == "arena_batch_metrics"` OR
  `event_type == "arena_stage_summary"`.
- Ignores LifecycleTraceEvent events (P7-PR3) UNLESS the reader chooses to cross-join.
- Tolerates unknown fields (forward-compat).

## 8. Privacy + retention

- Log lines do NOT include PII / account identifiers / credentials.
- Retention: piggybacks on existing `engine.jsonl` rotation.
- No external service transmission in this contract. (External export is out of scope.)

## 9. What this contract **does NOT** require

- **Per-alpha formula_hash** in every event (P7-PR3 already provides this optionally; aggregate metrics do not need per-alpha granularity).
- **Parent-child lineage**.
- **Full CandidateLifecycle reconstruction** — P7-PR2 provides this on demand but aggregate metrics stand alone.
- **Human-readable alpha explanation**.
- **Semantic lineage graph**.
- **Formula interpretability**.

## 10. Success criteria for P7-PR4-LITE (future)

Once implemented, the contract is operational when:

- ≥ 3 `arena_batch_metrics` events emitted per Arena run.
- ≥ 3 `arena_stage_summary` events emitted per Arena run.
- Counter conservation passes (test-enforced).
- Per-stage pass_rate computable from aggregate metrics alone (no per-candidate join needed).
- Top-reject-reason distribution observable without scanning full engine.jsonl.
- Behavior-invariance tests confirm NO change to arena2_pass / arena3_pass / arena4_pass decisions.

## 11. Non-goals

- Not designed for fine-grained trade-level attribution.
- Not designed for live risk monitoring.
- Not designed to replace CANARY health dashboards.
- Not designed to infer causality between generation profiles and market regimes (that's 0-9O territory).
