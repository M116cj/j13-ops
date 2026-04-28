# 04 — Economic Baseline

**Order:** TEAM ORDER 0-9Y-FINAL-0-MASTER-STATE-LOCK
**Phase:** 0 / sub-doc 04
**Captured (UTC):** 2026-04-28T02:55Z

## Source

`docs/recovery/20260424-mod-7/0-9y-system-completion-and-runtime-enablement/c-economic-edge-decomposition/08_final_report.md` (PR #58 / merge `e8b988b`).

## Verdict carried forward

```
DECOMPOSED_GROSS_EDGE_LOST_TO_COST
```

Secondary findings:
- WIN_RATE_STRUCTURALLY_LOW
- TRADE_FREQUENCY_AMPLIFIES_COST
- NO_HIDDEN_COHORT_EDGE
- VAL_NOT_REACHED

## Headline data (n = 106 post-restart batches; current 60-bar formulation)

| Metric | Value |
|---|---|
| `train_gross_pnl_median` | **+2.46 bps** (always positive; 0/106 ≤ 0) |
| `train_gross_minus_net_median` (cost charged) | **+3.60 bps** |
| `train_net_pnl_median` | **-1.33 bps** |
| `cost / gross` ratio | **1.54×** |
| Edge gap to breakeven | **1.32 bps short** |
| `train_win_rate_median` | **0.32** (max 0.494; **zero batches reach 0.50**) |
| `train_total_trades_median` | 989 |
| `signal_density_per_bar` | 0.00702 (ample) |
| `gross > 0 AND net > 0` | **1.9 %** (2/106 batches truly tradeable) |
| Per-cohort edge (14 symbols × 3 regimes) | **0 / 14** cells with median(gross) > median(cost) |

## Confirmed not-causes (from 0-9Y-C)

- ❌ NOT negative gross edge — gross is always positive
- ❌ NOT per-symbol concentration — uniform across cohorts
- ❌ NOT train→val overfitting — both train and val cost-negative
- ❌ NOT insufficient signal density — sparser quartile actually has BETTER net
- ❌ NOT a telemetry artifact — chain-fix verified live (CI=0, UR=0, conservation residual=0 in 106/106)

## Locked-cannot-relax constraints

| Constraint | Why locked |
|---|---|
| Cost model (Binance Futures 5–10 bps taker) | PR #41 retro proved lowering cost manufactures `SINGLE_SYMBOL_ARTIFACT` survivors |
| Validator stack (A1/A2/A3/A4) | Mathematically correct per 0-9X-PIPELINE-DEPLOYABLE-FLOW Phase 4; weakening admits money-losing alphas |
| `A2_MIN_TRADES = 25` | Forbidden by master order |
| Champion promotion / `deployable_count` semantics | Forbidden by master order |
| `alpha_zoo` DB write | Forbidden / blocked |
| CANARY / production rollout | Forbidden / blocked |

## Strategic implication (carried into FINAL-1 / D)

Only the **alpha-generation axis** may be redesigned:
1. **Target / horizon** — change forward-return horizon (e.g., 60 → 180 / 240 / 360 bars) to expose larger gross-per-trade
2. **Feature space** — add cross-asset / regime / volatility-normalized / volume-flow features to enable higher-WR signals
3. **Trade-frequency / signal-aggregation policy** — fewer-but-stronger trades to reduce cost burn (Phase-5 inverse correlation supports this)
4. **(Later optional)** alpha_zoo dry-run for external formula families
5. **(Later optional)** microstructure / orderbook path (higher cost, longer timeline)

## Master plan position

```
A → B1 → B2 → B3 → C ✓ → FINAL-0 (this) → D → HE0 → HE1 → HE2 → HE3 → TF1 → FS1 → j13-CHECKPOINT → HE4 → HE5 → HE6 → CANARY-OR-REDESIGN → MASTER-FINAL-REPORT
```

FINAL-0 is the master baseline. From here, every redesign attempt is anchored to these numbers.

## Acceptance for downstream phases

A redesign path is considered to "improve edge" if **at any horizon or any cohort** post-redesign:
- `train_gross_pnl_median > train_gross_minus_net_median` (gross > cost)
- AND `gross > 0, net > 0` rate > 5 %
- AND artifact check clean (no SINGLE_SYMBOL_ARTIFACT, no overfitting)

A redesign restores deployable flow if:
- `deployable_count > 0`
- AND realistic cost unchanged
- AND validator unchanged
- AND artifact check clean

These thresholds are referenced by HE5 / HE6 / Final-CANARY-or-Redesign.
