# 04 — Live Sample (Subprogram B1)

## Status: deferred to post-merge worker restart

The live sample evidence requires the patched A1 workers to be running. Per the §17.6 stale-service rule, a worker restart is needed after the PR merges to /main and Alaya pulls. **This restart is operator-authorized**, not autonomous within this PR's scope.

## Pre-merge expectation

Once `zangetsu_ctl.sh restart` runs against the new HEAD, the next `arena_batch_metrics` event in `zangetsu/logs/engine.jsonl` will include the new top-level fields:

```json
{
  "event_type": "arena_batch_metrics",
  "telemetry_version": "1",
  ...
  "reject_reason_distribution": {"COST_NEGATIVE": 10},
  "aggregate_metrics": {
    "schema_version": "0-9y-b1-v1",
    "symbol": "LINKUSDT",
    "regime": "BULL_TREND",
    "lane": "baseline",
    "round_total_cost_bps": 14.5,
    "alphas_with_train_backtest": <int>,
    "alphas_with_val_backtest": <int>,
    "alphas_with_combined_sharpe": <int>,
    "train_gross_pnl_median": <float | null>,
    "train_gross_pnl_mean":   <float | null>,
    "train_net_pnl_median":   <float | null>,
    "train_net_pnl_mean":     <float | null>,
    "train_gross_minus_net_median": <float | null>,
    "train_total_trades_median":    <int   | null>,
    "train_total_trades_mean":      <float | null>,
    "train_sharpe_median":          <float | null>,
    "train_win_rate_median":        <float | null>,
    "val_net_pnl_median":           <float | null>,
    "val_total_trades_median":      <int   | null>,
    "val_sharpe_median":            <float | null>,
    "combined_sharpe_median":       <float | null>,
    "signal_density_per_bar":       <float | null>
  },
  "aggregate_metrics_availability": {
    "round_total_cost_bps": true,
    "train_gross_pnl_median": <bool>,
    "train_gross_pnl_mean":   <bool>,
    "train_net_pnl_median":   <bool>,
    "train_net_pnl_mean":     <bool>,
    "train_gross_minus_net_median": <bool>,
    "train_total_trades_median":    <bool>,
    "train_total_trades_mean":      <bool>,
    "train_sharpe_median":          <bool>,
    "train_win_rate_median":        <bool>,
    "val_net_pnl_median":           <bool>,
    "val_total_trades_median":      <bool>,
    "val_sharpe_median":            <bool>,
    "combined_sharpe_median":       <bool>,
    "signal_density_per_bar":       <bool>,
    "fee_cost_separate":             false,
    "slippage_cost_separate":        false,
    "funding_cost_separate":         false,
    "long_trade_count_separate":     false,
    "short_trade_count_separate":    false,
    "primary_reject_gate_explicit":  false
  }
}
```

## Pre-restart sanity (current emit)

A live sample BEFORE the restart confirms the existing event shape (so we can diff it against the post-restart sample later):

```json
{"arena_stage": "A1",
 "batch_id": "R...-LINKUSDT-BULL_TREND",
 "entered_count": 10, "passed_count": 0,
 "rejected_count": 10, "skipped_count": 0,
 "reject_reason_distribution": {"COST_NEGATIVE": 10},
 "top_reject_reason": "COST_NEGATIVE",
 "event_type": "arena_batch_metrics",
 "telemetry_version": "1",
 "timestamp_start": "2026-04-27T18:21Z"}
```

(no `aggregate_metrics` field present pre-merge)

## Post-restart verification commitment

After PR merge + worker restart:
1. Capture last 100 `arena_batch_metrics` events from `engine.jsonl`.
2. Verify every event contains `aggregate_metrics` and `aggregate_metrics_availability`.
3. Verify `schema_version == "0-9y-b1-v1"`.
4. Verify availability flags are coherent (e.g., `train_gross_pnl_median` boolean matches whether `alphas_with_train_backtest > 0`).
5. Verify the conservation parser from PR #51 still returns 100/100 `residual=0`.
6. Append the captured sample to this file as an appendix.

## Verdict implication

This PR's verdict is `PARTIAL_METRICS_EXPOSED_WITH_NULL_FLAGS` (per master order options) for two reasons:

1. **Six fields are not separately exposed** by the engine and are flagged `*_separate: false`:
   - fee_cost / slippage_cost / funding_cost (bundled in `cost_per_trade`)
   - long_trade_count / short_trade_count (in trade_log array but not exposed by BacktestResult)
   - primary_reject_gate_explicit (available indirectly via top_reject_reason)

2. **Live runtime verification of the new fields is gated** on the post-merge restart, which is operator-authorized rather than autonomous-PR-merge. This file documents the expected shape and the verification protocol.

The verdict is "PARTIAL" not "COMPLETE" because (1) is a real exposure gap with documented availability flags. The order's spec explicitly accepts this: "add explicit null fields with availability flags rather than inventing values."
