# 10 — Formula Universe Deep Inventory (Track K)

## 1. Source Inventory

| Source | Path | Lines | Est. formulas |
| --- | --- | --- | --- |
| **arXiv recent papers** | `~/strategic-research/alpha_zoo/arxiv/alphas.md` | 291 | ~15-20 |
| **BigQuant / Qlib Alpha158** | `~/strategic-research/alpha_zoo/bigquant/alphas.md` | 339 | ~30-40 |
| **JoinQuant / Alpha191 (Guotai Junan)** | `~/strategic-research/alpha_zoo/joinquant/alphas.md` | **1393** | ~120-150 |
| **Quantpedia** | `~/strategic-research/alpha_zoo/quantpedia/alphas.md` | 166 | ~5-10 |
| **SSRN papers** | `~/strategic-research/alpha_zoo/ssrn/alphas.md` | 165 | ~10-15 |
| **TQuant Lab / TEJ Taiwan** | `~/strategic-research/alpha_zoo/tquantlab/alphas.md` | 171 | ~15-20 (Taiwan-specific) |
| **WorldQuant BRAIN** | `~/strategic-research/alpha_zoo/wq_brain/alphas.md` | 390 | ~30-40 |
| **WorldQuant 101 (Kakushadze 2015)** | `~/strategic-research/worldquant_101/alphas_raw.md` | 235 | **101** |
| **WQ→Zangetsu translatability matrix** | `~/strategic-research/worldquant_101/translatability_to_zangetsu.md` | 103 | (audit doc) |
| **Currently in alpha_zoo_injection.py ZOO list** | `zangetsu/scripts/alpha_zoo_injection.py` | 30 | **30** (hand-translated, deployed) |
| **seed_101_alphas_batch2.py** (DEPRECATED guard) | `zangetsu/services/seed_101_alphas_batch2.py` | n/a | n/a (DEPRECATED_BLOCKED) |

**Total raw collected: ~360-450 alpha formulas across 8 source bodies + 30 already hand-translated for Zangetsu.**

## 2. Family Taxonomy

Per `alpha_zoo_injection.py` ZOO list (30 production-ready formulas):

| Family | Count | Examples |
| --- | --- | --- |
| **trend / momentum** | 8 | `sign_x(delta_20(close))` (`qp_tsmom`), `delta_20(high)` (`alphagen_dh20`), `neg(delta_5(close))` (`wqb_g24`) |
| **mean reversion** | 7 | `neg(sub(close, scale(close)))` (`wqb_s01`), `protected_div(sub(vwap_20, close), add(vwap_20, close))` (`wq101_42`), `neg(scale(rsi_14))` (`ind_rsi_rev`) |
| **volume × price interaction** | 6 | `neg(correlation_10(open, volume))` (`wq101_6`), `correlation_10(close, volume)` (`alphaforge_ccv`), `correlation_5(ts_rank_5(volume), ts_rank_5(low))` (`alpha191_191`) |
| **volatility / range** | 4 | `delta_20(bollinger_bw_20)` (`ind_bbw_delta`), `tanh_x(protected_div(sub(high, close), mul(close, volume)))` (`cogalpha_v3`) |
| **liquidity / VWAP** | 3 | `vwap_deviation_20` (`ind_vwap_dev`) |
| **funding-based** (Crypto-specific) | 1 | `neg(funding_zscore_20)` (`ind_funding_rev`) |
| **price-action raw** | 1 | `protected_div(sub(close, open), sub(high, low))` (`wq101_101`) |

→ **Trend + mean-reversion dominate.** Volume × price is healthy (6). Volatility is light (4). Funding-based is novel-crypto (1) — under-explored. Liquidity/VWAP is light.

## 3. Translatability Classification (per WQ101 reference)

From `~/strategic-research/worldquant_101/translatability_to_zangetsu.md`:

| Category | Notes |
| --- | --- |
| ✅ Direct Zangetsu equivalent | rank period operators, basic arithmetic, power 2/3/5, abs, sign |
| ⚠️ Approximation needed | `rank()` (cross-sectional) → `ts_rank_20()`; `delay()` → `x − delta_N(x)`; `decay_linear()` → `decay_N()` (verify weighting) |
| ❌ Untranslatable | `indneutralize()`, `cap`, `IndClass`, ternary `?:`, comparison operators, bare numeric constants |

**Estimate**: ~60% of WQ101 (≈60 of 101) directly or approximately translatable to Zangetsu primitives. Remaining ~40% blocked by missing primitives (cross-sectional rank, ternary, signedpower with arbitrary exponents, indneutralize) — see Track L primitive gap analysis.

## 4. Cross-Source Duplicate Estimate

Hand-spot-check across sources:
- WQ101 #6, #12, #42, #44, #53, #54, #101 ARE in current ZOO (7 formulas)
- Qlib's `roc_5/roc_20` ≈ WQ-style returns; ZOO has both
- Alpha191's #5 (ts_max_3 + correlation_5) is the same momentum-pattern as WQ101 #44
- Quantpedia tsmom is the same as WQ-classic time-series momentum

Net duplicate rate: **~15-20% across 8 sources**. After dedup, the **unique exploitable universe is ~280-360 formulas** (vs the raw ~360-450 collected).

## 5. Tier Classification

### Tier 1 — High Confidence (multi-source confirmed, crypto-tested, in current ZOO)
Already in `alpha_zoo_injection.py`. **30 formulas.**
- 7 from WQ101
- 5 from Qlib (Alpha158)
- 3 from Alpha191
- 2 from Quantpedia
- 4 from arXiv recent
- 3 from WQ Brain
- 6 indicator-based novel

### Tier 2 — Translatable but Unproven on 1-min Crypto
Estimate: **~80-100 additional formulas** can be hand-translated:
- Remaining WQ101 directly-translatable (~30)
- Alpha191 high-IC subset (~40)
- Qlib Alpha360 momentum subset (~15)
- Quantpedia trend strategies (~5)

Path: extend `alpha_zoo_injection.py` ZOO list once cold-start governance is unblocked (Track A applied + Tracks D/E merged).

### Tier 3 — Requires Primitive Expansion (blocked by Track L)
Estimate: **~150-200 formulas** require missing primitives:
- Cross-sectional rank (universe-wide) — Zangetsu is single-symbol
- Ternary / conditional operators
- Arbitrary exponent `signedpower(x, a)` — current limit `pow{2,3,5}`
- Industry neutralization (irrelevant for crypto)
- True `delay(x, d)` (currently approximated as `x - delta_N(x)`)

Recommendation per Track L: Expand selectively, not wholesale. Cross-sectional rank is HIGH-VALUE (would unlock ~70 WQ-style formulas), but architectural cost is significant.

## 6. Recommendation for Future Cold-Start

| Tier | Count | Action |
| --- | --- | --- |
| Tier 1 | 30 | Already in ZOO; priority for first cold-start (post-Track A) |
| Tier 2 | ~80-100 | Hand-translate as a separate research order; expand ZOO under governance |
| Tier 3 | ~150-200 | Defer until primitive expansion order completes |

**Current ZOO coverage of robustly-deployable formulas: 30 / ~280 = 11% of the unique universe.**

## 7. Forbidden Operations Honored

- NO injection performed in this audit
- NO deprecated seed execution
- NO DB writes
- All file inspections via `ssh + ls/wc/head/grep` — read-only
