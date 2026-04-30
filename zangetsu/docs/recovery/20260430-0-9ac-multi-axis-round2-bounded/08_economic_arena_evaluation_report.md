# 08 — Economic Arena Evaluation Report

**ORDER**: 0-9AC-CLOSE — Workstream E

## Adapter (unchanged safety stance from 0-9AB)

`zangetsu/core_factory/economic_arena_adapter.py` — shadow-only:
- Reads zangetsu/data/*.parquet only
- Writes outputs to shadow_outputs/ only
- Calls services.arena_gates (pure Python, no DB)
- No exchange API call, no production DB write, no runtime worker touched

Round 2 additions:
- `@lru_cache` on per-(symbol, timeframe, axis_id) data dict for D's 14-symbol load
- `EvaluationParams` dataclass for clip / trigger / band_k / sigma_window
- Extended `EvaluationResult` with `clip_metadata` and `trigger_metadata`

## Run Statistics

```
candidates evaluated: 1280 / 1280
duration:             153.59 s
status distribution:
  PASSED          20
  REJECTED        1260
  NOT_EVALUATED   0
  ERROR           0
UNKNOWN_REJECT:    0
```

## Reject Reason Distribution (overall)

| Reason | Count |
|---|---:|
| no_trades_generated | 915 |
| non_positive_net | 313 |
| too_few_trades | 32 |
| UNKNOWN_REJECT | 0 |

## Per-Axis Status (verified from shadow_batch_results.jsonl)

| Axis | n | PASSED | REJECTED | NOT_EVALUATED | ERROR |
|---|---:|---:|---:|---:|---:|
| H | 192 | 11 | 181 | 0 | 0 |
| C | 192 | 9 | 183 | 0 | 0 |
| D | 896 | 0 | 896 | 0 | 0 |
| **Total** | **1280** | **20** | **1260** | **0** | **0** |

## Per-Axis Reject Reasons

| Axis | Rejected | no_trades_generated | non_positive_net | too_few_trades |
|---|---:|---:|---:|---:|
| H | 181 | 94 | 77 | 10 |
| C | 183 | 93 | 68 | 22 |
| D | 896 | 728 | 168 | 0 |

D's no-trade share = 728 / 896 = 81.3% — band-crossing structurally improved D's signal (pre-Round-2 D had no_trades_generated dominant), but the share is still > 50% so correction_success scored 3 / 10 (per §6 of 06_round2_tournament_design.md).

## Acceptance Mapping

- AC22 PASS Economic Arena assessment safely attempted (1280 / 1280)
- AC23 PASS NOT_EVALUATED separate from REJECTED (0 NOT_EVALUATED)
- AC24 PASS reject reasons reported per axis
- AC25 PASS UNKNOWN_REJECT explicitly reported (0)
