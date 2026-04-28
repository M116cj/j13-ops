# 03 — Missing Primitives Review

Question for HE0/HE1/HE2: "if we redesign the forward-return horizon to
180/240/360, can the *current* primitive set express the alphas a
longer-horizon target wants to find?"

## 1. Categories the GP can express today

(from `01_grammar_inventory.md`)

- Single-symbol mean-reversion / momentum on close & 21 indicators
- Bounded transforms (`tanh_x`, `sign_x`, `pow_n`)
- Single-symbol time-series tail behaviour (`delta_d`, `ts_max_d`,
  `ts_min_d`, `ts_rank_d`, `decay_d` for d ∈ {3,5,9,20})
- Pairwise correlation **between two single-symbol terminals only**
  (e.g. `correlation_5(close, volume)` — never across symbols)
- Series-level normalisation (`scale`)
- Vol-normalised returns via composition (e.g. `protected_div(delta_20, normalized_atr_20)` — already in seeds)
- Funding-flow contrarian via `funding_zscore_p`

## 2. Categories the GP **cannot** express today

| Family | Missing primitive(s) | Why this matters at horizon 180/240/360 |
|---|---|---|
| **Cross-asset correlation** | symbol-pair `correlation` / `cospread` / `lead-lag` operators | At 3–6h horizons, BTC-led moves dominate alt-coin returns. Engine has no way to encode "ALT return rank vs BTC". `correlation_d` only works on the 5 OHLCV args of the *same* symbol. |
| **Regime conditioning** | `if_regime(R, alpha_a, alpha_b)`, `regime_score(R)`, regime-tag terminal | `market_state.py` produces 13 regimes per (symbol, bar) but the regime is metadata only. GP cannot gate behaviour on regime; that knowledge has to be re-discovered as a fragile composition every time. |
| **Order-book / microstructure** | bid-ask imbalance, taker_buy_ratio (Binance kline does carry it), book pressure, trade flow imbalance, kyle's λ proxy | At 1m bar resolution, ms-level book imbalance is meaningless; at 3–6h, *averaged* book metrics still carry signal. The pipeline does NOT subscribe to book data (`data_collector.py` only pulls OHLCV + funding + OI). |
| **Higher-moment statistics** | `skewness_d`, `kurtosis_d`, `entropy_d`, `hurst_d`, `variance_ratio_d`, `autocorr_d` | All listed in `indicator.py:30 INDICATOR_CATEGORIES["statistical"]` but **not wired** to the GP pset. Longer horizons typically benefit from tail-risk-aware features (skew, kurt) that the engine cannot reach. |
| **Rolling stats** | `ts_sum_d`, `ts_mean_d`, `ts_std_d`, `covariance_d` | Implemented in `alpha_primitives.py` but **not registered** in the DEAP pset. The GP cannot build moving-average crossover, vol-of-vol, or rolling z-scores from primitives — it has to reconstruct them as `protected_div(sub(close, decay_d(close)), …)` which is fragile. |
| **Argmax/argmin recency** | `ts_argmax_d`, `ts_argmin_d` | Implemented but not registered. "How many bars since the last high?" is a classical longer-horizon trend marker; engine cannot ask. |
| **Multi-timeframe** | `mtf_rsi`, `mtf_atr`, etc. | `indicator.py:29` lists the family; **none wired**. At horizon 240 (= 4h on 1m bars), the natural feature is "RSI on the 1h or 4h resampled close" — the rust indicator engine even ships `multi_timeframe.rs` (`indicator_engine/src/multi_timeframe.rs:90` MTF_RSI 4h example) but the python pset does not surface it. |
| **Log/exp transforms** | `log_x`, `exp_x` | Defined in `alpha_primitives.py` but **not registered**. Without `log_x`, the GP cannot construct log-returns; it must approximate via `protected_div(sub(close[t], close[t-d]), close[t-d])` and rely on `tanh_x` to bound. |

## 3. Reconciliation against `indicator.py` taxonomy

`zangetsu/engine/components/indicator.py:19-31` declares
`INDICATOR_CATEGORIES` with 11 categories totalling roughly 150
indicator names — including `cross_asset` (11 names: `btc_dominance`,
`eth_correlation`, `btc_correlation`, `sector_momentum`, etc.),
`volume_micro` (14 names: `tick_volume`, `buy_sell_ratio`,
`volume_imbalance`, `kyle_lambda`, `amihud_illiq`, `roll_spread`...),
`statistical` (`skewness`, `kurtosis`, `hurst`, `entropy`, `autocorr`,
`variance_ratio`), `multi_timeframe` (6 MTF names), `price_action`
(16 candlestick patterns), and `funding` (11 derivatives-flow names).

**Of these declared categories, only 21 indicators are wired to
the GP pset** (per `INDICATOR_NAMES` in `alpha_engine.py:289-296`).
`indicator.py` is the *catalog of what the rust library can compute*;
`alpha_engine.py` is the *catalog of what the GP is allowed to use*.
The two diverged: there is a 7× gap between what the indicator engine
exposes and what the search exposes.

This is the single largest concrete finding of the audit.

## 4. Cross-asset feature availability — explicit check

- `data_collector.py` downloads 14 symbols' OHLCV + funding + OI as
  separate parquet files. Per-symbol pipelines.
- `arena_pipeline.py` evolves alphas **per symbol** (line 568:
  `for sym in settings.symbols`). Each `AlphaEngine` instance receives
  a single-symbol indicator cache.
- `alpha_engine._build_primitive_set` registers terminals for
  *one symbol's* OHLCV — `close, high, low, open, volume`. There is
  no `btc_close, eth_close, …` terminal.
- The `correlation_d` operator takes two arrays but both must be
  arguments to the AST → both come from the same symbol's data.

**Conclusion: cross-asset features are structurally impossible at
the GP layer today.** Adding them is not a one-line constant change;
it requires a multi-symbol indicator cache and either
(a) per-bar cross-symbol feature pre-computation, or
(b) a new "global feature" terminal class wired into pset.

## 5. Regime feature availability — explicit check

- `market_state.py` produces a per-(symbol, bar) regime label and 5-factor
  scores (mom / vol / vm / fund / oi).
- `arena_pipeline.py:639-665` invokes `build_market_state` per symbol
  and stores `symbol_market_states[sym]` for **passport metadata only**.
- The GP indicator cache does **not** include regime factors as terminals.
  The 5 factor floats per bar are not exposed to alpha formulas.
- Therefore regime is a *post-hoc tag* on candidates, not a *condition*
  the GP can branch on.

**Conclusion: regime conditioning is structurally absent.** GP candidates
are evaluated under a fixed regime tag (`symbol_regimes[sym]`) which
selects symbol cohort but not formula behaviour.

## 6. Microstructure feature availability — explicit check

- `data_collector.py` pulls only 1m OHLCV + 8h funding + 5m OI.
- No order-book snapshots. No tick-level trade flow. No taker buy-volume
  delta beyond what's embedded in volume itself.
- Binance Futures kline does include `taker_buy_volume` field; the
  pipeline does not surface it as a terminal.

**Conclusion: microstructure features are not in scope until a new data
pipeline (book snapshots, tick stream, or kline-extended fields) is
built.** The Phase-5 AKASHA carry-forward already flagged this:
`scope new data pipeline for order-book snapshots + funding rate
derivatives + cross-symbol correlations (~1-2 weeks infra)`.

## 7. Artifact-risk read

If we keep grammar fixed and only flip horizon to 180/240/360:

- The GP must construct any longer-horizon edge using the same 21 × 6 =
  126 single-symbol indicator terminals plus 35 ops, depth ≤ 6.
- Most longer-horizon edges in published research lean on
  multi-timeframe rolling stats (`ts_mean_240`, `ts_std_360`),
  cross-asset spreads (`pair_corr_BTC_ALT`), or regime-aware switches
  — exactly the families absent from the pset.
- High risk that GP will manufacture *spurious* survivors: a depth-6
  composition can in principle approximate a moving average, but the
  search is an exponential needle-in-haystack vs. a single
  `ts_mean_d` primitive. With a 2 000-eval/round budget and 4 454
  unique formulas in 6.5 days of live runtime → 0 survivors at horizon
  60, the audit's prior shows search efficiency is already maxed out.
  Asking the same engine to also discover longer-horizon edges in the
  same budget is dimensionally optimistic.

## 8. Minimum primitive expansion to make horizon redesign meaningful

If horizon redesign is the ONLY change, the audit recommends pre-pending
two small grammar PRs that are essentially zero-design-cost (operators
already exist in `alpha_primitives.py`, just need 4 lines of
`pset.addPrimitive` per item):

| Primitive | Already implemented | Action |
|---|---|---|
| `ts_sum_d` for d ∈ {20, 60, 240} | yes (`alpha_primitives.ts_sum`) | register in pset |
| `ts_mean_d` for d ∈ {20, 60, 240} | yes | register in pset |
| `ts_std_d` for d ∈ {20, 60, 240} | yes | register in pset |
| `ts_argmax_d`, `ts_argmin_d` for d ∈ {20, 60, 240} | yes | register in pset |
| `log_x` | yes | register in pset |

Cost: 1 file edit, 1 LEAN-config update, 1 grammar_hash bump.
Benefit: every longer-horizon classical feature (rolling vol, rolling z,
recency-of-extreme, log-return) becomes expressible in a single AST node
instead of a 4–6-deep composition. This is the cheapest move on the
table that unlocks horizon-redesign expressiveness.

The structural changes (cross-asset terminals, regime conditioning,
microstructure data pipeline) are larger and belong to follow-up orders
beyond HE0–HE5.
