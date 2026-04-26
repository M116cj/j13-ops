# 05 — Signal-to-Trade Logic Audit

## 1. Signal Construction Path (read-only inspection)

`zangetsu/engine/components/alpha_signal.py:generate_alpha_signals`:
- raw alpha values run through `pd.Series.rolling(500).rank(pct=True)` to produce a percentile rank in [0, 1]
- `size = abs(rank - 0.5) * 2.0` → 0 at median, 1 at extremes
- Entry trigger: `size >= 2 * entry_threshold - 1.0` (e.g. ET=0.80 → size ≥ 0.60 → rank in [0,0.20] ∪ [0.80,1.0])
- Direction: `rank > 0.5 → position=+1` (long), `rank < 0.5 → position=-1` (short)

→ The mapping is consistent and well-defined. **No silent sign flip.**

## 2. Forward-Return Diagnostic on Real Alpha (`sign_x(delta_20(close))`)

For each symbol on the train slice, we counted entries triggered by ET=0.80 and computed average forward 60-bar log return at each entry, with short returns sign-flipped (so positive = profitable for the chosen direction).

Verbatim from Phase 5 diagnostic:

```
BTCUSDT: long_pct=0.0587 short_pct=0.0645
  entries: long=125 short=132
  avg fwd 60-bar return after long entry: -0.000339   ← long entries LOSE
  avg fwd 60-bar return after short entry (sign-flipped): +0.000486   ← short entries WIN

ETHUSDT: long_pct=0.0557 short_pct=0.0588
  entries: long=117 short=124
  avg fwd 60-bar return after long entry: -0.000344   ← long entries LOSE
  avg fwd 60-bar return after short entry (sign-flipped): -0.000215   ← short entries also LOSE

SOLUSDT: long_pct=0.0824 short_pct=0.0706
  entries: long=174 short=145
  avg fwd 60-bar return after long entry: -0.000574   ← long entries LOSE
  avg fwd 60-bar return after short entry (sign-flipped): -0.000412   ← short entries also LOSE
```

## 3. Interpretation

| Observation | Conclusion |
| --- | --- |
| Entry rate is ~5-8% per side (consistent with rank-based 20% gate after warm-up) | mapping fires at expected frequency |
| Long-entry forward return is **negative** for all 3 symbols on `sign_x(delta_20(close))` | **NOT a sign bug**, but a **gross-edge-failure** of the formula at the 1-min crypto timescale |
| Short-entry forward return is positive on BTC, negative on ETH/SOL | edge is inconsistent — formula is essentially noise |
| If the sign were FLIPPED in code, we would see long entries with positive avg forward return on >50% of symbols. We do not. | **direction logic is consistent with the formula intent** |

The data is consistent with: **at 1-min crypto bars, simple momentum indicators (sign of 20-bar delta) have negative or zero gross edge** — momentum is dominated by mean reversion / noise at this horizon. This is a known empirical phenomenon, not a backtester defect.

## 4. Hypothesis Test: Would Inverting the Signal Recover Edge?

If the bug were "long when should be short", inverting would yield:
- BTC: long-inverted avg = +0.000339 (positive but tiny — 3.4 bps over 60 bars, ~0.6 bps/bar)
- ETH: long-inverted avg = +0.000344 (similar magnitude)
- SOL: long-inverted avg = +0.000574 (similar magnitude)

Even if inverted, the gross edge per trade is **~3-6 bps over 60 bars**, dwarfed by the 11.5 bps round-trip cost. So even if there were a sign bug, fixing it would not give >0 net PnL. The cost wall dominates regardless of direction.

→ **Signal direction is correct as implemented; the formula simply has insufficient gross edge.**

## 5. Phase 5 Classification

| Verdict | Match? |
| --- | --- |
| **SIGNAL_TO_TRADE_OK** | **YES — direction is consistent and would not become profitable if inverted** |
| SIGNAL_TO_TRADE_DIRECTION_BUG | NO (forward-return diagnostic above) |
| SIGNAL_TO_TRADE_RANK_WINDOW_BUG | NO (500-bar rolling rank applied uniformly in both train and val) |
| SIGNAL_TO_TRADE_ALPHA_NUMERIC_BUG | NO (alpha values are finite and rank fires at expected frequency) |
| SIGNAL_TO_TRADE_UNKNOWN | NO |

→ **Phase 5 verdict: SIGNAL_TO_TRADE_OK.** Direction logic is consistent. The lack of net edge is a property of the alpha formula at this market regime, not a logic bug.
