# 06 — Reject Reason Report

**ORDER**: 0-9AD — Phase 6

## Overall Distribution (1753 REJECTED of 1792)

| Reason | Count | Share |
|---|---:|---:|
| no_trades_generated | 1058 | 60.4% |
| non_positive_net | 585 | 33.4% |
| too_few_trades | 110 | 6.3% |
| **UNKNOWN_REJECT** | **0** | **0%** |

Per-axis (single axis = C): same as overall.

## NOT_EVALUATED Separation

NOT_EVALUATED count = 0 in run. Rule enforced: NOT_EVALUATED carry blocker_reason, NEVER reject_reason. Verified at runtime by economic_arena_adapter and tested in test_not_evaluated_does_not_contribute_to_feedback.

## Per-Side Failure Mode

| Side | Dominant reject | Secondary | Tertiary |
|---|---|---|---|
| LONG | no_trades_generated (52.7% of long rejects) | non_positive_net (34.7%) | too_few_trades (12.7%) |
| SHORT | no_trades_generated (67.7% of short rejects) | non_positive_net (32.1%) | too_few_trades (0.1%) |

SHORT-side under-trades dramatically — only 1 SHORT candidate failed at "too_few_trades" (between 1 and 24 trades), all others either fired enough or never fired at all.

## Per-Symbol no_trades_generated

| Symbol | Candidates | Passed | no_trades |
|---|---:|---:|---:|
| 1000PEPEUSDT | 128 | 2 | 77 |
| 1000SHIBUSDT | 128 | 3 | 77 |
| AAVEUSDT | 128 | 4 | 76 |
| AVAXUSDT | 128 | 5 | 75 |
| BNBUSDT | 128 | 4 | 75 |
| BTCUSDT | 128 | 2 | 75 |
| DOGEUSDT | 128 | 3 | 77 |
| DOTUSDT | 128 | **0** | 75 |
| ETHUSDT | 128 | 3 | 75 |
| FILUSDT | 128 | 2 | 75 |
| GALAUSDT | 128 | 2 | 75 |
| LINKUSDT | 128 | 2 | 75 |
| SOLUSDT | 128 | 5 | 75 |
| XRPUSDT | 128 | 2 | 76 |

DOTUSDT had 0 PASSED. AVAXUSDT and SOLUSDT tied for the most PASSED at 5 each.

## Reject Reason Quality

UNKNOWN_REJECT = 0 → reject_reason_quality scored 10/10 in scoreboard.

## Acceptance Mapping

- AC13 PASS evaluated rejections have reject_reason
- AC14 PASS NOT_EVALUATED carry blocker_reason (rule enforced; 0 in run)
- AC15 PASS UNKNOWN_REJECT explicitly reported (0)
