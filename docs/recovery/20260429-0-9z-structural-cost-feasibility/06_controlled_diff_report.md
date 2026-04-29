# 06 — CONTROLLED DIFF / FORBIDDEN AUDIT

**TEAM ORDER**: 0-9Z-STRUCTURAL-COST-FEASIBILITY-AND-ROUTING-DECISION
**Date**: 2026-04-29
**Phase**: 6 / 8

## git status (full repo scope)
```
?? docs/recovery/20260429-0-9z-structural-cost-feasibility/   ← NEW (8 evidence files)
 M calcifer/maintenance.log                                     ← runtime log (NOT staged)
 M calcifer/maintenance_last.json                               ← runtime state (NOT staged)
 M calcifer/report_state.json                                   ← runtime state (NOT staged)
 M zangetsu/logs/engine.jsonl.1                                 ← runtime log (NOT staged)
```

## Diff stat (zangetsu source files)
```
$ git diff --stat HEAD -- zangetsu/services zangetsu/engine zangetsu/tests zangetsu/config
(empty — no source changes)
```

**0-9Z is docs-only by design** — pure read-only analysis on:
- `zangetsu/config/cost_model.py` (108 LOC, audited but **not modified**)
- `zangetsu/engine/components/backtester.py` (220 LOC, traced but not modified)
- `zangetsu/services/arena_pipeline.py` / `arena23_orchestrator.py` / `arena45_orchestrator.py` (call-site verification only)
- `zangetsu/engine/components/alpha_signal.py` (signal-urgency analysis for Phase 3, no edits)
- HE5 frozen dataset `/tmp/0_9y_he4_shadow_collected.jsonl` (counterfactual replay)

## Source-changes scope
| Class | Path | Status | LOC |
|---|---|---|---|
| Code | — | NOT MODIFIED | 0 |
| Tests | — | NOT MODIFIED | 0 |
| Evidence docs | `docs/recovery/20260429-0-9z-structural-cost-feasibility/*.md` | NEW (8) | ~880 |

`engine.jsonl.1` and `calcifer/*` files are runtime logs / state — not source code, not staged.

## Master-order Phase 6 forbidden-change audit

### 1. alpha generation logic
`zangetsu/engine/components/alpha_engine.py`: **NOT in diff**. Untouched.
`zangetsu/services/arena_pipeline.py`: **NOT in diff**. Untouched.

### 2. mutation/crossover/search policy
`zangetsu/engine/components/alpha_engine.py` (DEAP GP toolbox): unchanged.

### 3. Arena thresholds
`zangetsu/services/arena23_orchestrator.py:779` (`A2_MIN_TRADES = 25` gate): unchanged.
Validation thresholds in `engine/components/alpha_signal.py`: unchanged.

### 4. champion promotion / `deployable_count` semantics
`arena23_orchestrator.py` / `arena45_orchestrator.py` / `champion_pipeline*` tables: unchanged.

### 5. capital allocation / execution engine / live trading
No execution code anywhere in the repo (zangetsu has no live order placement). 0-9Z did not introduce any.

### 6. CANARY / production rollout
No env activation by 0-9Z. All live workers continued running on baseline (no `ARENA_TF3_SHADOW`/`ARENA_AGGREGATION_*`/`ARENA_HORIZON_*` env).

### 7. cost model
`zangetsu/config/cost_model.py`: **READ-ONLY audited, NOT modified** in this order. The audit (Phase 1) documents the formula and current values without proposing changes.

### 8. Database writes
**Zero DB writes by 0-9Z.** All DB queries were `SELECT`-only (Phase 0 stage counts, Phase 2 hypothetical scenarios used in-memory only).

### 9. API key usage
Binance API key present at `/home/j13/.env.global` (read-only scope per j13 verification). 0-9Z did **NOT** invoke the key — all fee data sourced from public Binance documentation.

### 10. Worker restarts
**Zero restarts by 0-9Z.** Workers continued running on commit `bcf53cb5` post-HE4 cleanup throughout the entire 0-9Z analysis.

## STOP-conditions check (master-order Phase 6 spec)

| STOP cause | Status |
|---|---|
| STOP-1: live order placement | ❌ no — zero order placement attempted |
| STOP-2: production trading key usage | ❌ no — Binance key NOT invoked |
| STOP-3: weakening A2_MIN_TRADES | ❌ no — verdict explicitly preserves A2_MIN_TRADES=25 |
| STOP-4: changing Arena pass/fail rules | ❌ no |
| STOP-5: ignoring cost/funding/slippage | ❌ no — all explicitly modeled in Phase 1-4 |
| STOP-6: fee schedule unverifiable | ❌ no — public Binance VIP tier schedule + zangetsu cost model both verifiable |
| STOP-7: cost model path ambiguous | ❌ no — Phase 1 traces the full path with file:line references |
| STOP-8: forbidden runtime change | ❌ no — pure docs-only, zero source mutation |
| STOP-9: code patch touching alpha/threshold/champion/execution/capital/risk | ❌ no |

✅ **No STOP triggered.**

## Required classification (per master-order Phase 6 spec)

| Component | Classification |
|---|---|
| Source code changes | **NONE** (0-9Z is docs-only by design) |
| DB queries | **READ_ONLY** (`SELECT count(*)`, `select status, count(*)`, etc. — no `INSERT/UPDATE/DELETE`) |
| Runtime activations | **NONE** (no env activation, no worker restart) |
| API key usage | **NONE** (Binance key not invoked) |
| Counterfactual analysis | **READ_ONLY** (in-memory math on HE5 frozen dataset) |
| Evidence docs (8 files) | **EXPLAINED_DOCS_ONLY** |

## Forbidden ops count
**0** — 0-9Z is pure docs-only / read-only analysis. No source mutation, no DB write, no env activation, no API key usage, no worker restart.

## Verdict
**PHASE_6_COMPLETE** — controlled diff is purely additive evidence documentation; zero source / DB / runtime / API mutation. All 9 STOP conditions verified clear.

## Next
Phase 7 — final report.
