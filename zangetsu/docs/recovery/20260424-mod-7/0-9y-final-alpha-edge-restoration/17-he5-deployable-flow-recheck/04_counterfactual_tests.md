# 04 — COUNTERFACTUAL TESTS

**TEAM ORDER**: 0-9Y-HE5-DEPLOYABLE-FLOW-RECHECK
**Date**: 2026-04-29
**Phase**: 4 / 8

## Methodology
**Read-only offline analysis** on the HE4 frozen dataset (3266 batches × 3 horizons, 32 660 alpha entries). For each batch, recompute hypothetical net under different what-if scenarios. **No DB writes, no source changes, no production runs.**

## Scenario A — Cost reduction (what if real cost were lower?)

### Mechanism
For each batch, compute `net_new = (1 − f) × gross + f × net` where `f ∈ {0.1, 0.2, …, 1.0}` is the cost-fraction kept. (At `f=1.0`, original; at `f=0.5`, cost halved; at `f=0.0`, no cost.) Count batches where `net_new > 0`.

### Results
| f (cost factor) | Batches with net > 0 | % |
|---:|---:|---:|
| 1.0 (current) | 0 | 0.00% |
| 0.9 | 1 | 0.03% |
| 0.8 | 146 | 4.47% |
| **0.7** | **842** | **25.78%** |
| 0.6 | 2617 | 80.13% |
| **0.5** | **3252** | **99.57%** |
| 0.4 | 3264 | 99.94% |
| 0.0 | 3264 | 99.94% |

### Interpretation
- **Tipping point at ~0.65× cost**: at 30-35% cost reduction, the median batch flips positive
- **At 50% cost reduction (0.5×)**: 99.57% of batches would be net-positive (essentially the entire fleet)
- **Cost is the dominant binding constraint** — no other variable in the system shows this kind of leverage

### Practical feasibility
- Cost model is **forbidden** to modify (master-order hard rule)
- Real-world cost reflects actual fees + slippage on Binance perpetuals
- **Operator-side cost reduction** = exchange-tier negotiation, maker-only execution, smart routing — these are infrastructure changes outside zangetsu's control

## Scenario B — Trade-count halved (TF3-style filtering)

### Mechanism (using TF3 live results as oracle)
TF3 live shadow proved that aggregation profiles (STRENGTH_q=0.95) reduce trade count by ~93% while improving per-trade gross by ~25%, but cost/gross ratio only improves to ~1.30 (down from 1.55).

### Mapping to current question
| Profile | trades_med | gross/trade | cost/gross | net (median) | net > 0? |
|---|---:|---:|---:|---:|---|
| Baseline (no filter) | 980 | +0.00244 | 1.55 | -1.22 | ❌ |
| TF3 STRENGTH_q=0.95 | 64.5 | +0.00310 | 1.30 | -0.06 | ❌ (closer but negative) |
| TF3 HYBRID q=0.90 K=50 | 89.2 | +0.00318 | 1.34 | -0.09 | ❌ |
| Hypothetical q=0.99 (top 1%) | ~10 | +0.0040 (extrapolated) | ~1.10 (extrapolated) | -0.01 (extrapolated) | ❌ borderline |

### Interpretation
- Random trade-halving: no improvement (cost and gross scale together)
- **Quality-filtered trade-halving (TF3-style)**: improves cost/gross from 1.55 → 1.30, but **net stays negative** at all tested filter levels
- Even extreme filtering (top 1%) extrapolates to net ≈ -0.01 bps — essentially zero, not robustly positive
- **Filtering alone cannot flip net positive** without cost reduction or fundamental edge improvement

## Scenario C — Win-rate +5pp uplift

### Mechanism
Holding average win/loss size constant, increase win rate from current 0.31 to 0.36. Compute Δnet/trade.

Using a symmetric approximation: if average winning trade gross = average losing trade absolute loss = `w`, current per-trade net = `(0.31 − 0.69) × w = −0.38w`. At new win rate 0.36, per-trade net = `(0.36 − 0.64) × w = −0.28w`. Δnet/trade = +0.10w.

### Results
- Current per-trade gross = +0.00244 bps; under symmetric model, `w ≈ 0.024 bps` (gross is sum of wins + losses, dominated by wins)
- Δnet per trade = +0.10 × 0.024 = +0.0024 bps
- Δnet per batch (× 980 trades) = +2.4 bps
- Current net = -1.22 bps → **estimated net_new = +1.18 bps (POSITIVE)**

### Interpretation
- **A +5pp win-rate uplift would flip the system positive** — assuming win/loss sizes are symmetric (a structural assumption)
- This requires alphas with stronger directional edge — i.e., a deeper / smarter feature space, microstructure features, or a different validation regime
- **No path within explored axes (OP1/TF/HE)** has produced a +5pp win_rate uplift in live data:
  - OP1: primitive expansion did not improve win_rate measurably
  - TF3 STRENGTH_q=0.95: win_rate uplift = +4.5pp ← close to threshold but cost still dominates
  - HE4: no win_rate change across horizons
- TF3 came tantalizingly close (+4.5pp) but the *concurrent* skip_rate of 93% reduced the absolute gross too much

### Combination: TF3 strength filter + +5pp win rate
The +4.5pp win_rate at TF3 q=0.95 PLUS a hypothetical further +0.5pp would push past +5pp. But whether this exists is empirical, not algorithmic.

## Counterfactual classification (per master-order Phase 4 enum)

| Scenario | Result | Master-order classification |
|---|---|---|
| A. Cost reduction | net > 0 at 0.65×+ cost | **COST_REDUCTION_WORKS** ✅ (but cost is forbidden) |
| B. Trade reduction (TF3-style) | net stays negative | **TRADE_REDUCTION_WORKS_PARTIALLY** (improves but doesn't flip) |
| C. Win-rate +5pp | net flips positive | **EDGE_IMPROVEMENT_WORKS** (but requires a path that doesn't currently exist) |

## Combined classification
**Multiple axes contain "if-only" levers**:
- ✅ Cost reduction would solve (BUT forbidden; structural change)
- ⚠️ Trade reduction improves (BUT cannot fully solve in current pipeline)
- ✅ Edge / win-rate improvement would solve (BUT no proven path within current architecture)

**No counterfactual works WITHOUT a structural / forbidden change.**

## Verdict
**PHASE_4_COMPLETE** — counterfactuals identify two axes that theoretically work (cost reduction or +5pp win_rate uplift), but **neither is achievable within the current architecture and HE5's forbidden constraints**.

## Next
Phase 5 — final decision matrix.
