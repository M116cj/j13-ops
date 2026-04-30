# 05 — Economic Arena Evaluation Report

**ORDER**: 0-9AB — Workstream D

## Adapter Safety Statement

The shadow Economic Arena adapter (zangetsu/core_factory/economic_arena_adapter.py) satisfies §9 safety conditions:

- Reads OHLCV / funding / OI from zangetsu/data/*.parquet only.
- Writes outputs ONLY into shadow_outputs/ under the evidence folder.
- Calls zangetsu.services.arena_gates directly (pure Python, no DB).
- No exchange API call, no production DB write, no runtime worker touched.

## Pipeline Stages

| Stage | Action |
|---|---|
| 1 | Load OHLCV / funding / OI parquet |
| 2 | Resample 1m bars to 15m via timestamp bucket aggregation |
| 3 | Walk AST recursively against curated primitive inventory |
| 4 | Generate trades from signal sign-flips filtered by intended_side_mode |
| 5 | Compute net = mean gross bps − round-trip cost (14.5 bps) |
| 6 | Apply A2 gate (trade_count ≥ 25 AND net positive) |
| 7 | Assign status PASSED / REJECTED / NOT_EVALUATED / ERROR |

## Run Statistics

- Candidates assessed: 576 / 576
- Evaluation duration: 141.75 seconds
- Status distribution:
  - PASSED 8
  - REJECTED 568
  - NOT_EVALUATED 0
  - ERROR 0

## Reject Reason Distribution

| Reason | Count |
|---|---:|
| no_trades_generated | 399 |
| non_positive_net | 129 |
| too_few_trades | 40 |
| UNKNOWN_REJECT | 0 |

## Per-Axis Status

| Axis | n | PASSED | REJECTED | NOT_EVALUATED | ERROR |
|---|---:|---:|---:|---:|---:|
| H | 192 | 5 | 187 | 0 | 0 |
| C | 192 | 3 | 189 | 0 | 0 |
| D | 192 | 0 | 192 | 0 | 0 |

## Acceptance Mapping

- AC20 PASS Economic Arena assessment safely attempted (all 576 candidates assessed)
- AC21 PASS no production DB mutation (read-only adapter)
- AC22 PASS NOT_EVALUATED separate from REJECTED (0 NOT_EVALUATED here)
- AC23 PASS all REJECTED candidates carry reject_reason
- AC25 PASS UNKNOWN_REJECT explicitly reported (count = 0)
