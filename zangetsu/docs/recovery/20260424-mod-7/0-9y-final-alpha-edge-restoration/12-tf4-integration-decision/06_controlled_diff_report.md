# 06 — CONTROLLED DIFF / FORBIDDEN AUDIT

**TEAM ORDER**: 0-9Y-TF4-INTEGRATION-DECISION
**Date**: 2026-04-28
**Phase**: 6 / 8

## git status (zangetsu scope)
```
?? zangetsu/services/aggregation_config.py                                  ← NEW (125)
?? zangetsu/tests/test_tf4_aggregation_config.py                            ← NEW (251)
?? zangetsu/docs/recovery/.../12-tf4-integration-decision/                  ← NEW (8 files)
 M zangetsu/services/arena_pipeline.py                                      ← +60 / −0 (4 surgical edits)
 M zangetsu/logs/engine.jsonl.1                                             ← runtime log (NOT staged)
```

## Source-changes scope
| Class | Path | Status | LOC |
|---|---|---|---|
| Production config module | `zangetsu/services/aggregation_config.py` | NEW | 125 |
| Tests | `zangetsu/tests/test_tf4_aggregation_config.py` | NEW | 251 |
| Pipeline integration | `zangetsu/services/arena_pipeline.py` | MOD | +60 / −0 |
| Evidence docs | `zangetsu/docs/recovery/.../12-tf4-.../*.md` | NEW (8) | ~750 |

`engine.jsonl.1` is runtime log — **not** source code, not staged.

## Master-order Phase 6 safety greps

### 1. Forbidden tokens in source diff
```
git diff HEAD -- zangetsu/services/arena_pipeline.py | \
  grep -iE "A2_MIN_TRADES|alpha_zoo|CANARY|production rollout|order_router|capital|cost_model|fee_bps|slippage_bps|champion_pipeline|deployable_count\s*=|VAL_MIN_TRADES|entry_rank_threshold|exit_rank_threshold"
```
**No matches.** ✅

### 2. Forbidden tokens in `aggregation_config.py` (tokenize-scan, TF4 test #7)
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

**TF4 test #7 PASS** — none appear in `aggregation_config.py` code (NAME tokens only).

### 3. alpha_zoo write-safety ladder
`zangetsu/scripts/alpha_zoo_injection.py`: **unchanged** (`git diff --name-only HEAD` does not list it).

### 4. APPLY/runtime-switchable
TF4 introduces `ARENA_AGGREGATION_MODE` etc., but these are **read-only at module-import time** (cached in `_CONFIG`). Master-order rule "flags must be read-only for production (not toggled automatically)" satisfied.

### 5. Validator unchanged
`engine/components/alpha_signal.py`: not in `git diff --name-only HEAD`. `entry_rank_threshold`, `exit_rank_threshold`, `rank_window`, `min_hold`, `cooldown` are imported only in alpha_signal.py and that module is not modified.

### 6. Cost model unchanged
`cost_bps` and `cost_model.get(sym).total_round_trip_bps` are referenced in arena_pipeline.py but **not modified by TF4 diff**. The shadow + pre-filter both call `backtester.run(..., cost_bps, ...)` with the same value baseline already pays.

### 7. A2/A3/A45 inputs unchanged
TF4 patch does not modify:
- A2 entry path (`arena23_orchestrator.py`) — not in diff
- A2_MIN_TRADES (no NAME-token reference in TF4 diff)
- A3 / A45 (`arena45_orchestrator.py`) — not in diff
- champion promotion logic — not in diff
- `deployable_count` semantics — not assigned in diff (only echoed in shadow_profiles dict by TF3, unchanged in this PR)

## Required classification (per Phase 6 spec)
| Component | Classification |
|---|---|
| `zangetsu/services/aggregation_config.py` | **EXPLAINED_PRODUCTION_CONFIG_ONLY** — env-gated read-only resolver |
| `zangetsu/services/arena_pipeline.py` (4 surgical edits, +60 LOC) | **EXPLAINED_INTEGRATION_HOOK_ONLY** — gated by `_TF4_CFG.is_active`; baseline path bit-equivalent when MODE=OFF |
| Telemetry fields (`aggregation_mode`/`aggregation_skipped_count_total` etc.) | **EXPLAINED_TELEMETRY_ONLY** — additive keys; emitted only when MODE != OFF |
| Tests | **EXPLAINED_TEST_ONLY** |
| Docs (8 evidence files) | **EXPLAINED_DOCS_ONLY** |
| Validation / cost / A2 / champion / deployable / execution / risk / capital | **NO CHANGES** — verified absent |

## STOP-conditions check (Phase 6 spec)
| STOP cause | Status |
|---|---|
| Source changes outside approved scope | ❌ no — only the gated pre-filter hook + new config module |
| `A2_MIN_TRADES` changed | ❌ no |
| Validation thresholds changed | ❌ no |
| Cost model changed | ❌ no |
| `alpha_zoo` write enabled | ❌ no |
| CANARY started | ❌ no |
| Production rollout started | ❌ no |
| Execution / capital / risk modified | ❌ no |
| DB guards weakened | ❌ no |

✅ **No STOP triggered.**

## Forbidden ops count
**0** — no forbidden touches in TF4 source diff, new config module, or tests.

## Verdict
**PHASE_6_COMPLETE — controlled diff is purely additive (1 config module + 1 test file + 4 surgical additive edits to arena_pipeline.py + 8 evidence docs); zero forbidden touches; all 6 required classifications hold.**

## Next
Phase 7 — final report.
