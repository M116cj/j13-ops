# 03 — Signal Quality and Cost Diagnosis (Phase 3)

**Phase 3 Verdict:** `SIGNAL_NO_EDGE`

Cost model is a realistic exchange-grade Binance Futures schedule. Train-window backtest `net_pnl ≤ 0` for ≈98–99% of generated alphas means **gross PnL on train data does not exceed transaction cost** for the overwhelming majority. The dominant failure mode is *no edge in the alpha generation universe*, not *cost too high*.

## Cost model — `zangetsu/config/cost_model.py`

Three tiers across 14 symbols:

| Tier | Symbols | taker_bps | maker_bps | slippage_bps | funding_8h_avg_bps | round-trip cost (taker×2 + slip + funding) |
|---|---|---|---|---|---|---|
| Stable | BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT, DOGEUSDT | 5.0 | 2.0 | 0.5 | 1.0 | **11.5 bps** |
| Diversified | LINKUSDT, AAVEUSDT, AVAXUSDT, DOTUSDT, FILUSDT | 6.25 | 2.5 | 1.0 | 1.0 | **14.5 bps** |
| High-Vol | 1000PEPEUSDT, 1000SHIBUSDT, GALAUSDT | 10.0 | 4.0 | 2.0 | 1.0 | **23.0 bps** |

`CostModel` defaults: `default_taker_bps=6.25`, `default_slippage_bps=1.5` for unknown symbols.

> Comment in module: "Costs vary by exchange, symbol, and account tier. […] V5 Architecture: 14 symbols across 3 tiers. […] Based on Binance Futures tiered model."

These taker/maker tiers and slippage bands are realistic for Binance Futures USDT-margined contracts at typical retail / VIP-1 tiers. **Not abnormally strict.**

## A1 fitness rejection mechanism

Source — `zangetsu/services/arena_pipeline.py:1041–1048`:

```python
# at cost=0.5x had negative train PnL but positive val PnL
if float(bt.net_pnl) <= 0:
    stats["reject_train_neg_pnl"] += 1
    _emit_a1_lifecycle_safe(
        stage_event=_SE_EXIT, status=_LS_REJECTED,
        alpha_hash=alpha_hash, source_pool=sym,
        reject_reason="TRAIN_NEG_PNL", log=log,
    )
```

`bt.net_pnl` is the per-alpha train-window backtest **net** PnL — i.e., **gross PnL minus modeled cost** from `cost_model.py`. The gate fires if net ≤ 0.

The historical comment (`# at cost=0.5x had negative train PnL but positive val PnL`) tells us this gate was tuned for a previous cost-multiplier experiment; under current 1.0× cost, almost all alphas fail it.

## Direct numerical view from runtime stats

Per-round samples (`engine.jsonl` runtime stats lines, all from 17:48Z–17:59Z):

| round | symbol/regime | alphas_evaled | reject_train_neg | reject_few_trades | reject_val_few | reject_val_neg_pnl |
|---|---|---|---|---|---|---|
| R272000 | LINK / BULL_TREND | 2000 | 1967 | 19 | 4 | 8 |
| R49500 | (j01 / W0) | 500 | 499 | 0 | 0 | 1 |
| R272010 | FIL / BEAR_TREND | 2000 | 2066 (cum) | 19 | 4 | 9 |
| R417300 | AAVE / BULL_TREND | 2000 | 1859 | 80 | 5 | 34 |
| R417310 | SOL / BULL_TREND | 2000 | 1945 | 84 | 5 | 41 |
| R417320 | SOL / BULL_TREND | 2000 | 2036 (cum) | 88 | 7 | 42 |
| R417330 | 1000PEPE / BULL_TREND | 2000 | 2127 (cum) | 96 | 7 | 42 |
| R49640 | BTC / BEAR_TREND | 2000 | 1890 | 4 | 0 | 4 |

(Note: some `reject_train_neg` numbers are cumulative across the worker's lifetime.)

Patterns:
- Across **all** symbols and regimes, `reject_train_neg` is between 90–99% of evaluated alphas
- `val_*` rejects are tiny — they only see the 1–2% that pass train fitness
- `reject_combined_sharpe = 0` everywhere — the V10 gate that previously dominated is no longer firing because alphas don't reach it

## Are candidates negative *before* cost?

The pipeline does not log gross_pnl as a separate field at the per-alpha level; only `net_pnl` reaches the rejection gate. There is no JSONL field exposing the gross-vs-cost split of failed alphas in the current telemetry surface.

What we **can** infer:

1. `SIGNAL_TOO_SPARSE` (44 / 5000 ≈ 0.9%) is a separate bucket — these are alphas that produced **too few signals to even backtest**. They are not the dominant failure mode.
2. `LOW_BACKTEST_SCORE` (21 / 5000 ≈ 0.4%) is the next bucket — these alphas produced enough signals but had a poor combined score.
3. The remaining ≈ 98.7% (`COST_NEGATIVE`) had **enough signal** (passed sparseness check) but the train net PnL was ≤ 0 once cost was deducted.

The third group is the one this diagnosis order targets. Within it, two extremes are possible:

a) `gross_pnl ≤ 0` (no edge before cost) — alpha is genuinely unprofitable
b) `0 < gross_pnl < cost` (edge exists but doesn't beat cost)

Without per-alpha gross logging, the pipeline cannot directly distinguish (a) from (b). However:

- `SIGNAL_TOO_SPARSE` rate of ~1% says alphas are producing trades, not silence
- `LOW_BACKTEST_SCORE` rate of ~0.4% says of the alphas that DO produce trades, very few even come close to the score threshold
- The original 89 fresh alphas (which presumably passed train PnL once) all have `indicator_alpha_ratio_pct = 0`, `avg_depth = 0`, `avg_nodes = 0` — purely degenerate raw-OHLCV formulas. They likely had marginal positive train net PnL by accident, then collapsed at the A2 holdout test.

## Are train and validation both failing, or only validation?

The current 6.5-day pipeline has only TRAIN failing (`reject_train_neg` ~98%). **Validation gates are not even reached** for those 98%. So this is *not* an OOS / overfitting failure — it is a fitness-on-train failure.

## Is `combined_sharpe` gate dominating?

No. `reject_combined_sharpe = 0` in every observed round. The V10 `combined_sharpe_low` gate was a known prior dominator (per AKASHA Phase 3E note), but it is now silent because alphas die earlier on `train_neg_pnl`.

## Cost vs observed edge — plausibility check

Round-trip cost ranges 11.5 bps (Stable) → 23 bps (High-Vol). For a 60-bar forward horizon (1-min bars on Binance Futures), an alpha needs to gross more than that **per round-trip trade** to be net-positive on average across the train window.

For OHLCV-only formulas without indicator / order-book / funding features (the historical 89 are exactly that, with depth=0), achieving consistent ≥ 12–23 bps edge per trade is empirically very hard. AKASHA carry-forward records this conclusion explicitly:

> "10h offline replay exhausted the space"

## Is this consistent with prior calibration artifact review?

Yes, fully consistent. The 0-9w-calibration-candidate-review evidence (referenced in PR #41 — "all 8 cost=0.5x survivors are SINGLE_SYMBOL_ARTIFACT — calibration BLOCKED") shows that even when `cost=0.5x` (half the production cost) was tested, the surviving alphas were single-symbol artifacts not portable to live cost. Returning to `cost=1.0x` removed those artifacts and the train-fitness gate became dominant.

## Required Phase 3 classification

```
SIGNAL_NO_EDGE
```

**Why not `SIGNAL_EDGE_EXISTS_COST_TOO_STRICT`:** The cost model is realistic (5–10 bps taker + 0.5–2 bps slippage + 1 bps funding = standard Binance Futures); reducing it would be live-execution-incompatible. The PR #41 calibration review already proved that lowering cost yields "single symbol artifact" alphas.

**Why not `SIGNAL_OVERFITS_TRAIN_FAILS_VALIDATION`:** The dominant rejection is at TRAIN, not at validation. Overfit-on-train would imply train passes and val fails; here train itself fails.

**Why not `SIGNAL_COST_AND_QUALITY_BOTH_FAIL`:** While both clearly contribute, the order's classification options ask for the dominant axis. Cost is at industry-realistic level; the quality (gross edge) is the variable that has not exceeded it under the current alpha-generation universe.

**Why not `SIGNAL_METRICS_NOT_EXPOSED`:** Metrics are exposed at the bucket level (`COST_NEGATIVE`, `SIGNAL_TOO_SPARSE`, `LOW_BACKTEST_SCORE`) — sufficient for this verdict. A finer split between `gross<0` vs `0<gross<cost` would be useful but is not required to determine that the current alpha universe lacks edge against realistic costs. (Recommended P1 improvement: see 07_final_report.md.)
