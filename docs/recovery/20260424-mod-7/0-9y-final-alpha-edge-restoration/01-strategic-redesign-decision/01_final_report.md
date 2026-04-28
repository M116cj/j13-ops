# 01 — Final Report (Sub-order D Strategic Redesign Decision)

**Sub-order:** TEAM ORDER 0-9Y-D-STRATEGIC-REDESIGN-DECISION
**Phase:** 1
**Date (UTC):** 2026-04-28T02:55Z
**Author:** Claude Lead

## Final verdict

```
DECISION_PATH_A_PLUS_C_HORIZON_AND_TRADE_FREQUENCY
```

(Per master order Phase 1 expected default.)

## Decision summary

| Path | Recommended? | Rationale |
|---|---|---|
| A — Target / Horizon Redesign | **PRIMARY** | weighted score 3.95; addresses gross-per-trade axis; existing data; quick implementation |
| C — Trade-Frequency / Signal Aggregation | **PARALLEL** | weighted score 3.65; addresses cost-burn axis; complementary to A; read-only diagnosis is zero-risk |
| B — Feature-Space Expansion | DEFERRED | weighted score 3.20; slower implementation; revisit at Phase 8 checkpoint if A+C insufficient |
| D — Alpha Zoo Dry-Run | DEFERRED | optional; lower priority |
| E — Microstructure | DEFERRED | strategic future option; do not attempt before A/B/C exhausted |

## Why A + C and not A only or A + B

- **A only** has the highest single-path score but the carry-forward analysis identifies *two* sides of the gap (gross too small AND cost burn too high). Treating only the gross side ignores the inverse density-vs-net correlation found in 0-9Y-C Phase 5.
- **A + B** is strong but B requires multi-day code (new operators, feature builders, possibly cross-asset alignment). Pushing both at once increases governance risk and parallel-merge complexity. B remains the natural follow-up if A+C is insufficient.
- **A + C** combines the two highest-ROI / lowest-implementation-time paths. C's diagnosis phase (TF1) is read-only, so it can run concurrently with A's plumbing/generation/telemetry phases (HE0–HE3) without merge conflict.

## Implementation plan downstream

Per master order recommended execution order:

```
HE0 Horizon Target Design Spec       (A — design)
HE1 Horizon Target Plumbing          (A — plumbing)
HE2 A1 Horizon-Aware Generation      (A — generation)
HE3 Horizon Economic Telemetry       (A — telemetry)
TF1 Trade-Frequency Diagnosis         (C — read-only diagnosis)
FS1 Feature-Space Quality Audit       (preparation for Phase 8 checkpoint)
j13 Checkpoint                       (HARD STOP — decision on horizon-only vs +B/C/D/E expansion)
HE4 Horizon Shadow Run Activation    (post-checkpoint)
HE5 Horizon Economic Edge Analysis   (post-shadow)
HE6 Deployable Flow Recheck          (post-analysis)
Final CANARY-or-Redesign Decision
Master Final Report
```

## Q1 / Q2 / Q3 self-check

- **Q1 Adversarial (5-dim)**:
  - Input boundary: each of 5 paths scored on 7 dimensions; no path silently ignored
  - Silent failure: weighted average + combined-path table cross-checked; A+C wins both
  - External dependency: scoring rubric defined in `00_decision_matrix.md`; no hidden assumptions
  - Concurrency: A + C are designed to run in parallel without shared-state contention (different code areas)
  - Scope creep: docs-only; no code/config/runtime touched
- **Q2 Structural**: docs-only decision; no source mutation; downstream phase plan documented for traceability
- **Q3 Efficiency**: 2 docs (00_decision_matrix + 01_final_report); per spec the decision matrix is the primary deliverable

## Forbidden ops audit

**0** — docs-only. No threshold / validation / cost / promotion / champion / deployable_count change. No alpha_zoo / CANARY / production / runtime calibration. No DB write. No worker kill / force-push / hard reset.

## Next sub-order

```
TEAM ORDER 0-9Y-HE0-HORIZON-TARGET-DESIGN-SPEC
```

Branch: `phase-8/0-9y-he0-horizon-target-design`
Evidence dir: `docs/recovery/20260424-mod-7/0-9y-final-alpha-edge-restoration/02-horizon-target-design/`
