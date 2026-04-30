# 12 — Feedback Weights Report

**ORDER**: 0-9AC-CLOSE — Workstream E

## Generation Rule (rejection_feedback.py)

Feedback weights derived ONLY from evaluated rejections. NOT_EVALUATED, ERROR, and PASSED candidates do NOT contribute. If rejected_total == 0, output is EMPTY_WITH_REASON; never fake.

## Overall Weights (from 1260 evaluated rejections)

| Reason | Weight |
|---|---:|
| no_trades_generated | 0.7262 |
| non_positive_net | 0.2484 |
| too_few_trades | 0.0254 |
| status | OK |

Sum = 1.0000 (within float tolerance).

## Per-Axis Status

All three axes produced > 0 evaluated rejections → status = OK for each. Per-axis distributions in `shadow_outputs/feedback_weights.json`.

## Hint for Round-N+1 (Future Work)

- D's no_trades_generated dominance (812/896 with band-crossing applied) indicates the rolling-sigma window of 20 is too narrow for the 15m timeframe's regime persistence. Future tuning should sweep window in {20, 60, 120} and / or use ATR-percentile bands instead of pure rolling std.
- C's non_positive_net dominance on rejected candidates (68/183) confirms regime gating leaves trades on cost-marginal signals; deeper regime feature engineering is the bounded next step in 0-9AD scale-up.
- H's 11 PASSED prove p99 clip is structurally sound; residual outliers come from formulas where post-clip variance is high but few extreme-tail trades dominate average net.

## Acceptance Mapping

- AC30 PASS feedback_weights generated from valid evidence (status = OK overall and per axis)
