# 06 — alpha_zoo Static Readiness

## 1. Tool

`zangetsu/scripts/alpha_zoo_injection.py` (129 lines).

## 2. CLI Flags

```python
parser.add_argument("--strategies", nargs="+", default=["j01", "j02"])
parser.add_argument("--symbols", nargs="+", default=None)
parser.add_argument("--limit-symbols", type=int, default=None)
parser.add_argument("--allow-dirty-tree", action="store_true", default=True)
parser.add_argument("--dry-run-one", action="store_true")
```

| Flag | Behavior |
| --- | --- |
| `--strategies` | run for j01 and/or j02 |
| `--symbols` | restrict symbol list |
| `--limit-symbols` | restrict to first N symbols |
| `--allow-dirty-tree` | allow git working tree to be dirty (default ON) |
| `--dry-run-one` | flag is parsed but **never referenced in the body of the script** — appears unimplemented |

→ **No effective dry-run flag.**

## 3. Default Behavior

Calls `cold_start_hand_alphas.run_for_strategy(strategy, args)` per strategy, which:

1. Opens an **asyncpg connection pool** (live DB writes possible).
2. Iterates `for formula in SEED_FORMULAS, for sym in symbols: await seed_one(db, ...)`.
3. `seed_one()` runs the same 5-stage val-filter chain as arena_pipeline (with an additional train_neg_pnl gate that arena_pipeline doesn't have).
4. If all gates pass, **INSERTs into `champion_pipeline_staging` with full provenance** (line 250-280 of cold_start_hand_alphas.py).
5. Then **`SELECT admission_validator(staging_id)`** to promote to fresh.

→ **Default behavior is LIVE WRITE** to staging + admission_validator. Not safe for read-only diagnosis.

## 4. Formula List

30 hand-translated formulas grouped by source:

| Group | Count | Source tags |
| --- | --- | --- |
| WorldQuant 101 | 7 | wq101_6, wq101_12, wq101_42, wq101_44, wq101_53, wq101_54, wq101_101 |
| Qlib Alpha158 (BigQuant) | 5 | qlib_kmid, qlib_rsv_5, qlib_rsv_20, qlib_roc_5, qlib_roc_20 |
| GuotaiJunan Alpha191 (JoinQuant) | 3 | alpha191_2, alpha191_5, alpha191_191 |
| Quantpedia momentum | 2 | qp_tsmom, qp_52wh |
| arXiv recent | 4 | cogalpha_v3, alphagen_dh20, alphaforge_ccv, alphaforge_af2 |
| WorldQuant BRAIN community | 3 | wqb_g24, wqb_g25, wqb_s01 |
| Indicator-based (ZANGETSU 126 terminals) | 6 | ind_rsi_rev, ind_rsi_ts_rank, ind_bbw_delta, ind_funding_rev, ind_vwap_dev, ind_stoch_k |

## 5. Primitive Compatibility

All formulas use only:

- ZANGETSU's 126 indicator terminals (rsi_14, vwap_20, stochastic_k_14, bollinger_bw_20, funding_zscore_20, etc.)
- Subset of 35 operators (sub, add, mul, neg, sign_x, protected_div, scale, ts_max_3, ts_min_5, correlation_5, ts_rank_5, delta_3, pow5, tanh_x, etc.)
- 5 OHLCV terminals (open, high, low, close, volume)

The docstring confirms: untranslatable WQ101 alphas (rank, indneutralize, ternary, bare-constants) were already filtered out.

## 6. fitness_version Tagging

Per docstring: `alpha_zoo.{wq101|qlib|alpha191|quantpedia|arxiv|wqbrain|indicators}.v1`. But the runtime body of `alpha_zoo_injection.py` line 102 simplifies: it sets `css.SEED_FORMULAS = [f for f, _ in ZOO]` and lets `run_for_strategy` tag uniformly. Per-formula source tag is captured in the comment but NOT carried through to fitness_version. (This is a minor governance/audit concern but does not affect this order.)

## 7. Validation Bypass Risk

| Check | Result |
| --- | --- |
| Bypasses 9-stage val-filter chain | NO (cold_start uses essentially the same chain plus stricter train_neg_pnl) |
| Sets `zangetsu.admission_active='true'` | NO (never sets server-side; relies on `admission_validator()` to set it locally) |
| Writes directly to `champion_pipeline_fresh` | NO (writes to staging only; admission_validator promotes) |
| Inserts fake / synthetic rows | NO (real backtest results) |

→ **The tool is governance-compliant** for staging writes — it goes through the same path as A1 and respects all val gates.

## 8. Phase 6 Classification

Per order §16:

| Verdict | Match? |
| --- | --- |
| **ZOO_STATIC_READY_FOR_OFFLINE_REPLAY** | **YES** (the eval helpers `compile_formula`, `evaluate_and_backtest`, `load_symbol_data`, `build_indicator_cache` are importable and reusable in a separate offline script) |
| ZOO_HAS_SAFE_DRY_RUN | NO (`--dry-run-one` flag exists but is unimplemented in body) |
| ZOO_STAGING_WRITE_ONLY | YES (default behavior; not bypassing fresh) |
| ZOO_FRESH_DIRECT_WRITE_UNSAFE | NO |
| ZOO_BYPASSES_VALIDATION_UNSAFE | NO |
| ZOO_REQUIRES_REFACTOR_BEFORE_USE | partial — for SAFE production cold-start a `--dry-run` flag would be a nice-to-have, but for offline replay the eval helpers are already separately importable |
| ZOO_UNKNOWN | NO |

→ **Phase 6 verdict: ZOO_STATIC_READY_FOR_OFFLINE_REPLAY.** Tool itself is governance-compliant for live cold-start (writes to staging, no validation bypass). For this read-only order, we replicate the val-eval chain in a fresh /tmp/ script that does not open a DB connection (Phase 7).
