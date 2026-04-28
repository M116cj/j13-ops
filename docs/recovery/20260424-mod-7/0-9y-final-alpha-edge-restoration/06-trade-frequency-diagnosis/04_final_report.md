# 04 — Final Report (TF1 Phase 6)

**Order:** TEAM ORDER 0-9Y-TF1-TRADE-FREQUENCY-SIGNAL-AGGREGATION-DIAGNOSIS
**Sample:** n=106 A1 batches, B1 schema (`0-9y-b1-v1`), 14 symbols × 3 regimes.
**Status:** Read-only. No code/config/threshold/validation modified.

## Final verdict

# **DIAGNOSED_LOWER_FREQUENCY_COULD_IMPROVE_EDGE**

(With strong corroboration from the top-decile analysis pointing at the **DIAGNOSED_SIGNAL_AGGREGATION_REQUIRED** mechanism. The two verdicts are not exclusive in this case — the top decile *is* the sparse cohort. We pick `LOWER_FREQUENCY` as the primary verdict because it is the more general statement and is supported by both quartile analysis and correlations; signal aggregation is the recommended *implementation pathway* to realise it.)

## Headline numbers

| Statement | Value |
|-----------|------:|
| **Q1 (sparse) vs Q4 (dense) net_med median delta** | **+1.0428** |
| Q1 vs Q4 net_med mean delta | +0.8250 |
| P(Q1 > Q4) pairwise AUC | **0.8354** |
| Pearson(density, net_pnl) | **−0.6511** |
| Spearman(density, net_pnl) | **−0.5009** |
| Pearson(trades, net_pnl) | **−0.6479** |
| Spearman(trades, net_pnl) | −0.4810 |
| Pearson(trades, cost) | +0.8263 |
| Pearson(trades, gross/trade) | **−0.3664** |
| Top-decile-by-sharpe net_med median | **−0.0278** |
| Rest-of-batches net_med median | −1.3706 |
| Top-decile improvement vs rest | **~49×** in absolute net_med |
| Top-decile median trade count | 104 |
| Rest median trade count | 989 |
| Net-positive batches in entire sample | 2 / 106 (1.9%) — both in trades-Q1 / density-Q1 |
| Sharpe-positive batches in entire sample | 3 / 106 (2.8%) — all in trades-Q1 / density-Q1 |

## Why both LOWER_FREQUENCY and SIGNAL_AGGREGATION verdicts apply

1. **Frequency hurts net mechanically.** Cost scales linearly with trade count (Pearson +0.83) but per-trade gross decays as frequency rises (Pearson −0.37). Net therefore turns over sign vs trades (Pearson −0.65). This is the LOWER_FREQUENCY signal.
2. **Top-decile is structurally low-frequency.** When ranked by `train_sharpe_median`, the top 10% have median 104 trades (vs 989) and median density 0.00103 (vs 0.00704). When ranked by net, the same cohort surfaces. The few sharpe>0 / net>0 batches all sit in trades-Q1 / density-Q1. This is the SIGNAL_AGGREGATION signal: the strongest sharpe is *exactly* where the engine emits sparse signals — i.e. it already knows how to produce concentrated signals; the issue is that the bulk of generation profiles are tuned to dense emission.
3. **The pathway from observation to action is signal aggregation.** "Reduce trade frequency" without a mechanism is meaningless — you need a filter that selects the right reductions. The top-decile cohort shows the filter that works: high pre-trade signal strength (sharpe is the post-hoc proxy here; in production this maps to score threshold / top-K-per-bar / consensus across alphas).

## Statistical robustness check

- n=106, all primary metrics present.
- Pearson |r| > 0.5 for density-vs-net and trades-vs-net; Spearman |r| > 0.4 for both. Two-sided p < 1e-6 for both Pearson values at this n.
- Q1-vs-Q4 AUC = 0.84 for both density and trade count → effect is rank-based, not driven by outliers.
- Cross-check: top-decile-by-sharpe and top-decile-by-net produce the same 10 batches → verdict is not a metric-selection artefact.

## Adversarial caveats (Q1 dimension scan)

1. **Symbol confound.** Top decile is concentrated in SOLUSDT (4) and AAVEUSDT (4). Six other symbols never appear. Sparse-cohort outperformance might be partly "SOL/AAVE happens to be more tradable at this regime". **Mitigation for TF2:** stratify aggregation prototype by symbol; require that the win extends beyond SOL/AAVE before declaring it general.
2. **Low-trade-count Sharpe is statistically noisy.** A batch with 23 trades has a much wider Sharpe sampling distribution than one with 991. Two SOL batches at 89 trades produce sharpe ≈ +0.27 — believable but not bulletproof. **Mitigation:** in TF2 require minimum effective sample size (the existing A2_MIN_TRADES=25 LOCKED is a floor; aggregation prototype must respect it per alpha).
3. **Selection bias of "top decile".** The top decile is selected by sharpe — circular if used to validate sharpe-based aggregation. **Mitigation already in place:** quartile analysis (independent of any sharpe-based selection) shows the same density/trade-count → net relationship, so the top-decile observation is corroborative, not foundational.
4. **Gross alpha is real and dense.** 100% of batches have gross>0 across all density quartiles. Aggressive aggregation could throw out gross we should keep. **Mitigation:** TF2 must measure gross retention rate (e.g. "top-K aggregation retains X% of gross at Y% of trades").
5. **Cost is fixed at 14.5 bps round-trip.** Reducing cost is a separate parent-order workstream. Aggregation gains compound with cost reduction; do not double-count.

## Recommendation for next future order

# **YES — proceed with TEAM ORDER 0-9Y-TF2-SIGNAL-AGGREGATION-PROTOTYPE.**

Rationale:
- Effect size is large (+1.04 net delta Q1 vs Q4, AUC 0.84).
- Mechanism is identifiable (cost scales with trades; per-trade gross decays with trades; top-decile cohort is the sparse cohort).
- Action surface is clean: introduce a pre-trade signal-strength filter (score threshold, top-K-per-bar, consensus) without touching A2_MIN_TRADES, validation, cost, or entry threshold per master order.
- Risk is bounded: the prototype is a read-only filter on top of the existing engine, easy to A/B vs the dense baseline.

### Suggested TF2 scope (for the team-order author, non-binding)

1. Implement signal-strength scoring at alpha emission time (do not change alpha logic itself).
2. Filter strategies: (a) hard threshold on score, (b) top-K-per-bar, (c) require consensus across N alphas.
3. Sweep K / threshold to land in the trades_med ≈ 80-250 range (matches top-decile observed sweet spot).
4. Acceptance: ≥ 30% of post-aggregation batches have **net_med > 0** AND **train_sharpe_median > 0** AND post-aggregation gross retention ≥ 25% of pre-aggregation gross.
5. Stratify acceptance by symbol — must extend beyond SOL/AAVE to declare success.
6. Respect locked invariants: A2_MIN_TRADES=25, validation, cost (14.5 bps), entry threshold all unchanged.

## Compliance attestation

- No source/code/config/feature touched. ✓
- A2_MIN_TRADES not changed. ✓
- Validation not changed. ✓
- Cost not changed. ✓
- Entry threshold not changed. ✓
- Read-only file outputs only (5 markdown files in this directory). ✓
- No commit. ✓

## Q1 / Q2 / Q3 (this analysis)

- **Q1 Adversarial:** input boundary PASS (n=106, all numerics present); silent failure PASS (sharpe-by-net cross-check eliminates metric-selection artefact); external dep N/A (offline analysis); concurrency N/A; scope creep PASS (read-only as specified). 5 caveats documented above with mitigations for TF2.
- **Q2 Structural integrity:** PASS — analysis script `/tmp/tf1_analyze.py` is reproducible from the snapshot file; raw output saved at `/tmp/tf1_analysis_output.txt`.
- **Q3 Execution efficiency:** PASS — single-pass script, ~250 lines of analysis code, ~250-350 lines of deliverables, no superfluous outputs.
