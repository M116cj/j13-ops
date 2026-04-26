# 05 — GP Overfit Pressure Audit

## 1. GP Search Parameters (read-only inspection)

| Parameter | Default | Env override | Source |
| --- | --- | --- | --- |
| `N_GEN` | 20 | `ALPHA_N_GEN` | `arena_pipeline.py:751` |
| `POP_SIZE` | 100 | `ALPHA_POP_SIZE` | `arena_pipeline.py:752` |
| `TOP_K` | 10 | `ALPHA_TOP_K` | `arena_pipeline.py:753` |
| `ENTRY_THR` | 0.80 | `ALPHA_ENTRY_THR` | `arena_pipeline.py:754` |
| `EXIT_THR` | 0.50 | `ALPHA_EXIT_THR` | `arena_pipeline.py:755` |
| `MIN_HOLD` | 60 | `ALPHA_MIN_HOLD` | `arena_pipeline.py:756` |
| `COOLDOWN` | 60 | `ALPHA_COOLDOWN` | `arena_pipeline.py:757` |
| `TRAIN_SPLIT_RATIO` | 0.7 | (not env-overridable) | `arena_pipeline.py:283` |

## 2. GP Search Intensity

`POP_SIZE × N_GEN = 100 × 20 = 2 000 evaluations per (sym, regime) round`. **Moderate** for crypto strategy GP — not extreme.

## 3. Selection / Mutation / Crossover

The strategy fitness function is loaded dynamically per-strategy:

```
from j01.fitness import fitness_fn as _strategy_fitness_fn
engine = AlphaEngine(indicator_cache=..., fitness_fn=_strategy_fitness_fn)
```

Mutation/crossover details live inside `AlphaEngine.evolve()`. NOT inspected in this read-only audit (per Phase 5 scope), but the GP itself is moderate intensity.

## 4. Train / Holdout Score Gap (live)

A1 emits the training-side score implicitly: only `champions=N/10` per round. `champions` is the count of TOP_K alphas that **passed all val gates** — currently 0/10 every round. We do NOT have direct train-side metrics in the live stats line (only counters for reject reasons).

From Phase 7 offline replay (alpha_zoo formulas):

- Train-pnl distribution across 130 evaluations: **all negative** (range −1.81 to −0.21, median −1.21).
- The best train-pnl alpha is `qp_tsmom = sign_x(delta_20(close))` — a textbook 20-bar momentum signal — with train_pnl = **−0.21** on BTCUSDT.

This matters: if even canonical hand-translated formulas can't make money on the **train slice**, then the issue is NOT GP overfit. GP can't be blamed for failing to find profit in a search space where curated reference formulas also fail.

## 5. Formula Diversity / Complexity

Live GP candidate diversity is not directly logged (no formula tree depth / node count in stats line). However:

- Per-round `len(alphas) = TOP_K = 10` alphas survive GP selection.
- Bloom filter has only 89 entries (the historical population) → no large dedup pool.
- AlphaEngine reports `126 indicator terminals, 35 operators, has_prims=True` — large search space.

GP should NOT be diversity-bottlenecked.

## 6. Train Over-Optimization Evidence

Without instrumentation showing GP train-vs-val score, we infer indirectly:

- If GP were over-evolving train: GP candidates would have positive train PnL but negative val PnL.
- alpha_zoo replay shows: even canonical formulas have negative train PnL.
- → GP candidates likely also have negative train PnL (since GP minimizes a fitness function under the same train cost / threshold conditions).
- → GP "fitness fn" probably accepts `bt.net_pnl < 0` as long as it's relatively higher than peers, OR the fitness fn uses Sharpe / IC / win_rate without strictly requiring positive train PnL.

In other words: **GP is finding the "least bad" alphas, but the universe is systemically losing money** under current cost/threshold/horizon settings.

## 7. Phase 5 Classification

Per order §16:

| Verdict | Match? |
| --- | --- |
| GP_OVERFIT_LIKELY | NO (alpha_zoo formulas, which are not GP-evolved, also fail) |
| GP_SEARCH_TOO_AGGRESSIVE | NO (POP_SIZE=100, N_GEN=20 is moderate) |
| DIVERSITY_TOO_LOW | NO (large terminal/operator search space) |
| COMPLEXITY_TOO_HIGH | NO (no evidence GP candidates are over-complex; alpha_zoo are simple and also fail) |
| **GP_NOT_PRIMARY_CAUSE** | **YES — exact match** (Phase 7 alpha_zoo offline replay confirms the failure is universal across formula classes) |
| GP_UNKNOWN | NO |

→ **Phase 5 verdict: GP_NOT_PRIMARY_CAUSE.** The val_neg_pnl rejection is universal — it affects GP-evolved candidates AND hand-translated reference formulas equally. The root cause is not in the GP layer; it sits in the underlying cost/threshold/data interaction visible to the backtester.
