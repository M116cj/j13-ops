# 05 — CONTROLLED DIFF / FORBIDDEN AUDIT

**TEAM ORDER**: 0-9Y-HE1-HORIZON-TARGET-PLUMBING
**Date**: 2026-04-28
**Phase**: 5 / 7

## git status (zangetsu scope)
```
?? zangetsu/services/horizon_config.py                                          ← NEW (167)
?? zangetsu/tests/test_he1_horizon_config.py                                    ← NEW (228)
?? zangetsu/docs/recovery/.../13-he1-horizon-target-plumbing/                   ← NEW (7 files)
 M zangetsu/engine/components/alpha_engine.py                                   ← +44 / -9 (7 surgical edits)
 M zangetsu/services/arena_pipeline.py                                          ← +35 / -1 (3 surgical edits)
 M zangetsu/logs/engine.jsonl.1                                                 ← runtime log (NOT staged)
```

## Source-changes scope
| Class | Path | Status | LOC |
|---|---|---|---|
| Horizon config module | `zangetsu/services/horizon_config.py` | NEW | 167 |
| Tests | `zangetsu/tests/test_he1_horizon_config.py` | NEW | 228 |
| AlphaEngine integration | `zangetsu/engine/components/alpha_engine.py` | MOD | +44 / -9 |
| Pipeline horizon plumbing | `zangetsu/services/arena_pipeline.py` | MOD | +35 / -1 |
| Evidence docs | `zangetsu/docs/recovery/.../13-he1-.../*.md` | NEW (7) | ~750 |

**Total new + modified source LOC**: ~474 (config 167 + tests 228 + alpha_engine net +35 + arena_pipeline net +34) — within master-order budget (~80-150 LOC pipeline modification + tests + new module).

`engine.jsonl.1` is runtime log — **not** source code, not staged.

## Diff classification (deletions explained)

The `-9` in alpha_engine.py and `-1` in arena_pipeline.py are NOT behavioral deletions — they are signature replacements:

| File | Deleted lines | Reason |
|---|---|---|
| `alpha_engine.py` | `def _forward_returns(close: np.ndarray) -> np.ndarray:` | replaced by signature with `horizon: Optional[int] = None` |
| `alpha_engine.py` | `# Cumulative forward return over ALPHA_FORWARD_HORIZON bars.` | replaced with HE1 comment block (semantically equivalent + new comment) |
| `alpha_engine.py` | `# Must match the min_hold used downstream in alpha_to_signal.` | preserved in expanded HE1 comment |
| `alpha_engine.py` | `import os as _os` (inside `_forward_returns`) | preserved inside the new `if horizon is None:` branch |
| `alpha_engine.py` | `horizon = max(1, int(_os.environ.get('ALPHA_FORWARD_HORIZON', '60')))` | preserved inside `if horizon is None:` branch (env-fallback semantically equivalent) |
| `alpha_engine.py` | `forward_returns = self._forward_returns(close)` (×2) | replaced with `forward_returns = self._forward_returns(close, horizon=self.horizon)` |
| `alpha_engine.py` | `alpha_hash = hashlib.md5(formula.encode("utf-8")).hexdigest()[:16]` | replaced with conditional logic: `if _h == 60 → legacy format` else multi-horizon format |
| `arena_pipeline.py` | `engine = AlphaEngine(indicator_cache=symbol_indicator_cache.get(sym, {}), fitness_fn=_strategy_fitness_fn)` | replaced with multi-line constructor call adding `horizon=_he1_horizon` |

**No semantic deletions.** Every removed line is replaced by an equivalent or strictly-additive form that preserves pre-HE1 behavior when `horizon=60`.

## Master-order Phase 5 safety greps

### 1. Forbidden tokens in modified source files
```
git diff HEAD -- zangetsu/engine/components/alpha_engine.py | \
  grep -iE "A2_MIN_TRADES|alpha_zoo|CANARY|production rollout|order_router|capital|fee_bps|slippage_bps|champion_pipeline_staging|deployable_count\s*=|VAL_MIN_TRADES|entry_rank_threshold|exit_rank_threshold|cost_model"
```
**No matches.** ✅

```
git diff HEAD -- zangetsu/services/arena_pipeline.py | grep -iE "..."
```
**No matches.** ✅

### 2. Forbidden tokens in `horizon_config.py` (tokenize-scan, HE1 test #8)
27 forbidden identifiers scanned via `tokenize.tokenize()`:
- `alpha_zoo`, `ALPHA_ZOO`, `alpha_zoo_injection`
- `champion_pipeline_staging`, `champion_pipeline_fresh`
- `execute_insert`, `DB_WRITE`
- `canary_active`, `CANARY_ENABLED`, `production_rollout`
- `real_capital`, `ORDER_ROUTER`, `order_router`
- `execute_order`, `live_trading`
- `A2_MIN_TRADES`, `MIN_TRADES`, `a2_min_trades`
- `cost_bps`, `cost_model`, `fee_bps`, `slippage_bps`
- `entry_rank_threshold`, `exit_rank_threshold`, `rank_window`
- `VAL_MIN_TRADES`, `validation_threshold`

**HE1 test #8 PASS** — none appear in `horizon_config.py` code (NAME tokens only).

### 3. Validator unchanged
`engine/components/alpha_signal.py`: not in `git diff --name-only HEAD`. `entry_rank_threshold`, `exit_rank_threshold`, `rank_window`, `min_hold`, `cooldown` are imported only in alpha_signal.py — module not modified.

### 4. Cost model unchanged
`cost_bps` is referenced in arena_pipeline.py but **not modified by HE1 diff**. The `backtester.run(..., cost_bps, ...)` call site is unchanged; the same `cost_bps` value is passed in single-horizon mode and would be passed in multi-horizon mode (each round still uses the symbol's `cost_model.get(sym).total_round_trip_bps`).

### 5. A2 / A3 / A45 inputs unchanged
HE1 patch does not modify:
- A2 entry path (`arena23_orchestrator.py`) — not in diff
- A2_MIN_TRADES (no NAME-token reference in HE1 diff)
- A3 / A45 (`arena45_orchestrator.py`) — not in diff
- champion promotion logic — not in diff
- `deployable_count` semantics — `_b1_aggregate_metrics["deployable_count"]` is unchanged; HE1 only adds new `horizon` field alongside

### 6. alpha_zoo write-safety ladder
`zangetsu/scripts/alpha_zoo_injection.py`: **unchanged** (not in `git diff --name-only HEAD`).

### 7. Runtime calibration
No new runtime-toggle env vars introduced beyond the documented HE1 set (`ACTIVE_A1_HORIZONS`, `ARENA_HORIZON_MODE`, `ARENA_HORIZON_FIXED`). All 3 are read once at module import (cached in `_CONFIG`); production never auto-toggles.

## Required classification
| Component | Classification |
|---|---|
| `zangetsu/services/horizon_config.py` | **EXPLAINED_HORIZON_PLUMBING_ONLY** — env-gated read-only resolver, no live decisions |
| `zangetsu/engine/components/alpha_engine.py` (7 edits, +44/-9) | **EXPLAINED_HORIZON_PARAMETERIZATION_ONLY** — adds `horizon` parameter throughout the engine; `horizon=60` baseline is bit-identical to pre-HE1 |
| `zangetsu/services/arena_pipeline.py` (3 edits, +35/-1) | **EXPLAINED_HORIZON_HOOK_ONLY** — selects per-round horizon, plumbs to AlphaEngine, emits as telemetry |
| Telemetry fields (`horizon`, `horizon_config`) | **EXPLAINED_TELEMETRY_ONLY** — additive keys; `horizon` always emitted (default 60); `horizon_config` only when multi-horizon active |
| Tests | **EXPLAINED_TEST_ONLY** |
| Docs (7 evidence files) | **EXPLAINED_DOCS_ONLY** |
| Validation / cost / A2 / champion / deployable / execution / risk / capital | **NO CHANGES** |

## STOP-conditions check (Phase 5 spec)
| STOP cause | Status |
|---|---|
| Source changes outside approved scope | ❌ no |
| Forbidden touch found | ❌ no — all 7 grep categories empty |

✅ **No STOP triggered.**

## Forbidden ops count
**0** — no forbidden touches in HE1 source diff, new modules, or tests.

## Verdict
**PHASE_5_COMPLETE** — controlled diff is purely additive horizon plumbing (1 config module + 1 test file + 7 surgical edits to alpha_engine.py + 3 surgical edits to arena_pipeline.py + 7 evidence docs); zero forbidden touches; all 7 required classifications hold.

## Next
Phase 6 — final report.
