# 05 — Cost and Turnover Risk Matrix

**TEAM ORDER**: 0-9AA — Phase 5
**Date**: 2026-04-30
**Mode**: READ-ONLY / DECISION-ONLY

## Why This Phase

0-9Z anchored: current effective cost ≈ 14.5 bps, break-even ≤ 9.4 bps, required cut ≈ 35%. Any axis whose natural turnover is high enough that gross edge per trade is dominated by 14.5 bps round-trip will repeat the 0-9Y exhaustion outcome. Selection must explicitly favor low-turnover or high-gross-per-trade axes.

## Per-Axis Cost / Turnover Profile

| Axis | Expected Holding Period | Expected Trade Frequency | Expected Gross-per-Trade | Cost / Gross Risk | Funding Sensitivity | Slippage Sensitivity | A2 Risk (≥25 trades) | Implementation Burden | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| **A — Microstructure** | seconds–minutes | very high (HFT-scale) | low per trade, high in aggregate | **VERY HIGH** — only viable maker-only at VIP3+ | low (very short holds) | very high | safe (huge trade count) | very high (data layer + execution arch) | `COST_HOSTILE_UNTIL_EXEC_ARCH` |
| **B — Funding / OI** | hours–days (8h funding cycles) | low (tens per symbol per year on funding events) | high per trade (regime-shift sized moves) | **LOW** | low (positions held through funding ticks) | low | risky if signals too sparse — needs ≥25 trades per Arena window | low–medium (parquet already exists) | `LOW_COST_RISK_BUT_A2_SPARSITY_RISK` |
| **C — Regime conditional** | minutes–hours (regime gates current alpha) | medium — depends on regime gate tightness | medium (regime-filtered subset of existing edge) | medium | low | medium | medium — gate too tight → too few trades | low | `MEDIUM_COST_RISK_TUNABLE` |
| **D — Cross-sectional rank** | hours–days (rebalance window) | low–medium (rebalance per period) | medium-high (rank-spread sized) | **LOW** | medium (rank long pays funding more often) | low–medium (multi-symbol portfolio dilutes per-leg slippage) | medium — small universe (14) limits independent trades | medium | `LOW_COST_RISK_BUT_UNIVERSE_THIN` |
| **E — Liquidity / volume shock** | minutes–hours | medium-high (events) | medium-high per event | medium-high | low | medium | safe — events frequent enough | medium | `MEDIUM_COST_RISK` |
| **F — Volatility expansion** | minutes–hours | medium | low without direction filter; medium with filter | high without filter; medium with | low | medium | safe in count, but false breakouts dominate net | medium | `HIGH_COST_RISK_UNLESS_HYBRIDIZED` |
| **G — Alt timeframe / universe** | varies | varies | inherits from underlying axis | varies | varies | varies | varies | low | `MODIFIER_ONLY` |
| **H — Hybrid (e.g. C+B / C+D / C+E)** | inherits from gate component | gated frequency (lower than primary) | gated gross (higher per surviving trade) | **LOW–MEDIUM** | inherits | inherits | medium — gating reduces count, must verify ≥25 | medium | `BEST_COST_PROFILE_IF_GATED` |

## Cost-Wall Verdict per Axis

| Axis | Survives 14.5 bps cost wall under current architecture? |
|---|---|
| A | NO without execution arch + microstructure data |
| B | likely YES (low turnover, large per-trade moves) |
| C | conditionally YES — requires gate tightness tuned to keep gross-per-trade > cost |
| D | likely YES (portfolio rebalance, low per-leg cost) |
| E | conditionally YES — depends on event-edge size |
| F | NO without direction filter / hybrid gate |
| G | n/a (modifier) |
| H | YES if gate filters out cost-dominated trades |

## Implication for Selection

- **B (Funding/OI)** has the structurally cleanest cost profile but carries A2-sparsity risk.
- **D (Cross-sectional)** has cost-friendly portfolio dilution but universe-thin risk.
- **C (Regime)** is cost-tunable via gate tightness — the most flexible.
- **H (Hybrid C-gated B/D/E)** combines Cs tunability with B/Ds low turnover, the strongest cost-profile candidate.
- **F (Volatility)** alone is cost-hostile; rescued only as a hybrid component.
- **A (Microstructure)** is cost-hostile until execution architecture is built.

## Deliverable

`05_cost_and_turnover_risk_matrix.md` — frozen.
