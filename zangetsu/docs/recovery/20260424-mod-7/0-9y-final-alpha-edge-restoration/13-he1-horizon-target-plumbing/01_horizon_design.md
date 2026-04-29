# 01 — HORIZON DESIGN

**TEAM ORDER**: 0-9Y-HE1-HORIZON-TARGET-PLUMBING
**Date**: 2026-04-28
**Phase**: 1 / 7

## Active horizons
```
ACTIVE_A1_HORIZONS = (60, 180, 240, 360)   # bars
```
- 60 = pre-HE1 single-horizon baseline (preserved)
- 180 / 240 / 360 = candidate horizons for HE-series exploration

## 5 horizon rules (per master order)

### Rule 1 — One horizon per A1 round
Each A1 round invocation (in `arena_pipeline.py`'s per-symbol-per-regime evolution loop) selects exactly one horizon. The chosen horizon governs:
- the forward-return computation in `_forward_returns(close, horizon)`
- the `alpha_hash` composition for that round
- the telemetry field on the emitted `arena_batch_metrics` event

### Rule 2 — Horizon selected per round, not per alpha
Within one round, all alphas evolved by the AlphaEngine share the same horizon. Different rounds may have different horizons (depending on selection mode); but within one round, horizon is constant.

Rationale: the GP search trains the population against a single forward-return target series — switching horizon mid-round would invalidate IC computations.

### Rule 3 — All alphas in a round share the horizon
Logical extension of Rule 2: the AlphaEngine instance for a round receives `horizon` as a constructor argument and uses it consistently for all alphas it evaluates.

### Rule 4 — Horizon is immutable during evaluation
Once an `AlphaEngine` is instantiated for a round, its horizon does not change. The horizon is stored as `self.horizon: int` and `_forward_returns(close, horizon=self.horizon)` is called consistently.

### Rule 5 — Horizon attached to:
- **alpha metadata**: `AlphaResult.horizon` (new field on the dataclass)
- **telemetry**: `arena_batch_metrics["aggregate_metrics"]["horizon"]` (additive; only emitted when ACTIVE_A1_HORIZONS != (60,) — i.e., when HE1 multi-horizon is actually configured)
- **alpha_hash**: composed as `hash(formula | "h" | horizon)` for non-60 horizons; **legacy fast-path** `hash(formula)` preserved for horizon=60 to maintain bit-identity with pre-HE1 baseline

## Selection strategies (per master order)

### `SIMPLE_CYCLE` (multi-horizon design default)
```
horizon = ACTIVE_A1_HORIZONS[round_index % len(ACTIVE_A1_HORIZONS)]
```
- Deterministic, equal allocation of search budget across horizons.
- `round_index` = 0-based monotonic counter (round_number - 1).
- When `len(ACTIVE_A1_HORIZONS) == 1`, this devolves to a fixed single horizon.

### `RANDOM_UNIFORM`
```
horizon = random.choice(ACTIVE_A1_HORIZONS)
```
- Stateless; useful for experimentation but harder to audit per-round behavior.

### `FIXED` (production fallback)
```
horizon = ARENA_HORIZON_FIXED   (default 60)
```
- Always the same value regardless of round.
- This is the **production safety mode**: with `ARENA_HORIZON_MODE` unset and `ACTIVE_A1_HORIZONS` unset (default `(60,)`), this mode produces horizon=60 for every round → bit-identical to pre-HE1.

## Production deployment defaults

| ENV var | Unset → resolves to |
|---|---|
| `ACTIVE_A1_HORIZONS` | `(60,)` — single horizon, equivalent to pre-HE1 |
| `ARENA_HORIZON_MODE` | `FIXED` — pre-HE1-equivalent behavior |
| `ARENA_HORIZON_FIXED` | `60` — pre-HE1 baseline value |

When all 3 unset (current production state on commit `986932df`), the **selected horizon is always 60** for every round. This is the bit-identical baseline path. Pre-HE1 behavior is preserved.

## Multi-horizon activation requires explicit opt-in
Operator wanting to explore multi-horizon must set BOTH:
```
ACTIVE_A1_HORIZONS=60,180,240,360
ARENA_HORIZON_MODE=SIMPLE_CYCLE
```
This is the design's safety property: production never accidentally switches to multi-horizon evaluation without explicit operator action.

## Future composition with HE2/HE3/HE4/HE5
The selected horizon is plumbed into:
- `AlphaEngine.__init__(horizon=...)` ← HE1
- `AlphaResult.horizon` ← HE1
- `_b1_aggregate_metrics["horizon"]` ← HE1

Future orders can extend without re-architecting:
- HE2 will use `horizon` to drive A1 generation profile selection
- HE3 will use `horizon` to split economic telemetry per horizon
- HE4 will run SHADOW evaluations across horizons
- HE5 will check whether deployable_count rises under multi-horizon

## Hash composition decision (critical)

| Case | Hash form | Rationale |
|---|---|---|
| `horizon == 60` | `md5(formula)[:16]` | **Legacy fast-path** — preserves pre-HE1 hash format so existing 89 entries in `champion_pipeline_fresh` and bloom dedup remain consistent. Test 4 ("baseline=60 identical") satisfied. |
| `horizon != 60` | `md5(formula + "|h" + str(horizon))[:16]` | **Multi-horizon distinction** — same formula at h=180 vs h=240 produces different hashes, preventing cross-horizon mixing. Test 3 ("hash differs by horizon") satisfied. |

This dual-format approach is the **only** way to satisfy both:
- "baseline (60) identical to pre-HE1" (Test 4)
- "alpha_hash differs by horizon" (Test 3)
without invalidating existing `champion_pipeline_fresh` records.

## Verdict
**HORIZON_DESIGN_READY** — 5 rules + 3 selection strategies + dual-hash composition rule, all satisfying baseline-preservation invariant.

## Next
Phase 2 — config spec (env-driven flags).
