# 02 — Final Report (Sub-order HE0 Horizon Target Design Spec)

**Sub-order:** TEAM ORDER 0-9Y-HE0-HORIZON-TARGET-DESIGN-SPEC
**Phase:** 2
**Date (UTC):** 2026-04-28T03:08Z
**Author:** Claude Lead

## Final verdict

```
COMPLETE_HORIZON_TARGET_DESIGN_READY
```

The design specification is sufficient for HE1 (Horizon Target Plumbing) to be implemented in a fresh execution session. All 10 design decisions (D1–D10) and 7 risks (R1–R7) are documented with concrete owner, mitigation, and action item.

## Spec-compliance audit (per master-order Phase 2 required decisions)

| Required decision | Doc location | Status |
|---|---|---|
| label construction | `00_design_spec.md` D2 | ✓ |
| no-lookahead rule | `00_design_spec.md` D3 + `01_risk_register.md` R6 | ✓ |
| candidate horizon identity | `00_design_spec.md` D4 + `01_risk_register.md` R5 | ✓ (composite `candidate_id`) |
| horizon-aware alpha_hash or separate identity key | `00_design_spec.md` D4 | ✓ (separate composite key; alpha_hash unchanged) |
| horizon budget split | `00_design_spec.md` D5 | ✓ (equal split, last horizon takes remainder) |
| telemetry fields | `00_design_spec.md` D6 | ✓ (delegated to HE3 with full field list) |
| legacy candidate handling | `00_design_spec.md` D7 | ✓ (legacy = implicit horizon 60; one-shot backfill optional in separate B-stream order) |
| validation unchanged | `00_design_spec.md` D8 | ✓ |
| cost unchanged | `00_design_spec.md` D9 | ✓ |
| A2_MIN_TRADES unchanged | `00_design_spec.md` D10 | ✓ |
| Required risk register | `01_risk_register.md` R1–R7 | ✓ (7 risks, all with severity/likelihood/owner/mitigation) |

## Implementation interface contract (for HE1 implementer)

```python
# Constants — module-level in arena_pipeline.py
ACTIVE_A1_HORIZONS: tuple[int, ...] = (180, 240, 360)

# Function signature change — alpha_engine.py:633
def _forward_returns(close: np.ndarray, horizon: int) -> np.ndarray: ...

# Identity contract — alpha_engine.py:805 area
alpha_hash = hashlib.md5(formula.encode("utf-8")).hexdigest()[:16]   # UNCHANGED
candidate_id = f"{alpha_hash}_h{horizon}"                             # NEW

# Bloom dedup contract
bloom_add(candidate_id)  # NEW; legacy bloom_add(alpha_hash) remains for legacy 60-bar paths
```

## Required tests (HE1 must produce)

1. `test_active_a1_horizons_constant` — value is exactly `(180, 240, 360)`
2. `test_invalid_horizon_fails_closed` — `_forward_returns(close, 0)` and negative-horizon raise or return all-NaN
3. `test_label_shift_180` — last 180 of `_forward_returns(close, 180)` are NaN
4. `test_label_shift_240` — last 240 of `_forward_returns(close, 240)` are NaN
5. `test_label_shift_360` — last 360 of `_forward_returns(close, 360)` are NaN
6. `test_no_future_leakage` — for each horizon, `fwd_return[i]` does not depend on `close[j]` where `j ≥ i + horizon` (synthetic adversarial test: change `close[i + horizon]`, see if `fwd_return[i]` changes)
7. `test_metadata_includes_horizon` — `BacktestResult` or candidate metadata has `horizon` field after evaluation
8. `test_identity_separates_formula_and_horizon` — same formula, two horizons → two distinct `candidate_id`s
9. `test_validation_thresholds_unchanged` — A2_MIN_TRADES still 25; gate constants unchanged
10. `test_cost_model_unchanged` — `cost_per_trade` and `round_total_cost_bps` derivation untouched

## Forbidden ops audit (this sub-order)

**0** — docs-only design spec. No source / code / config / runtime / DB / threshold / validator / cost / alpha_zoo / CANARY / production / calibration / promotion semantics change.

## Q1 / Q2 / Q3 self-check

- **Q1 Adversarial (5-dim)**:
  - Input boundary: D2/D3 cover NaN tail, D4 covers same-formula-different-horizon, D5 covers budget rounding
  - Silent failure: every risk has explicit detection mechanism (mostly via HE3 telemetry); R5 hash collision detection is mandatory unit test
  - External dependency: design references existing functions (alpha_engine, arena_pipeline, arena_pass_rate_telemetry) by file:line; no fictitious APIs
  - Concurrency: per-process state is fine (each Python worker is independent; horizon selection is per-round single-threaded)
  - Scope creep: ONLY design + risk register; no implementation; legacy backfill explicitly deferred to separate optional order
- **Q2 Structural**: design preserves backward-compat with the 89 existing fresh-pool alphas (alpha_hash unchanged, implicit horizon=60); HE1 implementation guidance is "additive — extend, don't break"
- **Q3 Efficiency**: 3 docs (00 design + 01 risk register + 02 final report) per spec; no extras

## Files in this sub-order

| File | Purpose |
|---|---|
| `00_design_spec.md` | 10 design decisions + per-horizon expected-trade math |
| `01_risk_register.md` | 7 risks with severity, likelihood, owner, mitigation, action item |
| `02_final_report.md` | this file — verdict + spec-compliance audit + interface contract + test list |

## Next sub-order

```
TEAM ORDER 0-9Y-HE1-HORIZON-TARGET-PLUMBING
```

Branch: `phase-8/0-9y-he1-horizon-target-plumbing`
Evidence dir: `docs/recovery/20260424-mod-7/0-9y-final-alpha-edge-restoration/03-horizon-target-plumbing/`
**Note**: HE1 is a CODE change. Per j13 directive, HE1 is deferred to a fresh execution session for clean context.
