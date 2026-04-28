# 01 — Grammar Inventory (read from source at HEAD `348eeb7`)

Inventory of the GP search space the engine is currently authorised to explore.
All numbers are pulled from `zangetsu/engine/components/alpha_engine.py` and
`zangetsu/engine/components/alpha_primitives.py`. Indicator catalog cross-checked
against `zangetsu/engine/components/indicator.py`.

## 1. OHLCV terminals (5)

`alpha_engine.py:298` — `OHLCV_ARGS = ("close", "high", "low", "open", "volume")`.
Bound to DEAP `pset` ARG0..ARG4. These are the *only* asset-level inputs.

## 2. Indicator terminals — full mode (default, 21 × 6 = 126)

`alpha_engine.py:289-296`

```python
INDICATOR_NAMES = [
    "rsi", "stochastic_k", "cci", "roc", "ppo", "cmo",
    "zscore", "trix", "tsi", "obv", "mfi", "vwap",
    "normalized_atr", "realized_vol", "bollinger_bw",
    "relative_volume", "vwap_deviation",
    "funding_rate", "funding_zscore", "oi_change", "oi_divergence",
]
PERIODS = [7, 14, 20, 30, 50, 100]
```

| Family | Terminals (per family × 6 periods) |
|---|---|
| Momentum / oscillator | rsi, stochastic_k, cci, roc, ppo, cmo, trix, tsi → 8 × 6 = 48 |
| Statistical | zscore → 1 × 6 = 6 |
| Volume | obv, mfi, vwap, relative_volume, vwap_deviation → 5 × 6 = 30 |
| Volatility | normalized_atr, realized_vol, bollinger_bw → 3 × 6 = 18 |
| Funding / OI | funding_rate, funding_zscore, oi_change, oi_divergence → 4 × 6 = 24 |
| **Total** | **126 indicator terminals** |

## 3. Indicator terminals — lean mode (`ZANGETSU_PSET_MODE=lean`, 12 × 4 = 48)

`pset_lean_config.py`. Drops `cci, ppo, cmo, trix, mfi, realized_vol,
funding_rate, oi_change, oi_divergence` and periods `7, 30`. Justified by
"all 1551 archive survivors used 0 indicator terminals" (CD-05 hygiene
note in the file header).

## 4. Operator inventory — what GP can compose (35 ops)

From `alpha_engine._build_primitive_set` (`alpha_engine.py:435-494`):

| Group | Operators | Arity | Count |
|---|---|---|---|
| Binary arithmetic | `add`, `sub`, `mul`, `protected_div` | 2 | 4 |
| Unary math | `neg`, `abs_x`, `sign_x`, `tanh_x` | 1 | 4 |
| Parametric power | `pow2`, `pow3`, `pow5` | 1 | 3 |
| Time-series (× 4 periods d ∈ {3,5,9,20}) | `delta_d`, `ts_max_d`, `ts_min_d`, `ts_rank_d`, `decay_d` | 1 | 5 × 4 = 20 |
| Pairwise corr (× 3 periods d ∈ {5,10,20}) | `correlation_d` | 2 | 3 |
| Normalization | `scale` | 1 | 1 |
| **Total** | | | **35** |

### Operators in `alpha_primitives.py` but **NOT** registered in pset

| Available in primitives | Status |
|---|---|
| `safe_divide` | not registered (alias of `protected_div`) |
| `log_x`, `exp_x` | **not registered** in GP pset |
| `signed_power(x, p)` | not registered (only fixed `pow2/3/5`) |
| `ts_argmax`, `ts_argmin` | **not registered** in GP pset |
| `ts_sum`, `ts_mean`, `ts_std` | **not registered** in GP pset |
| `covariance` | **not registered** in GP pset |
| `rolling_scale` | **not registered** in GP pset |
| `clip_range` | not registered |

That is **9 fully-implemented primitives the GP cannot reach today**, including
the entire suite of `ts_sum / ts_mean / ts_std` rolling statistics — strange
absence given they would form the backbone of any longer-horizon design.

## 5. AST shape constraints

`alpha_engine.py:323-324, 510-532`:

| Setting | Value |
|---|---|
| `MIN_DEPTH` | 2 |
| `MAX_DEPTH` | 6 |
| Initial depth (`expr` registered) | `genHalfAndHalf(min_=2, max_=4)` |
| Mutation expr | `genHalfAndHalf(min_=0, max_=2)` |
| Static depth limiter | applied to `mate` and `mutate` |
| Selection | `selTournament(tournsize=3)` |
| Crossover | `cxOnePoint`, `cxpb=0.5` |
| Mutation | `mutUniform`, `mutpb=0.2` |
| HOF size | `top_k = ALPHA_TOP_K` (default 10) |
| Pop / gen budget | `ALPHA_POP_SIZE × ALPHA_N_GEN` env-driven (defaults 100 × 20 = 2000 evals/(symbol,regime,lane,profile) per round) |

## 6. Forward-target pipeline

`alpha_engine._forward_returns` (`alpha_engine.py:633-643`):
- Reads `ALPHA_FORWARD_HORIZON` env, default **60 bars**, single value.
- No multi-horizon awareness — HE0/HE1 will introduce a tuple
  `(180, 240, 360)` per design spec.
- IC computed via Spearman against this single horizon.
- Fitness function is strategy-injected (`fitness_fn`) so the engine itself
  is horizon-agnostic; only `_forward_returns` is hard-tied.

## 7. Grammar identity hash

`provenance.compute_grammar_hash(operator_names, indicator_terminal_names)`
hashes `OPS:` ∪ `IND:` lexicographically. Therefore the *grammar identity*
is exactly:

- 35 operator names
- 126 indicator terminal names (or 48 in lean mode)
- 5 OHLCV argument names (implicit in `pset`)

Any add / remove / rename of these 161+5 names changes `grammar_hash` and
therefore changes `passport.engine_hash`. This is the right hook for a future
grammar expansion: the audit log will pick up the change automatically.

## 8. Search-space arithmetic (back-of-envelope ceiling)

A depth-6 binary AST has up to 2⁶ − 1 = 63 nodes. With 35 operators and
126+5 = 131 terminals, the *theoretical* tree count at depth ≤ 6 is on
the order of `131^32 × 35^31` — combinatorially enormous, but the relevant
question is the *useful* slice:

- IC > 0 candidates after 60-bar forward-return labelling
- net_pnl > cost (14.5 bps round-trip) on Binance Futures realistic execution

Per Phase-5 evidence (0-9X feature-space diagnosis), 4 454 distinct
formulas were generated by GP+LGBM in the live pipeline window — none
produced a deployable alpha. The combinatorial space is *not* the
binding constraint; the constraint is the lossy contract from
"OHLCV + 21 indicators × 6 periods × 35 ops at horizon 60" → "post-cost
edge". Section 03 enumerates which primitives are *missing* and why
adding horizons alone may not free the constraint.

## 9. What changes between full and lean mode

| Mode | Indicators | Periods | Indicator terminals | Total terminals (incl. OHLCV) |
|---|---|---|---|---|
| `full` (default) | 21 | 6 | 126 | 131 |
| `lean` (env opt-in) | 12 | 4 | 48 | 53 |

Lean mode does **not** alter the 35 operators, the depth bounds, or the
forward-return horizon. It is a pure terminal-pruning hygiene fix
motivated by historical "0 indicator usage" survivorship.
