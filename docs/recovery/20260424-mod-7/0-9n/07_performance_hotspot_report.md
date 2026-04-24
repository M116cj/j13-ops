# 07 — Performance Hotspot Report

TEAM ORDER 0-9N §9.6 deliverable.

## 1. Scope

Identify **safe** performance optimization opportunities that **do not alter strategy semantics**. Hard boundary: no change to pass/fail predicates, thresholds, alpha generation operators, or Arena decision logic.

## 2. Current arena_pipeline.py per-candidate cost breakdown (estimated)

Per-alpha evaluation in `arena_pipeline.py` (observed from code inspection):

| Step | Est. cost | Cache state |
|---|---|---|
| `engine.ast_to_callable(ast_json)` → callable | O(ast size) | **Not cached across evolutions** |
| `func(close, high, low, close, vol)` evaluation | O(N timesteps × indicator depth) | Indicator cache (symbol-level) reused ✓ |
| `np.nan_to_num` + `np.std` check | O(N) | Unchanged |
| `hashlib.md5(formula.encode()).hexdigest()[:12]` | Fast | Unchanged |
| Bloom dedup check | O(1) expected | Bloom filter reused ✓ |
| `generate_alpha_signals(...)` | O(N) | Unchanged |
| `backtester.run(...)` (full A1 backtest) | **Dominant cost** O(N × trades) | Unchanged |
| Val backtest (holdout slice) | Second-dominant cost | Indicator cache swap overhead documented (Patch E 2026-04-19) |
| DB `asyncpg.execute` for admission | Network RTT | Unchanged |

Hot path is **backtester.run() × 2** (train + val). Per-round cost scales with POP_SIZE × N_GEN. At typical configs this is the dominant wall-clock contributor.

## 3. Safe optimization candidates

### 3.1 Bloom dedup WITHOUT unnecessary re-compilation

Observation: today, if `_bloom_key = f"{regime}|{alpha_hash}"` is in bloom, the loop `continue`s AFTER:
- `engine.ast_to_callable(ast_json)` compile
- alpha value evaluation
- `np.nan_to_num` / `np.std` check
- `alpha_hash` computation

Optimization: check bloom by `alpha_hash` BEFORE compile + evaluate. Order of operations:

```python
# Current (simplified):
compile → evaluate → hash_or_use_result_hash → bloom_check → continue-if-hit

# Proposed:
if _bloom_key_probable_fast(regime, alpha_result.hash or fallback):
    continue                # skip before expensive compile
else:
    compile → evaluate → bloom_add
```

**Gotcha**: `alpha_result.hash` may not be populated by GP for every candidate. In those cases, the fallback is `hashlib.md5(formula.encode()).hexdigest()[:12]` which is cheap enough to compute pre-compile.

**Estimated saving**: ~5-15% per-candidate CPU if bloom hit rate is 5-15% (which is observed for stable indicator families).

**Risk**: NONE if alpha_hash derivation is deterministic and unchanged. Decision logic unaffected.

### 3.2 Cache invalidation hygiene on indicator_cache swap

Observation: `engine.indicator_cache.clear(); engine.indicator_cache.update(holdout_indicator_cache.get(sym, {}))` happens inside the per-alpha inner loop, once per alpha for the val backtest. Then a `finally` block reverts. This means per-alpha cache swap overhead is paid per alpha.

Optimization: Batch all A1-passing alphas' val evaluation — run all val backtests with holdout cache installed once, then restore. Requires buffering alpha-level signals until the batch is complete.

**Risk**: Breaks existing fail-fast continue-on-val-error semantics unless buffering preserves per-alpha exception isolation. Design care required.

**Estimated saving**: Depends on alpha count per symbol × regime; could be 2-5x fewer cache swaps.

**Order class**: Performance-only (no semantic change) but requires behavior-invariance tests. Could be folded into P7-PR4-LITE or a dedicated perf order.

### 3.3 Batch-evaluation of alpha set via vectorization

Observation: Each alpha is evaluated independently as `func(close, high, low, close, vol)`. If POP_SIZE alphas share the same input arrays, `func` calls can sometimes be batched (stacked into a 2D array in/out) if the alpha expression tree supports broadcasted evaluation.

**Risk**: Requires AlphaEngine to expose a batched-callable API, and careful handling of per-alpha errors. Opens the black box modestly.

**Estimated saving**: Significant (50%+ in ideal case) but risk of altering per-alpha error semantics if batching masks individual failures.

**Order class**: **Needs j13 explicit authorization** — dips into AlphaEngine semantics. Out of 0-9N scope; file as candidate for 0-9O+ performance addendum.

### 3.4 Early rejection of constant-output alphas before full eval

Observation: `if np.std(alpha_values) < 1e-10: continue` catches constant outputs AFTER full evaluation.

Optimization: Sample the alpha on a small random subset (e.g., 1000 timesteps) first; if std < 1e-10, reject. Full evaluation only for non-constant alphas.

**Risk**: Subsample std may differ from full std; need careful tolerance. Small-sample false negatives (reject a real alpha) possible.

**Estimated saving**: Depends on constant-alpha rate; observed at ~3-5% so saving is modest.

**Order class**: Performance-only; needs behavior-invariance evidence that constant-alpha rejection set is identical between subsample and full eval.

### 3.5 Parallelize per-(symbol, regime) evaluation

Observation: Outer loop `for symbol in DIRECTIONAL: for regime in REGIMES:` is serial. Each (symbol, regime) pair is independent for alpha evaluation.

Optimization: `asyncio.gather()` across regimes, with concurrent worker pool. Already partially done via async DB; extend to alpha eval.

**Risk**: Worker pool → increased memory / CPU contention; per-worker state isolation needed (indicator_cache is shared!).

**Estimated saving**: 2-8x wall-clock depending on worker count and available cores.

**Order class**: Performance; requires careful state-isolation design. Out of 0-9N scope.

### 3.6 Log-parsing acceleration for post-hoc reconstruction

Observation: 0-9G SHADOW and 0-9K P7-PR2 reconstruction parse engine.jsonl line-by-line in Python. At 322K lines the parse is ~10 seconds, tolerable now but will scale poorly.

Optimization: Stream with `json.loads` + early filter (pre-filter lines containing `"A2 "` / `"A3 "` before JSON parse). Or use `orjson` for faster JSON parsing.

**Risk**: None if filter is correctness-preserving. Use `"REJECTED"` or `"A2 "` / `"A3 "` / `"A1 "` as text-level pre-filter; JSON parse only matching lines.

**Estimated saving**: 50-70% of reconstruction time.

**Order class**: Tool-only (scripts/`candidate_lifecycle_reconstruction.py`). Low-risk. Fold into 0-9O or dedicated tooling order.

### 3.7 Artifact reuse across repeated SHADOW runs

Observation: Each 0-9G/0-9J/0-9L SHADOW re-parses the full engine.jsonl. Successive SHADOW runs on overlapping windows redo work.

Optimization: Cache reconstructed lifecycles by `(pre_sha, post_sha, observation_window)` — if inputs unchanged, reuse output.

**Risk**: None if hash is correct.

**Estimated saving**: 90%+ of repeat-run time if hot cache is available.

**Order class**: Tooling-only. Low risk.

## 4. Forbidden optimization categories

Per 0-9N §9.6 explicit:

- **No threshold change** (even if it would speed up rejection).
- **No Arena relaxation** (even if it would "pass" more candidates).
- **No pass/fail semantic change** (even if it would enable batching).
- **No champion promotion logic change**.
- **No execution / capital / risk change**.

## 5. Recommended priority order

| Priority | Optimization | Order candidate |
|---|---|---|
| **1 (easy win)** | §3.1 Bloom dedup before compile | Fold into P7-PR4-LITE |
| **1 (easy win)** | §3.6 Log-parse pre-filter | Fold into P7-PR4-LITE |
| **1 (easy win)** | §3.7 Reconstruction result cache | Tooling-only order |
| **2 (medium)** | §3.2 Batched val evaluation | 0-9O or standalone perf order |
| **2 (medium)** | §3.4 Early constant rejection | Standalone perf order |
| **3 (hard / high risk)** | §3.3 Batched alpha-callable | Explicit authorization required |
| **3 (hard / high risk)** | §3.5 Per-(symbol,regime) parallelism | Explicit authorization required |

## 6. Safe performance testing methodology

All performance changes MUST be validated with:

1. **Behavior-invariance tests**: same inputs → same Arena decision outputs (pass/fail on a fixed test candidate set).
2. **Wall-clock benchmarks**: pre-change vs post-change baseline; report p50 / p95 / p99.
3. **Memory benchmarks**: peak RSS during a run; no regression tolerated.
4. **Controlled-diff**: runtime SHA changes classify as `EXPLAINED_TRACE_ONLY` (if trace-path adjustment) or remain `FORBIDDEN_UNAUTHORIZED_RUNTIME_SHA` until explicit authorization.

## 7. Summary

0-9N identifies 7 safe-ish optimization candidates. Three are easy wins (bloom ordering, log-parse pre-filter, result cache) appropriate for fold-in with telemetry work. Two medium-risk candidates (batched val, early constant rejection) warrant standalone perf orders. Two high-risk candidates (batched callable, parallel symbol/regime) require explicit j13 authorization because they touch AlphaEngine or state-isolation semantics.

**No performance change is implemented in 0-9N itself.** This report feeds into future orders.
