# ZANGETSU Primitive Gap Analysis (2026-04-27)

## Status Summary

**Engine Configuration:**
- Total indicator terminals: 126 (21 indicators × 6 periods)
- Total operators registered: 35
- Total primitives in alpha_primitives.py: 28 distinct functions
- Startup log confirms: "126 indicator terminals, 35 operators, has_prims=True"

**Coverage Analysis:**
- Primitives PRESENT: 23/40 (58%)
- Primitives MISSING: 17/40 (42%)
- Critical gaps in cross-sectional ops, normalization, and auxiliary functions

---

## Registered Operators (35 total)

### Binary Arithmetic (4)
- ✅ add, sub, mul, protected_div (all available)

### Unary Math (4)
- ✅ neg, abs_x, sign_x, tanh_x (all available)

### Power Functions (3)
- ✅ pow2, pow3, pow5 (hardcoded, use prims.power internally)

### Time-Series Ops (20)
- ✅ delta_{3,5,9,20}, ts_max_{3,5,9,20}, ts_min_{3,5,9,20}, ts_rank_{3,5,9,20}, decay_{3,5,9,20}

### Pairwise (3)
- ✅ correlation_{5,10,20} (available, causal)

### Normalization (1)
- ✅ scale (full-series L1 normalize, available)

---

## Available in alpha_primitives.py but NOT REGISTERED (5)

| Primitive | Arity | Status | Reason |
|-----------|-------|--------|--------|
| log_x | 1 | AVAILABLE | Not registered to pset; no hardcoded wrapper. **Easy add.** |
| exp_x | 1 | AVAILABLE | Not registered to pset. **Easy add.** |
| signed_power | 2 | AVAILABLE | Not registered; power(2,3,5) cover common cases. Could be added for flexibility. |
| covariance | 2 | AVAILABLE | Not registered (only correlation_{5,10,20} are). **Medium add (cross-sectional risk).** |
| rolling_scale | 1 | AVAILABLE | Not registered (only scale is). **Easy add (rolling normalization).** |
| ts_mean | 1 | AVAILABLE | Implemented but not registered (rolling mean). **Easy add.** |
| ts_sum | 1 | AVAILABLE | Implemented but not registered (rolling sum). **Easy add.** |
| ts_std | 1 | AVAILABLE | Implemented but not registered (rolling volatility). **Easy add.** |
| ts_argmax, ts_argmin | 1 | AVAILABLE | Implemented but not registered. **Easy add (timing indicators).** |
| safe_divide | 2 | AVAILABLE | Alias for protected_div with explicit default. Not registered. |

**Total available but unregistered: 10**

---

## Known Missing Primitives (17)

### Cross-Sectional Rank (HIGH LEAKAGE RISK)
| Primitive | Complexity | Leakage | Causal | Crypto-Suitable | Notes |
|-----------|------------|---------|--------|-----------------|-------|
| **rank** | Hard | HIGH | Non-causal | No | Requires multi-symbol context, synchronous evaluation. Severely leaks future info in live trading. WorldQuant uses this; **DO NOT ADD**. |
| **group_rank** | Hard | HIGH | Non-causal | No | Sector/industry-relative rank. Same leakage risk. |

### Normalization (MEDIUM PRIORITY)
| Primitive | Complexity | Leakage | Causal | Crypto-Suitable | Notes |
|-----------|------------|---------|--------|-----------------|-------|
| **zscore** | Easy | Low | Causal | Yes | Z-score normalize: (x - mean) / std. Can be done rolling. Use ts_mean + ts_std wrapper. Consider **ADD** with rolling window. |
| **winsorize** | Medium | Low | Causal | Yes | Clip at percentiles (e.g., 5th/95th). Implementable via ts_min/ts_max on percentile ranks. Medium effort. |

### Mathematical (EASY TO ADD)
| Primitive | Complexity | Leakage | Causal | Crypto-Suitable | Notes |
|-----------|------------|---------|--------|-----------------|-------|
| **sqrt_x** | Easy | None | Causal | Yes | Safe positive sqrt; return 0 for NaN. Already in alpha_primitives (used internally). **Easy ADD.** |
| **identity** | Easy | None | Causal | Yes | Passthrough x. Normally not explicit in operators. |

### Time-Series Argument (EASY TO ADD)
| Primitive | Complexity | Leakage | Causal | Crypto-Suitable | Notes |
|-----------|------------|---------|--------|-----------------|-------|
| **ts_min / ts_max / ts_mean / ts_std** | Easy | None | Causal | Yes | All implemented in alpha_primitives; not registered. With periods {3,5,9,20} → 16 new operators. **ADD.** |
| **ts_argmax, ts_argmin** | Easy | None | Causal | Yes | Already in alpha_primitives. Returns normalized index ∈ [0,1]. **Easy ADD.** |

### Pairwise Statistical (MEDIUM PRIORITY)
| Primitive | Complexity | Leakage | Causal | Crypto-Suitable | Notes |
|-----------|------------|---------|--------|-----------------|-------|
| **covariance_N** | Medium | Medium | Causal | Yes | Already in alpha_primitives. Pairwise; would need periods {5,10,20}. Medium effort, medium causal risk if used on forward-looking pairs. |

### Advanced Univariate (MEDIUM TO HARD)
| Primitive | Complexity | Leakage | Causal | Crypto-Suitable | Notes |
|-----------|------------|---------|--------|-----------------|-------|
| **decay_linear_N** (custom weights) | Medium | None | Causal | Yes | Currently decay_{3,5,9,20} use linear. Custom weights or exp decay not exposed. Low priority. |
| **ternary / if-else** | Medium | None | Causal | Yes | `if cond > 0 then a else b`. Requires custom GP node type (not simple primitive). Implementable but non-trivial. Medium effort. |
| **indneutralize** | Hard | HIGH | Depends | No | Industry/sector neutralization. Requires multi-symbol, cross-sectional context. **DO NOT ADD** for crypto. |

### Advanced Math (RARELY USED)
| Primitive | Complexity | Leakage | Causal | Crypto-Suitable | Notes |
|-----------|------------|---------|--------|-----------------|-------|
| **log1p_x** | Easy | None | Causal | Yes | log(1 + |x|) * sign(x). Safer for near-zero x. Available in numpy; can wrap. Low priority. |
| **softmax** | Medium | None | Causal | Yes | Requires all inputs at once. Usually used for portfolio weights, not alpha expression directly. |

---

## Recommendations

### TIER 1: ADD IMMEDIATELY (Low Risk, High Value)

1. **log_x, exp_x** — Already implemented, just register to pset
   - Risk score: 0 (no new leakage, simple causal unary ops)
   - Expected impact: Enables log-space formulas common in ML alphas

2. **ts_mean_{3,5,9,20}, ts_sum_{3,5,9,20}, ts_std_{3,5,9,20}** — All implemented
   - Risk score: 0 (causal rolling univariate)
   - Expected impact: 12 new operators, unlock volatility-based signals

3. **ts_argmax_{d}, ts_argmin_{d}** (for d ∈ {3,5,9,20})
   - Risk score: 0 (timing indicator, causal)
   - Expected impact: 8 new operators, enables "when did the max/min occur"

4. **rolling_scale** — Implemented, causal
   - Risk score: 0
   - Expected impact: Rolling normalization, reduces GP bloat from nested scale calls

### TIER 2: ADD WITH CAUTION (Medium Risk, Medium Value)

5. **zscore** (rolling z-normalize) — Custom wrapper over ts_mean + ts_std
   - Risk score: 1 (low, but requires window size; default to d=20)
   - Implementation: `(x - ts_mean(x, d)) / (ts_std(x, d) + eps)`
   - Expected impact: Stabilizes indicator-space formulas

6. **covariance_{5,10,20}** — Already in alpha_primitives
   - Risk score: 2 (causal, but pairwise; could leak if applied to forward-look-ahead pairs)
   - Implementation: Register to pset, periods {5,10,20}
   - Expected impact: 3 operators, enables covariance-based diversification signals

### TIER 3: RESEARCH / DEFER (High Risk or Complex)

7. **ternary / if-else** — Requires custom GP primitives
   - Risk score: 5 (complex to implement in DEAP, but causal)
   - Implementation: Define custom gp.Primitive with 3 args; ~50 LOC
   - Expected impact: Conditional logic (e.g., bullish when RSI < 30)

8. **sqrt_x** — Already partially used internally (for std dev)
   - Risk score: 0 (causal, safe for positive x)
   - Implementation: Wrap np.sqrt, return 0 for x < 0
   - Expected impact: Low (pow can approximate via power(x, 0.5))

9. **winsorize** — Percentile clipping
   - Risk score: 1 (causal, but needs percentile computation)
   - Implementation: ~30 LOC using ts_rank (percentile = rank * 100)
   - Expected impact: Outlier suppression for robust signals

### TIER 4: DO NOT ADD (Leakage, Non-Causal, or Unsuitable)

10. **rank** (cross-sectional) — **BLOCK**
    - Leakage: CRITICAL (synchronous evaluation required; breaks causality in live trading)
    - Crypto-suitability: NO (rank-based alphas require synchronized universe)

11. **indneutralize** — **BLOCK**
    - Leakage: CRITICAL (cross-sectional, multi-symbol)
    - Crypto-suitability: NO (crypto has no standard industry/sector taxonomy)

12. **group_rank** — **BLOCK**
    - Reason: Same as rank + grouping introduces clustering leakage

---

## Implementation Effort Estimate

| Task | Estimate | Risk |
|------|----------|------|
| Add TIER 1 (log_x, exp_x, ts_mean/sum/std, ts_argmax/min, rolling_scale) | ~2 hours | LOW |
| Add TIER 2 (zscore wrapper, covariance_{5,10,20}) | ~1 hour | MEDIUM |
| Add TIER 3 (ternary, sqrt_x, winsorize) | ~4 hours | MEDIUM-HIGH |
| Audit + regression testing | ~2 hours | — |
| **Total estimated effort** | **~9 hours** | **LOW-MEDIUM** |

---

## Summary

**Missing primitives: 17 out of ~40 common WorldQuant-style operators**

**Actionable adds: 23 new operators (TIER 1+2) with low to medium risk**

**Hard blocks: rank, indneutralize, group_rank — do not add (leakage, crypto-unsuitable)**

**Engine is 58% feature-complete. TIER 1 adds alone (23 new operators) would bring coverage to ~75% without significant leakage risk.**
