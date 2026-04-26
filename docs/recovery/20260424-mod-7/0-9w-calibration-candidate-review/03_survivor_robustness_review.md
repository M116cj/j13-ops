# 03 — Survivor Robustness Review

## 1. Methodology

For each of the 8 cost=0.5x survivors, we evaluate 5 robustness dimensions and assign a 0-10 score:

| Dimension | Test | Points |
| --- | --- | --- |
| Train+Val both positive | not just val>0 — also train>0 (no train-val divergence) | 3 |
| Cost-neighbor stability (cost=0) | same cell at cost=0 also positive | 2 |
| Cost-neighbor stability (cost=1.0x) | same cell at cost=1.0x still positive (not on edge) | 2 |
| Cross-symbol generalization | same formula+ET+MH at cost=0.5x positive on ≥2 of 3 symbols | 2 |
| val_sharpe ≥ 0.5 | strong consistency, not borderline | 1 |

Classification thresholds:
- score ≥ 7 → **ROBUST_CANDIDATE**
- score 5-6 → **FRAGILE_CANDIDATE**
- score < 5 + SINGLE_SYMBOL_ARTIFACT flag → **SINGLE_SYMBOL_ARTIFACT**
- score < 5 + TRAIN_NEG_VAL_POS flag → **COST_EDGE_TOO_THIN**
- otherwise → **REJECT_FOR_REVIEW**

## 2. Per-Survivor Scores

| # | formula | sym | ET | MH | val_pnl | score | classification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | wqb_s01 | SOL | 0.70 | 360 | +0.1275 | 3/10 | **SINGLE_SYMBOL_ARTIFACT** |
| 2 | wqb_s01 | SOL | 0.70 | 120 | +0.1193 | 3/10 | **SINGLE_SYMBOL_ARTIFACT** |
| 3 | wqb_s01 | SOL | 0.70 | 720 | +0.1185 | 3/10 | **SINGLE_SYMBOL_ARTIFACT** |
| 4 | wqb_s01 | SOL | 0.60 | 360 | +0.0960 | 3/10 | **SINGLE_SYMBOL_ARTIFACT** |
| 5 | wqb_s01 | SOL | 0.60 | 720 | +0.0901 | 3/10 | **SINGLE_SYMBOL_ARTIFACT** |
| 6 | wqb_s01 | SOL | 0.60 | 120 | +0.0753 | 2/10 | **SINGLE_SYMBOL_ARTIFACT** |
| 7 | wqb_s01_vwap | SOL | 0.70 | 360 | +0.0680 | 2/10 | **SINGLE_SYMBOL_ARTIFACT** |
| 8 | wqb_s01_vwap | SOL | 0.60 | 360 | +0.0534 | 2/10 | **SINGLE_SYMBOL_ARTIFACT** |

**100% of cost=0.5x survivors classify as SINGLE_SYMBOL_ARTIFACT.** None earn a robust or fragile-candidate classification.

## 3. Universal Failure Modes

Every cost=0.5x survivor fails ALL of the following simultaneously:

### 3.1 TRAIN_NEG_VAL_POS (8/8)

```
train_pnl range: -0.847  to  -0.318
val_pnl range:   +0.053  to  +0.128
```

→ Strategy is **train-unprofitable**, val-profitable. This is textbook regime shift / non-stationarity / curve fit. A formula that fails on the larger train slice but succeeds on the smaller val slice is **not a stable winner** — it has likely picked up a feature that exists in the val regime but not the train regime.

### 3.2 COLLAPSE_AT_1.0x (8/8)

For all 8 cells, raising cost back to 1.0x flips val_pnl from +0.05-0.13 to **−0.07 to −0.19**. The survivor lives in a thin cost window:

```
SOL cell wqb_s01 ET=0.70 MH=360:
  cost=0      val_pnl=+0.3226
  cost=0.5x   val_pnl=+0.1275  ← survivor zone
  cost=1.0x   val_pnl=−0.0675  ← collapse
```

The cost-edge thickness is ≤6 bps. Any execution slippage above 1 bp would erode this margin. **Production execution is unlikely to deliver the precise 5.75 bps target.**

### 3.3 SINGLE_SYMBOL_ARTIFACT (8/8)

For each of the 8 surviving cells, we tested the SAME formula + ET + MH at cost=0.5x on BTC and ETH:

```
formula        ET    MH   BTC val_pnl   ETH val_pnl   SOL val_pnl
wqb_s01        0.60  120  -0.1409      -0.2185       +0.0753  ← SOL only
wqb_s01        0.60  360  -0.1144      -0.1656       +0.0960  ← SOL only
wqb_s01        0.60  720  -0.1254      -0.2072       +0.0901  ← SOL only
wqb_s01        0.70  120  -0.0897      -0.2194       +0.1193  ← SOL only
wqb_s01        0.70  360  -0.0722      -0.1617       +0.1275  ← SOL only
wqb_s01        0.70  720  -0.0860      -0.2046       +0.1185  ← SOL only
wqb_s01_vwap   0.60  360  -0.1780      -0.2421       +0.0534  ← SOL only
wqb_s01_vwap   0.70  360  -0.1719      -0.1268       +0.0680  ← SOL only
```

→ **0 of 16 BTC/ETH cells survive** at cost=0.5x for these formulas. SOL is a 1-of-3 outlier. The strategy is **not symbol-generalizing** — it's exploiting something specific to SOL's price dynamics in the val period.

## 4. Why This Pattern Suggests Curve Fit / Regime Artifact

| Observation | Why it suggests artifact |
| --- | --- |
| 100% of survivors on a single symbol | a generalizable edge would manifest on at least 2 of 3 |
| Train PnL universally NEGATIVE while val POSITIVE | the formula does not represent a stable signal on the longer history |
| 1 narrow cost window (only 0.5x) — collapses at neighbor | edge thickness is below typical execution noise |
| 2 highly-correlated formulas (`wqb_s01`, `wqb_s01_vwap`) — both mean-reversion vs scaled price | suggests the survivor is one signal type viewed two ways, not two independent edges |
| ET=0.80 produces zero survivors at cost=0.5x | the survivor zone is at lower ET = more trades = more cost — **counter-intuitive** for a real edge (real edges should survive higher selectivity) |

## 5. SOLUSDT Val-Period Specificity

SOL's val slice (2024-05-02 → 2026-04-26) coincides with:
- The 2024 SOL ETF speculation cycle
- Multiple SOL-specific drawdowns and recoveries (Jupiter airdrop, Solana memecoin cycle 2024)
- Higher realised volatility than BTC/ETH

The mean-reversion formula `neg(sub(close, scale(close)))` essentially fades extreme normalised price moves. SOL's val period had **unusually high noise + range** — exactly the regime where mean-reversion strategies briefly outperform. This is consistent with a regime-specific artifact, not a durable edge.

## 6. Phase 3 Verdict

| Survivor | Verdict |
| --- | --- |
| All 8 cells | **SINGLE_SYMBOL_ARTIFACT** (100%) |
| Aggregate score | mean = 2.6/10, max = 3/10 |
| ROBUST_CANDIDATE count | **0** |
| FRAGILE_CANDIDATE count | **0** |

→ **Phase 3 verdict: ALL_SURVIVORS_REJECT_AS_ARTIFACT.**

No cost=0.5x survivor is robust enough to justify a controlled calibration implementation order. The "win" at cost=0.5x is thin (≤6 bps cost edge), train-val divergent, and isolated to a single symbol with no cross-symbol generalization.

→ **Even if cost calibration were lowered globally, none of these 8 cells should be promoted to live trading.** They demonstrate that a calibration WINDOW exists, but the WINNERS in that window are statistical artifacts.
