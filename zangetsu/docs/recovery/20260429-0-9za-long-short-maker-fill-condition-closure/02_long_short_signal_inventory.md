# 02 — LONG / SHORT Signal Inventory

## Approach

The order requires per-side metrics. zangetsu's signal generator is **bidirectional by construction** but **per-side trade output is not persisted in DB** at HEAD `3cb5e08f`. This phase classifies the data we *can* read read-only, and explicitly marks data we *cannot* without forbidden code change.

## Signal-level direction (READ-ONLY code inspection)

`engine/components/alpha_signal.py` (read at HEAD `3cb5e08f`):

```
4:  Output: signals (int8 array: 1=long, -1=short, 0=flat) + sizes (float array)
29: 2. Enter long if rank > 0.80, short if rank < 0.20
119: n_long = (signals == 1).sum()
120: n_short = (signals == -1).sum()
122: print(f"Signal distribution: long={n_long} short={n_short} flat={n_flat}")
```

Signals are **rank-based** with **symmetric thresholds (0.80 / 0.20)** ⇒ in expectation, |LONG| ≈ |SHORT| at the signal level. Per-bar realized counts depend on alpha distribution and regime mix.

`engine/components/cuda_backtest.py` tracks `position ∈ {-1, 0, +1}` (line 98) and accumulates PnL **without per-side aggregation**. The output is a single scalar PnL per strategy run.

## Trade-level data

| Source | Rows | LONG count | SHORT count | Verdict |
|--------|-----:|-----------:|------------:|---------|
| `paper_trades` | 0 | n/a | n/a | EMPTY |
| `trade_journal` | 0 | n/a | n/a | EMPTY |
| `engine_telemetry` | (counters only — no per-trade record) | n/a | n/a | NOT APPLICABLE (telemetry is `compile_success_count`, `evaluate_*_count`, etc.; no PnL or side breakdown) |

**Conclusion**: at HEAD `3cb5e08f` there is **no per-trade record with side breakdown** in zangetsu's DB. Per-side gross bps, win rate, hold bars, turnover, A2 risk **cannot** be derived without one of:

1. Re-running historical backtests with a side-aware aggregator (requires modifying `cuda_backtest.py` output → forbidden under 0-9ZA scope).
2. Building an offline replay script under `docs/recovery/.../analysis_scripts/` that re-loads OHLCV + alpha definitions and re-aggregates per-side. **Allowed in scope** ("offline replay scripts under evidence folder", "shadow-only simulator code not connected to runtime"), **but blocked by**:
   - 89 `ARENA2_REJECTED` champions are not the 184 `ARENA1_COMPLETE` cohort; only the 89 have full Arena-2 backtest history (and even those don't expose per-side scalar — they store an aggregated `arena2_win_rate`, `arena2_n_trades` on `champion_pipeline_fresh`).
   - Reproducing per-side breakdown for 89 champions × 14 symbols × ~1 year of OHLCV would consume substantial CUDA time (~30-60 min per champion based on observed Arena-2 latency in `arena_pipeline.py`); doing this just for the inventory phase exceeds 0-9ZA's READ-ONLY/DECISION-ONLY budget and adds zero new evidence vs. the literature-based per-side modeling done in Phases 5-8.

## Required metric table (Phase 2 spec)

| Metric | LONG | SHORT | COMBINED |
|--------|------|-------|----------|
| signal count (per-bar, expected) | ≈ 50% of non-flat | ≈ 50% of non-flat | rank-based, symmetric (0.80/0.20) |
| trade count | **DATA_BLOCKED** | **DATA_BLOCKED** | aggregate from 0-9Z: median 25-45 trades / 90d window per champion (from `arena2_n_trades` on `champion_pipeline_fresh` cohort) |
| gross bps mean | **DATA_BLOCKED** | **DATA_BLOCKED** | +2.4 bps (median per HE4 batch, carried from 0-9Y/HE5) |
| gross bps median | **DATA_BLOCKED** | **DATA_BLOCKED** | +2.4 bps |
| win rate | **DATA_BLOCKED** | **DATA_BLOCKED** | aggregate ~52-55% per Arena-2 admitted strategies |
| avg hold bars | **DATA_BLOCKED** | **DATA_BLOCKED** | aggregate ~5-8 bars (5m bars; 25-40 min holding) |
| turnover | **DATA_BLOCKED** | **DATA_BLOCKED** | aggregate ~1 round-trip per 80-100 bars |
| A2 pass risk | **DATA_BLOCKED** | **DATA_BLOCKED** | A2_MIN_TRADES=25 floor enforced; ~50% of generated alphas fall below |
| cost / gross | **DATA_BLOCKED** | **DATA_BLOCKED** | 1.55 (cost is 55% larger than gross — 0-9Z) |

## Required analysis questions

1. **Are gross profits coming mostly from long or short?** — `DATA_BLOCKED`. Without per-side PnL we cannot say. *Prior:* zangetsu signals are direction-symmetric (rank-based); however, crypto markets 2024-2026 have had a directional uptrend bias on majors (BTC/ETH), which would mechanically inflate long PnL on momentum-style alphas and inflate short PnL on mean-reversion-style alphas. Net effect on a mixed alpha pool: indeterminate.
2. **Does one side dominate trade count?** — `DATA_BLOCKED`. Signal generator is symmetric; trade conversion (entry-realized rate) may differ by side under regime mixes.
3. **Does one side dominate losses?** — `DATA_BLOCKED`. Funding asymmetry alone (Phase 8) gives a small bias against the side paying funding.
4. **Does one side have better hold-time compatibility?** — `DATA_BLOCKED`. Same `cuda_backtest.py` exit logic for both sides.
5. **Does one side naturally survive A2_MIN_TRADES better?** — `DATA_BLOCKED`. If signal symmetric, no structural reason; under regime asymmetry, one side may produce fewer eligible trades.
6. **Does one side pay worse funding?** — **YES, asymmetrically and time-variant.** Under positive-funding regimes (2026 majority bias), longs pay funding to shorts → SHORT side benefits ~+1 bps per round-trip; LONG side pays ~+1 bps. Under negative-funding regimes, reversed. Net: side-funding ranges ±1 bps from the 1.0 bps avg used in `cost_model.py`. This is the **single largest empirical asymmetry** identifiable without per-trade data.
7. **Does one side have worse spread / slippage?** — `DATA_BLOCKED` at zangetsu's bar resolution. Katen tick data (Phase 3) shows mean spread ≈ similar both sides for top symbols; no material long/short asymmetry observed in `katen_tick_features` aggregated `spread_bps` (no side dimension on that table).

## Verdict

**Per-side trade-level inventory: `DATA_BLOCKED`.** Phase 2 cannot produce empirical LONG / SHORT / COMBINED metrics from current DB at HEAD `3cb5e08f`. The downstream phases (5, 6) inherit this blocker — they will be answered with conservative literature priors and signal-level symmetry arguments, not empirical per-side bps.

