# 02 — Gross vs Cost Decomposition (Subprogram-C, Phase 2)

**Generated**: 2026-04-28
**Source**: `j13@100.123.49.102:/tmp/c_batches_snapshot.jsonl` (106 post-restart `arena_batch_metrics` events)
**Mode**: READ-ONLY. No source modified.
**Tool persistence**: §-1 verified — re-read raw file from Alaya, recomputed from scratch (no cached numbers).

---

## 1. Distribution: `train_gross_pnl_median` (bps)

| n | min | p10 | p25 | median | p75 | p90 | max | mean | stdev |
|---|---|---|---|---|---|---|---|---|---|
| 106 | 0.1054 | 1.1159 | 1.9746 | **2.4574** | 2.7846 | 3.0451 | 3.2955 | 2.2414 | 0.8044 |

**Reading**: every batch has positive gross. None are negative. Edge IS present, but small (~2.5 bps).

## 2. Distribution: `train_gross_minus_net_median` (= cost charged, bps)

| n | min | p10 | p25 | median | p75 | p90 | max | mean | stdev |
|---|---|---|---|---|---|---|---|---|---|
| 106 | 0.0895 | 1.0521 | 3.1101 | **3.5990** | 4.3802 | 4.7475 | 5.8367 | 3.4283 | 1.2983 |

(For reference, `round_total_cost_bps`: median 14.5, range 11.5–23 — per-trade headline; the per-round charged cost above is what the alpha actually pays given its trade frequency.)

## 3. Distribution: `train_net_pnl_median` (bps)

| n | min | p10 | p25 | median | p75 | p90 | max | mean | stdev |
|---|---|---|---|---|---|---|---|---|---|
| 106 | -3.1013 | -1.8867 | -1.7030 | **-1.3261** | -0.7488 | -0.2031 | 0.0227 | -1.1818 | 0.6346 |

**Reading**: net is negative across the entire distribution except a sliver near max (≈0).

## 4. Per-Batch Comparison (n=106)

| Bucket | Count | % |
|---|---|---|
| `gross > cost` (edge beats cost) | **4** | 3.8% |
| `0 < gross ≤ cost` (β-pattern: edge present, cost dominates) | **102** | **96.2%** |
| `gross ≤ 0` (no positive edge) | 0 | 0.0% |
| `gross > 0 AND net > 0` (truly tradeable) | 2 | 1.9% |

## 5. Cost / Gross Ratio (when gross > 0; n=106)

| min | p10 | p25 | median | p75 | p90 | max | mean | stdev |
|---|---|---|---|---|---|---|---|---|
| 0.6215 | 1.2206 | 1.3539 | **1.5385** | 1.6843 | 1.7991 | 2.1188 | 1.5112 | 0.2578 |

**Reading**: cost is typically **1.5×** gross. Median batch loses ~54% of its gross to fees.

## 6. Edge Gap: `cost - gross` (bps, when gross > 0; n=106)

| min | p10 | p25 | median | p75 | p90 | max | mean | stdev |
|---|---|---|---|---|---|---|---|---|
| -0.3896 | 0.2407 | 0.7156 | **1.3172** | 1.7246 | 1.8894 | 3.0819 | 1.1869 | 0.6332 |

**Reading**: median batch needs another **~1.3 bps of gross** (or equivalent cost reduction) to reach breakeven.

## 7. Sharpe Positivity

`train_sharpe_median ≥ 0`: **3 / 106 = 2.8%**
Median Sharpe = -2.22; p90 = -0.83. The Sharpe distribution mirrors the net-pnl distribution: nearly everything is loss-making after costs.

---

## Interpretation — Dominant Pattern

**Classification: `GROSS_LOST_TO_COST` (β-pattern dominant).**

- **0% of batches have gross ≤ 0** — every alpha batch produces *some* positive raw edge.
- **96.2% of batches have `0 < gross ≤ cost`** — they have edge, but cost is ≥ that edge, killing net.
- Median ratio `cost / gross = 1.54` ⇒ cost over-eats gross by ~54%.
- Median `cost - gross gap = 1.32 bps` ⇒ a small (~1–1.5 bps) cost reduction OR gross uplift would flip the median batch from losing to breakeven.
- Only 1.9% (2/106) cleared cost enough to be tradeable; only 2.8% even posted non-negative Sharpe.

The system is **not** producing alphas without edge (NEGATIVE_GROSS_DOMINANT is rejected: 0 cases). It is producing alphas whose edge is **systematically smaller than the cost they pay** — exactly the β-pattern. This is a cost-structure / trade-frequency problem, not a "no signal" problem.

---

## Verdict for Subprogram-C Synthesis

**Primary classifier: `GROSS_LOST_TO_COST` (β-pattern, cost > gross).**

Numerical backing:
- 96.2% of batches (102/106) sit in the β-bucket (gross > 0 but ≤ cost).
- Cost / gross ratio: median 1.54×, p25 1.35×, p75 1.68× — the central mass is *all* β-pattern.
- Median edge gap = 1.32 bps; the system is **near**, not far from, profitability.
- Per-trade `round_total_cost_bps` median 14.5 (range 11.5–23) is the lever: bringing effective cost down ~35% (median ~3.6 bps charged → ~2.3 bps charged) would push median net positive.

**Recommendation seed (not in scope, flagged for synthesis)**: focus C-Subprogram conclusion on cost reduction / trade-frequency throttling / fee-tier optimization, NOT on regenerating new signal families.

---

## Q1 Adversarial Check (this analysis)

- **Input boundary**: 106/106 events have `train_gross_pnl_median`, `train_gross_minus_net_median`, `train_net_pnl_median` non-null. PASS.
- **Silent failure**: paired comparison required all three fields present; 106/106 paired. No silent drops. PASS.
- **External dep**: read-only on snapshot; no live system touched. PASS.
- **Concurrency / race**: snapshot is static file. PASS.
- **Scope creep**: only the 7 requested statistics + interpretation + verdict; no recommendations executed. PASS.

Q1/Q2/Q3: all PASS for the analysis itself.
