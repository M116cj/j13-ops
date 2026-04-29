# 03 — PATCH REPORT

**TEAM ORDER**: 0-9Y-HE1-HORIZON-TARGET-PLUMBING
**Date**: 2026-04-28
**Phase**: 3 / 7

## Files added
| Path | LOC | Purpose |
|---|---|---|
| `zangetsu/services/horizon_config.py` | 167 | env-driven horizon resolver (`ACTIVE_A1_HORIZONS`, `ARENA_HORIZON_MODE`, `ARENA_HORIZON_FIXED`); `select_horizon(round_index)` helper |
| `zangetsu/tests/test_he1_horizon_config.py` | 228 | 8 tests covering all 7 master-order required cases plus invalid-handling + tokenize-scan |

## Files modified
| Path | LOC | Type |
|---|---|---|
| `zangetsu/engine/components/alpha_engine.py` | +44 / -9 (signature replacements) | 7 surgical edits |
| `zangetsu/services/arena_pipeline.py` | +35 / -1 (1-line replacement) | 3 surgical edits |

## alpha_engine.py edits (7 surgical)

**Edit 1** (`AlphaResult` dataclass): add `horizon: int = 60` field.

**Edit 2** (`AlphaEngine.__init__`): accept optional `horizon: Optional[int] = None` parameter.

**Edit 3** (`__init__` body): resolve effective horizon — explicit arg overrides; `None` falls back to `ALPHA_FORWARD_HORIZON` env (default 60), preserving pre-HE1 behavior. Stored as `self.horizon`.

**Edit 4** (`_forward_returns`): signature changes from `(close)` → `(close, horizon=None)`. When `horizon is None`, falls back to `ALPHA_FORWARD_HORIZON` env (default 60) — bit-identical to pre-HE1 for any caller that doesn't pass it.

**Edit 5a/5b** (inside `evolve()`): both `forward_returns = self._forward_returns(close)` calls now pass `horizon=self.horizon`.

**Edit 6** (`_individual_to_result`): alpha_hash composition.
- `horizon == 60`: `md5(formula)[:16]` ← legacy fast-path, identical to pre-HE1.
- `horizon != 60`: `md5(f"{formula}|h{horizon}")[:16]` ← multi-horizon distinction.

**Edit 7** (`AlphaResult` constructor): pass `horizon=int(self.horizon)`.

## arena_pipeline.py edits (3 surgical)

**Edit 1** (imports, after TF4 imports): add `from zangetsu.services.horizon_config import select_horizon as _he1_select_horizon, get_horizon_config as _he1_get_config`. Cache `_HE1_CFG = _he1_get_config()`.

**Edit 2** (per-round, before `engine = AlphaEngine(...)`): compute `_he1_horizon = _he1_select_horizon(round_number - 1)` with try/except fallback to 60. Pass to `AlphaEngine(..., horizon=_he1_horizon)`.

**Edit 3** (telemetry, before `_emit_a1_batch_metrics_from_stats_safe`): set `_b1_aggregate_metrics["horizon"] = int(_he1_horizon)` always (additive int field). Add `horizon_config` dict only when multi-horizon mode is active.

## Production deployment defaults (post-HE1)

| ENV var | Unset → | Production behavior |
|---|---|---|
| `ACTIVE_A1_HORIZONS` | `(60,)` | single horizon |
| `ARENA_HORIZON_MODE` | `FIXED` | always returns 60 |
| `ARENA_HORIZON_FIXED` | `60` | matches pre-HE1 |
| `ALPHA_FORWARD_HORIZON` (legacy) | `60` | `_forward_returns` env-fallback path |

With **all unset** (current production state), every A1 round selects horizon = 60. Forward-return computation uses `horizon=60`. Alpha hash uses legacy `md5(formula)` format. **Bit-identical to pre-HE1.**

## Multi-horizon activation
Operator must set BOTH:
```
export ACTIVE_A1_HORIZONS=60,180,240,360
export ARENA_HORIZON_MODE=SIMPLE_CYCLE
```
Then restart workers. From that point:
- Round 0 → horizon=60
- Round 1 → horizon=180
- Round 2 → horizon=240
- Round 3 → horizon=360
- Round 4 → horizon=60 (cycle restarts)
- ...

## Default-OFF guarantee (verified)

| Verification | Result |
|---|---|
| `select_horizon(r) == 60` for all `r` when env unset | ✅ verified by direct interpreter check + HE1 test #4 |
| `_forward_returns(close, horizon=60)` == `_forward_returns(close)` (env-fallback) | ✅ HE1 test #4 |
| `alpha_hash` for horizon=60 == `md5(formula)[:16]` (legacy format) | ✅ HE1 test #3 |
| `_b1_aggregate_metrics["horizon"]` is added unconditionally; `horizon_config` only when multi-horizon | ✅ HE1 test #6 |
| Existing TF2/TF3/TF4 tests still pass | ✅ 29/29 PASS in union suite |

## STOP-conditions check (Phase 3 spec)

| STOP cause | Status |
|---|---|
| Patch affects validation | ❌ no — `entry_rank_threshold` etc. unchanged |
| Patch changes baseline behavior | ❌ no — single-horizon=60 default verified bit-identical |
| Patch alters pass/fail counts | ❌ no — `passed_count`/`rejected_count`/`entered_count` (alpha-level) untouched |
| Refactor of pipeline | ❌ no — additive only |

✅ **No STOP triggered.**

## Verdict
**PHASE_3_COMPLETE** — minimal additive patch (~3 files, +44/+35 LOC modifications + 167 LOC new module + 228 LOC tests, total +474 net) within 80-150 LOC pipeline-modification budget; default OFF preserves bit-equivalent baseline.

## Next
Phase 4 — pytest verification.
