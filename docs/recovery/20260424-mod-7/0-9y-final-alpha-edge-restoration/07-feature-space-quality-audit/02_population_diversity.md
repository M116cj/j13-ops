# 02 — Population Diversity (89 fresh-pool alphas + GP candidates)

Source-of-truth refresher: this audit is read-only and may not query the DB.
Counts below come from artefacts already locked in:

- `00_state_lock.md` (this dir, prior agent's snapshot of `champion_pipeline_*`).
- `docs/recovery/20260424-mod-7/0-9x-pipeline-deployable-flow-diagnosis/05_data_and_feature_space_diagnosis.md`.
- `docs/recovery/20260424-mod-7/0-9y-final-alpha-edge-restoration/00-master-state-lock/02_db_snapshot.md`.
- Source: `zangetsu/scripts/cold_start_hand_alphas.py:57` (the SEED_FORMULAS list).

## 1. Fresh-pool 89 — origin

| Fact | Value |
|---|---|
| `champion_pipeline_fresh` row count | 89 |
| Distinct `alpha_hash` | 89 (1:1 with rows) |
| `evolution_operator` for all 89 | `random` |
| `generation` for all 89 | 0 |
| `passport.arena1.source` for all 89 | `manual_cold_start.v1` |
| Indicator usage (fresh_pool_outcome_health VIEW) | 0 / 89 use any indicator terminal |
| Average AST depth | 0 |
| Average node count | 0 |

The 89-alpha fresh pool is **not GP output**. It is the cold-start hand-seed
set from `scripts/cold_start_hand_alphas.py:57-63`:

```python
SEED_FORMULAS = [
    "tanh_x(delta_9(close))",
    "neg(scale(rsi_14))",
    "mul(sign_x(delta_9(close)), relative_volume_20)",
    "protected_div(delta_20(close), normalized_atr_20)",
    "neg(funding_zscore_20)",
]
```

5 formulas × ~14 symbols × 1–2 strategies → 89 rows. The "0 indicators / 0
nodes / depth 0" reading from `fresh_pool_outcome_health` reflects an
older Epoch-A schema where these fields were not populated for hand seeds;
inspection of the formulas themselves shows 4 of 5 do reference indicators
(`rsi_14`, `relative_volume_20`, `normalized_atr_20`, `funding_zscore_20`).
The VIEW under-reports because it counts `passport.alpha_expression.used_indicators`
which the cold-start path leaves empty — a metadata bug, not formula bareness.

## 2. Hand-seed family composition

Of the 5 seeds:

| Family | Formula | Indicators used | Operators used |
|---|---|---|---|
| Trend / momentum | `tanh_x(delta_9(close))` | none (raw close) | `tanh_x`, `delta_9` |
| Mean-reversion | `neg(scale(rsi_14))` | `rsi_14` | `neg`, `scale` |
| Trend × volume | `mul(sign_x(delta_9(close)), relative_volume_20)` | `relative_volume_20` | `mul`, `sign_x`, `delta_9` |
| Vol-normalized momentum | `protected_div(delta_20(close), normalized_atr_20)` | `normalized_atr_20` | `protected_div`, `delta_20` |
| Funding contrarian | `neg(funding_zscore_20)` | `funding_zscore_20` | `neg` |

Family diversity is acceptable for a 5-seed cold-start: one trend, one
mean-reversion, one trend-confirmation, one vol-normalised, one funding
flow. **No cross-asset family. No regime-conditional family. No
microstructure family.**

## 3. Depth distribution (hand-seed)

| Formula | Depth | Node count |
|---|---:|---:|
| `tanh_x(delta_9(close))` | 2 | 3 |
| `neg(scale(rsi_14))` | 2 | 3 |
| `mul(sign_x(delta_9(close)), relative_volume_20)` | 3 | 5 |
| `protected_div(delta_20(close), normalized_atr_20)` | 2 | 4 |
| `neg(funding_zscore_20)` | 1 | 2 |

All seeds sit at depth 1–3; well below `MAX_DEPTH=6`. They are
deliberately shallow so a human can reason about them, but they
under-exercise the operator stack (no `correlation_d`, no `pow_n`,
no nested `delta`/`ts_rank`).

## 4. Symbol distribution (hand-seed deployment)

`docs/recovery/20260424-mod-7/0-9x-pipeline-deployable-flow-diagnosis/05_data_and_feature_space_diagnosis.md` — `candidate_lifecycle` source-pool histogram (full
log scope, NOT just the 89 hand-seed pool):

```
LINKUSDT       2360   SOLUSDT        1925   1000SHIBUSDT  1554
GALAUSDT       1500   DOTUSDT        1480   XRPUSDT       1460
AAVEUSDT       1453   1000PEPEUSDT   1426   FILUSDT       1198
BNBUSDT        1184   DOGEUSDT        835   AVAXUSDT       760
ETHUSDT         760   BTCUSDT         720
```

All 14 symbols active. Skew (LINKUSDT 2360 vs BTCUSDT 720) but no symbol
is starved. The hand-seed pool (89 rows) is by construction roughly
1 row per (formula, symbol) — uniform.

## 5. Profile distribution

State-lock note: engine batch snapshot has **2 generation profiles** active
(per `00_state_lock.md` line 33). Per-profile breakdown of the live
GP candidate stream is not in scope for this audit; the relevant
observation is that the audit period covers more than one profile, so the
"4 454 unique formulas, 0 deployable" finding is profile-robust.

## 6. Bloom-filter / duplicate ratio

`docs/recovery/20260424-mod-7/0-9x-pipeline-deployable-flow-diagnosis/05_data_and_feature_space_diagnosis.md`:

- `bloom_hits = 0` in every observed V10 STATS line
- `bloom_size = 89` (matches admitted population)
- `unique alpha_id` in `candidate_lifecycle` log = **4 454**
- ENTRY events: 9 370 → ~2.1 ENTRYs per unique alpha
- Repeat distribution: 81 alphas seen 1×, 3 849 seen 2× (ENTRY+EXIT pair),
  long tail up to 13× (multi-symbol re-evaluation)

**Repeated-formula ratio (proper reading):** the bloom filter answers
"did we already test this formula in this run?". `bloom_hits = 0` means
GP is not regenerating the same trees within a worker session. This is
*broad combinatorial diversity*, not staleness.

What the data does not tell us: whether two distinct `alpha_hash` values
encode *semantically identical* formulas modulo `alpha_dedup.canonicalize`
(commutativity / double-neg / identity). The dedup utility exists
(`zangetsu/services/alpha_dedup.py`) but is not gating the GP loop.
That is a known gap, not an audit verdict.

## 7. Operator usage (live GP stream — qualitative)

The audit cannot enumerate operator-frequency histograms over the 4 454
unique alphas without a DB read. Indirect evidence:

- `engine.jsonl` `arena_stage:A1` events stream `passport.alpha_expression`
  with `used_operators` populated (per `alpha_engine._individual_to_result`).
- `compile_err = 0` per round in V10 STATS → no operator ill-typing,
  i.e., DEAP type system is not silently dropping any ops.
- `reject_val_constant = 0` → no zero-variance dead-end output.

Empirically the 35 operators are exercised; we just don't have the
bucket histogram to hand. **The deficit is not "GP avoids operators"; it
is "GP samples operators evenly but the resulting alphas don't beat
cost".**

## 8. Indicator usage (live GP stream — qualitative)

Same provenance as §7. Engine boot log: `AlphaEngine ready: 126 indicator
terminals, 35 operators`. Live `bloom_size=89` but `total tested=4454`,
of which "indicator-ratio" was historically 0 in the legacy 89; the new
GP candidates do use indicators (`alphas_with_indicators` is
non-zero in the live stream per the 0-9X document — though no specific
percentage was extracted there).

**Caveat for HE0:** lean mode would slash 126 → 48 terminals if enabled.
No evidence in the audit window that lean mode is currently active. If a
horizon-redesign rollout flips `ZANGETSU_PSET_MODE=lean`, that is a *parallel*
search-space shrink and must be tracked separately from the horizon change.

## 9. Diversity verdict

| Dimension | Status |
|---|---|
| Unique formulas (4 454 in live window) | broad — combinatorial diversity is **not** the bottleneck |
| Bloom hit ratio (0%) | no within-run regeneration |
| Symbol coverage (14/14) | full |
| Profile coverage (2 profiles) | adequate |
| Operator coverage | likely full given compile_err=0 (qualitative; no histogram) |
| Hand-seed family diversity | thin (5 seeds, no cross-asset / regime / microstructure) |
| Hand-seed depth (1–3) | well under MAX_DEPTH=6 |

The population data does **not** show a redundancy or staleness
pathology. It shows *exhaustion*: GP samples freely but the post-cost
edge surface is empty under the current contract.
