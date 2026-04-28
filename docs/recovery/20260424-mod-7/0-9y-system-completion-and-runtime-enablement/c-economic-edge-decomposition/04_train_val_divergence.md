# 04 — Train vs Val Divergence

**Source**: Alaya `/tmp/c_batches_snapshot.jsonl` (106 arena_batch_metrics events, 1060 alphas total)
**Mode**: READ-ONLY
**Date**: 2026-04-28

---

## 1. Population Coverage

| Metric | Count | Pct |
|---|---|---|
| Total batches (N) | 106 | 100.0% |
| `alphas_with_train_backtest > 0` | 106 | 100.0% |
| `alphas_with_val_backtest > 0` (val_seen) | **14** | **13.2%** |
| `alphas_with_combined_sharpe > 0` (val PASSED) | **0** | **0.0%** |

**Aggregate alpha funnel**: entered=1060, passed=0, rejected=1060, deployable=0.

### Distributions

```
alphas_with_train_backtest:    {10: 106}                                 # always 10/batch
alphas_with_val_backtest:      {0: 92, 1: 4, 2: 1, 3: 2, 4: 2, 5: 3, 6: 2}
alphas_with_combined_sharpe:   {0: 106}                                  # never any
```

**Reject reason distribution** (1060 alphas total):
- `COST_NEGATIVE`: 1024 (96.6%)
- `LOW_BACKTEST_SCORE`: 20 (1.9%)
- `SIGNAL_TOO_SPARSE`: 16 (1.5%)

**Top-reject-per-batch**: COST_NEGATIVE in 102/106 batches.

---

## 2. Val_Seen Subset (n=14 batches)

Even where val ran on ≥1 alpha, val outcomes are mostly negative:

| metric | n | min | p25 | median | p75 | max | pos |
|---|---|---|---|---|---|---|---|
| val_net_pnl_median | 14 | -0.0708 | -0.0504 | -0.0201 | -0.0031 | 0.0721 | 3 |
| val_sharpe_median  | 14 | -1.4105 | -0.4510 | -0.3784 | -0.0646 | 0.8956 | 3 |
| val_total_trades_median | 14 | 26 | 38 | 54 | 86 | 120 | 14 |

Train-side (all 106 batches): `train_net_pnl_median` median = **-1.326** (104/106 negative); `train_sharpe_median` median = **-2.224** (103/106 negative).

---

## 3. Paired Train-vs-Val (val_seen, n=14)

**net_pnl_median quadrants:**
| quadrant | count | pct |
|---|---|---|
| both_neg (cost dominance) | 11 | 78.6% |
| both_pos (true edge candidate) | 2 | 14.3% |
| train_neg_val_pos (noise/lucky val) | 1 | 7.1% |
| train_pos_val_neg (overfit) | **0** | 0.0% |

**sharpe_median quadrants:** both_neg=11 (78.6%), both_pos=3 (21.4%), no overfit pattern observed.

Critically: **0 batches show classic overfit (train_pos → val_neg)**. The dominant signature is `both_neg` — cost dominates on both windows. Note even the 2 `both_pos` net_pnl batches still failed `combined_sharpe` (none survived to deployable).

---

## 4. Verdict

**`TRAIN_VAL_BOTH_NEGATIVE` — with caveat: divergence not meaningfully testable at population level.**

Reasoning:
1. Of the 106 batches, only 13.2% (14) had any alpha survive train far enough to even attempt val. 86.8% died at train (overwhelmingly `COST_NEGATIVE` = `train_net ≤ 0`).
2. Of the 14 val_seen batches, **0 produced a passing alpha** (`alphas_with_combined_sharpe == 0` across the entire dataset).
3. Among val_seen pairs, 78.6% are both_neg — confirming the bottleneck is **universal cost dominance**, not train→val overfitting.
4. There is no observed "alpha looked good on train, broke on val" pattern in this snapshot. The pipeline is gated by costs at the train stage; val is a near-empty downstream signal.

**Implication**: Investigation/tuning effort should target the train-side cost structure (round_total_cost_bps=14.5 vs train_gross_minus_net_median≈4.4) — not val window methodology. Until train-side gross PnL clears the cost floor, train_val_divergence remains structurally untestable on this dataset.

---

## 5. Q1 Adversarial Notes

- **Input boundary**: handled `None` for val_*_median; treated `alphas_with_val_backtest` missing as 0.
- **Failure propagation**: counted only non-None pairs in quadrant analysis; no silent skip.
- **External dependency**: data sourced live via SSH; no cached/stale read.
- **Concurrency / race**: snapshot is static JSONL; no race.
- **Scope creep**: stayed within val/train pairing; did not modify data or pipeline.
