# 07 — Reject Reason Report

**ORDER**: 0-9AB — Workstream D

## Overall Distribution (568 REJECTED of 576)

| Reason | Count | Share |
|---|---:|---:|
| no_trades_generated | 399 | 70.2% |
| non_positive_net | 129 | 22.7% |
| too_few_trades | 40 | 7.0% |
| **UNKNOWN_REJECT** | **0** | **0%** |

## Per-Axis (output: shadow_outputs/reject_reason_summary.json)

| axis | rejected | no_trades | non_pos_net | too_few | unknown |
|---|---:|---:|---:|---:|---:|
| H | 187 | 137 | 35 | 15 | 0 |
| C | 189 | 92 | 80 | 17 | 0 |
| D | 192 | 170 | 14 | 8 | 0 |

(Counts derived from shadow_batch_results.jsonl by status + reject_reason group-by; reproduced in reject_reason_summary.json.)

## NOT_EVALUATED Separation

NOT_EVALUATED candidates have blocker_reason, NEVER reject_reason. In this run NOT_EVALUATED = 0, so no separation conflict arose. Rule is enforced by economic_arena_adapter.evaluate_candidate and verified by test_not_evaluated_does_not_contribute_to_feedback.

## Reject Reason Quality

UNKNOWN_REJECT count = 0 across all axes → reject_reason_quality = full 10/10 in axis_scoreboard.

## Acceptance Mapping

- AC23 PASS evaluated rejected candidates have reject reasons
- AC24 PASS non-evaluated candidates have blocker reasons (0 in this run; rule still enforced by code)
- AC25 PASS UNKNOWN_REJECT explicitly reported (0)
