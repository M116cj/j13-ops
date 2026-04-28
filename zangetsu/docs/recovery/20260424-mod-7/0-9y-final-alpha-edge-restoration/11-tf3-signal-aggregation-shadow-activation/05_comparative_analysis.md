# 05 — COMPARATIVE ANALYSIS

**TEAM ORDER**: 0-9Y-TF3-SIGNAL-AGGREGATION-SHADOW-ACTIVATION
**Date**: 2026-04-28
**Phase**: 5 / 8

## Δ comparison vs baseline (live data, n=352 batches)

| Metric | baseline | strength (q=0.95) | top_k (K=50) | hybrid (q=0.90, K=50) |
|---|---:|---:|---:|---:|
| **Δ trade_count_median** | 983 | −918.5 (−93.4%) | −893.8 (−90.9%) | −893.8 (−90.9%) |
| **Δ gross_pnl_median (bps)** | +2.4554 | −2.2443 | −2.1661 | −2.1745 |
| **Δ net_pnl_median (bps)** | −1.1768 | **+1.1134** | +1.0813 | +1.0849 |
| **Δ win_rate_median** | 0.3125 | **+0.0451 (+4.5pp)** | **+0.0476 (+4.8pp)** | +0.0460 (+4.6pp) |
| **Δ cost/gross ratio** | 1.4964 | **−0.1994 (−13.3%)** | −0.1624 (−10.9%) | −0.1580 (−10.6%) |
| **Δ net_per_trade (bps)** | ≈ −0.00120 | **−0.000971 (improved)** | −0.001099 | −0.001098 |
| **Δ gross_per_trade (bps)** | ≈ +0.00250 | +0.003102 (+24%) | +0.003176 (+27%) | +0.003182 (+27%) |
| skip_rate | 0 | 0.9344 | 0.9235 | 0.9270 |

(positive Δ = improvement for net/win_rate/gross_per_trade/net_per_trade; negative Δ = improvement for cost/gross)

## Per-criterion judgement (per master-order Phase 5 spec)

### 1. Cost reduction
| Profile | cost/gross | vs baseline |
|---|---:|---|
| **strength** | 1.2970 | **−13.3%** ✅ |
| top_k | 1.3340 | −10.9% ✅ |
| hybrid | 1.3384 | −10.6% ✅ |

All three profiles materially reduce cost burn. **`strength` is the leader.**

### 2. Win-rate improvement
| Profile | win_rate | Δ pp |
|---|---:|---|
| top_k | 0.3601 | **+4.76 pp** ✅ |
| hybrid | 0.3585 | +4.60 pp ✅ |
| strength | 0.3576 | +4.51 pp ✅ |

All profiles raise win rate by ~4.5-4.8 pp. Order is roughly even — top_k narrowly leads.

### 3. Net improvement
| Profile | net_pnl_median | Δ vs baseline |
|---|---:|---|
| **strength** | −0.0634 | **+1.1134 bps** ✅ |
| hybrid | −0.0919 | +1.0849 bps ✅ |
| top_k | −0.0955 | +1.0813 bps ✅ |

All profiles improve net (less-negative). `strength` is closest to break-even. **No profile achieves positive net per alpha** — the strength→quality monotonicity in real data is shallower than fixture predicted, so filtering does not push net positive at current cost levels.

### 4. Stability across symbols
14 unique symbols observed; top-1 share = 11.9%. No single-symbol dominance.
- baseline distribution and shadow distribution are sampled from the same per-symbol pool (shadow inherits the symbol the worker is currently scanning) → no introduced bias.
- Conservation per profile per batch: **0 / 352** residual ≠ 0 across all 3 profiles.

✅ **No single-symbol artifact.**

### 5. No conservation regression
| Counter | Pre-shadow (TF2 baseline 300 batches) | TF3 shadow window (352 batches, baseline path) |
|---|---|---|
| `UNKNOWN_REJECT` total | 0 | **0** ✅ |
| `COUNTER_INCONSISTENCY` | 0 | **0** ✅ |
| Conservation residual (entered = sum) | 0 | **0** ✅ |

Shadow path adds zero conservation regressions to baseline.

### 6. No telemetry anomalies
- `aggregate_metrics` schema unchanged — only the new `shadow_profiles` key is added (additive)
- `aggregate_metrics_availability` flags unchanged
- `top_reject_reason` continues to report `COST_NEGATIVE` as primary (unchanged)

## Classification per profile (master-order Phase 5 enum)

| Profile | Net improved? | Cost reduced? | Trade count reduced? | Win rate increased? | Artifact? | Conservation? | **Classification** |
|---|---|---|---|---|---|---|---|
| **strength** (q=0.95) | ✅ | ✅ | ✅ | ✅ | ❌ none | ✅ | **PROFILE_STRONGLY_IMPROVES_NET** |
| **top_k** (K=50) | ✅ | ✅ | ✅ | ✅ | ❌ none | ✅ | **PROFILE_STRONGLY_IMPROVES_NET** |
| **hybrid** (q=0.90, K=50) | ✅ | ✅ | ✅ | ✅ | ❌ none | ✅ | **PROFILE_STRONGLY_IMPROVES_NET** |

All three profiles satisfy every criterion. **No profile classified as DEGRADES, NO_EFFECT, UNSTABLE, or ARTIFACT_RISK.**

## Best profile selection (for next-step recommendation)

| Criterion | strength | top_k | hybrid |
|---|---|---|---|
| cost/gross reduction | **best** | mid | mid |
| net_pnl improvement | **best** (least negative) | 3rd | 2nd |
| net_per_trade | **best** | 3rd | 2nd |
| win_rate | 3rd | **best** | 2nd |
| skip_rate (more is more aggressive) | most (0.934) | least (0.924) | mid (0.927) |

**Winner: `STRENGTH_q0.95`** — wins 3/5 criteria including the two most economically meaningful (cost/gross, net per trade).

This **diverges from the TF2 fixture prediction** that HYBRID_q0.90_K=50 would be best. Reason: the synthetic fixture monotonicity (linear gross ∝ strength) overstates the marginal benefit of additionally bounding K once the strong-quantile cut is applied. In live data, the K-cut on top of the q-cut adds noise (K=50 sometimes admits weaker survivors of the quantile cut — 50 of e.g. 65 survivors after q=0.90, vs. q=0.95 keeping ~50 directly).

## Live data vs TF2 fixture summary
| Aspect | TF2 fixture | TF3 live |
|---|---|---|
| Hypothesis (strength→quality) | assumed | **confirmed directionally** |
| Best profile | HYBRID_q0.90_K=50 | **STRENGTH_q0.95** |
| Win-rate uplift (best) | +16.5 pp (overstated) | +4.6-4.8 pp (real) |
| Cost/gross reduction | n/a | **−13.3% (strength)** |
| Edge polarity flip (net negative → positive) | yes (fixture) | **no — net still slightly negative across all profiles** |

## Outstanding finding
**Net per trade is still negative across all profiles**. Live cost is high enough that filtering to the strongest 5-7% of entries reduces — but does not eliminate — the cost-burn. To achieve break-even net per trade, either:
- Even more aggressive filtering (e.g., q=0.99 → top 1%) — risks insufficient sample size for A2 gates (`A2_MIN_TRADES=25` per alpha)
- Cost model improvement — **forbidden** in TF3 (out of scope)
- Alpha-side improvement (better signal-strength source / richer features) — points to OP-line or HE-line orders

## Verdict
**PHASE_5_COMPLETE — three profiles all classified `PROFILE_STRONGLY_IMPROVES_NET`; no DEGRADES; no artifact; conservation intact.** Best profile = `STRENGTH_q0.95`. TF1 hypothesis is **confirmed in live data** with directionally correct sign and material economic improvement, though absolute net is still slightly negative.

## Next
Phase 6 — controlled diff + forbidden audit.
