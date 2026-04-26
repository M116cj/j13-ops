# 03 — A1 Generation Parameter Audit

## 1. GP Hyperparameters (arena_pipeline.py:751-757)

| Parameter | Current value | Source | Env override | Last changed |
| --- | --- | --- | --- | --- |
| `N_GEN` | 20 | line 751 | `ALPHA_N_GEN` (not set) | unknown — predates VERSION_LOG |
| `POP_SIZE` | 100 | line 752 | `ALPHA_POP_SIZE` (not set) | unknown |
| `TOP_K` | 10 | line 753 | `ALPHA_TOP_K` (not set) | unknown |
| `ENTRY_THR` | 0.80 | line 754 | `ALPHA_ENTRY_THR` (not set) | inherited from earlier zangetsu |
| `EXIT_THR` | 0.50 | line 755 | `ALPHA_EXIT_THR` (not set) | inherited |
| `MIN_HOLD` | 60 | line 756 | `ALPHA_MIN_HOLD` (not set) | inherited |
| `COOLDOWN` | 60 | line 757 | `ALPHA_COOLDOWN` (not set) | inherited |

## 2. Mutation / Crossover / Selection (deferred to AlphaEngine internals)

`zangetsu/engine/components/alpha_engine.py` orchestrates GP. The CLI-level audit shows arena_pipeline passes only `n_gen, pop_size, top_k` plus a generation-profile fingerprint; mutation/crossover/selection rates are GP defaults inside `AlphaEngine`. **No env override path observed for these.**

## 3. Random Seed Behavior

`A1_WORKER_SEED` env knob is read at line `_pb = _get_or_build_provenance(engine, worker_id, int(os.environ.get("A1_WORKER_SEED", str(worker_id))))` — fallback is `worker_id` (0-3). Seed is deterministic per worker but not globally fixed across runs.

## 4. Formula Constraints

| Constraint | Source | Value |
| --- | --- | --- |
| Indicator universe | engine output: `AlphaEngine ready: 126 indicator terminals, 35 operators` | 126 indicators × 35 operators |
| Symbol universe | data_cache loaded by A1 | 14 symbols (3 tiers: Stable 6 + Diversified 5 + High-Vol 3) |
| Regime universe | `arena13_feedback` reports regime_boosts for at least: `BULL_TREND`, `CONSOLIDATION` | observed in batch_id `R50384-XRPUSDT-CONSOLIDATION` |
| Duplicate suppression | bloom filter via `_bloom_key` + `rbloom_add` | enabled |
| Complexity penalty | applied via fitness function (j01.fitness or j02.fitness) | enabled (HEIGHT_PENALTY=1e-3) |

## 5. Train / Validation Objective

| Objective | Source |
| --- | --- |
| Train: fitness function (j01/j02) — IC over 100-bar segments + complexity penalty | `j01/fitness.py`, `j01/config/thresholds.py` |
| Validation: backtest on 30% holdout slice — net_pnl + sharpe + wilson_wr gates | `arena_pipeline.py:980-1050` |

## 6. Per-Round Activity (current observed)

```
batch_id: R50384-XRPUSDT-CONSOLIDATION
entered: 10
rejected: 18670
pass_rate: 0.0
```

→ N_GEN × POP_SIZE = 20 × 100 = 2000 candidates per generation per round. Multiple rounds compounded over the batch produce ~18.7k rejection events. **Generation budget is not the constraint — rejection is at the fitness/early-stage step, not the val gate.**

## 7. Reject-Reason Drift From Prior Orders

| Reject category | Prior orders' observation | Current observation |
| --- | --- | --- |
| `val_neg_pnl` | dominant (~99%) per PR #38 | not visible in current batch metrics (reaches 0 candidates) |
| `COUNTER_INCONSISTENCY` | not in prior taxonomy | **9330 / 18670 = 50%** |
| `COST_NEGATIVE` | not in prior taxonomy | **9319 / 18670 = 50%** |
| `SIGNAL_TOO_SPARSE` | minor | 20 / 18670 = 0.1% |
| `INVALID_FORMULA` | minor | 1 / 18670 |

`COUNTER_INCONSISTENCY` is raised at `arena_pipeline.py:230` (`acc.reject_counter.add("COUNTER_INCONSISTENCY", abs(residual))`) — this is a fitness-level numerical check, BEFORE val backtest. Same for `COST_NEGATIVE`. So the previous 4 orders' diagnosis (cost calibration, val_filter, threshold) was investigating a downstream gate that current candidates **do not even reach**.

## 8. Classification

| Verdict | Match? |
| --- | --- |
| A1_GENERATION_PARAMS_OK | partial — values intact, but reject distribution shifted |
| A1_GENERATION_TOO_AGGRESSIVE | NO (20×100×rounds = ~18k/batch is reasonable) |
| A1_GENERATION_TOO_NARROW | NO (126 indicators × 35 operators is wide) |
| **A1_GENERATION_UNDOCUMENTED** | **YES** — `COUNTER_INCONSISTENCY` and `COST_NEGATIVE` reject categories are not documented in prior governance orders or VERSION_LOG |
| A1_GENERATION_CONFLICT | NO |

→ **Phase 3 verdict: A1_GENERATION_PARAMS_OK + A1_GENERATION_UNDOCUMENTED.** All numeric parameters match prior governance. But the **rejection taxonomy actively in use** has drifted from what prior orders documented — this represents an undocumented behavioral change in alpha generation that requires further audit before any cold-start work.
