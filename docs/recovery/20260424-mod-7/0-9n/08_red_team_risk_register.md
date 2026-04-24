# 08 — Red-Team Risk Register

TEAM ORDER 0-9N §9.7 deliverable.

## 1. Purpose

Adversarial review of the proposed black-box optimization design for hidden risks that could weaken Arena quality, incentivize wrong behavior, or bypass governance.

## 2. Top-level risk matrix

| # | Risk | Severity | Likelihood | Mitigation |
|--:|---|---|---|---|
| R1 | Optimizer rewards pass-rate at the cost of edge quality | **High** | **Medium** | Multi-metric scoring; `oos_fail_rate` / `instability_penalty` in score; CANARY A/B must show NO regression in OOS stability |
| R2 | Feedback loop converges to a single overfit profile | **High** | **Medium-High** | `exploration_floor = 0.05` minimum; profile deprecation requires explicit order; N-round windowed metrics to avoid chasing single batches |
| R3 | Deployable_count gets inflated by relaxing definition without threshold order | Critical | Low (gated by governance) | 0-9M `NEVER_TRACE_ONLY_AUTHORIZABLE` + explicit threshold order required; `is_deployable_through("A3")` pinned by behavior-invariance tests |
| R4 | Telemetry emission slows down Arena beyond acceptable latency | Med | Low | Exception-safe emitter; emission cost benchmarked in perf tests before enabling; synchronous log.info() is OK at current log volumes |
| R5 | "trace-only" authorization is used to sneak in decision-logic changes | High | Low (Gate review) | Behavior-invariance tests + PR review; test_arena_gates_thresholds_* + test_arena2_pass_* catch any logic mutation; 0-9M audit trail leaves FORBIDDEN_TRACE_ONLY evidence |
| R6 | Profile fingerprint stability bug → same-config profiles split into multiple profile_ids | Med | Low | Canonical-JSON fingerprint spec (§03 §3); test-enforced |
| R7 | UNKNOWN_REJECT ratio drifts from 0% as Arena evolves (taxonomy lag) | Med | Med | Watch-list in §02 + 0-9O feedback flags UNKNOWN spike as governance alarm, not budget signal |
| R8 | Per-profile A/B CANARY creates adverse selection | Med | Medium (subtle) | CANARY must randomize symbol/regime assignment; budget split must be stable not adaptive within the canary window |
| R9 | Feedback decision records contain bugs that alter Arena behavior retroactively | Critical | Very Low | decision records are APPEND-ONLY; NEVER mutate Arena decisions of prior rounds; test-enforced |
| R10 | Governance creep: 0-9O exception expands to include alpha-logic change | Critical | Low | Order class boundaries per §06 matrix; explicit "generation-policy does NOT cover alpha-logic" |
| R11 | CANARY promotes to production without explicit order | Critical | Very Low (2-step) | 0-9S CANARY evidence is NOT rollout authorization; 0-9T requires separate production order + human sign-off |
| R12 | Schema v2 of arena_batch_metrics breaks old reconstruction | Low | Low | `telemetry_version` field + parser tolerates unknown fields |
| R13 | Attacker files a PR masquerading as "trace-only" but changing A2 predicate | Critical | Very Low | signed PR + Gate-A + Gate-B + test_arena2_pass_decision_unchanged + human review in PR |
| R14 | Budget allocator zeroes out a profile that would have produced future deployable candidates | Med | Med | `exploration_floor` prevents zero-allocation; profile deprecation requires explicit j13 order |
| R15 | Emission schema includes PII or credentials accidentally | High | Low | Schema design (§02 §08) explicitly excludes PII; reviewed in PR |

## 3. Adversarial questions (each answered)

### Q: Does the design accidentally weaken Arena standards?

**A**: No. The only Arena-adjacent change envisioned is **trace-only** emission around decision points (e.g., `_emit_a1_lifecycle_safe()` already landed in P7-PR3). The Arena decision predicates (`bt.total_trades < 30`, `arena2_pass()`, `arena3_pass()`, etc.) remain unchanged.

Specific guards:
- `test_arena_gates_thresholds_still_pinned_under_p7_pr3` pins all 6 threshold constants.
- `test_arena2_pass_decision_unchanged_*` tests confirm identical outputs on edge inputs.
- 0-9M `NEVER_TRACE_ONLY_AUTHORIZABLE` refuses trace-only classification for `zangetsu_settings_sha`.

### Q: Does it incentivize higher pass-rate but lower edge?

**A**: The scoring model in §04 § 4 includes `oos_fail_rate` penalty and `instability_penalty`. If a profile achieves high A2 pass-rate but candidates fail A3 OOS gate → A3 pass_rate drops → composite score drops. Edge-quality is captured by A3 pass_rate weight.

Residual risk: if A3 OOS gate is too lax, a profile could game A2 while still passing A3. Mitigation: don't lower A3 thresholds (already covered by §06 governance).

### Q: Does it optimize for deployable_count without robustness?

**A**: Scoring model includes only `normalized_deployable_count` with weight w4=0.30, balanced against oos_fail_rate penalty (w6) and instability_penalty (w8). A profile that increases deployable_count at the cost of robustness suffers in the composite score.

Residual risk: very low deployable_count baseline (6 in 7 days) makes early optimization hard — variance is high. Mitigation: N-round windowed metrics; CANARY long enough to smooth.

### Q: Does it create overfitting risk?

**A**: Risk exists. Mitigations:
- `oos_fail_rate` penalty in scoring.
- A3 val gate is downstream of A2 and already punishes overfit.
- `exploration_floor` prevents runaway exploitation of a single profile.
- CANARY is an A/B that must show NOT just better A2 pass-rate, but NO regression in downstream stability and risk.

### Q: Does it create governance bypass risk?

**A**: Not if the permission matrix in §06 is respected. Key guard: each order class has a specific authorization scope; an order cannot escalate scope without j13 explicit authorization. The Gate-A + Gate-B + signed PR + controlled-diff + behavior-invariance test quartet is non-bypassable.

Residual risk: IF `--authorize-trace-only` is passed for a field that corresponds to a runtime file containing both trace AND decision logic (true for arena_pipeline.py), the tool alone cannot verify the change is trace-only. Mitigations:
- behavior-invariance tests in every such PR (enforces decision-logic unchanged).
- PR review (human gate).
- Explicit audit trail in commit message and evidence report.

### Q: Does it require full lineage despite j13 not needing it?

**A**: No. The design explicitly treats alpha internals as black-box. Profile fingerprint is the only identity required. No parent-child ancestry, no per-alpha formula ancestry, no semantic explanation.

### Q: Does it blur the line between telemetry and strategy changes?

**A**: No — §06 permission matrix explicitly separates:
- **Telemetry-only order** (e.g., P7-PR4-LITE) = emits metrics; cannot change generation budget.
- **Generation-policy order** (e.g., 0-9O) = changes generation budget; requires explicit authorization.

Even if 0-9O runs against live telemetry, the budget shift is a separate authorized change, not an automatic consequence of telemetry.

## 4. Must-fix-before-implementation items (carried into P7-PR4-LITE + 0-9O)

1. **Counter conservation invariant test** in P7-PR4-LITE: for every batch, `entered = passed + rejected + skipped`. A bug in metric emission that violates this could silently corrupt profile scores.
2. **Profile fingerprint canonicalization test**: same profile config → same fingerprint. Cross-Python-version stable.
3. **Scoring monotonicity test**: swapping a "good" profile for a strictly-worse profile in metrics must produce a ≤ change in composite score.
4. **Feedback decision record append-only test**: records cannot be edited in place; any modification creates a new record with its own `decision_id`.
5. **Exception-safe emission test**: emission failure does NOT affect the Arena pass/fail observed by an external oracle (already covered by P7-PR3 tests, extend to arena_batch_metrics emission).
6. **Profile deprecation requires order flag**: the budget allocator cannot zero-out a profile without a corresponding explicit deprecation record signed in a PR.

## 5. Adversarial test cases recommended for P7-PR4-LITE / 0-9O

- `test_emitter_failure_never_changes_arena_decision_output`
- `test_bad_counter_detected_and_flagged_without_corrupting_score`
- `test_profile_fingerprint_cross_process_stable`
- `test_scoring_monotonic_in_pass_rate`
- `test_scoring_penalty_dominates_when_oos_fail_rises`
- `test_budget_allocator_respects_exploration_floor`
- `test_budget_allocator_refuses_to_zero_active_profile_without_order_flag`
- `test_feedback_decision_record_append_only`
- `test_no_telemetry_change_alters_arena2_pass_output_on_fixed_input`

## 6. Residual risk statement

Even after all mitigations, the black-box optimization design has these irreducible risks:

1. **Measurement lag** — short observation windows may produce high-variance profile scores. Mitigation: explicit N-round windowing (e.g., ≥ 20 batches).
2. **Concept drift** — market regime shift invalidates historical profile scores. Mitigation: regime-aware profile definitions; profile deprecation protocol.
3. **Adversarial market conditions** — a profile that "passes" on historical data fails catastrophically in unfamiliar regime. Mitigation: CANARY + drawdown guard + human-in-loop at production step.

These are strategic risks inherent to quant trading, not defects of the design. The design SURFACES them (via metrics) rather than hiding them.

## 7. Final red-team verdict

**The 0-9N design does NOT introduce unacceptable risk** if:

1. All items in §4 are enforced in P7-PR4-LITE + 0-9O.
2. The permission matrix in §06 is respected without escalation.
3. CANARY (0-9S) is mandatory before production (0-9T).
4. Behavior-invariance tests are extended per §5 as the program unfolds.

**The design DOES require careful implementation discipline** to stay on the safe side of the governance boundaries. The quality of the design is secondary to the quality of the human and automated gates enforcing it.
