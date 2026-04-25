# 0-9R — Sparse-Candidate Black-Box Optimization Design Final Report

## 1. Status

**COMPLETE — pending Gate-A / Gate-B / signed merge on Alaya side.**

Local design package complete (8 mandatory design docs + this final
report). Documentation-only PR; zero runtime code modifications.

## 2. Baseline

- origin/main SHA at start: `8921a5093dff8e746ecf8b54d7f99fae0b88a111`
- local main SHA at start: `8921a5093dff8e746ecf8b54d7f99fae0b88a111`
- branch: `phase-7/0-9r-sparse-candidate-blackbox-optimization-design`
- PR URL: filled in after `gh pr create`
- merge SHA: filled in after merge
- signature verification: ED25519 SSH `SHA256:vzKybH9THchzB17tZOfkJZPRI/WGkTcXxd/+a7NciC8` (same key as P7-PR4B PR #18 / 0-9O-B PR #19)

## 3. Mission

Design — but do not implement — the sparse-candidate black-box
optimization program for ZANGETSU. Use existing Arena pass-rate
telemetry, `generation_profile_metrics`, and dry-run feedback budget
allocator diagnostics to define how `SIGNAL_TOO_SPARSE` should be
reduced through future generation-profile policy interventions, with
strict guardrails against Arena weakening, threshold relaxation, and
edge-quality degradation.

## 4. Strategic premise

| Premise | Status |
| --- | --- |
| Black-box alpha accepted | ✅ no per-alpha lineage required |
| Arena pass-rate telemetry required | ✅ delivered by P7-PR4-LITE + P7-PR4B |
| Profile identity required | ✅ delivered by 0-9O-A |
| Profile-level scoring required | ✅ delivered by 0-9O-A |
| Three-state confidence required | ✅ delivered by P7-PR4B |
| Dry-run allocator required | ✅ delivered by 0-9O-B |
| Full alpha lineage required | ❌ explicitly rejected (§3.25) |
| Formula explainability required | ❌ explicitly rejected (§3.26) |
| Arena weakening as default solution | ❌ explicitly rejected (§3.30) |
| Lower `A2_MIN_TRADES` as default solution | ❌ explicitly rejected (§3.30) |

The sparse-candidate problem is a **profile-level systemic issue**
that must be addressed by **profile-level policy**, never by relaxing
Arena gates or thresholds.

## 5. Current bottleneck

`SIGNAL_TOO_SPARSE`. Dominant rejection reason at A2 (V10 path) per
`arena_rejection_taxonomy` mappings; surfaced by P7-PR4B's
aggregate `arena_batch_metrics` and 0-9O-B's allocator
`observed_bottleneck` classification.

Detailed root-cause: `01_sparse_candidate_root_cause_model.md`.

## 6. What changed

| File | Type | Notes |
| --- | --- | --- |
| `docs/recovery/20260424-mod-7/0-9r/01_sparse_candidate_root_cause_model.md` | new doc | SIGNAL_TOO_SPARSE Arena-level model |
| `docs/recovery/20260424-mod-7/0-9r/02_generation_profile_intervention_taxonomy.md` | new doc | 11 intervention classes + risk grading + sequence |
| `docs/recovery/20260424-mod-7/0-9r/03_allocator_diagnostic_interpretation_plan.md` | new doc | Allocator output → intervention selection rules |
| `docs/recovery/20260424-mod-7/0-9r/04_anti_overfit_guardrails.md` | new doc | G1–G13 hard guardrails |
| `docs/recovery/20260424-mod-7/0-9r/05_ab_evaluation_and_canary_readiness.md` | new doc | A/B cohort design, S1–S12 success / F1–F8 failure / rollback / CR1–CR9 + PR1–PR6 |
| `docs/recovery/20260424-mod-7/0-9r/06_governance_permission_matrix.md` | new doc | 17 task types × risk × authorization |
| `docs/recovery/20260424-mod-7/0-9r/07_red_team_risk_register.md` | new doc | R-01 to R-14 adversarial review |
| `docs/recovery/20260424-mod-7/0-9r/08_future_0-9r_impl_order_draft.md` | new doc | NOT AUTHORIZED future order draft |
| `docs/recovery/20260424-mod-7/0-9r/09_*.md` | this file | final report |

**Zero runtime files modified.** No `arena_pipeline.py`,
`arena23_orchestrator.py`, `arena45_orchestrator.py`, `arena_gates.py`,
`feedback_budget_allocator.py`, `feedback_decision_record.py`,
`generation_profile_metrics.py`, `generation_profile_identity.py`,
`zangetsu/config/`, `zangetsu/engine/`, `zangetsu/live/` change.
No tests added — documentation-only design package.

## 7. Root-cause model summary

`SIGNAL_TOO_SPARSE` is a Arena-level, profile-level bottleneck:

- **Operationally**: candidate produces too few trades (< 25) or too
  few positive-direction observations (`pos_count < 2`) on the
  evaluation window, blocking statistical-significance gating at A2 /
  A3.
- **Surfaced via**: `arena_rejection_taxonomy.classify` mapping
  `[V10]: trades=N < 25` / `[V10]: pos_count=N` / `<2 valid
  indicators` / `2IND-REJECT` log lines from
  `arena23_orchestrator.process_arena2` and
  `arena23_orchestrator.process_arena3`.
- **Aggregated via**: P7-PR4B's per-stage `arena_batch_metrics`,
  flushed every 20 champions per (stage × profile_id).
- **Scored via**: 0-9O-A's `compute_profile_score` with
  `w5_signal_too_sparse_penalty = 0.25`.
- **Diagnosed via**: 0-9O-B's `classify_bottleneck` with
  `BOTTLENECK_DOMINANCE_THRESHOLD = 0.40`.
- **Authoritative deployable_count source**: unchanged —
  `champion_pipeline.status = 'DEPLOYABLE'`.

Sufficient evidence for intervention requires:

1. `confidence == CONFIDENCE_A1_A2_A3_METRICS_AVAILABLE` per profile.
2. `sample_size_rounds >= 20` per profile.
3. `observed_bottleneck == SIGNAL_TOO_SPARSE_DOMINANT` for ≥ 3
   consecutive allocator runs.
4. ≥ 2 independent profiles showing dominance.
5. `unknown_reject_rate < 0.05` (no observation blind spots).
6. dry-run weight shift sign-stable for ≥ 5 consecutive runs.

Insufficient evidence (any single weakness disqualifies):

- single-batch / single-round observation
- non-FULL confidence
- < 20 rounds
- missing A2/A3 metrics
- `unknown_reject_rate >= 0.20` (counter inconsistency)
- A2 pass_rate viewed in isolation
- no regime / time-split breakdown
- non-production-equivalent environment

Detailed: `01_sparse_candidate_root_cause_model.md`.

## 8. Intervention taxonomy

11 intervention classes graded by risk and implementation eligibility:

| Code | Class | Status | Risk |
| --- | --- | --- | --- |
| PB-SHIFT | Profile budget shift | HIGH_RISK_IMPL_CANDIDATE | High |
| PB-SUPPRESS | Profile suppression | HIGH_RISK_IMPL_CANDIDATE | High |
| PB-FLOOR | Exploration floor preservation | SAFE_IMPL_CANDIDATE | Low |
| PB-QUARANTINE | Profile quarantine | HIGH_RISK_IMPL_CANDIDATE | High |
| PB-RESURRECT | Profile resurrection | SAFE_IMPL_CANDIDATE (depends on QUARANTINE) | Medium |
| PB-MUT | Mutation pressure adjust | HIGH_RISK_IMPL_CANDIDATE | High |
| PB-DENSITY | Density-aware preset | HIGH_RISK_IMPL_CANDIDATE | High |
| PB-DIV | Diversity-preserving sampling | SAFE_IMPL_CANDIDATE | Low |
| PRE-A2-SCREEN | Pre-A2 density screen | HIGH_RISK_IMPL_CANDIDATE | High |
| PB-SMOOTH | Profile score smoothing | SAFE / HIGH (scope-dependent) | Low / High |
| PB-VAR | Profile variance penalty | DESIGN_ONLY | Medium |

Recommended implementation order (lowest risk first): PB-FLOOR +
PB-DIV → PB-SHIFT (dry-run) → PB-SHIFT (CANARY apply) → PB-SUPPRESS
(CANARY) → PB-QUARANTINE + PB-RESURRECT (CANARY) → PB-DENSITY → PB-MUT
/ PRE-A2-SCREEN.

Forbidden classes (explicitly outside any sparse-candidate scope):
lowering `A2_MIN_TRADES`; weakening `arena2_pass` / `arena3_pass` /
`arena4_pass`; changing A3 OOS thresholds; changing CANDIDATE →
DEPLOYABLE gate; changing `deployable_count` semantics.

Detailed: `02_generation_profile_intervention_taxonomy.md`.

## 9. Allocator diagnostic interpretation

Future readers of `DryRunBudgetAllocation` events must follow:

1. Treat `confidence != CONFIDENCE_A1_A2_A3_METRICS_AVAILABLE` as
   non-actionable.
2. Verify `allocator_version == "0-9O-B"`, `mode == "DRY_RUN"`,
   `applied is False`. Any deviation triggers incident review.
3. Require `actionable_profile_count >= 2` for any weight-shift
   recommendation; `1` allows only PB-FLOOR / PB-DIV; `0` blocks.
4. Treat `proposed_profile_weights_dry_run` as **direction**, not as
   apply command. Use sign-of-delta vs `previous_profile_weights` and
   require ≥ 5 consecutive runs of stable direction.
5. Reject any profile with `COUNTER_INCONSISTENCY` or
   `MISSING_A2_A3_METRICS` reasons — allocator must not act on
   profiles in observation blind spots.
6. Map `observed_bottleneck` to intervention class per the table in
   `03_allocator_diagnostic_interpretation_plan.md` §4. Note that
   `OOS_FAIL_DOMINANT` and `UNKNOWN_REJECT_DOMINANT` do **not**
   trigger sparse interventions — they signal different problems
   (robustness vs taxonomy).
7. UNKNOWN_PROFILE is capped at exploration floor by allocator;
   readers must not promote it.
8. Future runtime consumer must add EMA smoothing (`α ≤ 0.2`,
   window ≥ 5), max-step limits (≤ 10% absolute per round), hard
   floor (≥ 0.05), and sum-1.0 sanity check.

Detailed: `03_allocator_diagnostic_interpretation_plan.md`.

## 10. Anti-overfit guardrails

13 hard guardrails (G1–G13):

| Code | Rule |
| --- | --- |
| G1 | A2 pass_rate cannot be the sole objective |
| G2 | A3 pass_rate degradation tolerance ≤ 5 pp absolute |
| G3 | `deployable_count` must not drop (7-day rolling median) |
| G4 | `unknown_reject_rate` must stay < 0.05 |
| G5 | `oos_fail_rate` must not increase ≥ 5 pp absolute |
| G6 | `profile_score` must use ≥ 20 round smoothing |
| G7 | Results compared per regime if available |
| G8 | Results compared per time-split |
| G9 | `EXPLORATION_FLOOR = 0.05` always preserved |
| G10 | No profile permanently killed without cooldown / re-entry |
| G11 | Sparse reduction must not come from threshold relaxation |
| G12 | Sparse reduction must not come from fake `passed_count` |
| G13 | Sparse reduction must not come from `deployable_count` semantic change |

Plus detection rules for: pass-rate overfitting, trade-count
inflation, weaker signal quality, regime concentration, sample-size
insufficiency, profile collapse, OOS degradation,
counter-inconsistency drift.

Detailed: `04_anti_overfit_guardrails.md`.

## 11. A/B evaluation and CANARY readiness

### 11.1 A/B design

- Cohort split by passport tag or worker_id.
- Per-strategy isolated (`STRATEGY_ID`).
- Baseline = current (post-0-9O-B) generation pipeline.
- Treatment = future 0-9R-IMPL intervention.
- Min ≥ 20 rounds × ≥ 7 calendar days × ≥ 2 macro regimes.
- Composite scoring: `0.4 * a2_pass_rate + 0.4 * a3_pass_rate + 0.2 *
  deployable_density`.

### 11.2 Success criteria (S1–S12)

All required: A2 SIGNAL_TOO_SPARSE rate ↓ ≥ 20% relative; A2
pass_rate ↑ ≥ 3 pp absolute or ≥ 15% relative; A3 pass_rate not
degrading > 2 pp; OOS_FAIL not increasing > 3 pp; deployable_count
not degrading; UNKNOWN_REJECT < 0.05; no threshold change; no Arena
pass/fail change; no champion promotion change; no execution / capital
/ risk change; per-regime deployable_count stable; composite score
↑ at ≥ 1σ.

### 11.3 Failure criteria (F1–F8)

Any triggers rollback: A2 ↑ but A3 collapse ≥ 5 pp; A2 ↑ but
deployable_count ↓; OOS_FAIL ↑ ≥ 5 pp; UNKNOWN_REJECT ↑ ≥ 2 pp;
trade-count inflation + pnl/trade ↓ ≥ 20%; profile collapse (< 50%
baseline actionable); exploration floor violated; single-regime /
single-time-slice domination.

### 11.4 CANARY readiness (CR1–CR9)

Required for 0-9S: 7-day stable dry-run, daily actionable
allocation, sign-stable shifts, isolation tests, 3× rollback drill,
Calcifer outcome watchdog, branch protection intact, controlled-diff
clean, j13 explicit authorization.

### 11.5 Production readiness (PR1–PR6)

CANARY success + 14-day stable + deployable improvement + no open
incidents + j13 production order + governance intact.

Detailed: `05_ab_evaluation_and_canary_readiness.md`.

## 12. Governance boundary

Permission matrix (17 task types) classifies all sparse-candidate
related work by risk:

- Documentation-only (Low) — **0-9R is here.**
- Offline analytics (Low) — within 0-9R if docs only.
- Runtime telemetry (Medium) — separate trace-only order required.
- Dry-run allocator change (Medium) — separate dry-run-only order.
- Real budget reweighting (High) — explicit 0-9R-IMPL + CANARY pass.
- Sampling policy change (High) — separate generation-policy order.
- Candidate prefilter change (High) — separate generation-policy order.
- Profile quarantine (High) — explicit order with re-entry rule.
- Threshold change (Critical) — explicit threshold order; never as
  side effect.
- Arena pass/fail change (Critical) — explicit Arena order.
- Champion promotion change (Critical) — explicit promotion order.
- Deployable_count semantics (Critical) — explicit semantics order.
- Execution / capital / risk (Critical) — execution / risk order.
- CANARY (High) — explicit 0-9S.
- Production rollout (Critical) — explicit 0-9T.
- Governance config (Critical) — governance-only order.

j13 generic authorization (e.g. "全權處理 sparse 問題") **does not**
substitute for an order-specific authorization sentence. Every
sparse-candidate task that crosses class boundaries requires a fresh
order with explicit scope and limits.

Detailed: `06_governance_permission_matrix.md`.

## 13. Red-team findings

14 risks identified (R-01 to R-14), each with detection tests and
mitigations:

| ID | Summary |
| --- | --- |
| R-01 | Indirect Arena weakening via PRE-A2-SCREEN truncation |
| R-02 | Pure pass-rate optimization sacrificing edge quality |
| R-03 | Hidden threshold change via per-profile relaxation factor |
| R-04 | Hidden sampling change via PB-MUT |
| R-05 | Bypassing `applied=false` in runtime consumer |
| R-06 | Dry-run / runtime mode confusion via runtime config flag |
| R-07 | Overfitting to recent log noise |
| R-08 | Sparse-prone profiles dominating allocation |
| R-09 | Suppressing useful rare-event alphas |
| R-10 | UNKNOWN_REJECT drift misclassifying sparse changes |
| R-11 | CANARY / production environment divergence |
| R-12 | Irreversible rollback due to candidate pool poisoning |
| R-13 | Multi-strategy cross-contamination |
| R-14 | Audit trail incompleteness |

Conclusion: 0-9R design has no internal fatal gap, but **all** future
0-9R-IMPL activations must satisfy the 14 mitigations + the 13
guardrails + S1–S12 + the governance permission matrix + j13's
explicit order.

Detailed: `07_red_team_risk_register.md`.

## 14. Future implementation order

`08_future_0-9r_impl_order_draft.md` — full order text for
**0-9R-IMPL — Sparse-Candidate Black-Box Optimization Implementation**:

- Scope limited to SAFE_IMPL_CANDIDATE classes (PB-FLOOR + PB-DIV +
  PB-SHIFT in dry-run apply mode).
- New module `zangetsu/services/feedback_budget_consumer.py` with EMA
  smoothing, floor / diversity enforcement, hot-swap-able weight
  cache, rollback path.
- ≥ 60 tests covering schema / EMA / floor / diversity / isolation /
  rollback / governance.
- DRY_RUN mode hard-coded (no runtime-switchable flag).
- Required documentation under
  `docs/recovery/20260424-mod-7/0-9r-impl/`.
- ≥ 7-day post-merge dry-run stability before completion.

**Marked NOT AUTHORIZED**. j13 must issue a separate order to start.

## 15. Behavior invariance

Explicit confirmation:

- No runtime code changed.
- No alpha generation changed.
- No formula generation changed.
- No mutation / crossover changed.
- No search policy changed.
- No generation budget changed.
- No sampling weights changed.
- No threshold changed (`A2_MIN_TRADES = 25` preserved; ATR / TRAIL /
  FIXED grids preserved; A3 segment thresholds preserved).
- No Arena pass/fail changed (`arena_gates.arena2_pass` /
  `arena3_pass` / `arena4_pass` unchanged).
- No champion promotion changed
  (`arena45_orchestrator.maybe_promote_to_deployable` unchanged;
  CANDIDATE → DEPLOYABLE gate untouched).
- No `deployable_count` semantic changed
  (`champion_pipeline.status='DEPLOYABLE'` remains the authoritative
  source; VIEW unchanged).
- No execution / capital / risk changed.
- No CANARY started.
- No production rollout started.
- No applied path introduced.
- No `applied=false` invariant weakened.
- No allocator output connected to runtime generation.
- No per-alpha lineage required.
- No formula explainability required.

## 16. Controlled-diff

Expected classification: **EXPLAINED** (docs-only).

```
Zero diff:                    ~43 fields (incl. all 6 CODE_FROZEN runtime SHAs)
Explained diff:               1 field   — repo.git_status_porcelain_lines
Explained TRACE_ONLY diff:    0 fields
Forbidden diff:               0 fields
```

No `--authorize-trace-only` flag needed. CODE_FROZEN runtime SHAs
unchanged: `zangetsu_settings_sha`, `arena_pipeline_sha`,
`arena23_orchestrator_sha`, `arena45_orchestrator_sha`,
`calcifer_supervisor_sha`, `zangetsu_outcome_sha`.

## 17. Gate-A

Expected: **PASS** (no runtime SHA changed → no governance-relevant
delta; Phase 7 entry prerequisites verifier should treat docs-only
PR as eligible).

## 18. Gate-B

Expected: **PASS** (PR-trigger restored by 0-9I; per-module summary
should classify as "skipping" when no module-relevant deltas exist).

## 19. Branch protection

Expected unchanged on `main`:

- `enforce_admins=true`
- `required_signatures=true`
- `linear_history=true`
- `allow_force_pushes=false`
- `allow_deletions=false`

This PR does not modify governance configuration.

## 20. Remaining risks

- **Design-only cannot prove improvement.** This package establishes
  the framework but does not validate that any specific intervention
  actually reduces SIGNAL_TOO_SPARSE without harming downstream.
- **Future implementation may overfit.** S1–S12 + G1–G13 + R-01 to
  R-14 are necessary but not sufficient — sparse-domain edge cases
  may still slip through.
- **Sparse reduction can harm edge.** The whole anti-overfit
  guardrail set exists because reducing rejection rate is not the
  same as improving profit quality.
- **CANARY required before live action.** No allocator output reaches
  runtime generation until 0-9S CANARY validates an
  intervention end-to-end.
- **`A2_MIN_TRADES = 25` must remain protected.** Any future order
  proposing to lower it as a sparse fix must be rejected at the
  governance permission matrix and red-team review level.
- **Profile identity propagation gap.** A1 currently does not persist
  `generation_profile_id` into passport (0-9O-A wired identity into
  A1 telemetry only). Future passport-persistence work would let
  P7-PR4B's A2/A3 telemetry pick up real upstream identity instead of
  falling back to orchestrator consumer profile. Unrelated to 0-9R
  but worth noting for sequencing.

## 21. Recommended next action

**TEAM ORDER 0-9R-IMPL — Sparse-Candidate Black-Box Optimization
Implementation.** Implement SAFE_IMPL_CANDIDATE classes (PB-FLOOR +
PB-DIV + PB-SHIFT in dry-run apply mode) per the
`08_future_0-9r_impl_order_draft.md` specification. Strict scope:
new `feedback_budget_consumer.py` module only; no Arena / threshold
/ promotion / execution change; DRY_RUN mode hard-coded.

If j13 explicitly wants deployment-path validation first →
**TEAM ORDER 0-9S — CANARY Readiness Gate** to design and stage the
CANARY apply switch.

If j13 wants observability completeness first →
optional **0-9P — Reject Taxonomy Completeness Audit** to lower
UNKNOWN_REJECT below 0.05 across all profiles before any
sparse-candidate intervention.
