# 02 — Revised Master Sequence (Post Phase-8 Checkpoint)

**Master Order:** 0-9Y-FINAL-ZANGETSU-ALPHA-EDGE-RESTORATION-PROGRAM
**Phase:** 8 / sub-doc 02
**Effective from:** 2026-04-28 j13 Option-A decision

## Original sequence (master order spec PHASE 0 → 13)

```
FINAL-0 → D → HE0 → HE1 → HE2 → HE3 → TF1 → FS1 → CHECKPOINT → HE4 → HE5 → HE6 → CANARY-OR-REDESIGN → MASTER-FINAL-REPORT
```

## Pre-checkpoint completed (this session A)

| # | Sub-order | Verdict | Merge SHA | Telegram |
|---|---|---|---|---|
| 1 | FINAL-0 | `COMPLETE_MASTER_BASELINE_LOCKED` | `fd88760` | 66490 |
| 2 | D | `DECISION_PATH_A_PLUS_C_HORIZON_AND_TRADE_FREQUENCY` | `348eeb7` | 66491 |
| 3 | HE0 | `COMPLETE_HORIZON_TARGET_DESIGN_READY` | `a5f7cabd` | 66492 |
| 4 | TF1 | `DIAGNOSED_LOWER_FREQUENCY_COULD_IMPROVE_EDGE` | `e6f25d7` | 66493 |
| 5 | FS1 | `FEATURE_SPACE_TOO_REDUNDANT_NEEDS_OPERATOR_EXPANSION` | `99ccd0d` | 66494 |
| 6 | CHECKPOINT (this) | OPTION A chosen | (this PR) | (this PR Telegram) |

## Post-checkpoint revised sequence (Option A)

The revised sequence introduces two NEW orders (OP1, TF2) before the original HE1, and shifts HE6 / CANARY-or-Redesign / Master-Final to follow HE5 unchanged.

```
1. OP1   Primitive Registration                      ← NEW (was implicit gap)
2. TF2   Signal Aggregation Prototype                ← NEW (replaces deferred Path C)
3. HE1   Horizon Target Plumbing                     ← original Phase 3
4. HE2   A1 Horizon-Aware Generation                 ← original Phase 4
5. HE3   Horizon Economic Telemetry                  ← original Phase 5
6. HE4   Horizon Shadow Run Activation               ← original Phase 9
7. HE5   Horizon Economic Edge Analysis              ← original Phase 10
8. HE6   Deployable Flow Recheck                     ← original Phase 11
9. Final CANARY-or-Redesign Decision                 ← original Phase 12
10. Master Final Report                              ← original Phase 13
```

(HE0 / TF1 / FS1 are already merged; they don't need re-execution.)

## Per-step scope summary

### Step 1 — TEAM ORDER 0-9Y-OP1-PRIMITIVE-REGISTRATION (next session start)

**Objective**: register 9 already-implemented but un-registered primitives into the GP pset so the grammar can compose them at any depth.

**Primitives to register** (per FS1 03_missing_primitives_review.md):
- `ts_sum`, `ts_mean`, `ts_std`, `ts_argmax`, `ts_argmin`
- `covariance`, `rolling_scale`, `log_x`, `exp_x`

**Suggested registration depths/periods**: at periods `(20, 60, 240)` per FS1 recommendation.

**Forbidden**: no validation / cost / A2_MIN_TRADES / alpha_zoo / CANARY / production change. No new operator implementations beyond the 9 already-shipped. No grammar depth change.

**Suggested branch**: `phase-8/0-9y-op1-primitive-registration`
**Evidence dir**: `docs/recovery/20260424-mod-7/0-9y-final-alpha-edge-restoration/09-op1-primitive-registration/`

**Verdict candidates**: `COMPLETE_OP1_PRIMITIVES_REGISTERED` / `BLOCKED_TEST_FAILURE` / `BLOCKED_FORBIDDEN_DIFF`.

### Step 2 — TEAM ORDER 0-9Y-TF2-SIGNAL-AGGREGATION-PROTOTYPE

**Objective**: build a pre-trade signal-strength filter / top-K-per-bar / consensus mechanism so that A1 emits fewer-but-higher-conviction trades.

**Per TF1 recommendation**:
- Pre-trade signal-strength filter (drop bottom-quartile signals)
- top-K-per-bar (cap concurrent open positions)
- Consensus / multi-feature alignment requirement

**Forbidden**: A2_MIN_TRADES = 25 unchanged; entry threshold unchanged; cost unchanged; validator unchanged.

**Suggested branch**: `phase-8/0-9y-tf2-signal-aggregation-prototype`
**Evidence dir**: `docs/recovery/20260424-mod-7/0-9y-final-alpha-edge-restoration/10-tf2-signal-aggregation/`

### Step 3-5 — TEAM ORDERS HE1, HE2, HE3 (per HE0 design spec)

Re-use the HE0 design spec from Phase 2 directly (already merged at `a5f7cabd`):
- `ACTIVE_A1_HORIZONS = (180, 240, 360)`
- Composite `candidate_id = f"{alpha_hash}_h{horizon}"`
- Equal horizon budget split
- Per-horizon telemetry

After OP1 lands, the grammar gains the 9 primitives. HE1 plumbing then runs against the expanded grammar; HE5 outcome table reflects true horizon economics, not grammar limitations.

### Step 6-9 — HE4 → HE5 → HE6 → Final-CANARY → Master-Final

Unchanged from original master order spec. HE4 starts the SHADOW-only run for 100+ batches per horizon over a 2-12h window. HE5 / HE6 analyze; Final-CANARY-or-Redesign chooses the next strategic move.

## Sequence dependencies

```
OP1 ──→ TF2 ──→ HE1 ──→ HE2 ──→ HE3 ──→ HE4 ──→ HE5 ──→ HE6 ──→ Final CANARY ──→ Master Final
 │       │       │       │       │       │       │       │           │              │
 │       │       │       │       │       │       │       │           │              └─ aggregates everything
 │       │       │       │       │       │       │       │           └─ chooses next path
 │       │       │       │       │       │       │       └─ confirms deployable flow restored?
 │       │       │       │       │       │       └─ analyzes per-horizon
 │       │       │       │       │       └─ 100+ batches per horizon, 2-12h
 │       │       │       │       └─ telemetry per horizon
 │       │       │       └─ generation per horizon
 │       │       └─ target label per horizon
 │       └─ aggregation prototype
 └─ primitive registration (grammar expansion)
```

Each step is gated by the previous: a `BLOCKED_*` verdict in any step suspends the chain and triggers j13 review.

## Forbidden ops invariants (cumulative across all steps)

These constraints apply to every step 1-9 in the revised sequence:

- No threshold change
- No validation change
- A2_MIN_TRADES = 25 unchanged
- No Arena pass/fail / champion promotion / deployable_count semantics change
- No alpha_zoo DB write
- No live CANARY
- No production rollout
- No runtime calibration change
- No DB guard weakening
- No cost model change
- No worker kill (operator-authorized restart only)
- No force-push / hard reset / log wipe

## Master final-verdict options (unchanged from original spec)

After Step 9 (Master Final Report), exactly one of:

- COMPLETE_DEPLOYABLE_FLOW_RESTORED_READY_FOR_CANARY_REVIEW
- COMPLETE_HORIZON_REDESIGN_IMPROVED_EDGE_NO_DEPLOYABLES_YET
- COMPLETE_FEATURE_EXPANSION_REQUIRED
- COMPLETE_TRADE_FREQUENCY_POLICY_REQUIRED
- COMPLETE_ALPHA_UNIVERSE_REDESIGN_REQUIRED
- COMPLETE_NO_EDGE_FOUND_STRATEGIC_CLOSURE_RECOMMENDED
- PARTIAL_HORIZON_PLUMBING_DONE_SHADOW_PENDING
- BLOCKED_RUNTIME_UNSTABLE
- BLOCKED_FORBIDDEN_DIFF
- BLOCKED_INSUFFICIENT_DATA
- BLOCKED_GOVERNANCE_FAILURE
