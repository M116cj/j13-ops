# 09 — Feedback Weights Report

**ORDER**: 0-9AB — Workstream D

## Generation Rule (rejection_feedback.py)

Feedback weights are derived ONLY from evaluated rejected candidates. NOT_EVALUATED, ERROR, and PASSED candidates do NOT contribute. If rejected_total == 0, output is EMPTY_WITH_REASON; never fake.

## Overall Weights (from 568 evaluated rejections)

| Reason | Weight |
|---|---:|
| no_trades_generated | 0.7025 |
| non_positive_net | 0.2271 |
| too_few_trades | 0.0704 |
| status | OK |

Sum to 1.0 (within float tolerance).

## Per-Axis

All three axes produced > 0 evaluated rejections → status = OK for all three. Per-axis weight distributions are stored in shadow_outputs/feedback_weights.json.

## Interpretation Hint for the Next Round

- The dominant rejection mode is **no_trades_generated** (70.2% overall, 88.5% in D, 73.3% in H, 48.7% in C). Round 2 should bias the grammar toward formulas that produce more sign-flips per bar (e.g., add a normalisation step or use a thinner ts window) rather than chasing higher gross-per-trade.
- C is the only axis where **non_positive_net** dominates (42.3% of C rejects) — meaning C produces signals but they lose money after cost. The fix space is gate tightness or cost-aware ranking.
- D rarely produces non_positive_net (7.3%) because it rarely produces enough trades at all — D needs a denser signal first, then revisit cost.

## Acceptance Mapping

- AC31 PASS feedback_weights generated from valid evidence (status = OK in this run)
