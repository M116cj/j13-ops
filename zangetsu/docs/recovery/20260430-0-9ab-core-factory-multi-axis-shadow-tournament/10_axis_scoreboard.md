# 10 — Axis Scoreboard

**ORDER**: 0-9AB — Workstream D

## Score Categories (out of 100)

| Category | Weight |
|---|---:|
| candidate_generation_success | 15 |
| formula_diversity | 15 |
| long_short_balance | 10 |
| economic_result_quality | 25 |
| cost_robustness | 15 |
| reject_reason_quality | 10 |
| feedback_usability | 10 |

## Final Ranking (from shadow_outputs/axis_scoreboard.csv)

| Rank | Axis | Total | Generation | Diversity | L/S Bal | Econ | Cost | Reject Q | Feedback |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | **C** | **89.12** | 15.00 | 15.00 | 9.51 | 14.61 | 15.00 | 10.00 | 10.00 |
| 2 | **H** | **88.81** | 15.00 | 15.00 | 9.98 | 13.83 | 15.00 | 10.00 | 10.00 |
| 3 | **D** | **86.21** | 15.00 | 15.00 | 9.44 | 14.77 | 12.00 | 10.00 | 10.00 |

## Spread Analysis

- C–H gap: 0.31 points (essentially tied)
- C–D gap: 2.91 points (within noise threshold)
- All three axes within 3 points → trigger condition for MULTI_AXIS_CONTINUE_ONE_MORE_ROUND per order §3.

## Cost-Robustness Sign Read

| Axis | avg_net_bps |
|---|---:|
| H (LONG) | +5278.89 (numerical-stability artifact, see 06) |
| H (SHORT) | -4917.35 (numerical-stability artifact) |
| C (LONG) | +12.72 |
| C (SHORT) | -2.61 |
| D (LONG) | -1.21 |
| D (SHORT) | -1.45 |

H's average is dominated by extreme tanh ∘ protected_div outputs — until a value-clip is added in round 2, H's +/-5000-bps numbers should not drive verdict.

## Acceptance Mapping

- AC32 PASS axis scoreboard ranks H/C/D
- AC44 PASS final verdict will be one of the 7 allowed (see 13_final_report.md)
