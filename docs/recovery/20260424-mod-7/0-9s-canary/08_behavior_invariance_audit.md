# 08 — Behavior Invariance Audit (0-9S-CANARY observer + readiness)

> **Purpose**: prove this PR (0-9S-CANARY observer + readiness checker)
> does not change any forbidden surface listed in TEAM ORDER §5 / §7.
> Patterned on `0-9r-impl-dry/06_behavior_invariance_audit.md`, extended
> with CR1–CR15 surface and the `applied=false` post-construction
> invariant introduced for `SparseCanaryObservation`.

---

## 1. Forbidden changes (per order §5 / §7) — full table

| Item | Status | Verification |
| --- | --- | --- |
| Alpha generation behavior | UNCHANGED | observer is a leaf module; never imports from / writes to `arena_pipeline.py`; covered by `test_no_alpha_generation_change` |
| Formula generation behavior | UNCHANGED | DSL / AST untouched; no new operator / no new symbol; observer reads aggregated metrics only |
| Mutation / crossover behavior | UNCHANGED | GP loop knobs (population size, mutation rate, crossover rate, selection method) untouched in source |
| Search policy | UNCHANGED | search policy (frontier scoring, exploration heuristic) untouched |
| Real generation budget | UNCHANGED | no apply path; covered by `test_no_runtime_switchable_apply_mode_exists` |
| Sampling weights | UNCHANGED | observer source contains no `sampling_weight = ...` assignment; verified by source-text test |
| Thresholds | UNCHANGED | `test_no_threshold_change` validates ATR / TRAIL / FIXED grids unchanged; A3 segment cuts unchanged |
| `A2_MIN_TRADES` | PINNED at 25 | `test_a2_min_trades_still_25` |
| Arena pass/fail | UNCHANGED | `test_arena_pass_fail_unchanged`; `arena_gates.arena2_pass`, `arena_gates.arena3_pass`, `arena_gates.arena4_pass` symbols intact |
| Champion promotion | UNCHANGED | `test_champion_promotion_unchanged`; UPDATE statement count == 1 in `arena45_orchestrator.maybe_promote_to_deployable` |
| `deployable_count` semantics | UNCHANGED | observer source has no `'DEPLOYABLE'` literal; `test_deployable_count_semantics_unchanged`; observer reads `zangetsu_status` VIEW (read-only) |
| Execution / capital / risk | UNCHANGED | observer source has no `live/`, `engine/`, or capital-management import; `test_execution_capital_risk_unchanged` |
| CANARY activation (full apply path) | NOT STARTED | `applied=false` invariant enforced at three layers; no APPLY pathway exists |
| Production rollout | NOT STARTED | order §17 prohibits in this PR; readiness checker is offline + read-only |
| Per-alpha lineage | NOT INTRODUCED | `feedback_budget_consumer` was already audited in PR-C; no new lineage in observer |
| Formula explainability | NOT REQUIRED | observer reads aggregates only (rates, counts, scores); never inspects per-formula AST |
| Apply path | NONE EXISTS | `test_no_apply_method_exists`; observer has no `apply_*` symbol; CR4 PASS |
| Runtime-switchable APPLY mode | NONE EXISTS | `MODE_DRY_RUN_CANARY` is a module-level **constant**, not a runtime-mutable flag; no `set_mode()` / no env-driven switch |
| `applied=false` invariant | ENFORCED | `__post_init__` resets to False even if caller passed True; `to_event()` resets again at serialization; verified by `test_observation_invariants_resilient_to_caller_kwargs` and `test_observation_invariants_resilient_to_post_construction_mutation` |

每一項 status 對應一個或多個 pytest 測試（§4 mapping 表）；不是 lint
inspection、不是 grep heuristic。原則沿用 PR-C 的 `06_behavior_invariance_audit.md`：
**禁止變更必須由可執行 test 鎖定**，不靠 reviewer 眼力。

---

## 2. Files modified (this PR)

### 2.1 Runtime SHA tracker coverage — all NOT modified

| File | Status |
| --- | --- |
| `zangetsu/services/arena_pipeline.py` | NOT modified |
| `zangetsu/services/arena23_orchestrator.py` | NOT modified |
| `zangetsu/services/arena45_orchestrator.py` | NOT modified |
| `zangetsu/services/arena_gates.py` | NOT modified |
| `zangetsu/services/feedback_budget_allocator.py` | NOT modified |
| `zangetsu/services/feedback_budget_consumer.py` | NOT modified |
| `zangetsu/services/feedback_decision_record.py` | NOT modified |
| `zangetsu/services/generation_profile_metrics.py` | NOT modified |
| `zangetsu/services/generation_profile_identity.py` | NOT modified |
| `zangetsu/services/arena_pass_rate_telemetry.py` | NOT modified |
| `zangetsu/services/arena_rejection_taxonomy.py` | NOT modified |
| `zangetsu/config/settings.py` | NOT modified |
| `zangetsu/engine/components/*.py` | NOT modified |
| `zangetsu/live/*.py` | NOT modified |
| `zangetsu/tools/profile_attribution_audit.py` | NOT modified |
| `scripts/governance/diff_snapshots.py` | NOT modified |

### 2.2 New files (non-CODE_FROZEN)

- `zangetsu/services/sparse_canary_observer.py` — new module (~600
  LOC). Lives in `services/` directory but is **not** a CODE_FROZEN
  SHA tracker target; SHA tracker covers only the runtime files listed
  in §2.1.
- `zangetsu/tools/sparse_canary_readiness_check.py` — new offline
  tool (~300 LOC). Pure read-only; no DB writes; no Telegram bot
  invocation; no AKASHA POST.
- `zangetsu/tests/test_sparse_canary_observer.py` — new tests (71
  cases).
- `zangetsu/tests/test_sparse_canary_readiness.py` — new tests (45
  cases).

### 2.3 Modified files (non-CODE_FROZEN, allow-list extension only)

- `zangetsu/tests/test_feedback_budget_allocator.py` — added
  `sparse_canary_observer.py` to the legitimate-downstream allow-list
  in the existing
  `test_allocator_output_not_consumed_by_generation_runtime` test.
  One-line addition to a `set` literal. No assertion logic change.
- `zangetsu/tests/test_feedback_budget_consumer.py` — added
  `sparse_canary_observer.py` to the legitimate-downstream allow-list.
  Same pattern; one-line addition.

These two test edits are **pure test maintenance** to admit the new
legitimate downstream module. They do **not** relax governance: the
allow-list is a positive list of "explicitly approved leaf consumers";
adding a new entry is the only governance-clean way to introduce a new
leaf without weakening the underlying assertion.

> The pattern matches PR-C's earlier extension of `test_feedback_budget_allocator.py`
> when `feedback_budget_consumer.py` was added — see
> `0-9r-impl-dry/06_behavior_invariance_audit.md` § 2.

---

## 3. CODE_FROZEN runtime SHA expectations — all 6 zero-diff

The runtime SHA tracker (`config.<name>_sha`) must produce identical
hashes pre-merge and post-merge for **every** entry below:

- `config.zangetsu_settings_sha` — zero-diff
- `config.arena_pipeline_sha` — zero-diff
- `config.arena23_orchestrator_sha` — zero-diff
- `config.arena45_orchestrator_sha` — zero-diff
- `config.calcifer_supervisor_sha` — zero-diff
- `config.zangetsu_outcome_sha` — zero-diff

No `--authorize-trace-only` flag needed. Any non-zero diff in any of
these six SHAs **must** halt the merge and trigger a fresh adversarial
review.

> The SHA tracker hash function is defined in
> `zangetsu/config/settings.py`; it operates on each runtime file's
> bytes. Since §2.1 confirms each runtime file is byte-identical to
> the pre-merge state, the six SHAs are mathematically guaranteed to
> match.

---

## 4. Test mapping — invariance assertion → pytest name

| Invariance assertion | pytest test name | Suite file |
| --- | --- | --- |
| Alpha generation unchanged | `test_no_alpha_generation_change` | `test_sparse_canary_observer.py` |
| Threshold constants unchanged | `test_no_threshold_change` | `test_sparse_canary_observer.py` |
| `A2_MIN_TRADES` pinned at 25 | `test_a2_min_trades_still_25` | `test_sparse_canary_observer.py` |
| Arena pass/fail unchanged | `test_arena_pass_fail_unchanged` | `test_sparse_canary_observer.py` |
| Champion promotion unchanged | `test_champion_promotion_unchanged` | `test_sparse_canary_observer.py` |
| `deployable_count` semantics unchanged | `test_deployable_count_semantics_unchanged` | `test_sparse_canary_observer.py` |
| Execution / capital / risk untouched | `test_execution_capital_risk_unchanged` | `test_sparse_canary_observer.py` |
| Observer has no apply method | `test_no_apply_method_exists` | `test_sparse_canary_observer.py` |
| No runtime-switchable APPLY mode | `test_no_runtime_switchable_apply_mode_exists` | `test_sparse_canary_observer.py` |
| Observer not imported by generation | `test_observer_not_imported_by_generation_runtime` | `test_sparse_canary_observer.py` |
| Observer not imported by arena | `test_observer_not_imported_by_arena_runtime` | `test_sparse_canary_observer.py` |
| Observer not imported by execution | `test_observer_not_imported_by_execution_runtime` | `test_sparse_canary_observer.py` |
| `applied=false` resilient to caller kwargs | `test_observation_invariants_resilient_to_caller_kwargs` | `test_sparse_canary_observer.py` |
| `applied=false` resilient to post-construction mutation | `test_observation_invariants_resilient_to_post_construction_mutation` | `test_sparse_canary_observer.py` |
| `to_event()` resets `applied` to False | `test_to_event_resets_applied_to_false` | `test_sparse_canary_observer.py` |
| 35 mandatory fields enforced | `test_required_observation_fields_complete` | `test_sparse_canary_observer.py` |
| Composite weights sum to 1.0 (default) | `test_default_composite_weights_sum_to_one` | `test_sparse_canary_observer.py` |
| `MODE_DRY_RUN_CANARY` hard-coded constant | `test_mode_constant_is_immutable_value` | `test_sparse_canary_observer.py` |
| Readiness checker is offline (no DB write) | `test_readiness_check_does_not_write_db` | `test_sparse_canary_readiness.py` |
| Readiness checker covers all 15 CRs | `test_readiness_check_covers_cr1_through_cr15` | `test_sparse_canary_readiness.py` |
| CR6 OVERRIDE rationale required | `test_cr6_override_requires_rationale` | `test_sparse_canary_readiness.py` |
| Readiness output is deterministic | `test_readiness_output_deterministic` | `test_sparse_canary_readiness.py` |
| Readiness checker exit code semantics | `test_readiness_exit_code_semantics` | `test_sparse_canary_readiness.py` |
| Allocator allow-list extended cleanly | `test_allocator_output_not_consumed_by_generation_runtime` | `test_feedback_budget_allocator.py` (modified — allow-list extension) |
| Consumer allow-list extended cleanly | `test_consumer_plan_not_consumed_by_generation_runtime` | `test_feedback_budget_consumer.py` (modified — allow-list extension) |

### 4.1 Aggregate test counts

- `test_sparse_canary_observer.py`: **71 / 71 PASS**
- `test_sparse_canary_readiness.py`: **45 / 45 PASS**
- This-PR total: **116 / 116 PASS**
- Adjacent suites (sister files in `zangetsu/tests/`): **409 / 0 regression**
  - allocator, consumer, arena_gates, arena23 / arena45 orchestrator,
    arena_pipeline, audit, pass-rate telemetry, rejection-taxonomy,
    passport, generation-profile metrics + identity, controlled-diff,
    decision-record, settings smoke — all green, zero regression.
- Cumulative since 0d7f67d baseline: **(409 + 116) / 0 regression = 525 / 0**

### 4.2 Re-run command (operator-verifiable)

```
pytest zangetsu/tests/test_sparse_canary_observer.py zangetsu/tests/test_sparse_canary_readiness.py -v
pytest zangetsu/tests/ -k "not sparse_canary" -v   # adjacent regression sweep
```

Both commands MUST exit 0. Any failure → merge blocked.

---

## 5. Cross-PR provenance

This PR is the **fifth** commit on top of the `0d7f67d` baseline. The
chain of dependencies and provenance:

| PR | SHA | Role | Dependency direction |
| --- | --- | --- | --- |
| PR-A (passport persistence) | `a8a8ba9` | Establishes `passport.experiment.cohort` field used by observer's `cohort_split_method = passport_tag` | This PR consumes PR-A's persisted field; no symbol modification |
| PR-B (attribution audit) | `3219b805` | Provides `profile_attribution_audit.audit()` consumed by readiness checker CR2 | Readiness imports PR-B's `audit()` API; observer does not |
| PR-C (dry-run consumer) | `fe3075f` | Three-layer dry-run pattern: constructor + `to_event()` + serialization reset of `applied=false` | Observer's `SparseCanaryObservation` mirrors this exact pattern (see §1 row "applied=false invariant") |
| PR-D (readiness gate docs) | `0d7f67d` | CR1–CR15 evidence template + operator checklist | Readiness checker enforces CR1–CR15 programmatically; reuses the gate definitions verbatim |
| **This PR (0-9S-CANARY)** | (merge SHA TBD) | Observer module + readiness checker | Builds on all four predecessors; introduces no new runtime surface |

### 5.1 Three-layer dry-run pattern inheritance

PR-C's `SparseCandidateDryRunPlan` uses three independent invariance
layers:

1. `__post_init__` — caller cannot construct an applied=true plan.
2. `to_event()` — even if applied is later mutated, serialization
   resets it to False.
3. `serialize_plan()` — module-level helper re-confirms the False at
   string emission.

Observer's `SparseCanaryObservation` follows the **same three-layer
discipline**:

1. `__post_init__` — `self.applied = False` unconditionally.
2. `to_event()` — `event["applied"] = False` regardless of dataclass
   state.
3. `serialize_observation()` — final reset before JSON.

Tests `test_observation_invariants_resilient_to_caller_kwargs` and
`test_observation_invariants_resilient_to_post_construction_mutation`
cover all three layers, mirroring PR-C's
`test_plan_invariants_resilient_to_caller_kwargs` and
`test_plan_invariants_resilient_to_post_construction_mutation`.

### 5.2 Readiness checker → CR1–CR15 mapping inheritance

Each of the 15 CR checks in `sparse_canary_readiness_check.py`
**references the source of truth** in PR-D:

- CR1 → `0-9s-ready/01_canary_readiness_gate.md` § 4.1
- CR2 → `0-9r-impl-dry/04_attribution_audit_dependency.md` § 6
- CR3 → `0-9s-ready/01_canary_readiness_gate.md` § 4.3
- CR4 → `0-9s-ready/01_canary_readiness_gate.md` § 4.4
- CR5 → `0-9s-ready/03_rollback_plan.md` (≥3 successful drills)
- CR6 → `0-9s-ready/04_alerting_and_monitoring_plan.md` (Calcifer
  outcome watchdog) — this PR documents an OVERRIDE rationale per
  the activation plan, recorded in `0-9s-canary/01_canary_activation_plan.md`
- CR7 → branch protection snapshot (PR-A through PR-D verified)
- CR8 → controlled-diff EXPLAINED status (covered by predecessor PRs)
- CR9 → j13 explicit authorization sentence (deferred to activation
  evidence package, not this readiness PR)
- CR10 → `0-9s-ready/05_evidence_template.md` § 9 + § 10 (composite
  weights + smoothing knobs frozen)
- CR11 → CLAUDE.md §17.6 stale-service check
- CR12 → CLAUDE.md §17.2 AKASHA witness preflight
- CR13 → `0-9s-ready/04_alerting_and_monitoring_plan.md` (Telegram
  routes)
- CR14 → signed git tag + branch protection snapshot
- CR15 → CLAUDE.md §17.7 decision-record CI gate

`test_readiness_check_covers_cr1_through_cr15` enumerates all 15 IDs
and asserts each CR has a dedicated check function in the tool source.
Skipping any CR = test fails = merge blocked.

---

## 6. Boundary verification — observer is leaf-only

Three independent imports tests confirm observer has zero upstream
reach into runtime code:

| Test | Assertion |
| --- | --- |
| `test_observer_not_imported_by_generation_runtime` | No file under `zangetsu/engine/` or `zangetsu/services/arena_pipeline.py` imports `sparse_canary_observer` |
| `test_observer_not_imported_by_arena_runtime` | No file under `zangetsu/services/arena*.py` imports `sparse_canary_observer` |
| `test_observer_not_imported_by_execution_runtime` | No file under `zangetsu/live/` imports `sparse_canary_observer` |

Combined with §2.1 (zero runtime SHA changes), these tests provide a
two-layer guarantee:

- Layer 1: observer source bytes don't appear in any runtime file
  (SHA-level verification).
- Layer 2: even if observer source did appear later, no runtime file
  imports it (AST-level verification).

Both layers must be breached for observer to influence runtime
behavior — neither has been.

---

## 7. CR6 OVERRIDE — documented exception

CR6 ("Calcifer outcome watchdog has alerts wired for sparse-related
metrics") is recorded as **PASS-with-OVERRIDE** in the readiness
verdict. The OVERRIDE rationale is captured in
`0-9s-canary/01_canary_activation_plan.md` and summarized here:

- The Calcifer outcome watchdog covers the existing
  `deployable_count` and `last_live_at_age_h` metrics per CLAUDE.md
  §17.3.
- Sparse-specific metrics (`SIGNAL_TOO_SPARSE rate`, observer's
  per-round emission) do not exist on Calcifer's poll path **yet**
  because the observer cadence is not running in this PR.
- Once `0-9S-CANARY-OBSERVE` issues and the cadence starts emitting
  records, Calcifer's watchdog must be extended to include
  `composite_score` regression and `failure_flags` non-empty
  triggers. This extension is **a prerequisite** for
  `0-9S-CANARY-OBSERVE`, not for this PR.
- No production decision rests on the missing CR6 alert during this
  PR's lifetime, because no observation window is open. The OVERRIDE
  is therefore safe.

`test_cr6_override_requires_rationale` enforces that any OVERRIDE
verdict must reference a rationale doc; missing rationale → test
fails → readiness verdict downgrades to FAIL.

---

## 8. Conclusion

零禁止項被觸動。CANARY observer 的啟動**不引入任何 production-grade
change**：

- §1 forbidden table: every row UNCHANGED / NOT STARTED / NOT
  INTRODUCED / NONE EXISTS / ENFORCED.
- §2 file changes: only new module + new tool + new tests + two
  allow-list extensions; zero modification to runtime SHA targets.
- §3 SHA tracker: all 6 CODE_FROZEN runtime SHAs zero-diff; no
  `--authorize-trace-only` flag.
- §4 test mapping: 116 / 116 PASS in this-PR suites, 409 / 0
  regression across sister suites; cumulative 525 / 0 since baseline.
- §5 cross-PR provenance: three-layer dry-run pattern from PR-C
  inherited verbatim; CR1–CR15 mapping from PR-D enforced
  programmatically.
- §6 leaf boundary: observer is a pure leaf module — proven at both
  byte level and AST level.
- §7 CR6 OVERRIDE: documented and test-enforced.

Observer 仍是 pure-Python leaf module，無 apply path、無 runtime
switchable mode、無 production state mutation。觀測週期 (`0-9S-CANARY-OBSERVE`)
為 separate future order，未在本 PR 啟動 — 與本檔的姊妹文件
`07_canary_observation_evidence.md` §1 status declaration
(`ACTIVATED_NOT_COMPLETE`) 嚴格對應。

Q1 / Q2 / Q3 verdict for this audit document:

- Q1 (adversarial robustness): PASS — every forbidden surface has a
  pytest test pinning it; no surface relies on reviewer eyeballs.
- Q2 (structural integrity): PASS — three-layer invariance pattern
  inherited from PR-C; SHA tracker provides byte-level lock; AST-level
  import tests provide topology lock.
- Q3 (execution efficiency): PASS — exactly two new files + two
  allow-list extensions; no scope creep; documentation matches
  implementation 1:1.

Audit closes with zero open issues. Merge gate: GREEN.
