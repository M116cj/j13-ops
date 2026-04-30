# 04 — Economic Arena Evaluation Report

**ORDER**: 0-9AD — Phase 4

## Adapter Safety (unchanged from 0-9AB / 0-9AC)

`zangetsu/core_factory/economic_arena_adapter.py` — shadow-only:
- Reads zangetsu/data/*.parquet only
- Writes outputs to shadow_outputs/ only
- Calls services.arena_gates (pure Python, no DB)
- No exchange API call, no production DB write, no runtime worker touched
- @lru_cache on per-symbol data dict (introduced 0-9AC, reused here for 14-symbol scan)

## Run Statistics

```
candidates assessed: 1792 / 1792
duration:            44.36 s    (cache amortizes 14-symbol load)
status distribution:
  PASSED          39
  REJECTED        1753
  NOT_EVALUATED   0
  ERROR           0
UNKNOWN_REJECT:   0
```

## Reject Reason Distribution

| Reason | Count | Share |
|---|---:|---:|
| no_trades_generated | 1058 | 60.4% |
| non_positive_net | 585 | 33.4% |
| too_few_trades | 110 | 6.3% |
| **UNKNOWN_REJECT** | **0** | **0%** |

## A1 / A2 Outcome

- 39 candidates cleared the shadow A2 gate (trade_count ≥ 25 AND post-cost net > 0).
- 1753 candidates failed.
- A2_MIN_TRADES = 25 unchanged (verified at services/arena_gates.py:48).

## Acceptance Mapping

- AC11 PASS shadow_batch_results.jsonl produced
- AC12 PASS every candidate has status
- AC13 PASS evaluated rejections have reject_reason (1753 / 1753)
- AC14 PASS NOT_EVALUATED candidates have blocker_reason (rule enforced; 0 in run)
- AC15 PASS UNKNOWN_REJECT explicitly reported (0)
