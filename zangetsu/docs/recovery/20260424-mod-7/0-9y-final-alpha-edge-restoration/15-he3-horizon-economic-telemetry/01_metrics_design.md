# 01 — METRICS DESIGN

**TEAM ORDER**: 0-9Y-HE3-HORIZON-ECONOMIC-TELEMETRY
**Date**: 2026-04-29
**Phase**: 1 / 8

## Goal
Per-batch emission of horizon-keyed economic metrics from the per-alpha data lists already populated by the round.

## Insight: A1 round = single horizon (HE1 design)
HE1 + HE2 enforce that **one A1 round uses exactly one horizon**, shared by all alphas in that round. Therefore:
- The per-batch `horizon_metrics` map will have **only the `selected_horizon` key populated** for that batch.
- Other horizons in `ACTIVE_A1_HORIZONS` are absent from this batch (will appear in batches when their turn arrives in SIMPLE_CYCLE).
- **Cross-batch aggregation by horizon happens at consumer side** (e.g., Phase 5 analysis groups by `selected_horizon` across many batches).

This shape matches the master-order spec:
> horizon_metrics (map keyed by h; only selected_horizon must be non-empty in baseline mode)

## `horizon_metrics[h]` shape
```python
horizon_metrics: Dict[int, Dict[str, Any]] = {
    h: {
        "trade_count_median":     <median across alphas in this round>,
        "trade_count_mean":       <mean>,
        "trade_count_total":      <sum>,
        "skipped_count_total":    <0 in baseline; set when TF4 PRE-FILTER active>,
        "gross_pnl_median":       <median>,
        "gross_pnl_mean":         <mean>,
        "gross_pnl_sum":          <sum across alphas>,
        "net_pnl_median":         <median>,
        "net_pnl_mean":           <mean>,
        "net_pnl_sum":            <sum across alphas>,
        "total_cost":             <round_total_cost_bps × len(alphas)>,
        "win_rate_median":        <median>,
        "signal_density_per_bar": <existing _b1_signal_density>,
        "gross_per_trade_median": <median of (gross_i / trades_i) where trades_i>0>,
        "net_per_trade_median":   <median of (net_i / trades_i) where trades_i>0>,
        "cost_per_trade":         <round_total_cost_bps / median trade_count if applicable>,
        "cost_over_gross_ratio":  <(gross−net) / gross median>,
        "alpha_count":            <number of alphas contributing>,
        "entered_count":          <total entry edges across alphas; carries from TF4 if active>,
        "kept_count":             <entered − skipped>,
    }
}
```

## Batch-level fields (per master-order Phase 1 spec)
The existing HE1/HE2 fields stay as-is; HE3 adds:
| Field | Type | When emitted |
|---|---|---|
| `horizon_metrics` | dict[int, dict] | always (default = `{60: {...}}`) |
| `horizon_metrics_keys` (optional alias) | list[int] | always (= `list(horizon_metrics.keys())`) |

The dict is **always emitted** because the helper does the work cheaply from already-populated lists. In baseline mode, `horizon_metrics = {60: {...}}` with the same numeric values that already appear in the existing batch fields (`train_gross_pnl_median`, etc.). This is **redundant by design** — the consumer can group by horizon across batches without re-parsing `selected_horizon`.

## Conservation per horizon
For the active horizon `h = selected_horizon`:
```
entered (entry edges across alphas) = kept + skipped
```
- In **baseline mode** (TF4 PRE-FILTER OFF): `kept = entered`, `skipped = 0`. Conservation trivially holds.
- In **multi-horizon SHADOW mode** (after HE4): each batch's horizon contributes to its own `horizon_metrics[h]`; conservation per-batch is independent.
- In **TF4 PRE-FILTER active**: `_tf4_skipped_total` is non-zero; `entered_count_total - kept_count_total - skipped_count_total = 0` invariant from TF4 carries through.

## No removal / no rename rule (per master-order Phase 1 spec)
**No existing `_b1_aggregate_metrics` keys are removed or renamed by HE3.** The new `horizon_metrics` key is added under a new namespace. Existing `train_gross_pnl_median`, `train_net_pnl_median`, etc. all continue to be emitted unchanged.

## Default invariant
With env unset (single-horizon=60, no TF4, no TF3 shadow):
- `horizon_metrics = {60: {trade_count_median: ..., gross_pnl_median: ..., net_pnl_median: ..., ...}}`
- All numeric values match the corresponding existing `train_*` fields exactly
- No new failure modes introduced — pure read-only computation from already-populated lists

## Helper module
A new pure helper `zangetsu/services/horizon_metrics.py` exposes:
```python
def build_horizon_metrics(
    selected_horizon: int,
    *,
    train_gross_pnl: list[float],
    train_net_pnl: list[float],
    train_total_trades: list[int],
    train_win_rate: list[float],
    round_total_cost_bps: float | None,
    signal_density_per_bar: float | None,
    skipped_count_total: int = 0,
    kept_count_total: int = 0,
    entered_count_total: int = 0,
) -> Dict[int, Dict[str, Any]]:
    """Build {selected_horizon: {trade_count_median, gross_pnl_median, ...}}.

    Pure; no side effects; deterministic; never raises (returns empty dict on error).
    """
```

## Telemetry compatibility
Downstream consumers of `arena_batch_metrics`:
- **Existing**: `_b1_aggregate_metrics` keys all still present
- **HE3 added**: `horizon_metrics` (additive top-level key inside `aggregate_metrics`)

Consumer parsing: `aggregate_metrics["horizon_metrics"]` returns the dict. Default schema for old consumers: ignore the new key (Python dicts are extensible).

## Q1 5-dim per-design

| Dim | Result |
|---|---|
| Input boundary | helper handles empty lists (returns `{h: {alpha_count: 0, ...}}` with all numeric fields None) |
| Silent failure propagation | helper wrapped in try/except in arena_pipeline; helper itself returns empty dict on internal error |
| External dependency | none — pure data manipulation |
| Concurrency / race | helper is stateless; per-batch invocation has independent inputs |
| Scope creep | strictly telemetry; no validation/cost/A2 references in helper or call site |

## Verdict
**METRICS_DESIGN_READY** — additive, baseline-preserving, pure-helper-based.

## Next
Phase 2 — patch implementation.
