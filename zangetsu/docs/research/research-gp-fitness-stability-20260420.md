# Research — GP alpha fitness for OOS stability (2026-04-20)

Non-deletable research archive per CLAUDE.md §11. Context: Zangetsu v0.6.0 new
A1 fitness formula was flagged by Gemini as producing zombie alphas because the
linear asymmetry penalty dominates the quadratic magnitude reward. Three parallel
research agents searched for practitioner, academic, and ML-theory precedent.

## Problem statement

GP evolves alpha formulas over a 70% training window. Fitness is the Spearman
rank correlation (IC) between alpha values and 60-bar forward returns. Previous
single-window `|IC|` fitness produced overfit alphas (99.7% val_neg_pnl OOS).
The replacement split the training window in half, required `sign(ic_early) ==
sign(ic_late)`, and scored
`fitness = |ic_early| * |ic_late| - abs(|ic_early| - |ic_late|) - 0.001 * tree_height`.

Gemini flagged: at typical IC scales (0.02-0.08) the linear asymmetry penalty
dominates the quadratic product reward. Concrete example: 0.10/0.06 scores
-0.034 while 0.02/0.02 scores -0.0026, i.e. the weak alpha wins.

## Agent 1 — industry / practitioner

Finding: Industry does not use any of A/B/C. Standard practice is
`ICIR = mean(IC_t) / std(IC_t)` across many folds (typically K=20+).

- AlphaForge (arxiv.org/html/2406.18394v1): ICIR as canonical.
- Warm-Start GP (arxiv.org/html/2412.00896v1): confirms ICIR.
- Numerai (docs.numer.ai/numerai-signals/scoring): "era-Sharpe" = ICIR.
- WorldQuant BRAIN (worldquant.com/brain/iqc-guidelines/): PnL-based,
  `sqrt(|Returns|/turnover) * Sharpe`.

Missed option (D): `mean(|IC|) - lambda * std(|IC|)` is K=2 ICIR with
explicit stability penalty; at K>=5 it becomes proper ICIR; K=5 with
NSGA-II multi-objective is 2025 SOTA
(Springer 10.1007/s10614-025-11289-1).

Rank: D > C > A > B. Add sign gate, raise K to 5, apply Deflated Sharpe
at final selection.

## Agent 2 — academic literature

Two schools:
1. Practitioner-GP papers (Ruan 2024 arXiv:2412.00896, Shi 2025
   Computational Economics 10.1007/s10614-025-11289-1) default to RankIC+ICIR.
2. Lopez de Prado school (Bailey & Lopez de Prado 2014 SSRN 2460551,
   Lopez de Prado 2018 Advances in Financial Machine Learning) does NOT
   prescribe an aggregator but mandates Deflated Sharpe + CPCV.

Key insight: two-halves split is degenerate CPCV (N=2, k=1). Lopez de
Prado warns this is too small for meaningful stability detection and
recommends K>=5 with purge/embargo.

On harmonic mean: F1 analogue. H(0.95, 0.20) = 0.33 vs AM 0.575,
strongly penalizes imbalance.

Zombie warning: Ruan 2024 observed 7/10 GP runs collapse to identical
alphas when fitness over-rewards low-magnitude symmetry.

Rank: A > C > B. Sign-gated harmonic + complexity penalty + post-hoc DSR.

## Agent 3 — ML theory

Math:
- AM >= GM >= HM >= min for positive reals; equality iff all equal.
- HM = 2ab/(a+b) = 2 / (1/a + 1/b); reciprocal makes HM -> 0 as either
  arg -> 0.
- Taylor around a=b=m with delta: HM(m-d, m+d) = m - d^2/m + O(d^3).
- Example a=0.9, b=0.1: AM=0.50, GM=0.30, HM=0.18, min=0.10.

min() is the alpha->0 limit of CVaR and Chebyshev scalarization. Zero
gradient on non-worst leg causes thrashing (Yu et al. NeurIPS 2020).

Failure modes:
- A (harmonic): 1/a explodes near zero, needs epsilon floor; sign gate
  is hard discontinuity.
- B (product-with-asymmetry): weaker than HM since product <= GM <= HM;
  asymmetry ratio undefined at origin.
- C (min): zero gradient on non-min leg; min of absolute values loses
  inconsistency signal unless paired with sign check.

Rule of thumb: differentiable training -> HM; ranking/selection only ->
min; never pure product.

Rank: A > C > B.

## Consensus

- All three reject B.
- Agents 2 and 3 pick A.
- Agent 1 prefers D (ICIR at K>=5) over all of A/B/C, but agrees A is
  best among the K=2 options.
- Unanimous add-ons: sign gate (we have), complexity penalty (we have),
  Deflated Sharpe at final selection (NOT implemented after v0.6.0 DSR
  removal — v0.6.1 gap).

## Recommendation for Zangetsu

Today (v0.6.0 still in flight): sign-gated, epsilon-floored harmonic mean.
`fitness = sign_gate * 2*|ic_e|*|ic_l| / (|ic_e|+|ic_l|+epsilon) - 0.001*tree_height`
Matches academic + ML-theory consensus. Minimum-surgery change, no new infra.

v0.6.1 (next session): raise K from 2 to 5 contiguous folds over training
window. Switch fitness to `mean(|IC_k|) - lambda*std(|IC_k|)` with
`sign_match_all_k` gate. Add Deflated Sharpe back at A4 stage as separate
post-hoc filter (not in the GP fitness loop).

v0.7.0: NSGA-II multi-objective on (mean_IC, -std_IC) per Springer 2025.

## Primary sources

- https://arxiv.org/html/2406.18394v1 (AlphaForge)
- https://arxiv.org/html/2412.00896v1 (Warm-Start GP / Ruan 2024)
- https://docs.numer.ai/numerai-signals/scoring
- https://www.worldquant.com/brain/iqc-guidelines/
- https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf
- https://link.springer.com/article/10.1007/s10614-025-11289-1
- https://papers.ssrn.com/abstract=2460551 (Bailey & Lopez de Prado 2014)
- https://en.wikipedia.org/wiki/F-score
- https://proceedings.neurips.cc/paper/2020/file/3fe78a8acf5fda99de95303940a2420c-Paper.pdf
  (Yu et al., PCGrad)
- https://proceedings.mlr.press/v235/lin24y.html (Lin et al., Smooth
  Tchebycheff Scalarization, ICML 2024)
- https://pubsonline.informs.org/doi/abs/10.1287/opre.1080.0684 (Zhu &
  Fukushima, CVaR portfolio)
- López de Prado, Advances in Financial Machine Learning, Wiley 2018
- https://github.com/Morgansy/Genetic-Alpha
- https://github.com/Yitong-Guo/Genetic-Algorithm-for-quantitative-alpha-factors-mining
