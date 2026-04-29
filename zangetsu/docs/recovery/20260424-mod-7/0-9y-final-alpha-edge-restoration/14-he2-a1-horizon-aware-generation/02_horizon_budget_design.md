# 02 — HORIZON BUDGET DESIGN

**TEAM ORDER**: 0-9Y-HE2-A1-HORIZON-AWARE-GENERATION
**Date**: 2026-04-29
**Phase**: 2 / 8

## Decision: SIMPLE_CYCLE per round

A1 budget is split across horizons by **per-round selection** using HE1's `select_horizon(round_index)`. The selection mode is determined by `ARENA_HORIZON_MODE`:
- **FIXED** (default): horizon = `ARENA_HORIZON_FIXED` (default 60) — single horizon, equal to pre-HE1
- **SIMPLE_CYCLE**: round-robin over `ACTIVE_A1_HORIZONS` — equal allocation across configured horizons
- **RANDOM_UNIFORM**: stateless uniform random choice

## Master-order j13 preference (from spec)
> Active redesign horizons = 180/240/360.
> 60 remains baseline reference unless explicitly included.

This translates to two valid HE2 deployment modes:

### Production-baseline (default, current state)
```
ACTIVE_A1_HORIZONS unset    → resolves to (60,)
ARENA_HORIZON_MODE unset    → resolves to FIXED
ARENA_HORIZON_FIXED unset   → resolves to 60
```
→ `select_horizon(r) == 60` for every round → bit-identical to pre-HE1.

### Redesign mode (operator opt-in only)
```
ACTIVE_A1_HORIZONS=180,240,360
ARENA_HORIZON_MODE=SIMPLE_CYCLE
```
→ Round 0 → 180, Round 1 → 240, Round 2 → 360, Round 3 → 180, ...

### Redesign mode with baseline anchor
```
ACTIVE_A1_HORIZONS=60,180,240,360
ARENA_HORIZON_MODE=SIMPLE_CYCLE
```
→ Round 0 → 60, Round 1 → 180, Round 2 → 240, Round 3 → 360, Round 4 → 60, ...

## Design requirements (per master-order Phase 2)

### 1. Generation profile id encodes horizon
Per-batch (NOT per-worker), derive:
```python
generation_profile_horizon = f"{_gen_profile_identity['profile_id']}:h{_he1_horizon}"
```
Example: base profile_id = `gp_26f478846fd0f729` → with h=180 → `gp_26f478846fd0f729:h180`.

This new field is emitted alongside the existing (worker-static) `generation_profile_id` and `generation_profile_fingerprint` in `arena_batch_metrics`. The static identity remains for downstream consumers; the horizon-aware identity is additive.

### 2. Batch telemetry exposes selected_horizon
Existing HE1 field `_b1_aggregate_metrics["horizon"]` is preserved. HE2 adds explicitly named alias + multi-horizon context:
- `selected_horizon` (int) — alias of `horizon`, kept for explicit naming per Phase 3 spec
- `active_horizons` (list[int]) — only emitted when multi-horizon mode is active
- `horizon_mode` (str) — only emitted when multi-horizon mode is active
- `generation_profile_horizon` (str) — only emitted when horizon != 60

When all 3 conditions hold (single horizon=60, FIXED mode, no profile), batch telemetry has only the `horizon: 60` field — minimal additive change to baseline schema.

### 3. A1 logs include selected_horizon
The horizon is already emitted in `arena_batch_metrics`. For per-round logging, the existing `arena_batch_metrics` record is the durable source; no additional INFO-level log per round is needed (would flood the log at 7-10 batches/min).

### 4. Candidate metadata / passport contains horizon
Two paths:
- **lifecycle trace** (live, used today): extend `_emit_a1_lifecycle_safe` to accept `horizon` param; forward via `LifecycleTraceEvent.extras={"horizon": h, ...}`. No schema change to the dataclass (extras is already `Optional[Dict[str, Any]]`).
- **passport** (dormant, schema-only): extend `ChampionPassport.stamp_arena1(..., horizon=None)` so when arena_pipeline starts using passports (future), horizon is supported. Today no live call site exists.

### 5. Same formula at different horizons → distinct identity
Already enforced by HE1's alpha_hash composition (`md5(formula+|h+horizon)` for h≠60). HE2 preserves this — no change to hash logic.

### 6. Budget split measurable
Per-round emission of `selected_horizon` + `active_horizons` + `horizon_mode` allows downstream consumers to compute `entered_count_by_horizon` aggregates from `arena_batch_metrics`. **HE3 will provide explicit per-horizon economic telemetry** (gross/net/cost split by horizon); HE2 enables this by ensuring the selected horizon is durably attached to every batch.

### 7. No selection bias
- `FIXED`: no bias by design (always same horizon)
- `SIMPLE_CYCLE`: equal cyclic allocation by design (each horizon gets exactly `1/len(active)` of rounds asymptotically)
- `RANDOM_UNIFORM`: uniform-random by design

## Production deployment plan
**HE2 patch does NOT change runtime env.** The patch ships dormant-by-default:
- env unset → single horizon=60 → bit-identical to pre-HE1/HE2 baseline
- multi-horizon activation requires explicit operator opt-in (set `ACTIVE_A1_HORIZONS=180,240,360` + `ARENA_HORIZON_MODE=SIMPLE_CYCLE` + worker restart)

The first authorized multi-horizon SHADOW activation will happen under **HE4** (not HE2).

## Failure handling
- Invalid env → fallback to baseline 60 + WARN log (HE1's existing fail-safe; no change in HE2)
- Per-batch profile_horizon construction wrapped in `try/except` — if it fails, batch metrics still emit without it
- Trace event emission already exception-safe (TF1 design); horizon-extras failure cannot block lifecycle events

## Classification
**BUDGET_DESIGN_READY_SIMPLE_CYCLE**

The default deployment mode is `FIXED` (preserves baseline). The recommended multi-horizon mode is `SIMPLE_CYCLE` over `(180, 240, 360)` (j13 redesign preference) or `(60, 180, 240, 360)` (with baseline anchor). HE2 supports both without code changes — switchover is env-only.

## Verdict
**PHASE_2_COMPLETE** — budget design ready, deployment plan documented, all 7 requirements addressed.

## Next
Phase 3 — patch implementation.
