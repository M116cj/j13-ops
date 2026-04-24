# 0-9O-A — Read-Only Scoring Model

## 1. Mode

All scoring output is marked:

```
mode       = "READ_ONLY"
applied    = False (on any downstream decision record)
confidence = "LOW_CONFIDENCE_UNTIL_A2_A3_METRICS_AVAILABLE"  (until P7-PR4B wires A2/A3)
```

Scoring is a diagnostic. It is not consumed by generation runtime,
Arena runtime, champion promotion, execution, capital, or risk
subsystems. See §6 "Guardrails".

## 2. Formula

```
profile_score =
    w1 * avg_a1_pass_rate
  + w2 * avg_a2_pass_rate
  + w3 * avg_a3_pass_rate
  + w4 * deployable_score
  - w5 * signal_too_sparse_rate
  - w6 * oos_fail_rate
  - w7 * unknown_reject_rate
  - w8 * instability_penalty
```

Where:

- `deployable_score = clamp(avg_deployable_count / deployable_ceiling, 0.0, 1.0)`,
  `deployable_ceiling = 10.0` by default (configurable via `weights`
  override, but never by runtime).

## 3. Default weights (per TEAM ORDER 2-3 §9)

```
w1_avg_a1_pass_rate          = 0.10
w2_avg_a2_pass_rate          = 0.30
w3_avg_a3_pass_rate          = 0.30
w4_deployable_score          = 0.20
w5_signal_too_sparse_penalty = 0.25
w6_oos_fail_penalty          = 0.20
w7_unknown_reject_penalty    = 0.50
w8_instability_penalty       = 0.15
```

Rationale:
- A2 and A3 carry the strongest signal about downstream quality and
  receive the highest positive weights.
- `w7` (UNKNOWN_REJECT) is intentionally the largest penalty —
  UNKNOWN_REJECT represents a telemetry bug; a profile driving those up
  must be identified and stopped.
- `w5` (SIGNAL_TOO_SPARSE) dominates the current A1 view but is
  moderate until A2 / A3 signal is available (confidence stays LOW).

## 4. Clamping

- Inputs are clamped to `[0.0, 1.0]` before weighting to protect
  against counter overflow (`pass_rate > 1.0` can only come from a
  counter bug).
- Output is clamped to `[PROFILE_SCORE_MIN, PROFILE_SCORE_MAX] =
  [-1.0, 1.0]`.

## 5. Dry-run budget recommendation

```
next_budget_weight_dry_run =
    EXPLORATION_FLOOR                          if not min_sample_size_met
    clamp(0.5 + 0.5 * profile_score,           otherwise
          EXPLORATION_FLOOR, 1.0)
```

- `EXPLORATION_FLOOR = 0.05` (matches 0-9N §05 §04.2 guardrail).
- `MIN_SAMPLE_SIZE_ROUNDS = 20` — below this threshold, the
  recommendation pins at exactly `EXPLORATION_FLOOR` so any future
  budget allocator reading this field can trivially detect "not yet
  actionable".

## 6. Guardrails

1. **No score feeds runtime**: no public helper in the module writes
   to generation config, sampler state, or Arena state.
2. **No promotion by score**: champion promotion path is unchanged.
3. **Exploration floor ≥ 0.05**: all recommendations respect the floor.
4. **Sample size gating**: below `MIN_SAMPLE_SIZE_ROUNDS`, the
   recommendation is never actionable.
5. **Low confidence marker**: set whenever A2 / A3 metrics missing —
   true for the whole of 0-9O-A.
6. **UNKNOWN_REJECT penalty dominates**: scoring framework treats any
   unknown as a signal of telemetry failure and penalises aggressively.
7. **Never reward pass_rate alone**: `deployable_score` is included in
   the positive side; pass_rate without deployable candidates cannot
   boost a profile above a profile that is actually producing
   deployable output.
8. **A1-only data cannot trigger budget allocation**: budget allocator
   is future 0-9O-B, gated on full confidence.
9. **Score never affects Arena decisions**: pure function, no side
   effects.
10. **Score never mutates threshold config**: write tests guard this.

## 7. Tests covering this model

- `test_profile_score_calculation`
- `test_profile_score_penalizes_signal_too_sparse`
- `test_profile_score_penalizes_unknown_reject_strongly`
- `test_profile_score_marks_low_confidence_without_a2_a3`
- `test_profile_score_requires_min_sample_size_20_for_actionability`
- `test_scoring_does_not_modify_generation_budget`
- `test_scoring_does_not_modify_arena_decisions`
- `test_next_budget_weight_dry_run_obeys_exploration_floor`
- `test_next_budget_weight_dry_run_is_not_applied`
- `test_dry_run_recommendation_labeled_low_confidence_when_metrics_incomplete`
