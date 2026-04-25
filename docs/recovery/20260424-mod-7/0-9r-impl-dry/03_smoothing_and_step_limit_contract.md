# 03 — Smoothing & Step-Limit Contract

## 1. EMA smoothing

```
ema_smooth(new, history=[h_old, ..., h_new], alpha=0.20)
```

Behavior:

1. Iteration is **oldest-first** (history list is treated as a time
   series).
2. For each profile id (sorted), seed `current` with the first valid
   history value; subsequent history values blend with
   `alpha * v + (1-α) * current`.
3. Final blend with `alpha * new_value + (1-α) * current`.
4. Profiles missing from history use the new value directly.
5. NaN / inf / non-numeric values are replaced with `0.0`.
6. Bad α (≤ 0 or > `EMA_ALPHA_MAX = 0.20`) is reset to
   `DEFAULT_EMA_ALPHA = 0.20`.

Determinism: same input → same output (sorted iteration over keys).

Mutation: input mappings are read-only; never mutated.

## 2. Step-limit

```
limit_step(proposed, previous, max_step_abs=0.10)
```

Behavior:

1. For each profile id in `proposed`, compute
   `delta = proposed[k] - previous.get(k, proposed[k])`.
2. If `delta > max_step_abs`: clip target to
   `previous[k] + max_step_abs`.
3. If `delta < -max_step_abs`: clip target to
   `previous[k] - max_step_abs`.
4. Floor result at `0.0` (no negative weights).
5. Bad `max_step_abs` (≤ 0 or > 1.0) → reset to `0.10`.

When `previous` is None / empty, returns `proposed` unchanged
(modulo zero-floor).

## 3. Floor + diversity + sum-to-1.0

```
enforce_floor_and_diversity(weights, floor=0.05, diversity_cap_min=2)
```

Behavior:

1. UNKNOWN_PROFILE capped at `floor` before normalization.
2. If `n * floor >= 1.0` (saturating case), split evenly.
3. Otherwise:
   ```
   floor_total = floor * n
   remainder   = 1.0 - floor_total
   if sum(raw) > 0:
       w[k] = floor + remainder * (raw[k] / sum(raw))
   else:
       w[k] = floor + remainder / n
   ```
4. Final `scale = 1.0 / sum(weights)` rebalance to compensate
   numeric drift.
5. Diversity cap: count profiles `>= floor`. If less than
   `diversity_cap_min`, fall back to even split.

Properties (locked by tests):

- Sum exactly 1.0 (within `1e-9`).
- All weights `>= 0`.
- All weights `>= floor` (modulo numerical scale).
- UNKNOWN_PROFILE never dominates.
- Deterministic.

## 4. Pipeline integration

`consume()` chains the three steps:

```
allocator_proposed_weights
    ↓ ema_smooth
smoothed_proposed_weights
    ↓ limit_step  (against caller-supplied previous_profile_weights)
max_step_limited_weights
    ↓ enforce_floor_and_diversity
final_dry_run_weights
```

All four stages are stored in the plan, so observers can audit each
transformation.

## 5. Test coverage (selected)

| Test | Property |
| --- | --- |
| `test_ema_alpha_lte_02` | α clamping |
| `test_smoothing_window_gte_5` | window minimum |
| `test_max_step_lte_10pp` | step clip |
| `test_exploration_floor_gte_005` | floor minimum |
| `test_ema_smooth_blends_history` | EMA arithmetic |
| `test_ema_smooth_does_not_mutate_inputs` | input safety |
| `test_limit_step_clips_positive_delta` | positive clip |
| `test_limit_step_clips_negative_delta` | negative clip |
| `test_enforce_floor_and_diversity_sum_to_one` | sum-to-1.0 |
| `test_enforce_floor_and_diversity_floor_active` | floor invariant |
| `test_enforce_floor_and_diversity_unknown_profile_capped` | UNKNOWN_PROFILE cap |
| `test_diversity_cap_prevents_profile_collapse` | diversity invariant |
| `test_pipeline_max_step_limit_respects_previous_weights` | end-to-end step-limit |
