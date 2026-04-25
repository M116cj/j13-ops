# 03 — Sparse-Candidate Dry-Run CANARY Observer Design

> Concrete-build evidence for TEAM ORDER 0-9S-CANARY. Pairs with
> `04_success_failure_criteria.md` (per-criterion evaluation rules) and
> sister docs `0-9s-ready/02_canary_success_failure_criteria.md`
> (abstract spec) and `0-9r-impl-dry/01_dry_run_consumer_design.md`
> (consumer counterpart pattern).

---

## 1. Mission

Per TEAM ORDER 0-9S-CANARY §6.1 / §1.1:

> Build the **read-only CANARY observer** for sparse-candidate dry-run
> telemetry — produce `sparse_canary_observation` evidence records
> (35-field schema, `mode=DRY_RUN_CANARY`, `applied=False`,
> `canary_version="0-9S-CANARY"`) by consuming existing dry-run
> telemetry from 0-9O-A / 0-9O-B / 0-9R-IMPL-DRY / 0-9P-AUDIT and
> P7-PR4B aggregates. The observer **never** applies recommendations,
> never connects to generation runtime, never touches Arena pass/fail
> logic, and never imports any module on the execution / capital /
> risk path.

The observer is the structural counterpart of the consumer in
0-9R-IMPL-DRY: identical three-layer dry-run invariant pattern,
identical "no public apply / commit / execute" symbol policy, identical
exception-safe failure handling. It exists so that — when (and only
when) a future `0-9S-CANARY-OBSERVE` activation order green-lights a
multi-day observation window — the evidence pipeline already has a
locked, audited, regression-tested entry point.

This PR ships the observer module, a readiness checker, and 116 unit
tests. It does not start any observation window, does not write to
production VIEW `<proj>_status`, and does not modify any threshold,
arena gate, champion promotion rule, deployable_count semantic, nor
execution / capital / risk path.

---

## 2. Module location

| Item | Path |
| --- | --- |
| Observer module | `zangetsu/services/sparse_canary_observer.py` (~600 LOC, pure-Python) |
| Readiness check tool | `zangetsu/tools/sparse_canary_readiness_check.py` (CR1–CR15 + structural isolation) |
| Test suite (observer) | `zangetsu/tests/test_sparse_canary_observer.py` (71 tests) |
| Test suite (readiness) | `zangetsu/tests/test_sparse_canary_readiness.py` (45 tests) |
| Combined cross-suite | 409 PASS / 0 regression after merge |

The module is a service (long-running orchestrator slot) per
`zangetsu/CLAUDE.md` folder conventions, but the observer functions
themselves are pure (no IO, no DB, no network, no filesystem). Service
placement is anticipatory — a future 0-9S-CANARY-OBSERVE activation
order will wire the observer into a periodic emit loop; until then the
module is callable only from tests and from caller-facing pipelines
that supply pre-aggregated metrics.

---

## 3. Imports

Explicit observer-module imports (verified by source-text test
`test_canary_observer_not_imported_by_*_runtime`):

```python
from zangetsu.services.feedback_budget_consumer import (
    PLAN_STATUS_ACTIONABLE,
    PLAN_STATUS_BLOCKED,
    PLAN_STATUS_NON_ACTIONABLE,
    SparseCandidateDryRunPlan,
)
from zangetsu.services.feedback_budget_allocator import (
    DryRunBudgetAllocation,
)
from zangetsu.services.feedback_decision_record import (
    DEFAULT_SAFETY_CONSTRAINTS,
)
```

Allowed import surface (read-only types and constants only):

| Source module | Symbols imported | Purpose |
| --- | --- | --- |
| `feedback_budget_consumer` | `PLAN_STATUS_ACTIONABLE`, `PLAN_STATUS_BLOCKED`, `PLAN_STATUS_NON_ACTIONABLE`, `SparseCandidateDryRunPlan` | Plan-status enums for `consumer_plan_stability` calculation; `SparseCandidateDryRunPlan` type for duck-typed plan inspection |
| `feedback_budget_allocator` | `DryRunBudgetAllocation` | Allocation type (informational; never executed) |
| `feedback_decision_record` | `DEFAULT_SAFETY_CONSTRAINTS` | Default safety-constraint list copied into every observation (immutable list pattern) |

Standard library: `json`, `math`, `uuid`, `dataclasses`, `datetime`,
`typing`. No third-party dependency.

Forbidden imports (verified by suite §11):

- `zangetsu.engine.alpha_generation` and any alpha generation entry
- `zangetsu.services.arena_pipeline` / `arena23_orchestrator` / `arena45_orchestrator` / `arena_gates`
- `zangetsu.live.alpha_signal_live` / `data_collector` / `alpha_dedup` / `alpha_ensemble` / `alpha_discovery`
- Capital allocator / risk module
- `zangetsu.tools.profile_attribution_audit` (verdicts are passed as a
  caller-supplied string, not pulled in by the observer)

---

## 4. Three-layer dry-run invariant

The observer enforces the **same** three-layer invariant pattern as
0-9R-IMPL-DRY's consumer (sister doc §3). All three layers must hold
simultaneously; any one of them failing in isolation is treated as a
governance-grade defect by the test suite.

| Layer | Location | What it guarantees |
| --- | --- | --- |
| 1. `__post_init__` reset | `sparse_canary_observer.py` lines 177–191 | Forcibly assigns `mode = MODE_DRY_RUN_CANARY`, `applied = APPLIED_FALSE`, `canary_version = CANARY_VERSION` regardless of caller-supplied kwargs at dataclass construction time |
| 2. `to_event()` re-assertion | `sparse_canary_observer.py` lines 193–200 | Re-applies the same three field values to the serialized payload at JSON-emit time, immune to post-construction attribute mutation |
| 3. No public apply / commit / execute symbol | Module surface | `dir(sparse_canary_observer)` MUST NOT contain `apply`, `commit`, or `execute` symbols. Verified by `test_no_apply_method_exists` (line 682) and `test_observation_no_apply_method` (line 184) |

Additional structural invariants verified by tests:

- `test_observation_invariants_resilient_to_caller_kwargs` (line 144)
  — caller cannot construct an observation with `mode="APPLIED"` or
  `applied=True`; the dataclass overrides at `__post_init__`.
- `test_observation_invariants_resilient_to_post_construction_mutation`
  (line 156) — direct attribute mutation after construction is
  re-overridden by `to_event()`.
- `test_no_runtime_switchable_apply_mode_exists` (line 689) — there is
  no module-level toggle (`APPLY_MODE = True/False`) that could flip
  the observer into apply mode at runtime.
- `test_observer_output_not_consumed_by_runtime` (line 698) — no
  runtime module imports `sparse_canary_observer`.

---

## 5. Inputs

All inputs are read-only. The observer accepts pre-aggregated metric
mappings; it does not perform any aggregation itself, does not query
any DB, and does not subscribe to any stream.

| Input | Source PR / module | Type | Required |
| --- | --- | --- | --- |
| `treatment_metrics` | P7-PR4B `arena_batch_metrics` aggregate (caller-aggregated) | `Mapping[str, Any]` | yes |
| `baseline` | Caller-supplied prior-window snapshot built from `arena_batch_metrics` + `<proj>_status.deployable_count` | `CanaryBaseline` dataclass | yes |
| `profile_weights` | 0-9O-A `generation_profile_metrics` per-profile weights | `Mapping[str, float]` | optional |
| `consumer_plans` | 0-9R-IMPL-DRY `SparseCandidateDryRunPlan` event stream (recent plans) | `Sequence[SparseCandidateDryRunPlan]` (or dict-likes) | optional |
| `readiness_verdict` | This PR's `sparse_canary_readiness_check.py` overall verdict | `str` (`PASS` / `FAIL` / `OVERRIDE`) | optional |
| `attribution_verdict` | 0-9P-AUDIT `profile_attribution_audit.py` (PR-B `3219b805`) | `str` (`GREEN` / `YELLOW` / `RED` / `UNAVAILABLE`) | optional |
| `observation_window_start` / `observation_window_end` / `observation_window_complete` | Caller (future activation pipeline) | `str` ISO-8601 / `bool` | optional |
| `rounds_observed` / `profiles_observed` | Caller-aggregated counters | `int` | optional |
| `rollback_executable` | Caller (rollback drill log status) | `bool` | default `True` |
| `execution_path_touched` | Controlled-diff CI verdict (0-9M) | `bool` | default `False` |
| `no_threshold_change` / `no_arena_change` / `no_promotion_change` / `no_execution_change` | Controlled-diff CI verdicts | `bool` flags | default `True` |
| `per_regime_stable` | Caller (per-regime deployable_count median check) | `Optional[bool]` | default `None` (→ `INSUFFICIENT_HISTORY`) |
| `composite_weights` | Caller override (None → 0.4 / 0.4 / 0.2 default) | `Mapping[str, float]` keys `{a2, a3, deploy}` | optional |
| `evidence_paths` | Caller (paths of supporting evidence files) | `Sequence[str]` | optional |
| `alerts_triggered` | Caller (Telegram / Calcifer alert IDs) | `Sequence[str]` | optional |

All inputs flow through `_safe_float` / `_safe_int` / type-coercion
helpers; no pathological caller input can crash `observe()`.

---

## 6. Outputs

`SparseCanaryObservation` event with 35 fields, locked by
`required_observation_fields()`. The full schema:

| # | Field | Type | Default | Source |
| --- | --- | --- | --- | --- |
| 1 | `telemetry_version` | `str` | `"1"` | constant `TELEMETRY_VERSION` |
| 2 | `canary_id` | `str` | `f"canary-{uuid.uuid4().hex[:16]}"` | factory `_new_canary_id()` |
| 3 | `run_id` | `str` | `""` | caller `observe(run_id=...)` |
| 4 | `created_at` | `str` ISO-8601 UTC | now() | factory `_utc_now_iso()` |
| 5 | `mode` | `str` | `"DRY_RUN_CANARY"` | invariant — overridden in `__post_init__` and `to_event()` |
| 6 | `applied` | `bool` | `False` | invariant — overridden in `__post_init__` and `to_event()` |
| 7 | `canary_version` | `str` | `"0-9S-CANARY"` | invariant — overridden in `__post_init__` and `to_event()` |
| 8 | `readiness_verdict` | `str` | `"NOT_EVALUATED"` | caller / readiness checker |
| 9 | `attribution_verdict` | `str` | `"UNAVAILABLE"` | 0-9P-AUDIT |
| 10 | `observation_window_start` | `str` | `""` | caller |
| 11 | `observation_window_end` | `str` | `""` | caller |
| 12 | `observation_window_complete` | `bool` | `False` | caller |
| 13 | `rounds_observed` | `int` | `0` | caller |
| 14 | `profiles_observed` | `int` | `0` | caller |
| 15 | `unknown_reject_rate` | `float` | `0.0` | `treatment_metrics["unknown_reject_rate"]` |
| 16 | `signal_too_sparse_rate` | `float` | `0.0` | `treatment_metrics["signal_too_sparse_rate"]` |
| 17 | `a1_pass_rate` | `float` | `0.0` | `treatment_metrics["a1_pass_rate"]` |
| 18 | `a2_pass_rate` | `float` | `0.0` | `treatment_metrics["a2_pass_rate"]` |
| 19 | `a3_pass_rate` | `float` | `0.0` | `treatment_metrics["a3_pass_rate"]` |
| 20 | `oos_fail_rate` | `float` | `0.0` | `treatment_metrics["oos_fail_rate"]` |
| 21 | `deployable_count` | `int` | `0` | `treatment_metrics["deployable_count"]` |
| 22 | `deployable_density` | `float` | `0.0` | `compute_deployable_density(deployable_count, passed_a3)` |
| 23 | `composite_score` | `float` | `0.0` | `compute_composite_score(...)` |
| 24 | `baseline_composite_score` | `float` | `0.0` | `baseline.composite_score` |
| 25 | `composite_delta` | `float` | `0.0` | `composite_score - baseline_composite_score` |
| 26 | `profile_diversity_score` | `float` | `0.0` | `compute_profile_diversity(profile_weights)` |
| 27 | `profile_collapse_detected` | `bool` | `False` | `detect_profile_collapse(profile_weights)` |
| 28 | `consumer_plan_stability` | `float` | `0.0` | `compute_consumer_plan_stability(consumer_plans)` |
| 29 | `success_criteria_status` | `Dict[str, str]` | `{}` | `evaluate_success_criteria(...)` |
| 30 | `failure_criteria_status` | `Dict[str, str]` | `{}` | `evaluate_failure_criteria(...)` |
| 31 | `rollback_required` | `bool` | `False` | `any(v == STATUS_FAIL for v in failure_criteria_status.values())` |
| 32 | `alerts_triggered` | `List[str]` | `[]` | caller |
| 33 | `evidence_paths` | `List[str]` | `[]` | caller |
| 34 | `safety_constraints` | `List[str]` | copy of `DEFAULT_SAFETY_CONSTRAINTS` | feedback_decision_record |
| 35 | `source` | `str` | `"sparse_canary_observer"` | constant |

Plus an `event_type` field added at serialization time by `to_event()`
(value `EVENT_TYPE_SPARSE_CANARY_OBSERVATION = "sparse_canary_observation"`),
and `mode` / `applied` / `canary_version` re-asserted in the payload.

`required_observation_fields()` returns the canonical 34-name tuple
(the 35th — `safety_constraints` — is intentionally excluded from the
required-list because tests treat it as a derived field; its presence
is verified separately by `test_sparse_canary_observation_schema_contains_required_fields`).

---

## 7. Composite scoring

Default composite formula and weights (matching 0-9R / 0-9S-READY
proposal and TEAM ORDER 0-9S-CANARY §4):

```
composite_score = w_a2 * a2_pass_rate
                + w_a3 * a3_pass_rate
                + w_deploy * deployable_density

where (default):
  w_a2     = DEFAULT_COMPOSITE_W_A2     = 0.4
  w_a3     = DEFAULT_COMPOSITE_W_A3     = 0.4
  w_deploy = DEFAULT_COMPOSITE_W_DEPLOY = 0.2
```

Weights sum to 1.0 (verified by
`test_default_composite_weights_sum_to_one`). Inputs are clamped to
`[0, 1]` by `_clip` before multiplication; the result is also clamped
to `[0, 1]` (verified by `test_compute_composite_score_clamps_to_unit`).

`compute_composite_score` is exception-safe: bad inputs (None, NaN,
inf, non-numeric) coerce to `0.0` via `_safe_float` and never raise
(verified by `test_compute_composite_score_handles_bad_input`).

### Override path

Callers may pass `composite_weights` as a `Mapping[str, float]` with
keys `{"a2", "a3", "deploy"}` to `observe()`. Missing keys fall back
to defaults via `_safe_float(w.get(key), DEFAULT_*)`. Override is
intended for governance-approved noise-floor tuning; the activation
order requires j13 explicit confirmation before non-default weights
are used (per `0-9s-ready/02_canary_success_failure_criteria.md` §6).

```python
obs = observe(
    ...,
    composite_weights={"a2": 0.5, "a3": 0.4, "deploy": 0.1},
)
```

Verified by `test_compute_composite_score_custom_weights`.

---

## 8. Deployable density

Formula:

```
deployable_density = clip(deployable_count / passed_a3, 0.0, 1.0)
```

Returns `0.0` when `passed_a3 <= 0` (no division by zero). Returns
clipped `1.0` when `deployable_count > passed_a3` (defensive: should
never happen in valid telemetry but the clamp prevents composite-score
overflow).

`passed_a3` is read from `treatment_metrics["passed_a3"]` (P7-PR4B
provides this as `arena_batch_metrics.a3_passed_count`); when missing,
density falls to `0.0` and the composite score reflects only A2 / A3
pass rates.

Verified by `test_compute_deployable_density`.

---

## 9. Profile diversity

Formula (fraction of profiles whose weight meets or exceeds the
exploration floor):

```
profile_diversity_score = |{p : weights[p] >= EXPLORATION_FLOOR}| / |weights|
```

where `EXPLORATION_FLOOR = 0.05` (mirrors 0-9R-IMPL-DRY consumer's
`enforce_floor_and_diversity` floor). Returns `0.0` for empty weights.

Float comparison uses an epsilon of `1e-12` to tolerate IEEE-754
rounding when callers pre-normalize weights to exactly the floor.

Verified by `test_compute_profile_diversity` and
`test_compute_profile_diversity_below_floor` (every weight strictly
below floor → score is `0.0`).

---

## 10. Profile collapse detection

A collapse is flagged when fewer than `DIVERSITY_CAP_MIN = 2` profiles
sit at or above the exploration floor:

```
def detect_profile_collapse(weights, *, diversity_cap_min=2) -> bool:
    above = sum(1 for v in weights.values() if v >= EXPLORATION_FLOOR - 1e-12)
    return above < diversity_cap_min
```

Returns `False` for empty weights (no data → no collapse claim, deferred
to `INSUFFICIENT_HISTORY`).

The threshold mirrors the consumer's `cap_min=2` contract from
0-9R-IMPL-DRY `03_smoothing_and_step_limit_contract.md`. Collapse
triggers `S7 = FAIL` and `F5 = FAIL` simultaneously (the F-criterion
is the actionable rollback signal; the S-criterion contributes to the
success-day count failure).

Verified by `test_detect_profile_collapse_when_one_profile_dominates`
(collapse → True), `test_detect_profile_collapse_when_diverse`
(diverse → False), and `test_detect_profile_collapse_empty` (empty →
False).

---

## 11. Consumer plan stability

Fraction of supplied 0-9R-IMPL-DRY plans whose `plan_status` field is
`PLAN_STATUS_ACTIONABLE` (= `"ACTIONABLE_DRY_RUN"`):

```
consumer_plan_stability = |{p : p.plan_status == ACTIONABLE_DRY_RUN}| / |plans|
```

Accepts both attribute-style (`SparseCandidateDryRunPlan` instances) and
mapping-style (`{"plan_status": "..."}`) inputs via `getattr` with a
`isinstance(p, Mapping)` fallback. Returns `0.0` for empty / `None`
plans.

This is a **soft observability metric**, not a gate. Its value flows
into evidence packages so that operators can see the consumer's
ACTIONABLE-emit ratio across the observation window. The threshold
`PLAN_STABILITY_MIN = 0.70` is documented but not currently enforced
in any S/F criterion — a future activation order may promote it.

Verified by `test_compute_consumer_plan_stability_with_actionable_plans`,
`test_compute_consumer_plan_stability_handles_dict_plans`, and
`test_compute_consumer_plan_stability_handles_empty`.

---

## 12. Failure-safety

The observer embodies CLAUDE.md §3 Q1 dimension #2 (silent failure
propagation): every public function is exception-safe and either
returns a safe-default value or returns a marker observation with
`rollback_required=True`.

| Function | Failure mode | Safe-default behavior |
| --- | --- | --- |
| `observe(...)` | Any internal exception | Catches, populates `success_criteria_status` with all `S1..S14 = NOT_EVALUATED`, populates `failure_criteria_status` with all `F1..F9 = NOT_EVALUATED`, returns observation with `mode=DRY_RUN_CANARY`, `applied=False` |
| `safe_observe(**kwargs)` | Any exception escaping `observe()` | Returns observation with `rollback_required=True` and `alerts_triggered=[f"observe_raised_{ExcClassName}"]` |
| `serialize_observation(obs)` | JSON-encode failure | Returns `""` (empty string) |
| `compute_composite_score(...)` | Bad inputs | Coerces to `_safe_float` defaults; clamps to `[0, 1]`; returns `0.0` on outer-frame exception |
| `compute_deployable_density(...)` | `passed_a3 <= 0`, bad ints | Returns `0.0` |
| `compute_profile_diversity(...)` | Empty / None weights | Returns `0.0` |
| `detect_profile_collapse(...)` | Empty / None weights | Returns `False` |
| `compute_consumer_plan_stability(...)` | Empty / None plans | Returns `0.0` |
| `evaluate_success_criteria(...)` | Any exception | Marks remaining `Si` as `NOT_EVALUATED` |
| `evaluate_failure_criteria(...)` | Any exception | Marks remaining `Fi` as `NOT_EVALUATED` |

### Input non-mutation

`observe()` reads from the input mappings via `.get()` and never
writes back. Verified by `test_observe_does_not_mutate_input`
(snapshots input dict via `json.dumps`, runs `observe`, asserts
identical snapshot).

### Pathological-input drill

`test_observe_handles_empty_metrics` — `treatment_metrics={}`,
`profile_weights=None`, `consumer_plans=None`, `baseline=CanaryBaseline()`
→ produces a valid observation with all-zero metrics and
`INSUFFICIENT_HISTORY` for delta criteria. No exception raised, no
silent corruption.

---

## 13. Allowed scope

Per TEAM ORDER 0-9S-CANARY §6 (Allowed Scope):

| Allowed | Forbidden |
| --- | --- |
| Read aggregated `arena_batch_metrics` / `arena_stage_summary` (P7-PR4B) | Connect to generation runtime |
| Read `generation_profile_metrics` (0-9O-A) | Modify any threshold (A2_MIN_TRADES / ATR / TRAIL / FIXED grids) |
| Read `DryRunBudgetAllocation` (0-9O-B) | Modify any Arena pass/fail logic |
| Read `SparseCandidateDryRunPlan` (0-9R-IMPL-DRY) | Modify champion promotion criteria |
| Read attribution verdicts (0-9P-AUDIT) | Modify deployable_count semantics |
| Build observation events with `mode=DRY_RUN_CANARY` | Touch execution / capital / risk path |
| Compute composite scores, diversity scores, plan stability | Activate any CANARY observation window (PR ships the observer; activation is a separate order) |
| Evaluate S1–S14 / F1–F9 criteria status | Mutate caller inputs |
| Emit observations with `applied=False` | Expose any apply / commit / execute symbol |

The observer also satisfies CLAUDE.md §17.1 (single truth) by-default
— it does NOT redefine `<proj>_status.deployable_count`; it consumes
the production VIEW field as already maintained by P7-PR4B.

---

## 14. Forbidden

The following invariants are verified by source-text and reflection
tests; any future PR that violates them is rejected:

1. **No apply path** — no public `apply` / `commit` / `execute` symbol
   in `dir(sparse_canary_observer)` (`test_no_apply_method_exists`,
   `test_observation_no_apply_method`).
2. **No runtime-switchable mode flag** — no module-level
   `APPLY_MODE = ...` toggle that could flip the observer into apply
   mode at runtime (`test_no_runtime_switchable_apply_mode_exists`).
3. **No import by Arena / runtime / execution** — verified by source-text
   grep tests covering `arena_pipeline`, `arena23_orchestrator`,
   `arena45_orchestrator`, `arena_gates`, `alpha_signal_live`,
   `data_collector`, `alpha_dedup`, `alpha_ensemble`, `alpha_discovery`,
   capital allocator, risk module
   (`test_canary_observer_not_imported_by_generation_runtime`,
   `test_canary_observer_not_imported_by_arena_runtime`,
   `test_canary_observer_not_imported_by_execution_runtime`,
   `test_observer_output_not_consumed_by_runtime`).
4. **No module-level side effect on import** — module body imports
   stdlib + 3 zangetsu type/constant modules; no `chdir`, no logging
   handler attach, no DB connection, no env reads.
5. **No threshold redefinition** — observer does not introduce or
   change any A2 / A3 threshold constant
   (`test_observer_does_not_redefine_arena_thresholds`).
6. **No alpha-generation change** — verified by
   `test_no_alpha_generation_change`.
7. **No A2_MIN_TRADES drift** — `test_a2_min_trades_still_25` confirms
   the threshold is still 25 (no observer-induced drift).
8. **No Arena pass/fail change** — `test_arena_pass_fail_unchanged`.
9. **No champion promotion change** — `test_champion_promotion_unchanged`.
10. **No deployable_count semantics change** —
    `test_deployable_count_semantics_unchanged`.
11. **No execution / capital / risk change** —
    `test_execution_capital_risk_unchanged`.
12. **No allocator output consumption by generation runtime** —
    `test_allocator_output_not_consumed_by_generation_runtime`.
13. **No consumer (PR-C) import by generation runtime** —
    `test_feedback_consumer_not_imported_by_generation_runtime`.

---

## 15. Test coverage summary

| Suite | File | Tests | Status |
| --- | --- | --- | --- |
| Observer | `zangetsu/tests/test_sparse_canary_observer.py` | 71 | PASS |
| Readiness | `zangetsu/tests/test_sparse_canary_readiness.py` | 45 | PASS |
| **Subtotal (this PR)** | | **116** | **PASS** |
| Cross-suite (full repo) | (zangetsu test root) | 409 | PASS / 0 regression |

Test categories within the observer suite:

- **Schema lock** (8 tests) — `required_observation_fields()`,
  field-default invariants, mode / applied / canary_version
  invariants, event_type at serialization, JSON roundtrip.
- **Invariant resilience** (4 tests) — caller kwargs override,
  post-construction mutation override, no apply method, no
  runtime-switchable apply mode.
- **Helper functions** (12 tests) — composite score (defaults / clamp
  / bad input / custom weights / weights-sum-to-1.0), deployable
  density, profile diversity, profile collapse, consumer plan
  stability (object / dict / empty).
- **Success criteria** (16 tests) — S1 through S14 individual
  thresholds, S9–S12 caller-flag pass-through, S13 default
  insufficient, S14 sigma comparison, history-gating for delta
  criteria.
- **Failure criteria** (10 tests) — F1 through F9 trigger, F8
  rollback unavailable, F9 execution path touched, clean treatment
  passes all (no F triggered).
- **Top-level `observe()`** (8 tests) — end-to-end production path,
  rollback_required derivation, no input mutation, empty metrics,
  `safe_observe` defaults, plan-stability passthrough,
  alerts/evidence passthrough.
- **Isolation** (13 tests) — runtime non-import (generation / arena /
  execution), allocator/consumer/observer non-consumption, no apply
  symbol, no runtime-switchable mode, no alpha generation change, no
  threshold change, A2_MIN_TRADES still 25, Arena unchanged, champion
  unchanged, deployable_count semantics unchanged, no threshold
  redefinition, execution/capital/risk unchanged.

Readiness suite covers CR1–CR15 + structural isolation checks; both
suites together provide 116 / 116 PASS, 0 regression at merge.

---

## 16. Cross-reference

| Topic | Source |
| --- | --- |
| Mission / scope statement | TEAM ORDER 0-9S-CANARY §1.1, §6 |
| Composite scoring proposal | `docs/recovery/.../0-9r/05_ab_evaluation_and_canary_readiness.md` §6, `0-9s-ready/02_canary_success_failure_criteria.md` §2 / §6 |
| S1–S14 / F1–F9 abstract spec | `0-9s-ready/02_canary_success_failure_criteria.md` |
| Per-criterion concrete evaluation | `04_success_failure_criteria.md` (this PR, sister doc) |
| Three-layer dry-run invariant pattern | `0-9r-impl-dry/01_dry_run_consumer_design.md` §3 |
| Smoothing / step / floor (S8 / F6) | `0-9r-impl-dry/03_smoothing_and_step_limit_contract.md` |
| Runtime isolation watchlist (S10 / S12 / F9) | `0-9r-impl-dry/05_runtime_isolation_audit.md` |
| Verdict consumption (CR2 / F7) | `0-9r-impl-dry/04_attribution_audit_dependency.md` |
| Outcome metric (S5 / S13 / F2) | CLAUDE.md §17.1 / §17.3 / §17.4 |
| Audit tool (PR-B) | `zangetsu/tools/profile_attribution_audit.py` (`3219b805`) |
| Consumer module (PR-C) | `zangetsu/services/feedback_budget_consumer.py` (`fe3075f`) |
| CR1–CR15 readiness gate | `0-9s-ready/01_canary_readiness_gate.md` |
| Rollback SOP (F1–F9 actions) | `0-9s-ready/03_rollback_plan.md` |
| Alert path (all F#) | `0-9s-ready/04_alert_path.md` |
| Engine project rules | `zangetsu/CLAUDE.md` |

---

## 17. Limitations and explicit non-goals

- This PR does NOT activate any CANARY observation window. The
  separate `0-9S-CANARY-OBSERVE` activation order is required.
- This PR does NOT hot-swap any weights, does NOT change Arena
  pass/fail logic, does NOT modify champion promotion criteria, does
  NOT modify deployable_count semantics, does NOT touch execution /
  capital / risk path.
- Composite weights default to 0.4 / 0.4 / 0.2; the activation order
  must restate or override.
- `per_regime_stable` is caller-supplied; the observer does NOT compute
  per-regime stability itself (regime label join is the activation
  pipeline's responsibility).
- Telegram alert wiring is NOT in scope; `alerts_triggered` is a
  passthrough field.
- AKASHA witness writes are NOT in scope; the observation event is a
  payload, not a side effect.

PR delivery: observer module + readiness checker + 116 unit tests.
S/F criteria evaluation logic is callable but only takes effect
operationally when the activation order green-lights an observation
window.
