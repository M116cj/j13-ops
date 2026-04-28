# 06 — CONTROLLED DIFF / FORBIDDEN AUDIT

**TEAM ORDER**: 0-9Y-TF3-SIGNAL-AGGREGATION-SHADOW-ACTIVATION
**Date**: 2026-04-28
**Phase**: 6 / 8

## git status (zangetsu scope)
```
?? zangetsu/services/tf3_shadow.py                                       ← NEW
?? zangetsu/tests/test_tf3_shadow.py                                     ← NEW
?? zangetsu/docs/recovery/.../11-tf3-signal-aggregation-shadow-activation/   ← NEW (8 files)
 M zangetsu/services/arena_pipeline.py                                   ← +44 LOC additive (4 surgical edits)
 M zangetsu/logs/engine.jsonl.1                                          ← runtime log (NOT staged)
```

## Source-changes scope
| Class | Path | Status | LOC |
|---|---|---|---|
| Shadow harness module | `zangetsu/services/tf3_shadow.py` | NEW | 254 |
| Tests | `zangetsu/tests/test_tf3_shadow.py` | NEW | 292 |
| Pipeline integration | `zangetsu/services/arena_pipeline.py` | MOD | +44 / −0 |
| Evidence docs | `zangetsu/docs/recovery/.../11-tf3-.../*.md` | NEW (8) | ~700 |

**Total new+modified source LOC**: 290 actually-runtime + ~700 docs. **Existing source files modified**: 1 (arena_pipeline.py, additive only).

`zangetsu/logs/engine.jsonl.1` shows up in `git status` — this is a runtime log written by live A1 workers, **not source code**. It will not be staged.

## Master-order Phase 6 safety greps

### 1. `A2_MIN_TRADES`
```
grep -RInE "A2_MIN_TRADES" zangetsu/services/tf3_shadow.py \
    zangetsu/tests/test_tf3_shadow.py \
    zangetsu/services/arena_pipeline.py
```
Code references in source diff (HEAD vs working tree, modified files only):
```
$ git diff HEAD -- zangetsu/services/arena_pipeline.py | grep "A2_MIN_TRADES"
(no output)
```
✅ **Zero forbidden code references.** Test file scans for `A2_MIN_TRADES` as a **forbidden token** (test #9), but only as a literal string in a check list — does not invoke or modify it.

### 2. alpha_zoo write-safety ladder
`zangetsu/scripts/alpha_zoo_injection.py`: **unchanged** (`git diff --name-only HEAD` does not list it).

### 3. CANARY / production / order_router / capital / risk
```
git diff HEAD -- zangetsu/services/arena_pipeline.py | \
  grep -iE "CANARY|production rollout|order_router|capital|risk[^.]"
```
**No matches.** Modified arena_pipeline.py diff is purely additive shadow-block scaffolding.

In `tf3_shadow.py` (new file), TF3 test #9 verifies via tokenize-based scan that no NAME tokens match: `alpha_zoo`, `ALPHA_ZOO`, `alpha_zoo_injection`, `champion_pipeline_staging`, `champion_pipeline_fresh`, `execute_insert`, `DB_WRITE`, `canary_active`, `CANARY_ENABLED`, `production_rollout`, `real_capital`, `ORDER_ROUTER`, `order_router`, `execute_order`, `live_trading`, `A2_MIN_TRADES`, `MIN_TRADES`, `a2_min_trades`. **All assertions pass.**

### 4. Validator threshold knobs
```
git diff HEAD -- zangetsu/services/arena_pipeline.py | \
  grep -iE "entry_rank_threshold|exit_rank_threshold|rank_window|VAL_MIN_TRADES|validation_threshold"
```
**No matches.** Validator-related identifiers (`entry_rank_threshold`, `exit_rank_threshold`, `rank_window`) are imported and used only in `engine/components/alpha_signal.py` and that module is not modified by TF3.

### 5. Cost model
```
git diff HEAD -- zangetsu/services/arena_pipeline.py | \
  grep -iE "cost_bps|cost_model|fee_bps|slippage_bps|round_total_cost"
```
The string `cost_bps` appears in the diff context — it is the **call-site argument forwarded** to backtester.run, both for baseline AND shadow. Identical value used in both code paths. The cost model itself (`cost_model.get(sym).total_round_trip_bps`) is NOT modified. The shadow path uses the SAME `cost_bps` baseline already pays.

### 6. Champion / deployable / promotion
```
git diff HEAD -- zangetsu/services/arena_pipeline.py | \
  grep -iE "round_champions|deployable_count\s*=|champion_pipeline|pass_count|promote"
```
**No matches in actual diff lines (additive shadow block only).** The diff context shows the existing `passed_count=round_champions` in the emit call, which is **unchanged**.

### 7. APPLY / runtime-switchable
```
grep -RInE "APPLY|apply_budget|runtime-switchable" zangetsu/services/tf3_shadow.py
```
**No matches.** Only `apply_signal_aggregation` (function name from TF2 helper) is referenced — not a runtime switching primitive.

## Required classification (per master-order Phase 6 spec)
| Component | Classification |
|---|---|
| `zangetsu/services/tf3_shadow.py` | **EXPLAINED_SHADOW_HARNESS_ONLY** — pure helper, env-gated invocation, no live decisions |
| `zangetsu/services/arena_pipeline.py` (4 surgical edits, +44 LOC) | **EXPLAINED_PROTOTYPE_ONLY** — gated by `_tf3_shadow_accs is not None`; baseline path bit-equivalent when shadow disabled |
| Telemetry fields (`shadow_profiles` dict in `aggregate_metrics`) | **EXPLAINED_TELEMETRY_ONLY** — additive key, no overwrite; emitted only when shadow=1 |
| Tests (`tests/test_tf3_shadow.py`) | **EXPLAINED_TEST_ONLY** |
| Docs (8 evidence files) | **EXPLAINED_DOCS_ONLY** |
| Validation / cost / A2 / champion / deployable / execution / risk / capital | **NO CHANGES** — verified absent |

## STOP-conditions check (Phase 6 spec)
| STOP cause | Status |
|---|---|
| Source changes outside approved scope | ❌ no — only the gated shadow block + new harness module |
| `A2_MIN_TRADES` changed | ❌ no |
| Validation thresholds changed | ❌ no — `engine/components/alpha_signal.py` unchanged |
| Cost model changed | ❌ no — `cost_bps` is the same value passed to both baseline and shadow backtester calls |
| `alpha_zoo` write enabled | ❌ no — `scripts/alpha_zoo_injection.py` unchanged |
| CANARY started | ❌ no |
| Production rollout started | ❌ no |
| Execution / capital / risk changed | ❌ no |
| DB guards weakened | ❌ no — no DB writes in TF3 path |

✅ **No STOP triggered.**

## Forbidden ops count
**0** — no forbidden touches in TF3 source diff or new modules.

## Verdict
**PHASE_6_COMPLETE — controlled diff is purely additive (1 helper module + 1 test file + 4 surgical additive edits to arena_pipeline.py + 8 evidence docs); zero forbidden touches; all 6 required classifications hold.**

## Next
Phase 7 — final report.
