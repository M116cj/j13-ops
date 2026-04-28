# 00 — State Lock (TF1 Phase 6)

**Order:** TEAM ORDER 0-9Y-TF1-TRADE-FREQUENCY-SIGNAL-AGGREGATION-DIAGNOSIS
**Parent:** MASTER ORDER 0-9Y-FINAL
**Phase:** 6 (read-only diagnosis)
**Run date:** 2026-04-28
**HEAD (j13-ops):** `348eeb7fd14a06f5a41cc75e3c5a872f7b91dbe3`

## Data source

- File: `j13@100.123.49.102:/tmp/c_batches_snapshot.jsonl`
- Provenance: extracted by parent order 0-9Y-C from `~/j13-ops/zangetsu/logs/engine.jsonl` (`event_type == arena_batch_metrics`)
- Schema: `0-9y-b1-v1` (B1 aggregate_metrics)
- Total rows: **106**
- All-primary-metrics-present rows: **106 / 106** (100% usable)

### Coverage

- Symbols (14): AAVEUSDT(13), GALAUSDT(13), LINKUSDT(13), XRPUSDT(10), SOLUSDT(8), FILUSDT(8), 1000SHIBUSDT(8), 1000PEPEUSDT(7), BNBUSDT(7), DOGEUSDT(6), DOTUSDT(4), AVAXUSDT(4), BTCUSDT(3), ETHUSDT(2)
- Regimes: BULL_TREND(40), BEAR_TREND(40), CONSOLIDATION(26)
- Stages: A1(106) — only A1 batches in snapshot
- Lanes: exploration(56), baseline(50)

## Analysis approach (read-only)

1. Quartile-bin batches by `signal_density_per_bar` and `train_total_trades_median`; compute median(`train_net_pnl_median`), median(`train_gross_pnl_median`), median(`train_gross_minus_net_median` = cost), median(`train_sharpe_median`), median(`train_win_rate_median`) per bin.
2. Pearson + Spearman correlations: trades vs (win_rate, net, gross, sharpe, cost); density vs (net, sharpe); trades vs gross/trade.
3. Top-decile by `train_sharpe_median` (n=10, top 9.4%) — compare net economics vs the rest.
4. Q1-vs-Q4 net delta with empirical AUC = P(Q1 > Q4) via pairwise comparison.
5. Per-symbol best-sharpe scan to test whether the result is symbol-driven.

## Forbidden actions (compliance)

- No edits to entry threshold, A2_MIN_TRADES (=25 LOCKED), validation, or cost. Read-only.
- No source/code/config/feature touched. No commit.

## Sample size verdict

n=106 ≥ 100 → **NOT BLOCKED_METRICS_INSUFFICIENT**.
