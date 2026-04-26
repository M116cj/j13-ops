# 07 — Materialization Watch

## 1. DB Probe Result (read-only SQL, post-PR-#37 merge)

PR #37 merged at 2026-04-26T13:17:28Z. Probe taken at ~13:32Z (~14 minutes post-merge).

| Table | Total rows | Rows after PR #37 merge | max(timestamp) |
| --- | --- | --- | --- |
| `champion_pipeline_staging` | 184 | **0** | 2026-04-21T04:34:21Z |
| `champion_pipeline_fresh` (created_at) | 89 | **0** | 2026-04-21T04:34:21Z |
| `champion_pipeline_fresh` (updated_at) | 89 | **0** | 2026-04-22T17:57:10Z |
| `champion_pipeline_rejected` (archived_at) | 0 | 0 | NULL |
| `engine_telemetry` (ts) | 0 | 0 | NULL |

| Status distribution (champion_pipeline_fresh) | Count |
| --- | --- |
| ARENA2_REJECTED | 89 |
| (any other status) | 0 |

| CANDIDATE or DEPLOYABLE rows | 0 |

## 2. Why 0 Materialization

The 13:30 stats line shows `champions=0/10` per round and `val_neg_pnl=499` (out of 500 candidates per round) per round. The 9-stage val-filter chain rejects 99.8% of all candidates at the holdout-side net-PnL gate (`bt_val.net_pnl <= 0`). The remaining ~0.2% are then rejected by `val_few` (< 15 holdout trades) or `val_wr` (Wilson-lower < 0.52). Net effect: 0 candidates reach the staging INSERT block.

This is the val-filter chain doing exactly what it was designed to do — reject overfit alphas that look profitable on train but lose money on holdout. The strict design is intentional (per the v0.5.9 + Patch E comments in the source). It is NOT broken; it is just well-calibrated for the current alpha-engine configuration, which evidently produces alphas that fit train but don't generalize.

## 3. Phase 6 Classification

Per order §Phase 6:

| Verdict | Match? |
| --- | --- |
| MATERIALIZATION_CONFIRMED (new rows in staging/fresh/rejected/telemetry after patch) | NO |
| **CRASH_FIXED_BUT_ALL_FILTERED** (A1 no longer crashes, stats line appears, but 0 rows materialize because all candidates are rejected before persistence) | **YES — exact match** |
| CRASH_FIXED_BUT_DB_WRITE_ERROR | NO |
| CRASH_NOT_FIXED | NO |
| NEW_BLOCKER_FOUND | NO |

→ **Phase 6 verdict: CRASH_FIXED_BUT_ALL_FILTERED.**
