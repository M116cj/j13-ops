# 06 — Synthesis (Subprogram C)

**Order:** TEAM ORDER 0-9Y-C-ECONOMIC-EDGE-DECOMPOSITION
**Phase:** 6
**Date (UTC):** 2026-04-28T00:14Z
**Author:** Claude Lead

## Synthesis of Phase 2-5 subagent verdicts

| Phase | Subagent verdict | Key number |
|---|---|---|
| 2 — Gross-vs-cost | `GROSS_LOST_TO_COST` | 96.2 % batches in β-pattern (0 < gross ≤ cost); 0 / 106 negative-gross |
| 3 — Per-cohort | `UNIFORM` | 0 / 14 (symbol × regime) cells with median(gross) > median(cost); CV(gross)≈CV(cost) |
| 4 — Train-vs-val | `TRAIN_VAL_BOTH_NEGATIVE` | val ran on 14 / 106; combined_sharpe passed on 0 / 106; in val-seen subset, 0 classic-overfit cases |
| 5 — Signal density | `SUFFICIENT_DENSITY_BUT_LOW_WIN_RATE` | median density 0.00702 (ample); WR median 0.32, max 0.494 (zero batches ≥ 50 %) |

All four subagents converge on a coherent picture.

## Causal chain

1. **Alpha generation produces signals with small positive gross edge** (median `train_gross_pnl_median = 2.46 bps`). The signal-generation layer is doing its job: edge exists.
2. **Win rate is structurally low** (median 0.32, max 0.494). At WR=0.32, expected value per trade is dominated by the loss leg even before cost.
3. **Trade frequency is high** (~989 trades / 140 000 bars = 0.0070 trades/bar). With low WR, more trades = more cost incurred.
4. **Per-trade cost (14.5 bps round-trip)** outpaces the per-trade gross expectancy (median ~2.5 bps when not annualized appropriately, but the takeaway is cost > gross).
5. **Aggregate cost charged per round** (median `train_gross_minus_net_median = 3.60 bps`) **exceeds aggregate gross** (median 2.46 bps) by ~1.32 bps.
6. **Net is therefore negative** (median `train_net_pnl_median = -1.33 bps`).
7. **Validator correctly rejects** every alpha with negative net → `COST_NEGATIVE` in 100 % of batches.
8. **No survivor reaches val** in 92 / 106 batches; in the 14 batches where val runs, both train and val are cost-negative (no train→val overfitting).
9. **Population is uniform** — no hidden symbol or regime cohort has gross > cost; rejection is not a sampling artifact.
10. **Density is sufficient**; sparser-quartile batches actually have better net (−0.29 vs Q3's −1.75), suggesting that less trading at the same gross expectancy + same cost would IMPROVE net by reducing total cost burn. But density alone won't fix the structural WR-cost gap.

## Root cause classification

**Primary**: `DECOMPOSED_GROSS_EDGE_LOST_TO_COST`

**Secondary findings (not separate roots, but compounding)**:
- `WIN_RATE_STRUCTURALLY_LOW` (≤ 50 % across all 106 batches; median 32 %)
- `TRADE_FREQUENCY_AMPLIFIES_COST` (denser quartile = worse net at fixed gross)
- `NO_HIDDEN_COHORT_EDGE` (uniform across 14 symbols × 3 regimes × 2 lanes)
- `VAL_NOT_REACHED` (14 / 106 batches; train kills 96 % of alphas before val)

## What this is NOT

- **NOT `NEGATIVE_GROSS_EDGE_DOMINANT`** — gross is positive in 100 % of batches
- **NOT `PER_SYMBOL_CONCENTRATION`** — uniform across cohorts
- **NOT `TRAIN_VAL_DIVERGENT_OVERFITTING`** — when val runs, both sides are cost-negative
- **NOT `INSUFFICIENT_SIGNAL_DENSITY`** — density is ample; sparsity actually correlates with better net (inverse direction from intuition)
- **NOT a telemetry artifact** — chain-fix from PRs #48-50 is verified live; conservation residual = 0 in 106 / 106 batches; no spurious CI/UR

## What constraints stay locked (cannot relax to "fix" this in C)

Per master plan + carry-forward audit:
- **Cost model is realistic Binance Futures** (5–10 bps taker tier; PR #41 retro proved lowering cost manufactures `SINGLE_SYMBOL_ARTIFACT` survivors). Cannot reduce.
- **Validator stack (A1/A2/A3/A4) is mathematically correct** per #53 Phase 4. Cannot weaken.
- **A2_MIN_TRADES = 25** unchanged (forbidden by order constraints).
- **No alpha_zoo / CANARY / production rollout** triggered.

## Implication for downstream subprograms

| Subprogram | Implication of C verdict |
|---|---|
| **D — Strategic Redesign Decision** | C's verdict says: signal layer produces small positive gross; cost layer dominates. Redesign must change one of: (a) target/horizon to expose larger gross-per-trade, (b) feature space to enable higher-WR signals, (c) trade-frequency policy (e.g., signal-aggregation, hold-time gates) to reduce cost burn. Cost itself is locked. |
| **E\* — Implement chosen redesign** | Implementation depends on D's choice. Likely candidates: order-book / funding-rate features (cross-symbol carry), longer hold (e.g., 240-bar fwd return), regime-conditional position sizing. |
| **F — Deployable flow recheck** | After E*, re-run Subprogram C analysis on the new generation profile. Expected: gross median > cost median in at least one cohort. |
| **G — CANARY readiness** | Gated by F's gross > cost result + a stable champion population. |
| **H — Production rollout** | Gated by G + j13 sign-off. |

## Confidence

**HIGH** — the verdict is supported by all four parallel analyses, each anchored to specific numerical evidence from the same 106-batch dataset. No subagent reported a conflicting or weak signal.

## Q1 / Q2 / Q3 self-check (Phase 6)

- **Q1 Adversarial (5-dim)**:
  - Input boundary: handled (val/combined null cases addressed in Phase 4 / 5; medians of small subsets disclosed; 14-batch val subset acknowledged as small but reported)
  - Silent failure: each verdict cites specific number from one of the four phase reports; no inferred-from-inference chains
  - External dependency: only engine.jsonl and the snapshot file; no DB/network/classify dependency
  - Concurrency: each batch is one worker × one moment; no cross-worker arithmetic involved
  - Scope creep: no source patch, no calibration, no DB write, no validator change
- **Q2 Structural**: read-only operations; runtime untouched; existing residual-correction branch preserved; PRs #48-50 chain-fix verified live
- **Q3 Efficiency**: 4 subagents in parallel for Phases 2-5; Lead synthesis in one document; 7 evidence files used out of 9 allowed
