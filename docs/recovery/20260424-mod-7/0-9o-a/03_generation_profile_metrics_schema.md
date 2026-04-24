# 0-9O-A — generation_profile_metrics Schema

## 1. Event type

`event_type = "generation_profile_metrics"`, `telemetry_version = "1"`.

## 2. Fields

| Field | Type | Notes |
|-------|------|-------|
| `telemetry_version` | string | `"1"` |
| `run_id` | string | set by caller |
| `generation_profile_id` | string | `UNKNOWN_PROFILE` when unavailable |
| `generation_profile_fingerprint` | string | `sha256:<hex>` or `UNAVAILABLE` |
| `profile_name` | string | human-readable, defaults to `profile_id` |
| `profile_config_hash` | string | mirrors `fingerprint` unless caller overrides |
| `total_batches` | int | number of `arena_batch_metrics` events aggregated |
| `total_candidates_generated` | int | = `total_entered_a1` |
| `total_entered_a1` / `total_passed_a1` / `total_rejected_a1` | int | A1 aggregates |
| `avg_a1_pass_rate` | float | batch-weighted mean |
| `total_entered_a2` / `total_passed_a2` / `total_rejected_a2` | int | A2 aggregates (0 until P7-PR4B) |
| `avg_a2_pass_rate` | float | `0.0` until P7-PR4B |
| `total_entered_a3` / `total_passed_a3` / `total_rejected_a3` | int | A3 aggregates (0 until P7-PR4B) |
| `avg_a3_pass_rate` | float | `0.0` until P7-PR4B |
| `total_deployable_count` | int | sum of batch-supplied `deployable_count` |
| `avg_deployable_count` | float | mean of batch-supplied values (0.0 if none) |
| `signal_too_sparse_count` / `_rate` | int / float | from `reject_reason_distribution` |
| `oos_fail_count` / `_rate` | int / float | from `reject_reason_distribution` |
| `unknown_reject_count` / `_rate` | int / float | from `reject_reason_distribution` |
| `instability_penalty` | float | `stddev / mean` of A1 pass rates; 0 if N < 2 |
| `profile_score` | float | read-only composite (see `04_read_only_scoring_model.md`) |
| `next_budget_weight_dry_run` | float | recommendation-only |
| `sample_size_rounds` | int | = `total_batches` |
| `min_sample_size_met` | bool | `sample_size_rounds >= 20` |
| `confidence` | string | `"LOW_CONFIDENCE_UNTIL_A2_A3_METRICS_AVAILABLE"` or `"FULL"` |
| `mode` | string | `"READ_ONLY"` |
| `created_at` / `updated_at` | RFC3339 Z | UTC |
| `source` | string | `"generation_profile_metrics"` |

## 3. Aggregation rules

Input: iterable of `arena_batch_metrics` dicts (output of
`arena_pass_rate_telemetry.build_arena_batch_metrics`).

1. Group by `arena_stage`.
2. Sum `entered_count`, `passed_count`, `rejected_count` per stage.
3. Compute per-stage mean `pass_rate = passed / entered` (zero-safe).
4. For each batch, read `deployable_count`; `None` or missing values are
   skipped — never inferred from `passed_count`.
5. For each batch, read `reject_reason_distribution` and accumulate
   SIGNAL_TOO_SPARSE / OOS_FAIL / OOS_OVERFIT (both map to oos) /
   UNKNOWN_REJECT counts.
6. Compute instability penalty from A1 pass-rate stddev / mean.
7. Compute `profile_score` via `compute_profile_score(...)`.
8. Compute `next_budget_weight_dry_run` via
   `compute_dry_run_budget_weight(...)`.
9. Set `min_sample_size_met = total_batches >= 20`.
10. Set `confidence = FULL` iff `min_sample_size_met AND
    (total_entered_a2 > 0 AND total_entered_a3 > 0)`; otherwise
    `LOW_CONFIDENCE_UNTIL_A2_A3_METRICS_AVAILABLE`.

## 4. Current A2 / A3 convention

Until P7-PR4B wires A2 / A3 `arena_batch_metrics`, all A2 / A3 counts
are reported as `0` and rates as `0.0`. The `confidence` field is the
sole signal that these values are not yet meaningful.

## 5. Exception safety

`aggregate_batches_for_profile(...)` never raises — on any internal
error it returns a zero-filled `GenerationProfileMetrics` with
`confidence = LOW_CONFIDENCE_UNTIL_A2_A3_METRICS_AVAILABLE`.
`safe_build_generation_profile_metrics(...)` wraps this with `None` on
fatal failure.

## 6. Tests covering this schema

- `test_generation_profile_metrics_schema_contains_required_fields`
- `test_generation_profile_metrics_aggregates_a1_counts`
- `test_generation_profile_metrics_handles_missing_a2_a3`
- `test_signal_too_sparse_rate_computation`
- `test_unknown_reject_rate_computation`
- `test_avg_pass_rate_computation`
- `test_deployable_count_aggregation_does_not_change_semantics`
