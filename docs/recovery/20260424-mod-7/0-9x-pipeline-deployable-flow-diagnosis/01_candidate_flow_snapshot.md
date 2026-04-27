# 01 — Candidate Flow Snapshot (Phase 1)

**Phase 1 Verdict:** `FLOW_BLOCKED_AFTER_A1` — runtime active, A1 produces zero new admissions, the 89 alphas that historically reached fresh are all `ARENA2_REJECTED`. No deployables.

> Of the listed classification options, the closest single fit is `FLOW_BLOCKED_AFTER_A1`. `FLOW_ALL_REJECTED_AT_A1` partially fits the **current** behavior (last 6.5 days), but does not capture the legacy 89-alpha A2 rejection. `FLOW_HAS_FRESH_NO_DEPLOYABLES` is also true at the moment but understates the upstream stall.

## End-to-end snapshot

```
A1 (arena_pipeline w0–w3, ~56 min uptime)
   • last 100 arena_batch_metrics: 0 / 1000 passed → 0.0%
   • dominant reject in JSONL telemetry: COST_NEGATIVE
   • dominant reject in runtime stats lines: reject_train_neg (≈98–99%)
   ▼
champion_pipeline_staging
   status               | admission_state    | count
   ARENA1_COMPLETE      | admitted           |   89   ← all from 2026-04-20 18:07 → 2026-04-21 04:34
   ARENA1_COMPLETE      | admitted_duplicate |   95   ← duplicates de-duped by validator
   no rows in any other status / admission_state
   last admission: 2026-04-21 04:34:21Z (~6.5 days stale)
   ▼
champion_pipeline_fresh
   status               | card_status | count
   ARENA2_REJECTED      | INACTIVE    |   89
   arena1_completed_at: 89/89   arena2_completed_at: 89/89
   arena3_completed_at:  0/89   arena4_completed_at:  0/89
   arena2_n_trades, arena2_win_rate: NULL for all 89 (A2 ran but produced no trade-level metrics)
   ▼
champion_pipeline_rejected: 0 rows (admission_validator rejection path never fired since v0.7.1)
   ▼
zangetsu_status.deployable_count = 0   last_live_at_age_h = NULL
```

## Counts at capture

| Table | Rows |
|---|---|
| `champion_pipeline` (legacy alias) | 89 |
| `champion_pipeline_fresh` | 89 |
| `champion_pipeline_staging` | 184 (89 admitted + 95 admitted_duplicate) |
| `champion_pipeline_rejected` | 0 |
| `champion_legacy_archive` | 1564 |
| `engine_telemetry` | 0 (table empty since v0.7.1) |

## Status / state breakdowns

`champion_pipeline_staging`:

| status | admission_state | count |
|---|---|---|
| ARENA1_COMPLETE | admitted | 89 |
| ARENA1_COMPLETE | admitted_duplicate | 95 |

All staging rows are stuck at `ARENA1_COMPLETE` (no rows ever moved beyond that staging status). The 89 admitted rows match 1:1 with the 89 fresh rows.

`champion_pipeline_fresh`:

| status | card_status | count |
|---|---|---|
| ARENA2_REJECTED | INACTIVE | 89 |

100% of the historical pool died at A2 with `card_status=INACTIVE`.

## Timestamps

| Table | first | last_create | last_update |
|---|---|---|---|
| staging | 2026-04-20 18:07:49 | 2026-04-21 04:34:21 | 2026-04-21 04:34:21 |
| fresh | 2026-04-20 18:07:49 | 2026-04-21 04:34:21 | 2026-04-22 17:57:10 |
| rejected | — | — | — |

`fresh.last_update = 2026-04-22 17:57:10` (5 days ago) reflects the last `updated_at` from card-rotation or status flip; no new admission since 2026-04-21 04:34.

## A1 progression of the 89 fresh

```sql
SELECT total, a1_done, a2_done, a3_done, a4_done FROM champion_pipeline_fresh ...
```

| total | a1_done | a2_done | a3_done | a4_done |
|---|---|---|---|---|
| 89 | 89 | 89 | 0 | 0 |

A1 marker complete (entered fresh = passed A1 fitness historically).
A2 marker complete (gate ran).
A3 / A4 markers never set — none ever passed A2.

## A2 metric quartiles (the 89 fresh)

```
arena2_n_trades:    NULL for all 89
arena2_win_rate:    NULL for all 89
```

A2 was "completed" in the sense that `arena2_completed_at` is filled, but the actual trade-level metrics are NULL — meaning A2's first gate (`arena2_pass`'s `if n < A2_MIN_TRADES`) likely fired before any trade-level computation finished, **OR** A2 ran with zero trades produced from the alpha (degenerate formula → no entry signal). Combined with `fresh_pool_outcome_health.indicator_alpha_ratio_pct = 0`, the 89 are degenerate raw-OHLCV-only formulas.

## Recent log flow check

Last 1000 lines of engine.jsonl filtered for `A1|A2|A23|A45|deployable|champion|fresh|staging|rejected|traceback|error` → `/tmp/0_9x_deployable_flow_recent.log`. Pattern observed across the window: per-round summaries shape

```
RNNNNNN | SYMBOL/REGIME | champions=0/10 | ~14s | rejects: few_trades=N train_neg=N val_few=N val_neg_pnl=N val_sharpe=N val_wr=N combined_sharpe=N
```

`champions=0/10` literally **every single round** observed across all 4 workers. No exception in the recent 30+ min window.

## Aggregate distribution (last 200 batches)

`{COST_NEGATIVE: 1944, SIGNAL_TOO_SPARSE: 47, LOW_BACKTEST_SCORE: 9}` (run on prior dataset; pattern is identical across 100 / 200 / 500 windows; deeper detail in 02).

## Required Phase 1 classification

```
FLOW_BLOCKED_AFTER_A1
```

Both interpretations are simultaneously true:
- the **historical** 89 alphas got past A1 fitness once but failed at A2
- the **current** 6.5-day flow has zero alphas surviving A1 fitness in the first place
