# 06 — CONTROLLED DIFF / FORBIDDEN AUDIT

**TEAM ORDER**: 0-9Y-TF2-SIGNAL-AGGREGATION-PROTOTYPE
**Date**: 2026-04-28
**Phase**: 6 / 8

## git status (zangetsu scope, post-Phase-5)
```
?? zangetsu/services/signal_aggregation.py        ← NEW
?? zangetsu/tests/test_signal_aggregation.py      ← NEW
?? zangetsu/docs/recovery/                         ← NEW (Phase 0–7 evidence dir)
 M zangetsu/logs/engine.jsonl.1                   ← runtime log (NOT staged)
```

`zangetsu/logs/engine.jsonl.1` is a runtime log written by live A1 workers — **not** a source change. It will not be staged.

## Source changes — controlled diff scope
| Class | File | Status | Lines |
|---|---|---|---|
| Helper module (prototype, default OFF) | `zangetsu/services/signal_aggregation.py` | NEW | 419 |
| Test file | `zangetsu/tests/test_signal_aggregation.py` | NEW | 411 |
| Evidence docs | `zangetsu/docs/recovery/.../10-tf2-signal-aggregation-prototype/` | NEW (8 files) | ~700 |

**Total new source LOC**: 830 (helper + tests). **Modified LOC**: 0. **No existing source files modified.**

## Safety greps (per master-order Phase 6 spec)

### 1. `A2_MIN_TRADES`
```
grep -RInE "A2_MIN_TRADES" zangetsu/services/signal_aggregation.py \
  zangetsu/tests/test_signal_aggregation.py
```
All matches are **docstring prose** or **test-rig string-list entries** describing what the helper does NOT touch. **Zero NAME-token matches** (verified by tokenize-based test #11 PASS).

| File | Lines | Type |
|---|---|---|
| `signal_aggregation.py:7` | docstring | prose: "validation thresholds, cost model, A2_MIN_TRADES, ..." |
| `test_signal_aggregation.py:16, 380, 383, 386` | docstring + forbidden-list literal | test scaffolding |

✅ No code reference to `A2_MIN_TRADES` exists.

### 2. alpha_zoo write-safety ladder (existing, unchanged)
```
grep -RInE "confirm-write|alpha_zoo_injection|no-db-write" \
  zangetsu/scripts/alpha_zoo_injection.py
```
Confirms the existing safety ladder is still in place: `--inspect-only ⊂ --dry-run ⊂ --no-db-write ⊂ --confirm-write` (default-deny). **TF2 does not modify `scripts/alpha_zoo_injection.py`** — `git diff --name-only HEAD -- zangetsu/scripts/alpha_zoo_injection.py` returns empty.

### 3. CANARY / production / order_router / capital / risk
```
grep -RInE "CANARY|production rollout|order_router|capital|risk" \
  zangetsu/services/signal_aggregation.py zangetsu/tests/test_signal_aggregation.py
```
| Match | Type |
|---|---|
| `signal_aggregation.py:34` (docstring): "No coupling to validation, cost, A2, alpha_zoo, CANARY, production flags." | prose |
| `test_signal_aggregation.py:424,428,430,432,439` | forbidden-list literals + test docstring |

✅ All matches are prose/test-rig — zero production-code references (verified by tokenize-based test #13 PASS).

### 4. Apply/runtime-switchable paths
```
grep -RInE "APPLY|apply_budget|runtime-switchable" \
  zangetsu/services/signal_aggregation.py zangetsu/tests/test_signal_aggregation.py
```
Result: **0 matches**. The helper exposes only `apply_signal_aggregation()` (a pure function), no runtime budget allocator, no live-flag switching. The string `apply_signal_aggregation` is the function name itself — does not match the `APPLY` regex (the regex is uppercase-only and word-boundary-tied via `RInE`).

## Required classification (per spec)
| Component | Classification |
|---|---|
| Signal aggregation helper (`services/signal_aggregation.py`) | **EXPLAINED_PROTOTYPE_ONLY** — pure function, default OFF, returns input unchanged on OFF/BASELINE |
| Telemetry fields (defined in helper output but not yet emitted from arena_pipeline) | **EXPLAINED_TELEMETRY_ONLY** — `aggregation_*` fields scaffolded in `AggregationResult.metadata`; arena_pipeline emission deferred to TF3 |
| Tests (`tests/test_signal_aggregation.py`) | **EXPLAINED_TEST_ONLY** — 13 tests covering required spec |
| Docs (`docs/recovery/...`) | **EXPLAINED_DOCS_ONLY** — 8 evidence files for this phase |
| Validation / cost / A2 / champion / deployable / execution / risk / capital | **NO CHANGES** (forbidden — verified absent) |

## STOP-conditions check (Phase 6 spec)
| STOP cause | Status |
|---|---|
| Source changes outside approved scope | ❌ no — only new helper + tests + docs |
| `A2_MIN_TRADES` changed | ❌ no — not referenced in code |
| Validation thresholds changed | ❌ no — `entry_rank_threshold` etc. untouched |
| Cost model changed | ❌ no — `cost_bps` etc. not referenced |
| `alpha_zoo` write enabled | ❌ no — `scripts/alpha_zoo_injection.py` unchanged |
| CANARY started | ❌ no — no CANARY references |
| Production rollout started | ❌ no |
| Execution / capital / risk changed | ❌ no — `order_router`, `execute_order` etc. absent from code |
| DB guards weakened | ❌ no — no DB calls in helper or tests |

✅ **No STOP triggered.**

## Forbidden ops count
**0** — no forbidden touches.

## Verdict
**PHASE_6_COMPLETE — controlled diff is purely additive (prototype helper + tests + docs); zero forbidden touches; all five required classifications hold.**

## Next
Proceed to Phase 7 — Final report.
