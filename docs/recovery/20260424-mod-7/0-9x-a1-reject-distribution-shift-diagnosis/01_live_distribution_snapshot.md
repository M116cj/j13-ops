# 01 — Live A1 Reject Distribution Snapshot

TEAM ORDER 0-9X-A1-REJECT-DISTRIBUTION-SHIFT-DIAGNOSIS — Phase 1 evidence
(read-only forensics; no source / runtime mutation).

## Capture metadata

- Source log: `/home/j13/j13-ops/zangetsu/logs/engine.jsonl` on Alaya (100.123.49.102)
- Tail snapshot: `/tmp/0_9x_engine_tail_20000.jsonl` (15533 lines — full live file at capture; rotated history sits in `engine.jsonl.1`)
- Aux capture: `/tmp/0_9x_recent_arena_batch_metrics.txt` (last 50 `arena_batch_metrics` line numbers)
- Captured: 2026-04-27 ~14:00Z by `log-forensics-agent`
- Method: SSH + python3 heredoc parsers (`/tmp/0_9x_dist_aggregator.py`, `/tmp/0_9x_stage_aggregator.py`) — not committed.

## Time window

- First ts (top of tail): `2026-04-27T10:58:53`
- Last ts (bottom of tail): `2026-04-27T14:00:22`
- Wall span covered: ~3h 1m
- Lines parsed as JSON: 15533 / 15533 (100%)

## arena_batch_metrics events

- Events parsed: **726**
- All carry `arena_stage=A1`, `event_type=arena_batch_metrics`, `telemetry_version` present, full `reject_reason_distribution` map present.

### Aggregate `reject_reason_distribution` (sum across all 726 batches)

| reject_reason | count | share |
|---|---:|---:|
| COUNTER_INCONSISTENCY | 7,648,410 | 50.02% |
| UNKNOWN_REJECT | 7,641,019 | 49.97% |
| COST_NEGATIVE | 6,928 | 0.045% |
| SIGNAL_TOO_SPARSE | 5,357 | 0.035% |
| LOW_BACKTEST_SCORE | 2,366 | 0.015% |
| **Total** | **15,304,080** | 100% |

Two near-mirror buckets dominate: `COUNTER_INCONSISTENCY` and `UNKNOWN_REJECT` together account for **~99.95%** of all A1 rejects. Three legitimate reasons (`COST_NEGATIVE`, `SIGNAL_TOO_SPARSE`, `LOW_BACKTEST_SCORE`) sum to <0.1%.

### Per-batch CI vs UR pairing

| Pair predicate | batch count |
|---|---:|
| Batches where `COUNTER_INCONSISTENCY` and `UNKNOWN_REJECT` both present | **726 / 726** |
| Pairs where the two counts are exactly equal | **0** |
| Pairs where the two counts differ | **726** |

The mismatch is small but consistent: in every observed batch, `COUNTER_INCONSISTENCY` is greater than `UNKNOWN_REJECT` by a tiny offset (typically 2). First three observed pairs:

| ts | batch_id | COUNTER_INCONSISTENCY | UNKNOWN_REJECT | delta |
|---|---|---:|---:|---:|
| 2026-04-27T10:58:53 | R327292-DOGEUSDT-BEAR_TREND | 6,910 | 6,908 | +2 |
| 2026-04-27T10:59:08 | R327293-DOGEUSDT-BEAR_TREND | 6,920 | 6,918 | +2 |
| 2026-04-27T10:59:22 | R327294-DOTUSDT-BULL_PULLBACK | 6,930 | 6,928 | +2 |

Implication for Phase 2: the two buckets are **not** pure aliases — but their per-batch values are within ±2 across 726 consecutive batches, strongly indicating shared upstream provenance (likely the same train-side reject path being double-counted into both taxonomies, with a small set of edge cases — equal to the per-batch `val_neg_pnl=5` plus boundary candidates — not quite mirroring).

## A1 stage event coverage (full tail, all events)

| metric | value |
|---|---:|
| Total parsed lines | 15,533 |
| Events tagged `arena_stage=A1` | 15,237 |
| Events tagged any other stage | 0 |

### Top per-candidate `reject_reason` values (NOT the batch metrics — individual stage events)

| reject_reason | count |
|---|---:|
| TRAIN_NEG_PNL | 7,246 |
| SIGNAL_TOO_SPARSE | 4 |

Only two distinct per-candidate `reject_reason` values surface in the structured field across the 3-hour window. `TRAIN_NEG_PNL` (the train-side negative-PnL eliminator) accounts for 99.94% of identified per-candidate rejections.

## Explicit `val_neg_pnl` evidence

- Substring `val_neg_pnl` present in tail: **True**
- Occurrence count: **72** (one per legacy INFO summary line, format
  `R<id> | <market>/<regime> | champions=N/M | <s>s | rejects: few_trades=N train_neg=N val_few=N val_neg_pnl=N val_sharpe=N val_wr=N combined_sharpe=N`)
- Per-batch typical pattern: `train_neg≈6988`, `val_neg_pnl=5`, `few_trades=5`, `val_wr=2`, others = 0.
- The val-side eliminator IS firing — but at **~5 candidates per batch**, three orders of magnitude below `train_neg`. It is observable in the unstructured `msg` text but does NOT surface as a distinct key in `reject_reason_distribution` (which lumps it under `COUNTER_INCONSISTENCY`/`UNKNOWN_REJECT`).

## Two representative raw `arena_batch_metrics` samples

Sample 1 (truncated to first 25 keys):

```json
{
  "ts": "2026-04-27T10:58:53",
  "msg_keys": [
    "arena_stage", "batch_id", "deployable_count", "entered_count",
    "error_count", "event_type", "generation_profile_fingerprint",
    "generation_profile_id", "in_flight_count", "pass_rate",
    "passed_count", "reject_rate", "reject_reason_distribution",
    "rejected_count", "run_id", "skipped_count", "source",
    "telemetry_version", "timestamp_end", "timestamp_start",
    "top_reject_reason"
  ],
  "reject_reason_distribution": {
    "COST_NEGATIVE": 5,
    "COUNTER_INCONSISTENCY": 6910,
    "LOW_BACKTEST_SCORE": 2,
    "SIGNAL_TOO_SPARSE": 5,
    "UNKNOWN_REJECT": 6908
  }
}
```

Sample 2 (truncated to first 25 keys):

```json
{
  "ts": "2026-04-27T10:59:08",
  "msg_keys": [
    "arena_stage", "batch_id", "deployable_count", "entered_count",
    "error_count", "event_type", "generation_profile_fingerprint",
    "generation_profile_id", "in_flight_count", "pass_rate",
    "passed_count", "reject_rate", "reject_reason_distribution",
    "rejected_count", "run_id", "skipped_count", "source",
    "telemetry_version", "timestamp_end", "timestamp_start",
    "top_reject_reason"
  ],
  "reject_reason_distribution": {
    "COST_NEGATIVE": 5,
    "COUNTER_INCONSISTENCY": 6920,
    "LOW_BACKTEST_SCORE": 2,
    "SIGNAL_TOO_SPARSE": 5,
    "UNKNOWN_REJECT": 6918
  }
}
```

## Findings handed to Phase 2

1. **Distribution is collapsed.** ~99.95% of A1 rejects are `COUNTER_INCONSISTENCY` + `UNKNOWN_REJECT`; the legitimate taxonomy buckets (`COST_NEGATIVE`, `SIGNAL_TOO_SPARSE`, `LOW_BACKTEST_SCORE`) are reduced to noise (<0.05% combined).
2. **CI/UR pair is near-mirror, not exact alias.** All 726 batches show both keys; CI consistently exceeds UR by a small fixed-ish offset (commonly +2). Phase 2 should test whether the offset equals legitimate-bucket sums or per-batch `val_neg_pnl + few_trades` boundary count.
3. **Per-candidate `reject_reason` is binary in practice.** Only `TRAIN_NEG_PNL` (n=7246) and `SIGNAL_TOO_SPARSE` (n=4) appear in the structured field — `val_neg_pnl` rejects exist (72 batches × ~5/batch in legacy text) but never surface as a structured `reject_reason` key.
4. **`val_neg_pnl` is alive but invisible to the taxonomy.** Phase 2 should confirm whether `val_neg_pnl` events are absorbed into `UNKNOWN_REJECT` (and possibly double-counted into `COUNTER_INCONSISTENCY`) — that hypothesis is consistent with the ±2 CI−UR delta and the 5/batch val_neg_pnl rate.
5. **Volume sanity.** ~7.65M rejects across 726 batches in 3h ≈ 10.5k rejects/batch ≈ ~6,990 train_neg + ~5 val_neg_pnl + minor other per batch. A1 is producing candidates and rejecting them at expected industrial rate; the bug is in the **labelling layer**, not the rejection layer.

## Provenance / verification

- Acceptance: re-run `/tmp/0_9x_dist_aggregator.py` against `/tmp/0_9x_engine_tail_20000.jsonl`; numeric outputs above must reproduce byte-for-byte.
- The tail file is a frozen copy at capture time; the live `engine.jsonl` continues to grow.
- No source modified. No runtime mutated. No commit performed.
