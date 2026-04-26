# 04 — Signal-to-Trade Parameter Audit

## 1. `alpha_signal.py` Constants

| Parameter | Source line | Value | Mathematical meaning |
| --- | --- | --- | --- |
| `entry_rank_threshold` | 18 | 0.80 | enter when `|rank − 0.5| × 2 ≥ 2 × 0.80 − 1 = 0.60` (i.e. rank ∈ [0, 0.20] ∪ [0.80, 1.0] = top/bottom 20%) |
| `exit_rank_threshold` | 19 | 0.50 | exit when `|rank − 0.5| × 2 < 0.50` (i.e. rank ∈ [0.25, 0.75]) |
| `rank_window` | 20 | 500 | rolling 500-bar percentile rank |
| `min_hold` | 21 | 60 bars | minimum bars per trade |
| `cooldown` | 22 | 60 bars | wait after exit before re-entry |

## 2. Direction Mapping

```python
size = abs(rank - 0.5) * 2.0
if bars_since_exit >= cooldown and size >= 2 * entry_rank_threshold - 1.0:
    if rank > 0.5:
        position = +1   # LONG
    elif rank < 0.5:
        position = -1   # SHORT
```

→ `rank > 0.5` ⇒ LONG; `rank < 0.5` ⇒ SHORT. Symmetric. **No direction inversion.**

## 3. Position Sizing

`agreements[i] = abs(rank - 0.5) * 2.0` — continuous [0, 1] magnitude attached to each entry. Backtester uses these as `sizes`.

Sizes are continuous. Position sign comes from `signals[i] ∈ {-1, 0, +1}`.

## 4. Exit Logic

```python
if hold_count >= min_hold and size < exit_rank_threshold:
    signals[i] = 0
    position = 0
```

Exit triggers when both:
- `min_hold = 60` bars elapsed AND
- size below `exit_rank_threshold = 0.50`

There is also a **forced exit** at `max_hold = 120` bars enforced at the backtester level (`zangetsu/engine/components/backtester.py`).

## 5. NaN / Inf Handling

`arena_pipeline.py:1004` — `av_val = np.nan_to_num(av_val, nan=0.0, posinf=0.0, neginf=0.0)`. Routed before signal generation. NaN/inf alpha values become 0 (constant signal) → `reject_val_constant`, NOT `val_neg_pnl`.

## 6. Sign Orientation Diagnostic (from PR #40 Phase 5)

For `sign_x(delta_20(close))`:
```
BTCUSDT: long_pct=0.0587 short_pct=0.0645 → entries fire at expected ~5-6% rate per side
ETHUSDT: long_pct=0.0557 short_pct=0.0588 → similar
SOLUSDT: long_pct=0.0824 short_pct=0.0706 → SOL fires more frequently (higher vol)
```

Forward 60-bar return after entry (sign-flipped for shorts):
```
BTC long: -0.000339   BTC short-flipped: +0.000486 (mixed)
ETH long: -0.000344   ETH short-flipped: -0.000215 (both lose)
SOL long: -0.000574   SOL short-flipped: -0.000412 (both lose)
```

→ **Direction logic is consistent with formula intent. The lack of edge is a property of the alpha at this timescale, not a sign bug** (PR #40 Phase 5 verdict: SIGNAL_TO_TRADE_OK).

## 7. Risk Inspections (per order)

| Special check | Result |
| --- | --- |
| ENTRY_THR=0.80 means "top 20%" via |rank-0.5|×2 ≥ 0.60 | YES — confirmed |
| Signal direction consistent? | YES — long when rank>0.5, short when rank<0.5 |
| Short logic symmetric? | YES — same threshold, opposite sign |
| Rank mapping creates too few trades? | NOT in alpha_signal.py — but Phase 1 shows current bottleneck is COUNTER_INCONSISTENCY (pre-signal) |
| Position size continuous or binary? | continuous ([0, 1]) |

## 8. Classification

| Verdict | Match? |
| --- | --- |
| **SIGNAL_PARAMS_OK** | **YES** |
| ENTRY_THRESHOLD_TOO_RESTRICTIVE | NO (PR #40 Phase 2 confirmed lowering ET makes things worse) |
| RANK_MAPPING_RISK | NO |
| DIRECTION_MAPPING_RISK | NO (forward-return diagnostic in PR #40 confirmed direction is right) |
| COOLDOWN_RISK | NO (60 bars cooldown matches min_hold) |
| SIGNAL_UNKNOWN | NO |

→ **Phase 4 verdict: SIGNAL_PARAMS_OK.** Signal-to-trade contract is internally consistent and matches PR #40 Phase 5 forward-return validation.
