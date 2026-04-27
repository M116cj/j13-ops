# 06 — Final Report (Subprogram B1)

**Order:** TEAM ORDER 0-9Y-B1-PIPELINE-METRICS-EXPOSURE-FIX

## Final verdict

```
PARTIAL_METRICS_EXPOSED_WITH_NULL_FLAGS
```

## Summary table

| Field | Value |
|---|---|
| Master order | 0-9Y / Subprogram B1 |
| Branch | `phase-8/0-9y-b1-pipeline-metrics-exposure` |
| Pre-PR HEAD | `486e726b` (origin/main after PR #54) |
| Files modified | `zangetsu/services/arena_pass_rate_telemetry.py` (+20), `zangetsu/services/arena_pipeline.py` (+180) |
| Files added | `zangetsu/tests/test_b1_aggregate_metrics_exposure.py` (+10 tests, ~150 LOC) |
| Test result | 10/10 new B1 tests + 102/102 pre-existing telemetry tests = 112 PASS |
| Conservation invariant | preserved (verified by both pre-existing + new tests) |
| A2_MIN_TRADES = 25 | unchanged |
| alpha_zoo write-guard | intact |
| APPLY / runtime-switchable | unchanged |
| Forbidden ops | 0 |
| Live verification | DEFERRED to post-merge worker restart (operator-authorized; protocol in 04_live_sample.md) |

## Why `PARTIAL_METRICS_EXPOSED_WITH_NULL_FLAGS`

Per the master order's options, the verdict is `PARTIAL_*` because **6 of the 16 requested fields are not separately exposable** by the underlying engine without changing `BacktestResult` schema (out of B1 scope):

| Field | Why unavailable | Availability flag |
|---|---|---|
| `fee_cost` | `cost_per_trade` is a single bps value bundled across fee+slip+funding | `fee_cost_separate: false` |
| `slippage_cost` | same | `slippage_cost_separate: false` |
| `funding_cost` | same | `funding_cost_separate: false` |
| `long_trade_count` | `trade_log` numpy array carries direction but `BacktestResult` does not expose split | `long_trade_count_separate: false` |
| `short_trade_count` | same | `short_trade_count_separate: false` |
| `primary_reject_gate` | available indirectly via `top_reject_reason` on the same event | `primary_reject_gate_explicit: false` |

Per master-order spec: "add explicit null fields with availability flags rather than inventing values." → done.

## What is exposed

**10 numeric medians/means + 4 identifiers + 1 derived field = 15 keys in `aggregate_metrics`:**

```
schema_version, symbol, regime, lane, round_total_cost_bps,
alphas_with_train_backtest, alphas_with_val_backtest, alphas_with_combined_sharpe,
train_gross_pnl_median, train_gross_pnl_mean,
train_net_pnl_median, train_net_pnl_mean,
train_gross_minus_net_median,
train_total_trades_median, train_total_trades_mean,
train_sharpe_median, train_win_rate_median,
val_net_pnl_median, val_total_trades_median, val_sharpe_median,
combined_sharpe_median, signal_density_per_bar
```

**21 boolean availability flags** in `aggregate_metrics_availability` (one per metric + 6 separability flags listed above).

## What this enables for downstream work

- **Subprogram C** (`Economic Edge Decomposition`) can now distinguish:
  - `gross < 0` vs `0 < gross < cost` via `train_gross_pnl_median` and `train_gross_minus_net_median`
  - whether train fails differently from val via `val_*_median` fields
  - whether the cost is plausibly the killer via `round_total_cost_bps`
  - whether signals are sparse via `signal_density_per_bar`

- **Subprogram F** (`Deployable Flow Recheck`) can verify whether redesign work changes the gross-edge distribution.

## Required Phase B1 classification

| Field | Status |
|---|---|
| metric_source_map | 01_metric_source_map.md |
| patch_report | 02_patch_report.md |
| test_report | 03_test_report.md (112 tests pass) |
| live_sample | 04_live_sample.md (deferred to post-restart) |
| controlled_diff_report | 05_controlled_diff_report.md (forbidden ops = 0) |

## Next subprogram

```
TEAM ORDER 0-9Y-B2-ENGINE-TELEMETRY-DIAGNOSIS-AND-REPAIR
```

## Forbidden ops audit

No threshold change, no validation change, no pass/fail change, no champion promotion change, no cost model change, no deployable semantics change, no DB schema change, no alpha_zoo write, no CANARY start, no production rollout, no kill switch disable, no force-push, no log wipe.

**Forbidden ops: 0.**
