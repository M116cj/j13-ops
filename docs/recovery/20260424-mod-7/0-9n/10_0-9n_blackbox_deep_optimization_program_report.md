# TEAM ORDER 0-9N — Black-Box Deep Optimization Program Report

## 1. Status

**COMPLETE** (documentation-only).

## 2. Scope

**Documentation / design / cartography only.** 0 runtime code changes. 0 threshold changes. 0 Arena pass/fail changes. 0 alpha generation changes. 0 champion promotion changes. 0 execution/capital/risk changes. No CANARY. No production rollout.

## 3. Baseline

| Field | Value |
|---|---|
| origin/main (pre) | `e3cadea8862787df418cdab896f8af1ed699b46e` |
| Last completed order | TEAM ORDER 0-9M — Phase 7 Controlled-Diff Acceptance Rules Upgrade (PR #14 merged) |
| Branch | `phase-7/0-9n-blackbox-deep-optimization-design` |
| Pre-snapshot manifest | `0ac03471fed6d6441c030a481927959d650c939549ddf8a37b9436f59ad49212` |

## 4. Strategic pivot

Before 0-9N, ZANGETSU Phase 7 was trending toward full per-alpha lifecycle provenance (P7-PR3 delivered A1 trace-native emission; future P7-PR4/5 would extend to A2/A3 with per-candidate FULL provenance as the target).

j13 has clarified that:
- **Alpha internals may remain black-box.**
- **Only Arena-level alpha pass-rate traceability is required.**

0-9N re-scopes the Phase 7 roadmap accordingly:

- **White-box**: Arena pass/reject aggregates per stage per batch per generation profile.
- **Black-box**: AlphaEngine internals, formula lineage, per-alpha explainability.

## 5. Design artifacts delivered

| # | File | Role |
|--:|---|---|
| 01 | `01_repo_cartography.md` | Repo state + alpha flow + Arena flow + telemetry stack + governance surface |
| 02 | `02_arena_pass_rate_telemetry_contract.md` | `arena_batch_metrics` + `arena_stage_summary` schemas |
| 03 | `03_generation_profile_metrics_contract.md` | `generation_profile_metrics` schema + scoring model + fingerprint canonicalization |
| 04 | `04_blackbox_feedback_guided_search_design.md` | Feedback loop architecture + budget allocator pseudocode + safety invariants |
| 05 | `05_sparse_candidate_bottleneck_plan.md` | SIGNAL_TOO_SPARSE diagnosis + correct solution path (improve generation, not weaken Arena) |
| 06 | `06_governance_boundary_map.md` | 20-row permission matrix + order-class → scope map + forbidden escalation paths |
| 07 | `07_performance_hotspot_report.md` | 7 safe optimization candidates + forbidden categories |
| 08 | `08_red_team_risk_register.md` | 15 risk rows + 15 adversarial questions answered + must-fix items |
| 09 | `09_implementation_roadmap.md` | P7-PR4-LITE → 0-9O → 0-9R → 0-9S → 0-9T sequence + milestone DONE criteria |
| 10 | `10_0-9n_blackbox_deep_optimization_program_report.md` | This summary |

All under `docs/recovery/20260424-mod-7/0-9n/`.

## 6. Arena pass-rate telemetry contract summary

**Schemas defined** (not implemented in 0-9N):

- `arena_batch_metrics`: per-batch-per-stage; entered/passed/rejected + reason distribution.
- `arena_stage_summary`: per-run-per-stage rollup; bottleneck_score.
- `generation_profile_metrics`: per-profile aggregate; profile_score + next_budget_weight.
- `feedback_decision_record`: append-only audit log for budget shifts.

**Deliberate omissions**:
- No per-alpha formula ancestry.
- No parent-child mutation lineage.
- No per-alpha semantic interpretability.
- No full CandidateLifecycle requirement in the feedback loop.

## 7. Generation profile metrics contract summary

Profile identity via canonical-JSON fingerprint (`SHA256(profile_config)`). Score = weighted sum of pass-rate metrics MINUS weighted sum of rejection / instability penalties. Budget allocator maps score → next_budget_weight with exploration_floor = 0.05.

## 8. Feedback-guided search design summary

Black-box alpha generator + white-box Arena telemetry + profile scoring + budget allocator. Arena decisions NEVER changed by feedback loop — only subsequent-round GENERATION BUDGET is shifted. Threshold-immovable.

## 9. Sparse-candidate plan summary

Current bottleneck: Arena 2 SIGNAL_TOO_SPARSE (88.2% of non-deployable rejections). Correct solution: tune generation profiles (under authorized 0-9R) to produce candidates that NATURALLY satisfy A2. **Wrong solution (EXPLICITLY REJECTED)**: lower `A2_MIN_TRADES`. 0-9M `NEVER_TRACE_ONLY_AUTHORIZABLE` + explicit threshold order is required to weaken Arena.

## 10. Governance boundary summary

20-row permission matrix separates:
- Documentation-only (0-9N)
- Telemetry / trace-only (P7-PR4-LITE)
- Generation-policy (0-9O / 0-9R)
- Threshold (separate explicit order)
- Arena-logic (separate explicit order)
- Promotion (separate explicit order)
- Execution (separate explicit order)
- CANARY (0-9S)
- Production (0-9T)

No order-class may escalate scope without new j13 authorization. `controlled-diff` + Gate-A + Gate-B + behavior-invariance tests enforce the boundary automatically.

## 11. Red-team verdict

Design surfaces 15 risks. All have mitigations (exploration_floor, multi-metric scoring, oos_fail_rate penalty, append-only decision records, human-in-loop at production). Must-fix items (counter conservation test, fingerprint stability test, scoring monotonicity test, append-only decision record test, emission failure safety test, exploration floor enforcement test) are carried into P7-PR4-LITE / 0-9O implementation phases.

Irreducible residual risks (measurement lag, concept drift, adversarial markets) are inherent to quant trading and are SURFACED by the design, not hidden.

**Red-team verdict: design is safe IF P7-PR4-LITE + 0-9O implementation discipline respects the governance boundaries.**

## 12. Performance optimization summary

7 safe optimization candidates identified. Three easy wins (bloom-before-compile, log-parse pre-filter, reconstruction result cache) may fold into P7-PR4-LITE. Two medium-risk candidates (batched val eval, early constant rejection) warrant standalone perf orders. Two high-risk candidates (batched alpha callable, per-symbol/regime parallelism) require explicit authorization due to AlphaEngine or state-isolation semantics.

## 13. Implementation roadmap summary

```
0-9N (this)  →  P7-PR4-LITE  →  0-9O  →  0-9R  →  0-9S  →  0-9T
design-only    telemetry         opti-     sparse    CANARY   production
(no runtime)   emission          mizer     tuning    (Arena   rollout
                                 impl      (policy)  unfreeze)
```

## 14. Validation

- Tests: 169/169 PASS unchanged (no runtime code changed; baseline preserved).
- Controlled-diff expected: **EXPLAINED** (0 forbidden; `diff_snapshots.py` is not in CODE_FROZEN catalog; only `docs/` + new snapshot files added).
- Gate-A + Gate-B expected: PASS on pull_request (doc PR touching `docs/recovery/**` + `docs/governance/snapshots/**`).
- Signed commit + branch protection intact.

## 15. Forbidden changes audit

- **Alpha generation**: unchanged ✓
- **Thresholds** (A2_MIN_TRADES etc.): unchanged ✓
- **Arena pass/fail behavior**: unchanged ✓
- **Champion promotion**: unchanged ✓
- **Execution / capital / risk**: unchanged ✓
- **CANARY**: NOT STARTED ✓
- **Production rollout**: NOT STARTED ✓
- **Full per-alpha lineage design**: **NOT REQUIRED** ✓ (explicit design choice per j13's direction)

## 16. Remaining risk

- **Trust-but-verify governance** (see 08 §4). The `--authorize-trace-only` flag relies on PR review + behavior-invariance tests for its final truth. 0-9M already mitigated this; 0-9N relies on the same guard.
- **CODE_FROZEN catalog expansion** (see 0-9M report §14). When new runtime files are added (e.g., 0-9O's `feedback_budget_allocator.py`), they must be added to `capture_snapshot.sh` CODE_FROZEN list — a governance step requiring its own order.
- **Baseline variance**. 6 deployable in 7 days = high per-batch variance. Optimizer must use N ≥ 20 rounds before acting on score deltas.

## 17. Recommended next action

**P7-PR4-LITE — Aggregate Arena Pass-Rate Telemetry**

Rationale:
- Implements §02 telemetry contract directly.
- Trace-only additive — uses 0-9M EXPLAINED_TRACE_ONLY pathway.
- Unblocks 0-9O (optimizer implementation needs real metric streams).
- Low risk; narrow scope; ~15-20 new tests.
- Can fold in 3 easy perf wins from `07_performance_hotspot_report.md`.

## 18. Correct wording

**Authorized** (used in this report):
- "0-9N = COMPLETE"
- "Documentation-only scope"
- "Arena pass-rate telemetry contract = DELIVERED"
- "Generation profile metrics contract = DELIVERED"
- "Feedback-guided search design = DELIVERED"
- "Sparse-candidate bottleneck plan = DELIVERED"
- "Implementation roadmap = DELIVERED"

**Forbidden** (NOT asserted anywhere in this report):
- "Arena 2 fixed"
- "Champion generation restored"
- "Production rollout started"
- "Thresholds optimized"

## 19. STOP

After signed PR merge and local main sync, 0-9N is COMPLETE and STOPPED. Awaiting j13 decision on the next order (P7-PR4-LITE recommended; alternatives listed in §09 §7).
