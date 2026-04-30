# 08 — Feedback Weights Report

**ORDER**: 0-9AD — Phase 8

## Generation Rule (rejection_feedback.feedback_weights_from_summary)

Feedback weights derived ONLY from evaluated rejections. NOT_EVALUATED, ERROR, and PASSED do NOT contribute. If rejected_total == 0, output is EMPTY_WITH_REASON; never fake.

## Overall Weights (from 1753 evaluated rejections)

| Reason | Weight |
|---|---:|
| no_trades_generated | 0.6035 |
| non_positive_net | 0.3337 |
| too_few_trades | 0.0627 |
| **status** | **OK** |

Sum = 1.0000.

## Per-Axis (single axis = C)

Same as overall (only one axis in this run).

## Diagnostic Read

- **no_trades_generated** dominates (60%): the C-axis grammar produces signals that often hover too far from zero to trigger sign-flip entries on 15m bars. Round-N+1 grammar bias should add ts_rank-based normalisation or a wider primitive selection.
- **non_positive_net** is 33%: when C does fire, the cost wall (14.5 bps) is decisive — gross-per-trade ≤ ~12 bps for these candidates, consistent with 0-9AC C-axis findings.
- **too_few_trades** is 6%: a small but non-zero band of "would-be passing" candidates sit at 1–24 trades — densifying triggers may rescue some.

## Acceptance Mapping

- AC19 PASS feedback_weights.json produced
- AC15 PASS UNKNOWN_REJECT explicitly reported (0 → no taxonomy gap flagged)
