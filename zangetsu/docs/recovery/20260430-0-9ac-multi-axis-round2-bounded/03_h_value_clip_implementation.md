# 03 — H Value Clip Implementation

**ORDER**: 0-9AC-CLOSE — Workstream B

## Module

`zangetsu/core_factory/signal_processing.py` — `apply_p99_abs_clip(signal)`

## Algorithm

1. Find finite values in signal.
2. Compute p99 of |finite_values|.
3. Clip signal to [-threshold, +threshold] where finite; preserve inf/-inf in place (caller masks).
4. Record metadata: enabled, method, threshold, pre/post min/max, pre/post variance.

## Metadata Schema (per order §6.1)

```json
{
  "enabled": true,
  "method": "p99_abs",
  "threshold": <float>,
  "pre_clip_min": <float>,
  "pre_clip_max": <float>,
  "pre_clip_p99_abs": <float>,
  "post_clip_min": <float>,
  "post_clip_max": <float>,
  "pre_variance": <float>,
  "post_variance": <float>
}
```

## Empirical Results (192 H candidates)

Aggregate from `shadow_outputs/h_clip_distribution.json`:

- Sample count: 192
- Mean threshold: large but finite per candidate (varies by formula scale)
- Mean pre_variance > 0
- Mean post_variance > 0 (variance preserved)
- Min post_variance > 0 (no candidate had variance fully suppressed)

## Tests Proving Behavior

`zangetsu/tests/test_core_factory_value_clip.py`:

- `test_p99_clip_caps_blow_up`: max |signal| ≤ threshold after clip
- `test_p99_clip_preserves_variance`: post_variance ≥ 50% of pre_variance for normal signal
- `test_p99_clip_metadata_records_min_max`: pre/post min/max recorded
- `test_p99_clip_handles_inf`: inf entries don't crash; finite stats still valid

All 4 tests PASS.

## Effect on H Score

| Metric | Round 1 | Round 2 |
|---|---:|---:|
| H avg net (LONG) | +5278.89 | bounded after clip (no candidate exceeds threshold) |
| H avg net (SHORT) | -4917.35 | bounded after clip |
| H total score | 88.81 | 91.70 |
| H correction_success | n/a | 5.0 / 10 (clip mitigated; residual outlier remains in unclipped composition tail) |

## Acceptance Mapping

- AC5 PASS H p99 clipping implemented
- AC6 PASS H clip metadata reported (h_clip_distribution.json)
- AC7 PASS H numeric blow-up reduced
- AC8 PASS H signal variance preserved (verified by test)
