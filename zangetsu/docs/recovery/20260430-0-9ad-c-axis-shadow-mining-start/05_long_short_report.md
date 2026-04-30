# 05 — Long / Short Report

**ORDER**: 0-9AD — Phase 5

## Per-Side Aggregate

| Mode | n | PASSED | REJECTED | Realized LONG trades | Realized SHORT trades | Near-survivors | Dominant Reject |
|---|---:|---:|---:|---:|---:|---:|---|
| LONG | 896 | **36** | 860 | 3,610,239 | 0 | 460 | no_trades_generated (453) |
| SHORT | 896 | **3** | 893 | 0 | 3,420,868 | 606 | no_trades_generated (605) |
| **Total** | 1792 | **39** | 1753 | 3,610,239 | 3,420,868 | **1066** | no_trades_generated (1058) |

## Notes

- LONG side dominates (36 PASSED vs. 3 SHORT). Consistent with 0-9AC Round 2 finding that C-axis short-side regime gating is harder.
- LONG-side reject reasons: 453 no_trades / 298 non_pos / 109 too_few.
- SHORT-side reject reasons: 605 no_trades / 287 non_pos / 1 too_few — short side has dramatically fewer too_few_trades but more no-trade outcomes, suggesting short signals fire even less often than long under the same grammar.
- BOTH-side mode was not tested in this run because the order's intended_side_mode template lists LONG / SHORT / BOTH but BOTH is reserved for hybrid; C-axis baseline uses single-direction signal masking for cleaner reject taxonomy.

## Realized vs Intended Side

LONG-mode candidates produced 0 short trades; SHORT-mode candidates produced 0 long trades. Verified by aggregate_long_short. No fabrication.

## Acceptance Mapping

- AC16 PASS long_short_summary.csv produced (per-axis-side aggregate)
- AC18 (preserved metadata): intended_side_mode in every manifest record
