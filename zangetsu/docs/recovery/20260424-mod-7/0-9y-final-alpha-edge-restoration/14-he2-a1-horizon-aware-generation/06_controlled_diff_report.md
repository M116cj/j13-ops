# 06 — CONTROLLED DIFF / FORBIDDEN AUDIT

**TEAM ORDER**: 0-9Y-HE2-A1-HORIZON-AWARE-GENERATION
**Date**: 2026-04-29
**Phase**: 6 / 8

## git status (zangetsu scope)
```
?? zangetsu/tests/test_he2_horizon_aware_generation.py                        ← NEW (299)
?? zangetsu/docs/recovery/.../14-he2-a1-horizon-aware-generation/             ← NEW (8 files)
 M zangetsu/services/horizon_config.py                                         ← +10 / -0
 M zangetsu/services/arena_pipeline.py                                         ← +35 / -1 (3 surgical edits)
 M zangetsu/engine/components/alpha_engine.py                                  ← +1 / -1 (HE1 hotfix)
 M zangetsu/engine/components/passport.py                                      ← +11 / -1 (signature ext + arena1 attach)
 M zangetsu/logs/engine.jsonl.1                                                ← runtime log (NOT staged)
```

## Source-changes scope
| Class | Path | Status | LOC |
|---|---|---|---|
| Horizon config helpers | `zangetsu/services/horizon_config.py` | MOD | +10 / 0 |
| Pipeline integration | `zangetsu/services/arena_pipeline.py` | MOD | +35 / -1 |
| Engine HE1 hotfix | `zangetsu/engine/components/alpha_engine.py` | MOD | +1 / -1 |
| Passport schema ext | `zangetsu/engine/components/passport.py` | MOD | +11 / -1 |
| Tests | `zangetsu/tests/test_he2_horizon_aware_generation.py` | NEW | 299 |
| Evidence docs | `zangetsu/docs/recovery/.../14-he2-.../*.md` | NEW (8) | ~810 |

**Total source LOC change**: +55 / -3 net = **+52 net** across 4 modified source files (within master-order budget). 1 new test file (299 LOC).

## Diff classification
| Type of `-` deletion | Count | Reason |
|---|---|---|
| HE1 hotfix (string quote correction in alpha_engine.py) | -1 | replaced unquoted `ALPHA_FORWARD_HORIZON` with quoted version |
| Signature replacement (passport.py stamp_arena1) | -1 | old signature line replaced with extended version (+horizon kwarg) |
| Signature replacement (`_emit_a1_lifecycle_safe` in arena_pipeline.py) | -1 | old signature replaced with extended version (+horizon kwarg) |

**No semantic deletions.** All `-` lines are immediately replaced by an additive equivalent that preserves pre-HE2 behavior when `horizon=None` (the new default).

## Master-order Phase 6 safety greps

### 1. `A2_MIN_TRADES`
Diff scan returns no matches. Tokenize-scan in HE2 test #12 verifies `horizon_config.py` has zero NAME-token references.

### 2. alpha_zoo write-safety
`zangetsu/scripts/alpha_zoo_injection.py`: **unchanged** (not in `git diff --name-only HEAD`).

### 3. CANARY / production / order_router / capital / risk
Diff scan returns no matches. Tokenize-scan in HE2 source files verifies absence of these identifiers in CODE.

### 4. APPLY / runtime-switchable
Master-order spec greps for these. HE2 introduces `ARENA_HORIZON_MODE`/`ACTIVE_A1_HORIZONS`/`ARENA_HORIZON_FIXED` env reads, all **read-only at module import** (cached in `_CONFIG`). No runtime auto-toggle.

### 5. Validator threshold knobs
`engine/components/alpha_signal.py` not in diff. `entry_rank_threshold`, `exit_rank_threshold`, `rank_window`, `min_hold`, `cooldown` are imported only in alpha_signal.py — module not modified by HE2.

### 6. Cost model
`cost_bps` and `cost_model.get(sym).total_round_trip_bps` are referenced in arena_pipeline.py but **NOT modified by HE2 diff**. The `backtester.run(..., cost_bps, ...)` call site is unchanged; same value passed regardless of horizon.

### 7. A2 / A3 / A45 inputs
HE2 patch does not modify:
- A2 entry path (`arena23_orchestrator.py`) — not in diff
- A3 / A45 (`arena45_orchestrator.py`) — not in diff
- `champion_pipeline_*` tables — no DB writes added by HE2

### 8. TF4 default OFF
HE2 test #13 explicitly verifies `aggregation_config.refresh_aggregation_config()` returns `mode=OFF` and `is_active=False` when env unset. **HE2 does NOT change TF4 default.**

## Required classification (per master-order Phase 6 spec)
| Component | Classification |
|---|---|
| `zangetsu/services/horizon_config.py` (helpers added) | **EXPLAINED_HORIZON_ONLY** — `get_active_a1_horizons()` / `get_horizon_mode()` are pure aliases of cached config |
| `zangetsu/services/arena_pipeline.py` (3 surgical edits, +35/-1) | **EXPLAINED_HORIZON_ONLY** — selection propagation, lifecycle trace forwarding, batch-metric emission |
| `zangetsu/engine/components/alpha_engine.py` (+1/-1) | **EXPLAINED_HORIZON_ONLY** — HE1 string-quote hotfix; same semantic, fixes NameError when env unset |
| `zangetsu/engine/components/passport.py` (+11/-1) | **EXPLAINED_METADATA_ONLY** — `stamp_arena1` schema extension with optional `horizon=None` kwarg; default behavior preserves pre-HE2 schema |
| Telemetry fields (`selected_horizon`, `active_horizons`, `horizon_mode`, `generation_profile_horizon`) | **EXPLAINED_TELEMETRY_ONLY** — additive keys; conditional emission preserves baseline schema |
| Lifecycle trace `extras={"horizon": h}` | **EXPLAINED_METADATA_ONLY** — uses pre-existing `extras` field (TF1 design); no schema change to `LifecycleTraceEvent` |
| Tests | **EXPLAINED_TEST_ONLY** |
| Docs (8 evidence files) | **EXPLAINED_DOCS_ONLY** |
| Validation / cost / A2 / champion / deployable / execution / risk / capital | **NO CHANGES** |

## STOP-conditions check (Phase 6 spec)
| STOP cause | Status |
|---|---|
| `A2_MIN_TRADES` changed | ❌ no |
| Validation thresholds changed | ❌ no |
| Cost model changed | ❌ no |
| `alpha_zoo` write enabled | ❌ no |
| CANARY started | ❌ no |
| Production rollout started | ❌ no |
| Execution / capital / risk changed | ❌ no |
| DB guards weakened | ❌ no |
| TF4 default OFF changed | ❌ no — HE2 test #13 verifies |

✅ **No STOP triggered.**

## Forbidden ops count
**0** — no forbidden touches in HE2 source diff, new test file, or evidence docs.

## Verdict
**PHASE_6_COMPLETE** — controlled diff is purely additive horizon-aware plumbing extension (4 source files modified +52 net LOC + 1 new test file 299 LOC + 8 evidence docs); zero forbidden touches; all 8 required classifications hold.

## Next
Phase 7 — final report.
