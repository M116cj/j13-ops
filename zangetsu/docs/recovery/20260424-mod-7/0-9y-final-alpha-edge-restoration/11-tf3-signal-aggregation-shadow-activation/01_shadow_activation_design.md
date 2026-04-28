# 01 — SHADOW ACTIVATION DESIGN

**TEAM ORDER**: 0-9Y-TF3-SIGNAL-AGGREGATION-SHADOW-ACTIVATION
**Date**: 2026-04-28
**Phase**: 1 / 8

## Goal
Run TF2 aggregation profiles **in parallel** with the existing baseline path inside `arena_pipeline.py`, computing shadow metrics per batch without affecting any baseline value, decision, or emission already made.

## Activation gate
```
ARENA_TF3_SHADOW=1   → shadow path RUNS
unset / 0 / anything else → shadow path SKIPPED (zero baseline impact)
```
Implemented as a single `os.environ.get(...) == "1"` check; cached at module import time into a `_TF3_SHADOW_ENABLED` constant for performance and to make the test rig trivial. Default = OFF.

## Insertion point
Inside the per-alpha loop in `services/arena_pipeline.py` (around line 1062 — between `generate_alpha_signals(...)` and `backtester.run(...)`):

```
signals, sizes, agreements = generate_alpha_signals(...)   # baseline (unchanged)

if _TF3_SHADOW_ENABLED:
    _tf3_run_shadow(
        signals=signals, sizes=sizes,
        backtester=backtester,
        close_f32=close_f32, high=high_f32, low=low_f32,
        sym=sym, cost_bps=cost_bps,
        max_hold=_STRATEGY_MAX_HOLD,
        accumulators={
          "strength": (_tf3_strength_gross, _tf3_strength_net, _tf3_strength_trades, _tf3_strength_skipped),
          "topk":     (_tf3_topk_gross, _tf3_topk_net, _tf3_topk_trades, _tf3_topk_skipped),
          "hybrid":   (_tf3_hybrid_gross, _tf3_hybrid_net, _tf3_hybrid_trades, _tf3_hybrid_skipped),
        },
    )

bt = backtester.run(signals, ..., sizes=sizes)   # baseline (unchanged)
```

## Profiles run per alpha
| Key | Profile | Parameters |
|---|---|---|
| `strength` | `STRENGTH_FILTER` | `strength_quantile=0.95` |
| `topk` | `TOP_K_PER_BAR` | `top_k=50` |
| `hybrid` | `HYBRID_TOPK_STRENGTH` | `strength_quantile=0.90, top_k=50` |

(parameters chosen from TF2 fixture sweep results — `STRENGTH_q0.95` and `HYBRID_q0.90_K=50` were the strongest performers; `TOP_K=50` matches the hybrid's K so the hybrid effect isolates to strength filtering.)

## Per-profile computation
For each profile:
1. Call `apply_signal_aggregation(signals, sizes, profile=..., strength=sizes, ...)` — **never mutates** input arrays
2. Take filtered `result.signals` and `result.sizes`
3. Run a **separate** `backtester.run(filtered_signals, ..., sizes=filtered_sizes)` call
4. Capture `bt_p.gross_pnl`, `bt_p.net_pnl`, `bt_p.total_trades` (and `result.skipped_count`) into per-profile per-symbol-regime accumulators

## Telemetry shape (additive — does not overwrite any existing field)
A new top-level dict `shadow_profiles` is added alongside the existing `aggregate_metrics`. Per-profile sub-dicts hold per-batch (per-symbol-regime) medians:

```python
shadow_profiles = {
  "baseline": {  # echoes the existing aggregate_metrics for easy comparison
    "trade_count_median": <existing train_total_trades_median>,
    "gross_pnl_median":   <existing train_gross_pnl_median>,
    "net_pnl_median":     <existing train_net_pnl_median>,
    "win_rate_median":    <existing train_win_rate_median>,
    "skipped_count_total": 0,
  },
  "strength_filter": { trade_count_median, gross_pnl_median, net_pnl_median,
                       win_rate_median, gross_per_trade_median,
                       net_per_trade_median, skipped_count_total,
                       quantile=0.95 },
  "top_k": { ... top_k=50 },
  "hybrid": { ... quantile=0.90, top_k=50 },
}
```

Conservation per profile, per alpha, holds at the trade level: `entered_trades = kept_trades + skipped_trades` (verified by TF2 test #4).

## Strict invariants
| Invariant | Mechanism |
|---|---|
| Baseline behavior identical when `ARENA_TF3_SHADOW != "1"` | hard env gate, single boolean cached at import |
| Baseline `bt` and `_b1_*` accumulators are NOT mutated by shadow code | shadow uses separate accumulators (`_tf3_*`); aggregation helper is pure |
| Champion promotion / `deployable_count` semantics | shadow path never touches `round_champions`, `pass_*`, or any A2/A3/A45 inputs |
| Validation thresholds unchanged | shadow does not pass arguments to `generate_alpha_signals` (uses its existing output only) |
| Cost model unchanged | shadow uses the **same** `cost_bps` baseline already pays; just runs the cost on filtered signal series |
| `A2_MIN_TRADES = 25` unchanged | shadow does not interact with A2 |
| No `alpha_zoo` write | shadow is read-only |
| Conservation `entered = kept + skipped` per profile per alpha | enforced by `apply_signal_aggregation` (TF2 test #4) |
| Determinism | aggregation helper is deterministic (TF2 test #3); shadow loop runs in same order as baseline |
| No mutation across profiles (shared state corruption) | each profile's call gets its own copy of input arrays via `apply_signal_aggregation` |

## Failure handling
Each shadow backtest call wrapped in `try / except` that logs and **continues** — a shadow-path bug must NEVER propagate to baseline. Mirroring the existing baseline pattern (see `# 0-9Y-B1: defensive try/except per field`).

## Performance budget
Per alpha: 1 baseline backtest + 3 shadow backtests = 4× backtest work. Baseline measured ~7 batches/min × ~10 alphas = ~70 alphas/min. Backtest is njit-cached numerical work, fast. Worst-case shadow throughput ≈ baseline ÷ 4 ≈ 1.75 batches/min. With ARENA_TF3_SHADOW=1 set, expect ~100 batches in ~60 minutes (probably faster — most A1 alphas trigger COST_NEGATIVE early; backtest body is short-circuited for those).

## Test plan (Phase 3)
1. **Default OFF baseline check** — same as before, no aggregation calls reachable
2. **ARENA_TF3_SHADOW=1 sentinel** — shadow block executes, baseline metrics still bit-equivalent
3. **Conservation**: per-profile per-alpha `entered = kept + skipped` (already verified by TF2 test #4)
4. **No regression**: existing TF2 tests + targeted `aggregation/arena_batch_metrics/telemetry` suites stay green
5. **Telemetry presence**: emitted batch event has `shadow_profiles` key when env=1, absent when env=0

## Operational plan (Phase 4)
1. Stop existing 4 `arena_pipeline.py` workers (let watchdog reclaim)
2. Edit `~/j13-ops/zangetsu/.env.global` (or worker systemd / process env) to include `ARENA_TF3_SHADOW=1`
3. Restart workers — they pick up new env + new code
4. Wait for ≥100 batches (target 200) — ~15-30 min observed at baseline rate; ~60 min worst-case at shadow throughput
5. Stop, parse logs, compute Phase 5 metrics
6. Restore `ARENA_TF3_SHADOW=0` (or unset) and restart workers to leave system in baseline state

## Forbidden touches (per master order, audited Phase 6)
- NO change to validation logic (`entry_rank_threshold`, `exit_rank_threshold`)
- NO change to cost model
- NO change to `A2_MIN_TRADES = 25`
- NO change to `deployable_count` semantics
- NO change to champion promotion
- NO `alpha_zoo` execution
- NO CANARY / production
- NO execution / capital / risk changes
- NO DB schema / guard changes

## Verdict
**DESIGN_READY_FOR_IMPLEMENTATION** — env-gated, additive, isolated; baseline path bit-equivalent when shadow OFF; shadow path emits parallel telemetry without overwriting.

## Next
Phase 2 — implement the patch in `arena_pipeline.py` (and a small pure helper in a new module if the inline cost is high).
