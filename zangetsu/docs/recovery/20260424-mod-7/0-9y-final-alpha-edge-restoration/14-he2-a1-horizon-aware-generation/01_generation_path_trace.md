# 01 — GENERATION PATH TRACE

**TEAM ORDER**: 0-9Y-HE2-A1-HORIZON-AWARE-GENERATION
**Date**: 2026-04-29
**Phase**: 1 / 8

## Trace methodology
```
grep -R "select_horizon|ACTIVE_A1_HORIZONS|ARENA_HORIZON|AlphaEngine|alpha_hash|AlphaResult|generation_profile|passport|arena_batch_metrics|horizon" -n \
  zangetsu/engine zangetsu/services > /tmp/0_9y_he2_generation_path_refs.txt
```
Findings consolidated below.

## Architecture map (post-HE1)

| Component | Path | Horizon awareness |
|---|---|---|
| Horizon config + selection | `zangetsu/services/horizon_config.py` | ✅ HE1 |
| AlphaEngine constructor | `engine/components/alpha_engine.py:544` | ✅ HE1 (`horizon: Optional[int] = None`) |
| `_forward_returns(close, horizon)` | `engine/components/alpha_engine.py:890` | ✅ HE1 |
| `AlphaResult.horizon` | `engine/components/alpha_engine.py:454` | ✅ HE1 (`horizon: int = 60`) |
| `alpha_hash` composition | `engine/components/alpha_engine.py:1062` | ✅ HE1 (legacy fast-path for h=60) |
| arena_pipeline horizon select | `services/arena_pipeline.py:~999` | ✅ HE1 (`_he1_horizon = _he1_select_horizon(round_number - 1)`) |
| arena_pipeline AlphaEngine wiring | `services/arena_pipeline.py:~1006` | ✅ HE1 (`AlphaEngine(..., horizon=_he1_horizon)`) |
| `_b1_aggregate_metrics["horizon"]` | `services/arena_pipeline.py:~1503` | ✅ HE1 |

## Components NOT yet horizon-aware (HE2 scope)

| Component | Path | Required HE2 change |
|---|---|---|
| Generation profile id | `services/generation_profile_identity.py` (called once at worker startup, line 869 in arena_pipeline) | Add per-batch horizon-suffixed profile id `gp:<base>:h<horizon>` for telemetry |
| Lifecycle trace event | `services/candidate_trace.py:489` (`LifecycleTraceEvent`); `services/arena_pipeline.py:66` (`_emit_a1_lifecycle_safe`) | Add `horizon` via existing `extras` dict (no schema change to dataclass) |
| Passport `stamp_arena1` | `engine/components/passport.py:17` | Extend signature with optional `horizon=None` kwarg (schema support only — no live call site exists today) |
| Batch telemetry | `services/arena_pipeline.py` (`_b1_aggregate_metrics`) | Add `selected_horizon`, `active_horizons`, `horizon_mode`, `generation_profile_horizon` (additive) |

## Per-question analysis (master-order Phase 1)

### 1. Where is horizon selected?
`services/arena_pipeline.py` line ~999 (post-HE1): `_he1_horizon = _he1_select_horizon(int(round_number) - 1)`. Wrapped in try/except with fallback to 60.

### 2. Is horizon selected once per round or per candidate?
**Per round.** Every alpha generated within the same `(round_number, sym, regime)` tuple shares the same `_he1_horizon`. Within a round, horizon is immutable by design (Rule 4 of HE1).

### 3. Does AlphaEngine receive selected horizon?
**Yes** (HE1). Line ~1006 in arena_pipeline.py: `engine = AlphaEngine(..., horizon=_he1_horizon)`. The engine stores it as `self.horizon` and uses it in `_forward_returns` and `_individual_to_result`.

### 4. Does AlphaResult carry horizon?
**Yes** (HE1). `AlphaResult.horizon: int = 60` field, populated by `_individual_to_result` with `horizon=int(self.horizon)`.

### 5. Does alpha_hash include horizon?
**Yes** (HE1, conditional). For `h == 60`: `md5(formula)[:16]` (legacy preserved). For `h != 60`: `md5(f"{formula}|h{h}")[:16]` (multi-horizon distinction).

### 6. Does candidate metadata carry horizon?
**Partial.** `AlphaResult.horizon` exists (HE1). However, the downstream candidate metadata as seen at `services/arena_pipeline.py` line ~1100 (after evolve, when `alpha_hash = alpha_result.hash or hashlib.md5(...)`) does NOT explicitly thread `alpha_result.horizon` into a "candidate metadata dict". The lifecycle trace events (`_emit_a1_lifecycle_safe`) currently do not include horizon either.

**HE2 action**: extend `_emit_a1_lifecycle_safe` to accept and forward `horizon` via `LifecycleTraceEvent.extras`.

### 7. Does generation profile id include horizon?
**No.** `_gen_profile_identity` is computed **once at worker startup** from a static config dict. The generated `profile_id` does NOT include horizon.

**HE2 action**: derive a per-batch horizon-aware profile id `f"{_gen_profile_identity['profile_id']}:h{_he1_horizon}"` at the batch metrics emit site. Do NOT mutate the worker-startup `_gen_profile_identity` (it's used by other systems for stable identity across rounds).

### 8. Does passport / trace carry horizon?
**Trace**: No (today) — but `LifecycleTraceEvent.extras: Optional[Dict[str, Any]]` field exists in `services/candidate_trace.py:528`. HE2 can use `extras={"horizon": h}` without schema change.

**Passport**: `engine/components/passport.py:17` `stamp_arena1` signature does NOT include horizon. The class is currently dormant (`grep stamp_arena1 services/ engine/` returns only the definition, no call sites). HE2 will extend the signature with optional `horizon=None` (schema support — live wiring is out-of-scope; will activate when passport stamping is wired to arena_pipeline).

### 9. Does telemetry include horizon?
**Partial.** `_b1_aggregate_metrics["horizon"]` (HE1). Missing: `selected_horizon`, `active_horizons`, `horizon_mode`, `generation_profile_horizon`.

**HE2 action**: add these fields to `_b1_aggregate_metrics`. `selected_horizon` is redundant alias of `horizon` (HE1) — kept for explicit naming per master-order Phase 3 spec. `active_horizons` and `horizon_mode` only emitted when multi-horizon mode is active (already true in HE1 via `horizon_config` sub-dict; HE2 will refactor to flatten these for easier consumer parsing).

### 10. Is default baseline still 60 when env unset?
**Yes** (HE1, verified). Default `HorizonConfig.active_horizons = (60,)`, `mode = FIXED`, `fixed_horizon = 60`. `select_horizon(r) == 60` for every `r` when env unset.

## Classification
**PATH_READY_HORIZON_PARTIAL**

HE1 wiring is sound; HE2 will extend horizon awareness into 4 currently-not-aware components:
1. Generation profile id (per-batch suffix)
2. Lifecycle trace event (via existing `extras` field)
3. Passport `stamp_arena1` (signature extension; live wiring deferred)
4. Batch telemetry (new fields: `selected_horizon`, `active_horizons`, `horizon_mode`, `generation_profile_horizon`)

## STOP-conditions check
| STOP cause | Status |
|---|---|
| HE1 implementation does not support safe extension | ❌ no — HE1 provides clean per-round horizon already |
| Horizon ambiguous in candidate identity | ❌ no — alpha_hash is unique per (formula, horizon); HE1 test #3 verifies |

✅ **No STOP triggered.**

## Verdict
**PHASE_1_COMPLETE** — generation path traced, 4 HE2 extension targets identified, no architectural blockers.

## Next
Phase 2 — horizon budget design.
