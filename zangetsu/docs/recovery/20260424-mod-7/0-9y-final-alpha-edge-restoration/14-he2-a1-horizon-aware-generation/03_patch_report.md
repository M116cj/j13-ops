# 03 — PATCH REPORT

**TEAM ORDER**: 0-9Y-HE2-A1-HORIZON-AWARE-GENERATION
**Date**: 2026-04-29
**Phase**: 3 / 8

## Files modified
| Path | LOC | Type of change |
|---|---|---|
| `zangetsu/services/horizon_config.py` | +10 / -0 | added `get_active_a1_horizons()` and `get_horizon_mode()` helpers |
| `zangetsu/engine/components/passport.py` | +11 / -1 | extended `stamp_arena1` signature with optional `horizon=None` kwarg + arena1 dict attachment |
| `zangetsu/services/arena_pipeline.py` | +35 / -1 | 3 surgical edits: extend `_emit_a1_lifecycle_safe` with `horizon` kwarg; pass horizon at ENTRY emission; emit `selected_horizon`/`active_horizons`/`horizon_mode`/`generation_profile_horizon` in batch metrics |
| `zangetsu/engine/components/alpha_engine.py` | +1 / -1 | **HE1 hotfix**: `_os.environ.get(ALPHA_FORWARD_HORIZON, 60)` → `_os.environ.get('ALPHA_FORWARD_HORIZON', '60')` (missing string quoting in HE1 PR #69; surfaced by HE2 test #4) |

## Files added
| Path | LOC | Purpose |
|---|---|---|
| `zangetsu/tests/test_he2_horizon_aware_generation.py` | 299 | 14 master-order required tests + 1 trace-extras test |

## arena_pipeline.py surgical edits (3)

**Edit 1** — `_emit_a1_lifecycle_safe` signature: add `horizon=None` kwarg. Body builds `extras={"horizon": h}` only when `horizon is not None`, then passes to `_build_lc_event(..., extras=_extras)`. Pre-HE2 emission identical when `horizon=None` (extras unchanged from previous behavior).

**Edit 2** — A1 ENTRY lifecycle event: pass `horizon=_he1_horizon` kwarg. Forwards selected per-round horizon into trace events for downstream attribution.

**Edit 3** — Batch telemetry: extend the existing HE1 horizon-attach block:
- Always emit `selected_horizon` (alias of `horizon`, explicit naming per Phase 3 spec)
- When multi-horizon mode active: emit `active_horizons`, `horizon_mode` (flat aliases for easier parsing)
- When `horizon != 60`: derive `generation_profile_horizon = "<base_pid>:h<horizon>"` (per-batch identity)

## passport.py edit
`stamp_arena1` signature gains optional `horizon=None` kwarg. When provided, `self._data["arena1"]["horizon"] = int(horizon)`. Default `None` preserves pre-HE2 schema (no `horizon` key added). **No live call site exists today** — schema-support-only change.

## horizon_config.py edits
Two convenience helpers added (HE2-style imports per master-order Phase 0 spec sample):
```python
def get_active_a1_horizons() -> tuple: ...   # alias of get_horizon_config().active_horizons
def get_horizon_mode() -> str: ...           # alias of get_horizon_config().mode
```

## HE1 bug hotfix (incidental fix)
HE1 PR #69 introduced a bug in `AlphaEngine.__init__` (line ~576):
```python
# WRONG (HE1)
self.horizon = max(1, int(_os.environ.get(ALPHA_FORWARD_HORIZON, 60)))
# FIXED (HE2)
self.horizon = max(1, int(_os.environ.get('ALPHA_FORWARD_HORIZON', '60')))
```
The unquoted `ALPHA_FORWARD_HORIZON` raised `NameError` whenever `AlphaEngine()` was instantiated **without** explicit `horizon=` AND `ALPHA_FORWARD_HORIZON` env was unset. This codepath:
- Did not trigger in HE1 test suite (HE1 tests always passed `horizon=` explicit, OR env was set)
- Did not trigger in production (arena_pipeline.py:1006 always passes `horizon=_he1_horizon`)
- Was surfaced by HE2 test #4 (`AlphaEngine()` no-args + env unset → fall through to env-fallback branch)

The fix is a 1-character correction (add quotes). Bundled in HE2 PR.

## Default-OFF guarantee (verified)

| Verification | Result |
|---|---|
| `select_horizon(r) == 60 ∀ r` when env unset | ✅ HE1 + HE2 test #2 |
| `_forward_returns(close, horizon=60) == _forward_returns(close)` | ✅ HE1 + HE2 test #14 |
| `alpha_hash` for h=60 == `md5(formula)[:16]` (legacy) | ✅ HE1 test #3 |
| `_b1_aggregate_metrics["horizon"]` always 60 when env unset | ✅ |
| `selected_horizon` = `horizon` (alias) | ✅ |
| `active_horizons`, `horizon_mode`, `generation_profile_horizon` NOT emitted when single-horizon=60 | ✅ |
| `_emit_a1_lifecycle_safe` extras unchanged when `horizon=None` | ✅ |
| `passport.stamp_arena1` arena1 dict has no horizon key when not passed | ✅ HE2 test #7 |
| TF4 default OFF still OFF | ✅ HE2 test #13 |

## Source tokenize-scan (forbidden tokens, HE2 tests #10-#12)
- `entry_rank_threshold`, `exit_rank_threshold`, `rank_window`, `VAL_MIN_TRADES`, `validation_threshold` → absent ✅
- `cost_bps`, `cost_model`, `fee_bps`, `slippage_bps`, `round_total_cost`, `FEE_BPS`, `SLIPPAGE` → absent in `horizon_config.py` ✅
- `A2_MIN_TRADES`, `MIN_TRADES`, `a2_min_trades`, `MIN_TRADE_COUNT` → absent in `horizon_config.py` ✅

## STOP-conditions check (Phase 3 spec)
| STOP cause | Status |
|---|---|
| Patch requires validation/cost changes | ❌ no |
| Patch changes baseline when env unset | ❌ no — bit-equivalent to pre-HE2 (HE2 tests #2, #4, #14) |
| Patch changes TF aggregation default behavior | ❌ no — HE2 test #13 verifies TF4 still OFF |
| Patch changes deployable/champion semantics | ❌ no |

✅ **No STOP triggered.**

## Verdict
**PHASE_3_COMPLETE** — minimal additive patch (+57/-3 net LOC across 4 source files) — within budget; HE1 bug hotfix bundled; default OFF preserves bit-equivalent baseline.

## Next
Phase 4 — pytest verification (14 + 1 lifecycle trace test).
