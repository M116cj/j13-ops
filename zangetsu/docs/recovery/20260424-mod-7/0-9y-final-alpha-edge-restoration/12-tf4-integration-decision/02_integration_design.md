# 02 — INTEGRATION DESIGN

**TEAM ORDER**: 0-9Y-TF4-INTEGRATION-DECISION
**Date**: 2026-04-28
**Phase**: 2 / 8

## Decision
```
aggregation_mode = PRE_FILTER + SHADOW
```
Pre-filter: when enabled, the chosen profile transforms `(signals, sizes)` **before** they reach the existing baseline backtester. The baseline validation / cost / promotion path operates on the kept signals only — its semantics are unchanged.

Shadow: TF3's existing 3-profile parallel emission path (gated by `ARENA_TF3_SHADOW`) **coexists** with the pre-filter and remains available for ongoing telemetry comparison. Pre-filter and shadow are orthogonal — both can be on, both can be off, either can be on alone.

## Properties (per master-order Phase 2 spec)

### 1. Location
**Inside A1, AFTER signal generation, BEFORE backtest / evaluation.**

In `services/arena_pipeline.py`, the call chain is:
```
generate_alpha_signals(alpha_values, ...)        # produces signals, sizes, agreements
   ↓
[TF4 PRE_FILTER hook ←  config-gated, default OFF]
   ↓
backtester.run(signals, ..., sizes=sizes)        # validation runs here, unchanged
```

### 2. Behavior
- Aggregation **selects a subset** of entry edges; suppressed-trade segments have signals zeroed (entry-edge filtering, identical to TF2 helper).
- Filtered-out trades counted as `aggregation_skipped_count`.
- Signals that pass the filter are **not modified** (bit-for-bit forwarded to backtester).

### 3. Baseline
- `ARENA_AGGREGATION_MODE = OFF` → identical behavior to pre-TF4. Bit-for-bit.

### 4. Validation
- **Unchanged.** `entry_rank_threshold`, `exit_rank_threshold`, `rank_window`, `min_hold`, `cooldown` in `engine/components/alpha_signal.py`: untouched.
- Validation operates only on kept signals (those signals were already passing all alpha-side validators by construction; the filter only suppresses what the alpha already produced).

### 5. Promotion
- **Unchanged.** Champion promotion logic in `arena23_orchestrator`, `arena45_orchestrator`, `champion_pipeline*` tables: untouched.
- TF4 patch does not write to any pipeline DB table.

### 6. Deployable
- **Unchanged.** `deployable_count` semantics (currently `None` per `cold_start_no_live_champion_ever`) is not redefined.

### 7. Conservation
At the **trade level** (within one alpha's signal series):
```
entered_trades = kept_trades + skipped_trades
```
Verified by TF2 test #4 + TF3 test #5/#7 across all 6 profiles. The TF4 pre-filter inherits this guarantee from `apply_signal_aggregation`.

At the **batch / alpha level** (existing schema), batch `skipped_count` (the alpha-skipped count, per `arena_batch_metrics`) is **unchanged** — TF4 does not skip alphas, only skips trades within an alpha. The new `aggregation_skipped_count_total` lives in the aggregate_metrics dict alongside existing fields.

### 8. Multi-profile
**Configurable selection of one profile via `ARENA_AGGREGATION_MODE`.** Production path runs **at most one** profile at a time (`STRENGTH_FILTER` or `TOP_K_PER_BAR` or `HYBRID_TOPK_STRENGTH` or `OFF`). Master-order rule "do NOT run multiple profiles in production path" satisfied.

(TF3's `shadow_profiles` dict — which runs all 3 profiles in parallel — is a separate, additionally-gated telemetry path and does not affect the live signal flow.)

### 9. Default
```
ARENA_AGGREGATION_MODE = OFF
```
At module import time. No environment changes required to deploy this PR — the live workers continue running on the bit-equivalent baseline.

### 10. Future compatibility
The pre-filter is positioned to compose with horizon redesign (HE-series):
```
generate_alpha_signals(...)              # baseline alpha → signals
  ↓
[TF4 PRE_FILTER]                          # aggregation (this order)
  ↓
[HE-series HORIZON RESHAPER]              # rewrap into horizon-aware events (future)
  ↓
backtester.run(...)                       # baseline validation
```
The pre-filter's output is a `(signals, sizes)` pair — same shape as `generate_alpha_signals` output — so HE-series can append further transformations without reorganizing the call chain.

## Explicit rejections (per master-order Phase 2)

| Rejected design | Why rejected |
|---|---|
| **Post-evaluation filtering** | would corrupt validation pass-rate accounting; reject reasons would be ambiguous (failed because of cost vs. failed because filter dropped) |
| **Modifying validation scores** | LOCKED by master order; would invalidate A1/A2/A3 pass-fail semantics |
| **Modifying net results after simulation** | breaks audit trail (TF1's "must not make candidates pass by suppressing bad outcomes after the fact"); aggregation must operate on signal-side, never on validation-side |
| **Influencing pass/fail thresholds** | LOCKED; thresholds are validator invariants |

These are NOT implemented and CANNOT be enabled by any TF4 config flag.

## Architecture diagram (final)
```
              ┌─────────────────────────────────────┐
              │ alpha_engine.eval_alpha             │
              │ → alpha_values: ndarray [N]         │
              └─────────────────────────────────────┘
                          ↓
              ┌─────────────────────────────────────┐
              │ generate_alpha_signals(alpha_values)│
              │ → signals, sizes, agreements        │
              └─────────────────────────────────────┘
                          ↓
              ┌─────────────────────────────────────┐
              │ TF4 PRE-FILTER (this order)         │
              │ if MODE != OFF:                     │
              │   apply_signal_aggregation(profile) │
              │   signals, sizes ← filtered         │
              │ else:                               │
              │   pass through (default)            │
              └─────────────────────────────────────┘
                          ↓
              ┌─────────────────────────────────────┐
              │ TF3 SHADOW (existing, env-gated)    │
              │ if ARENA_TF3_SHADOW=1:              │
              │   for p in [strength, topk, hybrid]:│
              │     run shadow backtest, accumulate │
              └─────────────────────────────────────┘
                          ↓
              ┌─────────────────────────────────────┐
              │ backtester.run(signals, sizes, ...) │
              │ ← baseline validation (UNCHANGED)   │
              └─────────────────────────────────────┘
```

## Telemetry impact
When `ARENA_AGGREGATION_MODE != OFF`, additive fields in `aggregate_metrics`:
- `aggregation_mode` (str): the profile name in effect
- `aggregation_skipped_count_total` (int): total trades suppressed across alphas in this batch
- `aggregation_kept_count_total` (int): total trades kept
- `aggregation_entered_count_total` (int): total entry-edges seen
- `aggregation_params` (dict): the q / top_k actually used

When `ARENA_AGGREGATION_MODE = OFF`, these fields are **NOT added** — schema identical to pre-TF4.

## Classification
**INTEGRATION_READY_PRE_FILTER_ONLY** ✅

Pre-filter is the ONLY production-path integration. Shadow telemetry is opt-in only. Post-evaluation filtering is explicitly rejected.

## Verdict
**PHASE_2_COMPLETE** — integration model formalized, 10 properties met, 4 alternative designs explicitly rejected, future horizon-aware composition path documented.

## Next
Phase 3 — config & flag spec.
