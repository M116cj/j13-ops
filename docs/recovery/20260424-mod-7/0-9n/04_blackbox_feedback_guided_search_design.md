# 04 — Black-Box Feedback-Guided Search Design

TEAM ORDER 0-9N §9.3 + §13 deliverable.

## 1. Purpose

Design how ZANGETSU should optimize alpha generation using **Arena pass-rate
feedback** without requiring alpha interpretability. The black-box alpha
generator stays black; the feedback loop reads ONLY aggregate metrics defined
in §02-03.

## 2. Core design principle

> **Alpha can be black. Arena must be transparent. Deployment must be governed.
> Optimization must be driven by pass-rate / reject-rate / deployable_count.**

## 3. System diagram

```
┌─────────────────────┐
│ Black-Box Alpha Eng │  ← AlphaEngine.evolve() — internals not interpreted
│  (GP operators,     │
│   fitness function) │
└──────────┬──────────┘
           │ candidates tagged with generation_profile_id
           ▼
┌──────────────────────────────────────────────────┐
│ Arena A0 → A1 → A2 → A3 → A4 → A5                │  ← decision logic unchanged
│ pass/fail gated by thresholds (A2_MIN_TRADES=25) │
└──────────┬───────────────────────────────────────┘
           │ emits arena_batch_metrics per batch
           │ emits arena_stage_summary per run
           ▼
┌─────────────────────────────────┐
│ generation_profile_metrics      │  ← computed by profile aggregator
│ (avg_a2_pass_rate, etc.)        │
└──────────┬──────────────────────┘
           │ profile_score per §03 §4
           ▼
┌─────────────────────────────────┐
│ Feedback Decision (0-9O)        │
│ next_budget_weight per profile  │
│ + feedback_decision_record      │  ← signed PR / j13-authorized when
└──────────┬──────────────────────┘     config-changing
           │
           ▼
┌─────────────────────────────────┐
│ Generation Budget Allocator     │  ← implementation in 0-9O
│ shifts N_GEN/POP_SIZE per prof. │     under j13 explicit authorization
└──────────┬──────────────────────┘
           │
           ▼
      (next round)
```

## 4. What the optimizer adjusts

| Adjustable | Semantic | Risk | Requires j13 authorization |
|---|---|---|---|
| **Budget per profile** (how many GP generations to spend on each profile) | Rebalance exploration | Low | YES (strategy change) — 0-9O implementation PR |
| **Active profile set** (which profiles to run this round) | Curate candidate pool | Low-Med | YES |
| **Exploration floor** (minimum budget to any active profile) | Prevent premature winner-takes-all | Low | YES |

## 5. What the optimizer **MUST NOT** adjust

| NOT adjustable by feedback | Why |
|---|---|
| Arena thresholds (A2_MIN_TRADES, A3_*) | Would weaken Arena quality; 0-9M `NEVER_TRACE_ONLY_AUTHORIZABLE` + threshold order required |
| Arena pass/fail predicates | Decision-logic change; requires explicit order |
| Alpha formula generation operators | Opens black box; not authorized |
| Champion promotion rules | Production risk; requires CANARY |
| Execution / capital / risk | Trading risk; requires separate order |
| Cost model | Affects evaluation fairness; requires threshold-class order |

## 6. Feedback loop pseudocode (0-9O target)

```python
# 0-9O implementation sketch (NOT to be implemented in 0-9N)

def feedback_budget_allocator(
    current_profiles: List[Profile],
    metrics_history: List[GenerationProfileMetrics],
    total_budget_next_round: int,
    exploration_floor: float = 0.05,
) -> dict[str, int]:
    """
    Returns {profile_id: allocated_budget} for the next GP round.
    Emits a feedback_decision_record for audit.
    """
    scores = {p.id: compute_profile_score(p, metrics_history) for p in current_profiles}

    # Normalize scores with exploration floor
    raw_weights = {pid: max(0.0, score + exploration_floor) for pid, score in scores.items()}
    total = sum(raw_weights.values())
    if total == 0:
        # Degenerate case: all profiles at or below floor — split evenly
        weights = {pid: 1.0 / len(raw_weights) for pid in raw_weights}
    else:
        weights = {pid: w / total for pid, w in raw_weights.items()}

    allocation = {pid: int(total_budget_next_round * w) for pid, w in weights.items()}
    emit_feedback_decision_record(
        previous_weights=PREV_WEIGHTS,
        new_weights=weights,
        reason=explain_shift(scores),
        observed_bottleneck=detect_bottleneck(metrics_history),
        expected_effect=project_effect(weights, metrics_history),
        safety_constraints=enumerate_safety_constraints(),
    )
    return allocation
```

## 7. Safety invariants (hard — enforced by tests + Gate-A/Gate-B + governance)

1. **Allocation never exceeds `total_budget_next_round`**. Invariant test.
2. **Every active profile gets at least `exploration_floor` budget** (or explicit deactivation via order). Invariant test.
3. **feedback_decision_record emission cannot alter Arena decisions on the current round**. Only changes budget for NEXT round.
4. **feedback_decision_record with a scope that includes config changes requires a signed PR**. Same Gate-A/B gating as other Phase 7 changes.
5. **Profile scoring cannot directly change thresholds**. The scoring sink is budget allocation only; threshold changes require a separate explicit threshold order.
6. **Scoring calculation must be pure function** (same inputs → same outputs). Test-enforced.

## 8. Exploration vs exploitation

The optimizer must balance:

- **Exploitation**: allocate more budget to high-scoring profiles that produce deployable candidates.
- **Exploration**: retain minimum budget for low-scoring profiles that MAY be mis-measured or operating in regime mismatch.

Recommended strategy (0-9O design tuning):

- `exploration_floor = 0.05` (5% budget minimum per active profile).
- If a profile is below floor for ≥ N rounds (e.g., N=5), emit a `profile_deprecated` record and exclude it from the pool — but require j13 authorization before doing so (see 0-9M-style governance).
- New profiles start with `exploration_floor * 2` as a bootstrap — gives them a chance to be measured.

## 9. Integration with existing taxonomy

The feedback loop can target specific rejection reasons:

- **If `SIGNAL_TOO_SPARSE` dominates**: budget shifts toward profiles with lower `signal_too_sparse_rate` (see §05 sparse-candidate plan).
- **If `OOS_FAIL` dominates**: profiles with lower train/val divergence.
- **If `UNKNOWN_REJECT` spikes**: governance alarm — telemetry drift; NOT a budget signal but a bug signal.

## 10. Integration with Phase 7 governance

| Feedback action | Governance path |
|---|---|
| Emit metrics / decision records | Trace-native (P7-PR4-LITE + 0-9O); uses `emit_lifecycle_trace_event()` or a new `emit_feedback_decision_record()` helper; exception-safe. |
| Change budget allocation | Runtime config change; requires signed PR + Gate-A + Gate-B. |
| Deprecate a profile | Explicit order; signed PR; j13 approval. |
| Test new profile in production | Requires CANARY order (0-9S-class). |

## 11. Failure modes and mitigations

| Failure | Mitigation |
|---|---|
| Feedback emission fails | Exception-safe wrapper — Arena continues untouched. |
| Profile scoring contains bug producing NaN score | Guardrail: treat NaN as -inf; test-enforced. |
| All profiles score ≤ -exploration_floor (no viable profile) | Degenerate branch: allocate evenly; alarm to j13 via Calcifer / Telegram. |
| New profile added mid-run | New profile_id is created at first batch emission; aggregator treats new IDs as bootstrapping. |
| Historical metrics become stale after threshold change (fingerprint changes) | Aggregator resets history for the new fingerprint; old profiles retained as archived. |

## 12. Relationship to future CANARY (0-9S)

0-9O produces a feedback loop but does NOT deploy it to production. 0-9S
separately runs the optimizer against a live Arena session (Arena unfreeze
required) and measures:

- Does A1 pass_rate improve under new budget allocation?
- Does A2 pass_rate improve?
- Does deployable_count improve?
- Does drawdown / risk regress against baseline?

CANARY is the final acceptance gate for the optimizer, not 0-9O.

## 13. What this design does **NOT** require

- Per-alpha semantic explanations.
- Formula-level mutation/crossover ancestry.
- Bayesian / posterior analysis over alpha internals.
- Symbol-level or regime-level alpha families (the profile abstracts over these).
- Manual operator tuning of individual alphas.

The optimizer is **pure black-box wrapped in white-box governance**. That is the
0-9N target architecture.
