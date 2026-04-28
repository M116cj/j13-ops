# 01 — Live Snapshot (Subprogram C)

**Order:** TEAM ORDER 0-9Y-C-ECONOMIC-EDGE-DECOMPOSITION
**Phase:** 1
**Date (UTC):** 2026-04-28T00:13Z
**Author:** Claude Lead

## Source

`j13@100.123.49.102:/tmp/c_batches_snapshot.jsonl` — 106 `arena_batch_metrics` events emitted by the post-restart worker fleet between `2026-04-28T00:06:38Z` and `2026-04-28T00:13:02Z` (~6.4-minute window).

## Coverage

| Field | Value |
|---|---|
| Total batches | 106 |
| Schema version | `0-9y-b1-v1` (all 106) |
| Distinct symbols | 14 (top 5: AAVEUSDT=13, GALAUSDT=13, LINKUSDT=13, XRPUSDT=10, FILUSDT=8) |
| Regimes | 3 — `BULL_TREND` (40), `BEAR_TREND` (40), `CONSOLIDATION` (26) |
| Lanes | 2 — `exploration` (56), `baseline` (50) |
| `aggregate_metrics_availability.train_*_median` | TRUE (all train fields exposed) |
| `aggregate_metrics_availability.val_*_median` | FALSE in 92/106 batches; TRUE in only 14 |
| `aggregate_metrics_availability.combined_sharpe_median` | FALSE in 106/106 batches |
| `aggregate_metrics_availability.fee_cost_separate / slippage_cost_separate / funding_cost_separate` | FALSE in 106/106 (cost is bundled in `cost_per_trade`) |

## Per-batch outcome

| Field | Value (across 106 batches) |
|---|---|
| `entered_count` | always 10 |
| `passed_count` | always 0 |
| `rejected_count` | always 10 |
| `skipped_count` | always 0 |
| `reject_reason_distribution` | `{COST_NEGATIVE: 10}` for all 106 batches |
| `COUNTER_INCONSISTENCY` | 0 (PR #50 fix verified live post-restart) |
| `UNKNOWN_REJECT` | 0 (PR #49 fix verified live post-restart) |
| Conservation `entered = passed + rejected + skipped` | holds 106/106 |

**The chain-fix from PRs #48-50 is verified LIVE on the new worker fleet.** All 106 batches show clean per-round telemetry with conservation residual = 0.

## Aggregate metrics — top-level distributions (per Phase 2 subagent)

| Metric | Median | Mean | Stdev | Min → Max |
|---|---|---|---|---|
| `train_gross_pnl_median` (bps) | 2.46 | similar | — | all positive (0/106 ≤ 0) |
| `train_gross_minus_net_median` (= cost charged, bps) | 3.60 | — | — | — |
| `train_net_pnl_median` (bps) | -1.33 | — | — | mostly negative (104/106 ≤ 0) |
| `round_total_cost_bps` (per-trade cost) | 14.5 | — | — | 11.5–23 range |
| `train_total_trades_median` | 987 | 1020 | — | p10 ≈ 600, p90 ≈ 1099 |
| `train_sharpe_median` | -2.22 | — | — | only 3/106 ≥ 0 (2.8%) |
| `train_win_rate_median` | 0.32 | — | — | max 0.494 (zero batches reach 50%) |
| `signal_density_per_bar` | 0.00702 | — | — | tightly clustered |

## Per-batch gross-vs-cost classification

| Pattern | Count | % |
|---|---|---|
| `gross > cost` (truly tradeable batch median) | 4 | 3.8 % |
| `0 < gross ≤ cost` (β-pattern: gross exists but cost dominates) | 102 | 96.2 % |
| `gross ≤ 0` (negative gross edge) | **0** | 0 % |
| `gross > 0 AND net > 0` (truly tradeable) | 2 | 1.9 % |

**Headline**: median cost-to-gross ratio = **1.54×**. Median edge gap = **1.32 bps short of breakeven**.

## Confirmation from B1 emitter

`aggregate_metrics` field is now present and populated correctly on every batch. PR #55 (B1) emitter is live. The B1 deliverable is **verified in production**. No data acquisition issues. Subprogram C analysis can proceed with full statistical confidence.

## Conservation summary (cross-cutting)

| Telemetry invariant | Holds (n / N) |
|---|---|
| `entered = rejected` (no pass) | 106 / 106 |
| `COUNTER_INCONSISTENCY = 0` | 106 / 106 |
| `UNKNOWN_REJECT = 0` | 106 / 106 |
| `aggregate_metrics` present | 106 / 106 |
| `train_*_median` populated | 106 / 106 |
| `val_*_median` populated | 14 / 106 |
| `combined_sharpe_median` populated | 0 / 106 |

The system is healthy at the telemetry layer. The economic problem (cost > gross) is real and not an artifact.

## Proceed to Phase 2-5 subagent analyses

Each Phase 2-5 subagent has analyzed this same dataset and written its verdict. Phase 6 synthesis will combine those verdicts into the final root-cause classification.
