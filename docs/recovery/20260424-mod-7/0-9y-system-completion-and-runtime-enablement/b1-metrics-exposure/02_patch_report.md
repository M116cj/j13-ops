# 02 — Patch Report (Subprogram B1)

## Files changed

```
 zangetsu/services/arena_pass_rate_telemetry.py |  20 +++
 zangetsu/services/arena_pipeline.py            | 180 +++++++++++++++++++++++++
 2 files changed, 200 insertions(+)
```

Both changes are **additive only** (no deletions, no semantic changes to existing fields).

## Diff scope by hunk

### `zangetsu/services/arena_pass_rate_telemetry.py` (+20 lines, 3 hunks)

1. **Hunk 1** — `ArenaBatchMetrics` dataclass: add two optional fields after `source`:
   ```python
   aggregate_metrics: Optional[Dict[str, Any]] = None
   aggregate_metrics_availability: Optional[Dict[str, bool]] = None
   ```

2. **Hunk 2** — `ArenaStageMetrics` accumulator: add the same two fields after `deployable_count`. Defaults None.

3. **Hunk 3** — `build_arena_batch_metrics()`: pass-through both fields from accumulator to event.

### `zangetsu/services/arena_pipeline.py` (+180 lines, 5 hunks)

1. **Hunk 1** — `_emit_a1_batch_metrics_from_stats_safe()`: add `aggregate_metrics: dict | None = None` and `aggregate_metrics_availability: dict | None = None` kwargs. Default `None`. Plumb into the `acc` accumulator.

2. **Hunk 2** — round loop accumulator init at line ~979 (after `round_champions = 0`):
   - `_b1_round_total_cost_bps_for_sym` (cost lookup)
   - `_b1_train_gross_pnl, _b1_train_net_pnl, _b1_train_total_trades, _b1_train_sharpe, _b1_train_win_rate`
   - `_b1_val_net_pnl, _b1_val_total_trades, _b1_val_sharpe`
   - `_b1_combined_sharpe`
   - `_b1_primary_reject_gates` (currently unused; reserved for future split)

3. **Hunk 3** — after successful train backtest (`bt = backtester.run(...)`): append per-alpha train metrics to the accumulators. Defensive try/except per field.

4. **Hunk 4** — after successful val backtest (`bt_val = backtester.run(...)`): append val metrics. Same defensive pattern.

5. **Hunk 5** — at round close, before the `_emit_a1_batch_metrics_from_stats_safe(...)` call:
   - Compute median + mean from accumulators (helpers `_b1_median`, `_b1_mean`)
   - Build `_b1_aggregate_metrics` dict (15 keys: schema_version + symbol + regime + lane + cost + 10 numeric metrics + signal_density)
   - Build `_b1_availability` dict (15 corresponding booleans + 6 "separability" flags = 21 total)
   - Pass both into the emit call as new kwargs

## Invariant preservation

| Invariant | Preserved? |
|---|---|
| Conservation: `entered = passed + rejected + skipped` | YES — no change to entered/passed/rejected/skipped logic |
| `reject_reason_distribution` semantics | YES — untouched |
| Reject gate decisions (`reject_few_trades`, `reject_train_neg_pnl`, `reject_val_*`, `reject_combined_sharpe_low`) | YES — accumulator update happens BEFORE reject `continue` statements but does not influence them |
| `A2_MIN_TRADES = 25` | UNCHANGED (verified in 05_controlled_diff_report.md) |
| Cost model | UNCHANGED |
| BacktestResult schema | UNCHANGED |
| `_compute_a1_reject_deltas` per-round delta accounting (PR #50) | UNCHANGED |
| Bloom filter | UNCHANGED |
| Provenance bundle | UNCHANGED |

## Risk assessment

- **R-1 (field-name collision):** mitigated. New field names `aggregate_metrics` / `aggregate_metrics_availability` are not present in any prior consumer (verified by grep).
- **R-2 (conservation broken):** mitigated. Test `test_b1_conservation_holds_with_aggregates_present` explicitly verifies the identity holds when aggregates are populated.
- **R-3 (DB write storm):** N/A — B1 does not touch DB writers. `engine_telemetry` writer is B2's scope.
- **R-9 (existing test failure):** verified PASS — see 03_test_report.md.

## Why aggregate updates happen BEFORE reject gates

The `bt = backtester.run(...)` returns a complete result with all fields. The accumulators capture the result immediately after the `try/except` succeeds, before any reject gate fires. This is intentional: it lets us see the full distribution including alphas that subsequently get rejected at any gate, which is exactly what the master order's economic-edge diagnosis (Subprogram C) needs.

## Why a separate `_b1_*` namespace

All new locals are prefixed `_b1_` to:
1. Make the patch obvious at code-review time.
2. Ensure no name collision with existing variables.
3. Allow future removal as a single search-replace if the design is rolled back.
