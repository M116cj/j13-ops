# P7-PR4-LITE — Aggregate Arena Pass-Rate Telemetry Design

## 1. Purpose

Implement the aggregate Arena pass-rate observability contract designed in
0-9N §02. ZANGETSU accepts fully black-box alpha / strategy internals. The
only required provenance is Arena-level alpha pass-rate traceability:

- how many alpha candidates enter each Arena stage
- how many pass each Arena stage
- how many fail / reject each Arena stage
- pass / reject rates by Arena stage
- top rejection reasons by stage
- deployable_count by batch / run
- generation_profile_id / batch_id linkage when available

P7-PR4-LITE does **not** implement full per-alpha lineage.

## 2. Deliverables

| Item | Location |
|------|----------|
| Helper module | `zangetsu/services/arena_pass_rate_telemetry.py` |
| Runtime A1 emission call site | `zangetsu/services/arena_pipeline.py` |
| Tests | `zangetsu/tests/test_arena_pass_rate_telemetry.py` |
| Docs | `docs/recovery/20260424-mod-7/p7-pr4-lite/` |

## 3. Event shapes

Two event types (`TELEMETRY_VERSION = "1"`):

### 3.1 `arena_batch_metrics`

Emitted once per (run, batch, stage) close. Required fields:

- `telemetry_version`
- `run_id`
- `batch_id`
- `generation_profile_id`
- `generation_profile_fingerprint`
- `arena_stage`
- `entered_count`
- `passed_count`
- `rejected_count`
- `skipped_count`
- `error_count`
- `in_flight_count`
- `pass_rate`
- `reject_rate`
- `top_reject_reason`
- `reject_reason_distribution`
- `deployable_count`
- `timestamp_start`
- `timestamp_end`
- `source`

### 3.2 `arena_stage_summary`

Aggregation over a list of batch events for a given stage. Required fields:

- `telemetry_version`
- `run_id`
- `batch_id`
- `arena_stage`
- `entered_count`
- `passed_count`
- `rejected_count`
- `skipped_count`
- `error_count`
- `in_flight_count`
- `pass_rate`
- `reject_rate`
- `top_3_reject_reasons`
- `bottleneck_score`
- `timestamp`
- `source`

`bottleneck_score` := `reject_rate` (higher = more likely bottleneck).

## 4. Module contract

`arena_pass_rate_telemetry` exports:

- Dataclasses: `ArenaBatchMetrics`, `ArenaStageSummary`, `ArenaStageMetrics`
- Helpers: `RejectReasonCounter`, `compute_pass_rate`, `compute_reject_rate`,
  `validate_counter_conservation`, `build_arena_batch_metrics`,
  `build_arena_stage_summary`, `safe_emit_arena_metrics`
- Constants: `TELEMETRY_VERSION`, `EVENT_TYPE_ARENA_BATCH_METRICS`,
  `EVENT_TYPE_ARENA_STAGE_SUMMARY`, `UNKNOWN_PROFILE_ID`,
  `UNAVAILABLE_FINGERPRINT`, `UNKNOWN_REJECT_NAME`, `COUNTER_INCONSISTENCY`

## 5. Fallback policy

| Condition | Value |
|-----------|-------|
| `generation_profile_id` unavailable | `"UNKNOWN_PROFILE"` |
| `generation_profile_fingerprint` unavailable | `"UNAVAILABLE"` |
| `deployable_count` unavailable | `None` (emitted as such — never inferred from `passed_count`) |
| Counter residual implies inconsistency | Route to `COUNTER_INCONSISTENCY` bucket |
| Reason cannot be canonicalized | Route to `UNKNOWN_REJECT` bucket |

No precision is faked; UNKNOWN / UNAVAILABLE remain measurable.

## 6. Rate formulas

```
pass_rate   = passed_count   / entered_count   (0.0 if entered_count == 0)
reject_rate = rejected_count / entered_count   (0.0 if entered_count == 0)
```

Both caps at `1.0` defensively against stats-level over-count.

## 7. Safety invariants

- All emission paths wrapped in `try/except` — never raise.
- All builder paths defend against dict / key errors.
- Module import never pulls in Arena runtime (`arena_pipeline`).
- Module has no side effects at import time.

## 8. Out of scope (deferred to 0-9O)

- `generation_profile_metrics` event scoring model.
- `feedback_decision_record` event.
- Budget allocator / profile score.
- Full per-alpha lineage / formula explainability.
