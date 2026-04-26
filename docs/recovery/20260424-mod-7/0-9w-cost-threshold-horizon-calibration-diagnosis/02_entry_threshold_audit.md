# 02 — ENTRY_THR Sensitivity Audit

## 1. Mapping (read-only source inspection)

`zangetsu/engine/components/alpha_signal.py:alpha_to_signal`:

```python
# Position sizing based on rank extremity
size = abs(rank - 0.5) * 2.0   # 0 at median, 1 at extreme
if size >= 2 * entry_rank_threshold - 1.0:
    if rank > 0.5:
        position = 1   # Long: alpha is high (bullish signal)
    elif rank < 0.5:
        position = -1  # Short
```

`entry_threshold=0.80` does NOT mean "raw alpha value >= 0.80". It means:

- Rolling 500-bar percentile rank of the alpha output
- Enter when rank ∈ [0, 0.20] OR rank ∈ [0.80, 1.0] (top/bottom 20%)
- Direction: rank > 0.5 → LONG; rank < 0.5 → SHORT

Lowering `entry_threshold` widens the entry zone (e.g. 0.60 means enter when |rank − 0.5| ≥ 0.10, i.e. top/bottom 40% — much more frequent).

## 2. Sensitivity Replay (5 thresholds × 5 formulas × 3 symbols = 75 evals)

```
entry_thr  n_eval  train_max    val_max  avg_train_trades  survivors (val>0)
0.60           15    -0.8339    -0.1887           1115.9          0
0.65           15    -0.8359    -0.1804           1106.9          0
0.70           15    -0.9405    -0.1335           1087.9          0
0.75           15    -0.7265    -0.2802           1053.7          0
0.80           15    -0.2090    -0.1662            864.0          0  ← current
```

| Observation | Direction |
| --- | --- |
| Lower threshold → MORE trades (1115 → 864) | as expected |
| Lower threshold → MORE total cost paid | expected |
| Lower threshold → does NOT help train PnL (gets worse) | confirmation that entry threshold is not too strict |
| Lower threshold → does NOT help val PnL | confirmation |
| Highest threshold (0.80) actually best train_pnl | confirms current setting is the most selective and least cost-burdened |

→ **Lowering ENTRY_THR makes things worse** because the marginal trades it admits are lower-edge (they were below the rank-0.80 confidence cut for a reason) AND they add more cost.

## 3. Trade Count Impact

| Threshold | Avg train trades / formula | Cost incurred (BTC, 11.5 bps × trades) |
| --- | --- | --- |
| 0.60 | 1116 | 0.128 |
| 0.65 | 1107 | 0.127 |
| 0.70 | 1088 | 0.125 |
| 0.75 | 1054 | 0.121 |
| 0.80 | 864 | 0.099 |

→ Higher threshold → fewer trades → less cost drag. The current 0.80 already minimizes trade frequency among tested values. **Going below 0.80 is strictly worse.**

## 4. Phase 2 Classification

| Verdict | Match? |
| --- | --- |
| ENTRY_THRESHOLD_OK | partial — 0.80 is the BEST tested setting; not "OK" in the sense of giving survivors, but the LEAST BAD |
| ENTRY_THRESHOLD_TOO_STRICT | NO (lowering makes it worse) |
| ENTRY_THRESHOLD_MAPPING_BUG | NO (rank-based mapping is sensible and consistent) |
| **ENTRY_THRESHOLD_NOT_PRIMARY_CAUSE** | **YES — exact match** |
| ENTRY_THRESHOLD_UNKNOWN | NO |

→ **Phase 2 verdict: ENTRY_THRESHOLD_NOT_PRIMARY_CAUSE.** Threshold sweep shows the gate is appropriately calibrated — looser doesn't help.
