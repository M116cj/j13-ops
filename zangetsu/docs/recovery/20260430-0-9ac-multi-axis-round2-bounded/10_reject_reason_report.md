# 10 — Reject Reason Report

**ORDER**: 0-9AC-CLOSE — Workstream E

## Overall Distribution (1260 REJECTED of 1280)

| Reason | Count | Share |
|---|---:|---:|
| no_trades_generated | 915 | 72.6% |
| non_positive_net | 313 | 24.8% |
| too_few_trades | 32 | 2.5% |
| **UNKNOWN_REJECT** | **0** | **0%** |

## Per-Axis (from shadow_outputs/reject_reason_summary.json)

| Axis | rejected | no_trades_generated | non_positive_net | too_few_trades | UNKNOWN_REJECT |
|---|---:|---:|---:|---:|---:|
| H | 181 | 94 | 77 | 10 | 0 |
| C | 183 | 93 | 68 | 22 | 0 |
| D | 896 | 728 | 168 | 0 | 0 |

## NOT_EVALUATED Separation

NOT_EVALUATED count = 0 in this run. Rule: NOT_EVALUATED candidates have blocker_reason, never reject_reason; verified by economic_arena_adapter logic and tested in test_not_evaluated_does_not_contribute_to_feedback.

## Reject Reason Quality

UNKNOWN_REJECT count = 0 across all axes → reject_reason_quality scored full 10/10.

## Acceptance Mapping

- AC23 PASS evaluated rejected candidates have reject reasons
- AC24 PASS non-evaluated candidates have blocker reasons (rule enforced; 0 in run)
- AC25 PASS UNKNOWN_REJECT explicitly reported (0)
