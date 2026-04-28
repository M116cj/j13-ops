# 02 — SIGNAL AGGREGATION DESIGN

**TEAM ORDER**: 0-9Y-TF2-SIGNAL-AGGREGATION-PROTOTYPE
**Date**: 2026-04-28
**Phase**: 2 / 8

## Context — current signal path
`zangetsu/engine/components/alpha_signal.py:generate_alpha_signals()` produces three NumPy arrays per alpha per (symbol × regime):
- `signals: int8[N]` — `+1` long / `−1` short / `0` flat (state-machine continuous holds)
- `sizes:   float64[N]` — position size = `|rolling_rank − 0.5| × 2` ∈ [0, 1]
- `agreements: float32[N]` — identical formula to `sizes`; the **per-bar signal strength / extremity** measure

Caller: `services/arena_pipeline.py:1049` ⟶ `backtester.run(signals, ..., sizes=sizes)`. `agreements` is **not** consumed by backtester.

## Where TF2 aggregation lives
**Insertion**: between `generate_alpha_signals()` and `backtester.run()`, as a pure helper. Default profile `OFF` returns inputs unchanged. The SHADOW caller passes filtered `signals` to a parallel backtest call for comparison. The live path is **never** modified by default.

```
alpha_values
  ↓ generate_alpha_signals()
(signals, sizes, agreements)
  ↓
+----------------------------------------+
| signal_aggregation.apply(...)          |  ← TF2 prototype helper, default OFF
+----------------------------------------+
  ↓
(signals_kept, sizes_kept, AggregationResult)
  ↓ backtester.run()  (only invoked in SHADOW path)
```

Live path remains unchanged: `arena_pipeline.py` calls `apply_signal_aggregation(..., profile="OFF")` (or doesn't call it at all) → identical behavior to today.

## Critical entry-edge rule (safety)
`signals` is a state-machine output: once a long position opens at bar `e`, `signals[e:x] = +1` until the exit bar `x`. **Naively zeroing weak bars mid-trade would prematurely terminate the trade from the backtester's perspective.** Therefore aggregation operates only on **entry transitions** (`signals[i-1] == 0 and signals[i] != 0`):
- Identify entry bars via diff.
- Suppress the entire trade segment (entry bar through next 0) when the entry-bar strength fails the profile criterion.
- Counted as `skipped_count += 1` per suppressed trade (one trade = one entry-edge).

This guarantees the conservation identity `entered = passed + rejected + skipped + in_flight + error` holds at the trade-level, and there is no in-flight half-trade artifact.

## Where signal_strength comes from
`agreements[i]` (≡ `sizes[i]`) is a clean `[0, 1]` extremity score already computed per bar. We use **`sizes` as `signal_strength`** because it is what the backtester already receives and is the canonical source of position weighting — keeps semantics consistent and avoids ambiguity.

## Profile catalog

### Profile 0 — `OFF` (alias `BASELINE`)
- pass-through
- `kept = entered`, `skipped = 0`
- `AggregationResult.signals == input.signals`
- *intent*: regression sentinel; required to be identical to no-op

### Profile 1 — `STRENGTH_FILTER`
- Parameter: `strength_quantile ∈ (0, 1)` — default `0.90` (top 10%)
- Process per (signal series): compute the q-quantile of **strengths at entry-edges only**, suppress entries below threshold.
- Recommended sweeps: `{0.90, 0.95, 0.98}` ≈ top 10% / top 5% / top 2%.
- Validator threshold (entry_rank_threshold=0.80 in `alpha_signal.py`) is **NOT** changed.

### Profile 2 — `TOP_K_PER_BAR`
- Parameter: `top_k: int` — default 30
- Process per (signal series): rank entry-edges by strength, keep the top K strongest entries; suppress the rest.
- Recommended sweeps: `K ∈ {10, 30, 50}` — calibrated against current ~982 trades/batch median.
- Note on naming: master order says "per bar, keep top K strongest signals". Single-alpha pipeline produces ≤1 signal per bar → "per bar" reduces to "across the series, keep K strongest bar-entries". Documented limitation.

### Profile 3 — `CONSENSUS_2_OF_3` — **DESIGN-ONLY (deferred)**
- Goal: require ≥2 of {formula signal, profile-family signal, symbol/regime signal} to agree on direction at the entry bar.
- **Why deferred**: arena_pipeline evaluates **one alpha per cycle** (the per-(symbol×regime) candidate); cross-alpha consensus would require re-architecting the inner loop and a parallel signal cache. Out of TF2 prototype scope.
- Documented as future work for TF3 / TF4. Placeholder profile name returns `not_implemented` with explicit error in unknown-profile fail-closed test.

### Profile 4 — `HYBRID_TOPK_STRENGTH`
- Apply `STRENGTH_FILTER` first (entries below quantile q dropped), then `TOP_K_PER_BAR` on the survivors.
- Parameters: `(strength_quantile, top_k)` — default `(0.90, 30)`.
- Use case: bound both the bar-level strictness and the absolute trade-count.

## Aggregation result shape
```python
@dataclass(frozen=True)
class AggregationResult:
    signals: np.ndarray         # int8[N], filtered
    sizes:   np.ndarray         # float64[N], filtered (cleared on suppressed segments)
    kept:    np.ndarray         # bool[K], one per ENTRY EDGE, True = trade kept
    profile: str                # "OFF" | "STRENGTH_FILTER" | "TOP_K_PER_BAR" | "HYBRID_TOPK_STRENGTH" | "CONSENSUS_2_OF_3"
    entered_count: int          # number of entry edges in input
    kept_count: int             # number of trades kept
    skipped_count: int          # entered_count - kept_count
    metadata: dict              # threshold, top_k, strength_at_thresh, mean_strength_kept, ...
```

## Telemetry additions
Per arena_batch_metrics emission, when SHADOW path is invoked:
- `aggregation_profile`: str
- `aggregation_skipped_count`: int (total across all alphas in batch)
- `aggregation_kept_count`: int
- `aggregation_skip_reason_distribution`: dict (e.g. `{"strength_below_q": 12, "below_topk_rank": 8}`)
- `aggregation_strength_threshold`: float (when applicable)
- `aggregation_top_k`: int (when applicable)

Conservation identity becomes: `entered = passed + rejected + skipped + in_flight + error`. The `skipped_count` is already in the schema (always 0 today) — TF2 SHADOW path increments it.

## Safety invariants
| Invariant | Mechanism |
|---|---|
| Default live path unchanged | `apply_signal_aggregation(..., profile="OFF")` is pass-through; arena_pipeline default value = `"OFF"` (or the call is gated behind a SHADOW-only flag) |
| Validator threshold unchanged | helper does NOT touch `entry_rank_threshold`/`exit_rank_threshold` in `alpha_signal.py` |
| Cost model unchanged | helper operates on signals/sizes only; cost is computed downstream by backtester unchanged |
| `A2_MIN_TRADES = 25` unchanged | helper does not touch A2 gate code or thresholds |
| Conservation holds | aggregation operates on entry-edges; entered = kept + skipped at trade level |
| No NaN propagation | NaN strength → treated as `−∞` (always suppressed); never raises |
| Deterministic | `np.argsort(strength, kind="stable")` for top-K; sort-tied by index |
| No future leakage | aggregation only inspects `strength[i]` at entry bar `i`, no look-ahead |
| No mutation of input | helper returns new arrays (np.copy) — input arrays untouched |
| Unknown profile fails closed | `profile not in ALLOWED_PROFILES` → raise `ValueError` (caller's responsibility to choose; never silently passes) |
| No alpha_zoo / CANARY / production flags | helper has zero coupling to those subsystems |
| Artifact risk | helper does not change which symbols / regimes are evaluated; `aggregation_skip_reason_distribution` exposes per-call decisions for audit |

## Mode of operation
- **offline / SHADOW-only**: SHADOW caller picks a profile, runs aggregation + backtest, compares to BASELINE in same batch.
- **runtime-selectable, default OFF**: arena_pipeline accepts an optional `aggregation_profile=None` parameter; when None or `"OFF"` → no aggregation invoked. Defaults to None (live behavior unchanged).
- **Production / CANARY**: NOT enabled. Hard-blocked by master order.

## Classification
**DESIGN_READY_FOR_SHADOW_PROTOTYPE**

Strength-filter and Top-K paths are unambiguous. Consensus deferred with explicit reason.

## Next
Proceed to Phase 3 — implementation in `zangetsu/services/signal_aggregation.py`.
