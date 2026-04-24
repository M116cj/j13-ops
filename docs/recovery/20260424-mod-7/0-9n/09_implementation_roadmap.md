# 09 — Implementation Roadmap

TEAM ORDER 0-9N §5 + §16 deliverable.

## 1. Order sequence

```
0-9N  ← THIS ORDER (design / cartography / roadmap ONLY; no runtime change)
  ↓
P7-PR4-LITE — Aggregate Arena pass-rate telemetry (trace-only, additive)
  ↓
0-9O — Feedback-guided generation profile scoring + budget allocator
  ↓
0-9R — Sparse-candidate generation-profile policy tuning
  ↓
0-9S — CANARY activation for the optimizer
  ↓
0-9T — Production rollout (only after CANARY evidence)
```

## 2. Per-order scope summary

### 2.1 P7-PR4-LITE — Aggregate Arena pass-rate telemetry

**Scope**:
- Add `arena_batch_metrics` + `arena_stage_summary` emission sites in:
  - `zangetsu/services/arena_pipeline.py` (A1 stage, per (symbol, regime) batch)
  - `zangetsu/services/arena23_orchestrator.py` (A2 + A3 stages)
- Extend `zangetsu/services/candidate_trace.py` with `build_arena_batch_metrics_event()` builder (uses same exception-safe emission pattern as P7-PR3).
- Add counter-conservation test, emission-failure-safety test, telemetry-version test.
- Additive-only; no Arena decision logic change; no threshold change.

**Order class**: Trace-only (per §06 #2 / #3).
**Controlled-diff expectation**: `EXPLAINED_TRACE_ONLY` on `config.arena_pipeline_sha` + `config.arena23_orchestrator_sha` via 0-9M `--authorize-trace-only` flags.
**Gate coverage**: Gate-A + Gate-B on pull_request.
**Tests**: ≥ 15 new test cases; 100% of existing baseline preserved.
**Rollback**: `git revert <merge_sha>` — restores pre-telemetry Arena.

**Bundled easy wins** (may fold in or ship separately):
- Bloom dedup re-order before compile (see `07_performance_hotspot_report.md §3.1`).
- Log-parse pre-filter (§3.6).
- Reconstruction result cache (§3.7).

### 2.2 0-9O — Feedback-guided generation profile scoring

**Scope**:
- New module `zangetsu/services/generation_profile_aggregator.py` consuming `arena_batch_metrics` stream + producing `generation_profile_metrics`.
- New module `zangetsu/services/feedback_budget_allocator.py` implementing scoring + budget shift per §04.
- New module emits `feedback_decision_record` events (append-only).
- Runtime wiring: `arena_pipeline.py` reads budget allocator output at start of each round.
- ≥ 20 new test cases (profile fingerprint, scoring, budget allocation, decision record).

**Order class**: Generation-policy (HIGH risk per §06 #5).
**Requires**: j13 explicit authorization + 0-9O order body.
**Controlled-diff**: `EXPLAINED_TRACE_ONLY` on arena_pipeline_sha; `EXPLAINED` on new modules.
**Gate coverage**: Gate-A + Gate-B; STRONG PR review.
**Safety invariants** (test-enforced):
- Scoring is pure function of metrics history.
- Budget allocation sums to `total_budget_next_round`.
- `exploration_floor = 0.05` enforced.
- Decision records append-only.
- No alteration of Arena decisions on current round.

**Expected behavior delta**: Arena decisions UNCHANGED per round. Only subsequent-round budget allocation shifts.

### 2.3 0-9R — Sparse-candidate generation-profile policy tuning

**Scope**:
- Generation profile definitions (new profiles + profile-level config).
- May NOT change thresholds; must NOT change Arena pass/fail; must NOT change AlphaEngine operators.
- A/B pairs of profiles with differing generation configs (see `05_sparse_candidate_bottleneck_plan.md §6`).
- Measurement-forward: each new profile starts at `exploration_floor` budget until N batches observed.

**Order class**: Generation-policy.
**Requires**: j13 explicit authorization.
**Requires explicit threshold order if** any attempt to change `A2_MIN_TRADES` / `ENTRY_THR` / `MIN_HOLD` / `COOLDOWN` is proposed — 0-9R alone does NOT authorize threshold changes.

**Expected outcome**: profiles with measurably lower `signal_too_sparse_rate` and higher `avg_a2_pass_rate` appear in the pool. Aggregate `deployable_count` improves.

### 2.4 0-9S — CANARY activation

**Scope**:
- Coordinate with Arena unfreeze (which is a separate upstream order).
- Run optimizer + new generation profiles in live Arena for a bounded canary window (e.g., 1 symbol, 1 regime, 1 week).
- Baseline measurement first (Profile A = control, current production); then 50/50 A/B with Profile B.
- Abort criteria: `oos_fail_rate` regression, drawdown breach, stability index crash.

**Order class**: CANARY (HIGH risk per §06 #12).
**Requires**: explicit CANARY order + Arena unfreeze order + pre-authored rollback runbook.
**Success criteria**: Profile B dominates Profile A on at least 3 of (A2 pass_rate, A3 pass_rate, deployable_count) WITHOUT regression on any of (oos_fail_rate, instability_index, drawdown).

### 2.5 0-9T — Production rollout

**Scope**: Full-traffic optimizer + tuned profiles. Remove Arena freeze. Enable full candidate pipeline.

**Order class**: Production (CRITICAL).
**Requires**: CANARY evidence PASS (0-9S) + j13 human sign-off + standing rollback procedure.

## 3. Milestone checklist

Each milestone is considered complete ONLY when all items below are true. All require signed PR + Gate-A + Gate-B.

### P7-PR4-LITE DONE criteria

- [ ] `arena_batch_metrics` emission observed in engine.jsonl during a test run.
- [ ] `arena_stage_summary` emission at run close.
- [ ] Counter conservation test passing: `entered == passed + rejected + skipped`.
- [ ] Behavior-invariance: `test_arena_gates_thresholds_*` pass; `test_arena2_pass_decision_unchanged_*` pass.
- [ ] Test count: baseline + ≥ 15 new P7-PR4-LITE tests.
- [ ] Controlled-diff: `EXPLAINED_TRACE_ONLY` on arena_pipeline_sha + arena23_orchestrator_sha.
- [ ] Signed PR merged; verified=true on main.

### 0-9O DONE criteria

- [ ] `generation_profile_metrics` events emitted per run.
- [ ] Budget allocator produces valid allocation summing to total_budget_next_round.
- [ ] `feedback_decision_record` emitted on every budget shift.
- [ ] Exploration floor enforced: no active profile at 0 budget.
- [ ] Test count: baseline + ≥ 20 new 0-9O tests covering scoring + allocator + decision records.
- [ ] Controlled-diff: `EXPLAINED_TRACE_ONLY` on arena_pipeline_sha; `EXPLAINED` elsewhere.
- [ ] Signed PR merged.

### 0-9R DONE criteria

- [ ] New profile(s) active in pool.
- [ ] Measurement window completed (≥ 20 batches per profile).
- [ ] Comparison report shows treatment profile pass-rate delta without quality regression.
- [ ] No threshold change occurred.
- [ ] Signed PR merged.

### 0-9S CANARY DONE criteria

- [ ] Arena unfreeze order executed.
- [ ] 1 symbol × 1 week CANARY window completed.
- [ ] Baseline vs treatment comparison report.
- [ ] No `oos_fail_rate` / drawdown / stability regression.
- [ ] Rollback runbook dry-run executed successfully.
- [ ] Signed PR with evidence merged.

### 0-9T DONE criteria

- [ ] Full-traffic enable.
- [ ] First 48 hours telemetry monitored.
- [ ] Automated rollback path armed.
- [ ] j13 human sign-off recorded.
- [ ] Signed PR merged.

## 4. Dependency graph

```
0-9N (this order)
  ↓
P7-PR4-LITE ← P7-PR3 (already merged)
  ↓
0-9O ← P7-PR4-LITE
  ↓
0-9R ← 0-9O
  ↓
0-9S ← 0-9R AND Arena-unfreeze (separate order)
  ↓
0-9T ← 0-9S evidence PASS
```

Arena unfreeze is a **separate governance order** not in this program sequence. It must be authorized independently and is a hard prerequisite for 0-9S.

## 5. Estimated timeline

Timeline is rough; actual pacing depends on j13 order cadence and observation windows. Historical Phase 7 order cadence has been ~1 order per session (MOD-7A through 0-9M).

| Order | Est. complexity | Est. duration |
|---|---|---|
| P7-PR4-LITE | Medium (2 files touched; telemetry emission; tests) | 1 session |
| 0-9O | High (new modules; scoring math; budget allocator; extensive tests) | 1-2 sessions |
| 0-9R | Medium (profile definitions + measurement harness) | 1 session + N-round observation window (20 batches) |
| 0-9S | High (Arena unfreeze coordination; live measurement; abort protocol) | 1-2 weeks wall-clock |
| 0-9T | Medium code, high risk | 1 session + ongoing monitoring |

## 6. Roadmap invariants (Phase 7 contract)

Across all future orders:

1. Signed PR-only flow — no direct main push.
2. Branch protection enforced: enforce_admins=true, req_sig=true, linear=true, no force push, no deletions.
3. Gate-A + Gate-B both trigger + pass on every PR.
4. Controlled-diff must be EXPLAINED / EXPLAINED_TRACE_ONLY; any FORBIDDEN triggers STOP.
5. Behavior-invariance tests extend with each order; existing tests never disabled.
6. Threshold changes ALWAYS require separate threshold order + explicit authorization.
7. Arena pass/fail changes ALWAYS require separate Arena-logic order.
8. Alpha operator changes ALWAYS require separate alpha-logic order.
9. Production rollout ALWAYS requires CANARY evidence + human sign-off.

## 7. Recommended next order

**P7-PR4-LITE** — Aggregate Arena Pass-Rate Telemetry.

Rationale:
- Directly enables §02 telemetry contract in runtime.
- Trace-only additive path; low risk.
- Uses 0-9M `EXPLAINED_TRACE_ONLY` classification — no per-PR exception record needed.
- Unblocks 0-9O (which needs real metric streams to score profiles).
- Scoping is narrow: ~2 runtime files touched, ~15-20 new tests, ~5 new docs.

Alternative next orders (each valid, j13 decision):
- **0-9P — Log-tooling acceleration + reconstruction result cache**. Performance tool order; low risk; speeds up all subsequent SHADOW / CANARY work.
- **Arena unfreeze order** — prerequisite for eventual 0-9S. High risk but not blocked by telemetry.

## 8. What 0-9N itself delivers

This roadmap document AND the 9 sibling design artifacts:

1. `01_repo_cartography.md`
2. `02_arena_pass_rate_telemetry_contract.md`
3. `03_generation_profile_metrics_contract.md`
4. `04_blackbox_feedback_guided_search_design.md`
5. `05_sparse_candidate_bottleneck_plan.md`
6. `06_governance_boundary_map.md`
7. `07_performance_hotspot_report.md`
8. `08_red_team_risk_register.md`
9. `09_implementation_roadmap.md` (this file)
10. `10_0-9n_blackbox_deep_optimization_program_report.md` (evidence summary)

All committed under `docs/recovery/20260424-mod-7/0-9n/` via signed PR.

No runtime code touched. No tests modified. No thresholds changed. No Arena logic altered. CANARY / production NOT started.
