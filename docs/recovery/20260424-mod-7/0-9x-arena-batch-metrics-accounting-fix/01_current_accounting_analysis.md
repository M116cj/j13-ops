# 01 — Current Accounting Analysis

Order: TEAM ORDER 0-9X-ARENA-BATCH-METRICS-ACCOUNTING-FIX
Phase: 1
Date (UTC): 2026-04-27
Author: Claude Lead

## Goal

Prove via live evidence that the conservation identity `entered = passed + rejected + skipped` does NOT hold pre-fix.

## Live batch sample (3 consecutive batches)

Captured from `/home/j13/j13-ops/zangetsu/logs/engine.jsonl` on Alaya at HEAD `0370b3e`:

### Batch R328310 — `GALAUSDT-BEAR_RALLY` @ `2026-04-27T15:13:31Z`

```json
{
  "arena_stage": "A1",
  "batch_id": "R328310-GALAUSDT-BEAR_RALLY",
  "entered_count": 10,
  "passed_count": 0,
  "rejected_count": 34190,
  "skipped_count": 0,
  "reject_reason_distribution": {
    "COST_NEGATIVE": 16,
    "COUNTER_INCONSISTENCY": 17090,
    "LOW_BACKTEST_SCORE": 5,
    "SIGNAL_TOO_SPARSE": 9,
    "UNKNOWN_REJECT": 17070
  },
  "top_reject_reason": "COUNTER_INCONSISTENCY"
}
```

**Conservation check**:
```
entered = 10
passed + rejected + skipped = 0 + 34190 + 0 = 34190
residual_implied = 10 - 34190 = -34180  ← BROKEN
```

**Reverse-engineer the pre-CI computation**:
```
sum(rejects ex-CI) = 16 + 5 + 9 + 17070 = 17100   (cumulative since worker start)
residual_pre_CI    = 10 - 0 - 17100 = -17090
CI bucket         += abs(residual_pre_CI) = 17090   ✓ matches event
rejected_count    += 17090 → 17100 + 17090 = 34190  ✓ matches event
```

The current code's "residual-correction" branch absorbs the cumulative-vs-per-round mismatch by inflating `rejected_count` and adding `abs(residual)` to the CI bucket. Conservation is broken at the telemetry-event level — downstream consumers see `entered_count=10` and `rejected_count=34190` without explanation.

### Batch R328311 — `DOTUSDT-BULL_PULLBACK` @ `2026-04-27T15:13:46Z` (Δ +15s)

`reject_reason_distribution`:
- COST_NEGATIVE = 16 (unchanged)
- COUNTER_INCONSISTENCY = **17100** (+10)
- LOW_BACKTEST_SCORE = 5 (unchanged)
- SIGNAL_TOO_SPARSE = 9 (unchanged)
- UNKNOWN_REJECT = **17080** (+10)

`rejected_count = 34210` (+20)

### Batch R328312 — `GALAUSDT-BEAR_RALLY` @ `2026-04-27T15:14:03Z` (Δ +17s)

`reject_reason_distribution`:
- COUNTER_INCONSISTENCY = **17110** (+10 from R328311)
- UNKNOWN_REJECT = **17090** (+10)
- (rest unchanged)

`rejected_count = 34230` (+20)

## Pattern

Each consecutive batch increments `COUNTER_INCONSISTENCY` and `UNKNOWN_REJECT` by ~+10, exactly equal to `entered_count` for that batch. This is consistent with:
- Worker is rejecting all 10 candidates each round (passed_count=0 in all 3 batches)
- The 10 new rejects are mostly mapped via `RAW_TO_REASON` to `COST_NEGATIVE` or `LOW_BACKTEST_SCORE` (which stay flat across batches because cumulative; the incremental contribution is hidden inside the cumulative number) OR fall through to `UNKNOWN_REJECT` because the running workers still have the **pre-taxonomy-hotfix** `RAW_TO_REASON` in memory (workers haven't restarted since 08:04Z; PR #49 merged at ~14:50Z but workers don't pick up source changes without restart).
- The "extra" +10 to `CI` = `entered - passed - new_rejects_already_counted_as_canonical` ≈ `entered - 0 - 0` = `10` (since the new rejects flow to UR and are subtracted out, the conservation residual matches per-round entered). After fix this collapses to zero or near-zero.

## Conclusion

Residual is not zero. `COUNTER_INCONSISTENCY` is a structural artifact of the cumulative-vs-per-round mismatch, not a real signal failure. **Phase 1 PROOF complete**. Proceed to Phase 2 patch design.
