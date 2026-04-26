# 03 — MAX_HOLD Horizon Sensitivity Audit

## 1. Source

`arena_pipeline.py:756`: `MIN_HOLD = 60` (env: `ALPHA_MIN_HOLD`).
`arena_pipeline.py:_STRATEGY_MAX_HOLD` resolved per strategy (j01: 120 bars).
`alpha_signal.py:alpha_to_signal`:

```python
if hold_count >= min_hold and size < exit_rank_threshold:
    signals[i] = 0
    position = 0
```

Exit happens when (a) min_hold elapsed AND (b) size drops below exit threshold. The MAX_HOLD parameter to `backtester.run` is a forced timeout for the trade.

## 2. Sensitivity Replay (5 horizons × 5 formulas × 3 symbols = 75 evals)

```
max_hold   n_eval  train_max    val_max  avg_train_trades  survivors (val>0)
120            15    -0.2090    -0.1662            864.0          0  ← current j01
240            15    -0.2029    -0.1662            770.8          0
360            15    -0.2029    -0.1662            751.5          0
720            15    -0.2029    -0.1662            745.7          0
1440           15    -0.2029    -0.1662            745.7          0
```

| Observation | Conclusion |
| --- | --- |
| Longer horizon slightly reduces trade count (864 → 745) | as expected (some trades that would have hit 120-bar cap now exit naturally) |
| Train PnL improvement: 0.006 (0.06% absolute) | **negligible** |
| Val PnL improvement: 0 (identical) | **none** |
| All horizons: 0 survivors | the horizon is not the constraint |

The plateau at 720+ shows the natural exit logic (rank size < exit_threshold) takes over before the timeout kicks in for most trades. Even 1440 (1 day at 1-min bars) doesn't change anything.

## 3. Forced Exit Frequency

The Phase 4 sanity test "buy_and_hold_long" with `MAX_HOLD=1_000_000` returned 0 trades — meaning the backtester never forces a position close on a continuously-asserted signal. So MAX_HOLD only kicks in when a position is held for that many bars without natural exit. The plateau at 720+ implies natural exit covers the vast majority of cases at min_hold=60 + exit_rank_threshold=0.50.

## 4. Phase 3 Classification

| Verdict | Match? |
| --- | --- |
| HORIZON_OK | YES |
| HORIZON_TOO_SHORT | NO (extending to 1440 = 1 day doesn't help) |
| HORIZON_FORCED_EXIT_BUG | NO |
| **HORIZON_NOT_PRIMARY_CAUSE** | **YES — exact match** |
| HORIZON_UNKNOWN | NO |

→ **Phase 3 verdict: HORIZON_NOT_PRIMARY_CAUSE.** MAX_HOLD_BARS=120 (j01 default) is not the constraint. Natural exit logic dominates regardless of timeout.
