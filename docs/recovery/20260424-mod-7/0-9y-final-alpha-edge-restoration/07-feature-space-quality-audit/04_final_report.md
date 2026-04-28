# 04 — Final Report (Phase 7 · Feature-Space Quality Audit)

**Master Order:** 0-9Y-FINAL-ZANGETSU-ALPHA-EDGE-RESTORATION-PROGRAM
**Sub-order:** TEAM ORDER 0-9Y-FS1-FEATURE-SPACE-QUALITY-AUDIT
**Phase:** 7
**HEAD:** `348eeb7fd14a06f5a41cc75e3c5a872f7b91dbe3`
**Mode:** READ-ONLY (no source / DB / alpha_zoo / CANARY / production touched)

## Final verdict

```
FEATURE_SPACE_TOO_REDUNDANT_NEEDS_OPERATOR_EXPANSION
```

The five-option verdict set in the order is interpreted strictly. The audit
chose this label for the following reasons:

- **Not `FEATURE_SPACE_ACCEPTABLE_FOR_HORIZON_TEST`.** `alpha_primitives.py`
  ships fully-implemented operators (`ts_sum`, `ts_mean`, `ts_std`,
  `ts_argmax`, `ts_argmin`, `covariance`, `rolling_scale`, `log_x`,
  `exp_x`, `clip_range`, `signed_power`) that are **not registered** in
  the GP pset. At horizon 180/240/360 the natural feature vocabulary
  (rolling mean / std / z, recency-of-extreme, log-return) becomes
  important; today the GP must approximate those via deep compositions.
  Sending HE1/HE2/HE3 horizon redesign onto this grammar means asking
  the engine to also rediscover basic rolling stats — a known dead-end.
- **Not `FEATURE_SPACE_NEEDS_CROSS_ASSET_FEATURES`** (primary).
  Cross-asset is a strict requirement *eventually* (BTC-led alt regimes
  dominate 3–6h horizons), but adding it changes the data pipeline,
  the per-symbol cache assumption, and the GP terminal class. That is
  too big a swing for a horizon-test order. Recommended for the
  follow-up program after HE5.
- **Not `FEATURE_SPACE_NEEDS_REGIME_FEATURES`** (primary).
  Regime conditioning is also a real gap (`market_state.py` produces 13
  regimes but the GP cannot branch on them), but again is more invasive
  than horizon redesign warrants. Tracked as a separate workstream.
- **Not `FEATURE_SPACE_NEEDS_MICROSTRUCTURE`.** True at the strategic
  level (no book / tick data) and consistent with AKASHA carry-forward
  ("scope new data pipeline for order-book snapshots…"), but not the
  *binding* gate for HE0–HE5 either.

The chosen label `FEATURE_SPACE_TOO_REDUNDANT_NEEDS_OPERATOR_EXPANSION`
captures the smallest blocking gap: the operator vocabulary visible to
GP is a redundant subset (35 ops, half of which are sign / pow / abs
variants) of a richer primitive library that already exists in source.
Fixing this is a one-day grammar PR, not a multi-week infra change.

## Headline numbers

| Metric | Value |
|---|---:|
| Indicator terminals wired to GP | **126** (21 indicators × 6 periods) |
| Indicators declared in `indicator.py` taxonomy but not wired | ~130 (cross_asset 11, volume_micro 14, multi_timeframe 6, statistical 7, price_action 16, much of trend / volatility / volume_base) |
| GP operators registered | **35** |
| Operators implemented in `alpha_primitives.py` but **not** registered in pset | **9** (`ts_sum`, `ts_mean`, `ts_std`, `ts_argmax`, `ts_argmin`, `covariance`, `rolling_scale`, `log_x`, `exp_x`; plus `clip_range`, `signed_power`, `safe_divide` which are arguably aliases) |
| MAX_DEPTH | 6 |
| Default A1 budget per (symbol, regime, lane) round | POP_SIZE × N_GEN = 100 × 20 = 2 000 evals |
| Unique formulas in live `candidate_lifecycle` window (Phase-5 evidence) | **4 454** |
| `bloom_hits` per round | **0** (no within-run formula recycling) |
| Fresh-pool 89 alphas | hand-seeded cold-start (`SEED_FORMULAS` × symbols), not GP output |
| Deployable (j01) | **0** (per master state lock and §17.3 Calcifer block) |

## Top 5 wired operators (by frequency in hand-seed set; live histogram unavailable)

(Hand-seed sample is the only set inspectable without a DB query; live
GP frequency would require an `engine.jsonl` aggregation that is not
in scope here. Listed in order of seed appearances.)

1. `delta_d` (3 of 5 seeds — `delta_9`, `delta_20`)
2. `neg` (2 of 5)
3. `tanh_x`, `scale`, `sign_x`, `mul`, `protected_div` — each in 1 seed

Live GP exercises all 35 operators (compile_err = 0) but the histogram
shape is unknown to this audit.

## Top 5 wired indicators (by hand-seed appearances)

1. `relative_volume_20`
2. `normalized_atr_20`
3. `rsi_14`
4. `funding_zscore_20`
5. (`delta_9(close)` raw — no indicator)

Live GP indicator-frequency histogram is also unknown without DB query.

## Key missing primitives (highest-leverage gaps)

The full enumeration is in `03_missing_primitives_review.md`. Highest
leverage for the upcoming horizon redesign:

1. **`ts_mean_d`, `ts_std_d`, `ts_sum_d` for d ∈ {20, 60, 240}** — already
   implemented; pset registration is 4 lines per item. Without these the
   GP cannot construct moving averages, rolling vol, or rolling z-scores
   in a single AST node. Required for any longer-horizon classical alpha.
2. **`log_x`** — already implemented; pset registration 1 line. Required
   to express log-returns naturally.
3. **`ts_argmax_d`, `ts_argmin_d`** — already implemented; pset
   registration 2 lines per d. Required for "bars-since-last-high" trend
   features at long horizons.
4. **Multi-timeframe terminals** (`mtf_rsi_240`, `mtf_atr_240`, etc.) —
   the rust indicator engine already ships `multi_timeframe.rs` (4h MTF
   RSI from 1m); python pset doesn't surface them. ~30 lines of glue.
5. (Strategic, NOT for HE0–HE5) cross-asset terminals (`btc_close`,
   `pair_corr_d(this, BTC)`), regime-conditional gates, microstructure
   terminals from a future book-snapshot pipeline.

## Recommendation for the next future order

**Horizon-only redesign is INSUFFICIENT.** Recommend pre-pending a small
grammar-expansion order before HE1:

> **TEAM ORDER 0-9Y-GE0-GRAMMAR-MIN-EXPANSION-FOR-HORIZON-REDESIGN**
> *Scope:* register the 9 already-implemented but unwired primitives
> (`ts_sum`, `ts_mean`, `ts_std`, `ts_argmax`, `ts_argmin`, `covariance`,
> `rolling_scale`, `log_x`, `exp_x`) into the pset for periods
> {20, 60, 240}. Update `pset_lean_config.py` accordingly. Bump
> `grammar_hash` (provenance auto-tracks). No schema / cost / threshold
> changes. ~150 LOC, single-file PR.
> *Acceptance:* `AlphaEngine` boot log shows operator count ≥ 50;
> `passport.alpha_expression.used_operators` field starts emitting the
> new operator names; `compile_err` remains 0.

Sequence:

1. **GE0** (proposed, ~1 day) — operator expansion described above.
2. **HE1** (existing roadmap) — multi-horizon `_forward_returns(close, horizon)` + `candidate_id` introduction.
3. **HE2** (existing) — orchestrator round-robin over `ACTIVE_A1_HORIZONS`.
4. **HE3** (existing) — per-horizon telemetry plumbing.
5. **HE5** (existing) — analyse per-horizon × per-operator outcome.

If the GE0 step is skipped, HE1–HE5 will produce a per-horizon outcome
table where the comparison is contaminated: every horizon is searched
under the same operator-poor grammar, so a "horizon X is best" finding
might just mean "horizon X happens to be the one where depth-6
compositions accidentally approximate `ts_mean_d` first".

## Adversarial caveats (Q1 dimension scan)

1. **Input boundary.** The audit input set is read-only artefacts and
   source files at HEAD `348eeb7`. No DB query, so live operator/
   indicator histograms are unverified. Mitigation: §7/§8 of
   `02_population_diversity.md` flag this as qualitative, not
   quantitative.
2. **Silent failure.** Possible silent failure: prior `00_state_lock.md`
   was written by an earlier subagent run; counts (89 / 184 / 0
   deployable) cross-verified against `0-9y/00-master-state-lock/02_db_snapshot.md`. ✓
3. **External dependency.** None — read-only filesystem inspection.
4. **Concurrency / race.** N/A (offline analysis).
5. **Scope creep.** Audit limited to grammar / primitive / population
   inspection. Did not propose horizon implementation, did not modify
   any code.

## Compliance attestation

- No source / config / engine code modified. ✓
- No DB write. ✓
- No alpha_zoo invocation. ✓
- No CANARY / production touched. ✓
- Read-only file outputs only (5 files in this directory). ✓
- No commit. ✓

## Q1 / Q2 / Q3

- **Q1 Adversarial:** PASS (5 dimensions documented above with
  mitigations).
- **Q2 Structural integrity:** PASS — verdict cross-verifiable from
  `alpha_engine._build_primitive_set` source against `alpha_primitives`
  source; reviewer can grep both and reproduce the missing-primitive
  list in 5 minutes.
- **Q3 Execution efficiency:** PASS — 5 files, ~480 lines total of
  deliverables, no superfluous reproduction of evidence already locked
  in earlier phase docs.
