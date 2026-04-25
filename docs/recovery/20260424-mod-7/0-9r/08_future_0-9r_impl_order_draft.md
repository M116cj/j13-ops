# 08 — Future Order Draft: TEAM ORDER 0-9R-IMPL

> **NOT AUTHORIZED IN 0-9R.**
> **DO NOT EXECUTE.**
> **REQUIRES SEPARATE j13 AUTHORIZATION.**
>
> 本檔僅為設計草稿，0-9R 完成後若 j13 顯式授權方可啟動。

---

## TEAM ORDER 0-9R-IMPL — Sparse-Candidate Black-Box Optimization Implementation

You are Claude CLI operating inside the ZANGETSU repository.

TEAM ORDER:
0-9R-IMPL — Sparse-Candidate Black-Box Optimization Implementation

MISSION:
Implement the selected generation-profile policy intervention designed
in 0-9R, in **dry-run apply mode** first, then in CANARY mode after
0-9S. Use the existing dry-run feedback budget allocator output to
drive the intervention. Do NOT modify Arena, alpha generation logic,
formula generation logic, mutation/crossover behavior, search policy,
A2_MIN_TRADES, Arena pass/fail logic, champion promotion, or
deployable_count semantics.

This order starts after 0-9R completed the design package.

This order is **implementation, scoped to the SAFE_IMPL_CANDIDATE
classes only** unless j13 explicitly extends scope:

- PB-FLOOR (Profile exploration floor preservation)
- PB-DIV (Profile diversity-preserving sampling)
- PB-SHIFT in **dry-run apply** mode only

HIGH_RISK classes (PB-SUPPRESS / PB-QUARANTINE / PB-MUT / PB-DENSITY /
PRE-A2-SCREEN) require independent j13 orders and are **not** included
in this draft.

STOP after signed PR merge, evidence report, dry-run apply stable for
≥ 7 days, and local main sync.

---

## 0. Baseline

Current main: <fill in when 0-9R-IMPL is authorized>

Last completed order: TEAM ORDER 0-9R — Sparse-Candidate Black-Box
Optimization Design.

0-9R result: COMPLETE.
0-9O-B result: COMPLETE.
P7-PR4B result: COMPLETE.
0-9O-A result: COMPLETE.
P7-PR4-LITE result: COMPLETE.

Current limitation: dry-run allocator runs but no runtime consumer
exists. 0-9R-IMPL creates the consumer.

---

## 1. Strategic intent

Build a **runtime consumer** that:

1. Subscribes to `dry_run_budget_allocation` events emitted by
   `feedback_budget_allocator.allocate_dry_run_budget`.
2. Maintains an EMA-smoothed view of `proposed_profile_weights_dry_run`.
3. Enforces invariants (PB-FLOOR + PB-DIV).
4. **Applies** the smoothed weights to the actual generation budget
   at the next round dispatch — but **only** after a flag flip
   protected by j13's CANARY order.

In 0-9R-IMPL itself, the consumer is built **dry-run apply** only:
mode=DRY_RUN, no real budget mutation. The CANARY apply switch lives
in 0-9S.

---

## 2. Required outcome

0-9R-IMPL must deliver:

1. `zangetsu/services/feedback_budget_consumer.py` — new module.
2. EMA smoothing helper (window ≥ 5 events, α ≤ 0.2).
3. PB-FLOOR enforcement: every profile gets ≥ 0.05.
4. PB-DIV enforcement: ≥ N profiles maintain floor (configurable).
5. Hot-swap-able weight cache with rollback path.
6. Runtime isolation: consumer is a separate systemd-unit-friendly
   module; arena_pipeline.py / arena23_orchestrator.py /
   arena45_orchestrator.py do NOT import it during 0-9R-IMPL phase.
7. Allocator subscription that ignores any event with `applied=True`
   (defense in depth — should never happen).
8. Event bus: stdout JSON line consumption (initial), upgrade to
   pgqueuer in future order if needed.
9. Mode flag hard-coded to DRY_RUN; no runtime-switchable config.
10. Tests: ≥ 60 covering schema, EMA, floor/div, isolation,
    rollback, governance.
11. Evidence package: full A/B baseline measurement (no treatment
    yet — treatment activation is 0-9S CANARY).
12. Controlled-diff: EXPLAINED (new module is non-CODE_FROZEN
    initially); if added to SHA tracker → EXPLAINED_TRACE_ONLY only
    via 0-9M-style authorization.

---

## 3. Non-negotiable constraints

1. Do not modify alpha generation behavior.
2. Do not modify formula generation behavior.
3. Do not modify mutation / crossover behavior.
4. Do not modify search policy behavior.
5. Do not modify real generation budget yet (consumer in dry-run
   mode; no actual write).
6. Do not modify generation sampling weights yet.
7. Do not modify candidate creation.
8. Do not modify thresholds.
9. Do not modify A2_MIN_TRADES.
10. Do not modify A3 thresholds.
11. Do not modify Arena pass/fail branch conditions.
12. Do not modify rejection semantics.
13. Do not modify champion promotion.
14. Do not modify deployable_count semantics.
15. Do not modify execution logic.
16. Do not modify capital allocation.
17. Do not modify risk controls.
18. Do not restart services in production (consumer ships unstarted).
19. Do not start CANARY (0-9S).
20. Do not start production rollout (0-9T).
21. Do not weaken branch protection.
22. Do not bypass signed PR-only flow.
23. Do not weaken controlled-diff.
24. Do not introduce per-alpha lineage.
25. Do not require formula explainability.
26. Do not connect dry-run allocator output to **actual** generation
    budget yet.
27. Do not introduce a runtime apply path in 0-9R-IMPL phase.
28. Do not allow pass-rate optimization to weaken edge quality.

---

## 4. Allowed scope

### 4.1 New module

```
zangetsu/services/feedback_budget_consumer.py
```

Purpose:

- Subscribe to `dry_run_budget_allocation` events.
- EMA smoothing.
- Floor + diversity enforcement.
- Hot-swap-able weight cache.
- DRY_RUN mode (no actual write).

### 4.2 New tests

```
zangetsu/tests/test_feedback_budget_consumer.py
```

### 4.3 New systemd unit (if applicable, infra change separate)

Not in 0-9R-IMPL — infra deploy is 0-9S domain.

### 4.4 Documentation

```
docs/recovery/20260424-mod-7/0-9r-impl/
```

### 4.5 Forbidden edits

The following must remain zero-diff:

- `zangetsu/services/arena_pipeline.py`
- `zangetsu/services/arena23_orchestrator.py`
- `zangetsu/services/arena45_orchestrator.py`
- `zangetsu/services/feedback_budget_allocator.py`
- `zangetsu/services/generation_profile_metrics.py`
- `zangetsu/services/generation_profile_identity.py`
- `zangetsu/services/feedback_decision_record.py`
- `zangetsu/services/arena_rejection_taxonomy.py`
- `zangetsu/services/arena_pass_rate_telemetry.py`
- `zangetsu/services/arena_gates.py`
- `zangetsu/config/settings.py`
- `zangetsu/engine/components/alpha_engine.py`
- All other `zangetsu/engine/`、`zangetsu/live/`、execution / risk
  modules.

---

## 5. Required tests (sketch)

§9 categories from 0-9R draft (≥ 60 tests):

- 9.1 Consumer schema
- 9.2 EMA smoothing correctness
- 9.3 PB-FLOOR enforcement
- 9.4 PB-DIV enforcement
- 9.5 applied=true event rejection
- 9.6 mode=DRY_RUN invariant
- 9.7 Rollback path
- 9.8 Hot-swap correctness
- 9.9 Runtime isolation (no Arena / pipeline / orchestrator imports
  the consumer)
- 9.10 Allocator output passthrough fidelity
- 9.11 Governance / behavior invariance

---

## 6. Required documentation

```
docs/recovery/20260424-mod-7/0-9r-impl/
  01_consumer_design.md
  02_ema_and_smoothing_contract.md
  03_floor_and_diversity_enforcement.md
  04_isolation_and_rollback.md
  05_test_results.md
  06_controlled_diff_report.md
  07_baseline_a_b_measurement.md
  08_0-9r-impl_final_report.md
```

---

## 7. Acceptance criteria

0-9R-IMPL is COMPLETE only if:

1. PR merged via signed PR-only flow.
2. Merge commit verified=true.
3. `feedback_budget_consumer.py` delivered.
4. Consumer in DRY_RUN mode (no actual budget write).
5. EMA + floor + diversity tests pass.
6. Isolation tests pass.
7. Rollback path tested.
8. ≥ 7 days of stable dry-run apply observation post-merge.
9. No G1–G13 anti-overfit violation in stable observation.
10. No runtime SHA changed except the new consumer source.
11. Branch protection intact.
12. CANARY (0-9S) prerequisites documented.

---

## 8. Recommended next action

After 0-9R-IMPL completes:

**TEAM ORDER 0-9S — CANARY Readiness Gate.** Switch consumer mode
from DRY_RUN to CANARY-apply for a small cohort. Validate against
A/B success criteria over ≥ 14 days.

If 0-9R-IMPL fails dry-run stability → STOP and review design.

---

## 9. j13 authorization placeholder

```
j13 authorizes TEAM ORDER 0-9R-IMPL — Sparse-Candidate Black-Box
Optimization Implementation. Execute under signed PR-only governance.
Scope is implementation of feedback_budget_consumer in DRY_RUN mode
only, with PB-FLOOR + PB-DIV invariants. Do not connect to actual
generation budget. Do not start CANARY or production rollout. Do
not modify Arena, alpha generation, formula generation, mutation/
crossover, search policy, real generation budget, sampling weights,
thresholds, A2_MIN_TRADES, Arena pass/fail, rejection semantics,
champion promotion, deployable_count semantics, execution, capital,
risk, CANARY, or production rollout. STOP after signed merge,
evidence report, ≥ 7 days dry-run stability, and local main sync.
```

---

> **REMINDER: this is a future-order DRAFT.**
> **0-9R does NOT authorize 0-9R-IMPL.**
> **j13 must issue a separate order to start.**
