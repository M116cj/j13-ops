# 04 — Success / Failure Criteria — Concrete Evaluation

> Concrete-evaluation evidence for TEAM ORDER 0-9S-CANARY. Pairs with
> `03_sparse_canary_observer_design.md` (module surface) and elevates
> sister doc `0-9s-ready/02_canary_success_failure_criteria.md` from
> abstract spec to per-field, per-flag, per-test evaluation rules
> implemented in `zangetsu/services/sparse_canary_observer.py`.

---

## 1. Evaluator entry points

Two top-level evaluators in `sparse_canary_observer.py`:

| Entry point | Returns | Inputs |
| --- | --- | --- |
| `evaluate_success_criteria(treatment, baseline, *, no_threshold_change, no_arena_change, no_promotion_change, no_execution_change, per_regime_stable)` | `Dict[str, str]` mapping `S1..S14` → `PASS` / `FAIL` / `INSUFFICIENT_HISTORY` / `NOT_EVALUATED` | `treatment: Mapping[str, Any]`, `baseline: CanaryBaseline`, plus 5 caller-supplied flags |
| `evaluate_failure_criteria(treatment, baseline, *, rollback_executable, execution_path_touched, attribution_verdict)` | `Dict[str, str]` mapping `F1..F9` → `PASS` (no failure) / `FAIL` (criterion triggered) / `NOT_EVALUATED` | `treatment: Mapping[str, Any]`, `baseline: CanaryBaseline`, plus 3 caller-supplied flags |

Both are exception-safe: any internal error marks remaining criteria
`NOT_EVALUATED` and never raises. Both are called from `observe()` with
`treatment` populated from the just-built observation field set, so
that S/F decisions and the observation share an internally consistent
metric snapshot.

`STATUS_PASS = "PASS"`, `STATUS_FAIL = "FAIL"`,
`STATUS_INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"`,
`STATUS_NOT_EVALUATED = "NOT_EVALUATED"` are module-level enums.

The `treatment` mapping shape passed by `observe()`:

```python
{
    "a2_pass_rate": float,
    "a3_pass_rate": float,
    "signal_too_sparse_rate": float,    # success-only key
    "oos_fail_rate": float,
    "unknown_reject_rate": float,
    "deployable_count": int,
    "profile_collapse_detected": bool,
    "profile_diversity_score": float,
    "composite_score": float,           # success-only key
}
```

---

## 2. Baseline schema

```python
@dataclass
class CanaryBaseline:
    a2_pass_rate: float = 0.0
    a3_pass_rate: float = 0.0
    signal_too_sparse_rate: float = 0.0
    oos_fail_rate: float = 0.0
    unknown_reject_rate: float = 0.0
    deployable_count: int = 0
    composite_score: float = 0.0
    composite_score_stddev: Optional[float] = None
    sample_size_rounds: int = 0
```

`sample_size_rounds < 20` triggers `INSUFFICIENT_HISTORY` for all
delta-style success criteria (S1–S5, S14). The threshold is enforced
by `_has_enough_history(baseline, min_rounds=20)`.

`composite_score_stddev` is the noise-floor σ for S14; when missing or
non-positive, S14 is `INSUFFICIENT_HISTORY`.

---

## 3. Constants in play

| Constant | Value | Used by |
| --- | --- | --- |
| `S1_SPARSE_REDUCTION_MIN_REL` | `0.20` | S1 threshold |
| `S2_A2_PASS_RATE_INCREASE_MIN_PP` | `0.03` | S2 threshold |
| `S3_A3_PASS_RATE_TOLERANCE_PP` | `0.02` | S3 tolerance |
| `S4_OOS_FAIL_TOLERANCE_PP` | `0.03` | S4 tolerance |
| `S6_UNKNOWN_REJECT_VETO` | `0.05` | S6 threshold |
| `S14_COMPOSITE_DELTA_MIN_SIGMA` | `1.0` | S14 σ multiplier |
| `F4_UNKNOWN_REJECT_TRIGGER` | `0.05` | F4 trigger |
| `EXPLORATION_FLOOR` | `0.05` | S8 / F6 (via diversity score) |
| `DIVERSITY_CAP_MIN` | `2` | profile-collapse detection |
| `DEFAULT_COMPOSITE_W_A2` | `0.4` | composite score |
| `DEFAULT_COMPOSITE_W_A3` | `0.4` | composite score |
| `DEFAULT_COMPOSITE_W_DEPLOY` | `0.2` | composite score |
| `_eps` (local in F-evaluator) | `1e-9` | F1 / F3 epsilon-tolerant `>= 5pp` comparisons |

---

## 4. Success criteria — S1 through S14

For every `Si`: ID + name → threshold → data source → calculation →
INSUFFICIENT_HISTORY trigger → observable evidence.

### S1 — A2 SIGNAL_TOO_SPARSE rate decreases ≥ 20% relative

| Field | Value |
| --- | --- |
| Threshold | `(baseline.signal_too_sparse_rate - treatment.signal_too_sparse_rate) / baseline.signal_too_sparse_rate >= S1_SPARSE_REDUCTION_MIN_REL` (= 0.20) |
| Data source | `treatment.signal_too_sparse_rate` (from P7-PR4B `arena_batch_metrics.signal_too_sparse_rate`); `baseline.signal_too_sparse_rate` (caller-aggregated) |
| Calculation | ```python<br>rel = (baseline.signal_too_sparse_rate - t_sparse) / baseline.signal_too_sparse_rate<br>out["S1"] = STATUS_PASS if rel >= S1_SPARSE_REDUCTION_MIN_REL else STATUS_FAIL<br>``` |
| INSUFFICIENT_HISTORY trigger | `not _has_enough_history(baseline)` (i.e. `baseline.sample_size_rounds < 20`) **OR** `baseline.signal_too_sparse_rate <= 0` (zero baseline → relative drop undefined) |
| Observable evidence | `obs.signal_too_sparse_rate` populates from `treatment_metrics["signal_too_sparse_rate"]` in `observe()`; `obs.success_criteria_status["S1"]` reflects the result |

### S2 — A2 pass_rate improves ≥ +3 pp absolute

| Field | Value |
| --- | --- |
| Threshold | `treatment.a2_pass_rate - baseline.a2_pass_rate >= S2_A2_PASS_RATE_INCREASE_MIN_PP` (= 0.03) |
| Data source | `treatment.a2_pass_rate` (P7-PR4B `arena_batch_metrics.a2_pass_rate`); `baseline.a2_pass_rate` |
| Calculation | ```python<br>out["S2"] = STATUS_PASS if (t_a2 - baseline.a2_pass_rate) >= S2_A2_PASS_RATE_INCREASE_MIN_PP else STATUS_FAIL<br>``` |
| INSUFFICIENT_HISTORY trigger | `baseline.sample_size_rounds < 20` |
| Observable evidence | `obs.a2_pass_rate` populates from `treatment_metrics["a2_pass_rate"]`; `obs.success_criteria_status["S2"]` reflects the result |

### S3 — A3 pass_rate does not degrade > 2 pp

| Field | Value |
| --- | --- |
| Threshold | `baseline.a3_pass_rate - treatment.a3_pass_rate <= S3_A3_PASS_RATE_TOLERANCE_PP` (= 0.02) |
| Data source | `treatment.a3_pass_rate` (P7-PR4B `arena_batch_metrics.a3_pass_rate`); `baseline.a3_pass_rate` |
| Calculation | ```python<br>out["S3"] = STATUS_PASS if (baseline.a3_pass_rate - t_a3) <= S3_A3_PASS_RATE_TOLERANCE_PP else STATUS_FAIL<br>``` |
| INSUFFICIENT_HISTORY trigger | `baseline.sample_size_rounds < 20` |
| Observable evidence | `obs.a3_pass_rate`; `obs.success_criteria_status["S3"]` |

### S4 — OOS_FAIL does not increase > 3 pp

| Field | Value |
| --- | --- |
| Threshold | `treatment.oos_fail_rate - baseline.oos_fail_rate <= S4_OOS_FAIL_TOLERANCE_PP` (= 0.03) |
| Data source | `treatment.oos_fail_rate` (`arena_batch_metrics.oos_fail_rate`); `baseline.oos_fail_rate` |
| Calculation | ```python<br>out["S4"] = STATUS_PASS if (t_oos - baseline.oos_fail_rate) <= S4_OOS_FAIL_TOLERANCE_PP else STATUS_FAIL<br>``` |
| INSUFFICIENT_HISTORY trigger | `baseline.sample_size_rounds < 20` |
| Observable evidence | `obs.oos_fail_rate`; `obs.success_criteria_status["S4"]` |

### S5 — deployable_count maintained or improved

| Field | Value |
| --- | --- |
| Threshold | `treatment.deployable_count >= baseline.deployable_count` |
| Data source | `treatment.deployable_count` (`<proj>_status.deployable_count` per CLAUDE.md §17.1; treatment-cohort filtered by caller); `baseline.deployable_count` |
| Calculation | ```python<br>out["S5"] = STATUS_PASS if t_deploy >= baseline.deployable_count else STATUS_FAIL<br>``` |
| INSUFFICIENT_HISTORY trigger | `baseline.sample_size_rounds < 20` |
| Observable evidence | `obs.deployable_count`; `obs.success_criteria_status["S5"]` |

### S6 — UNKNOWN_REJECT < 0.05

| Field | Value |
| --- | --- |
| Threshold | `treatment.unknown_reject_rate < S6_UNKNOWN_REJECT_VETO` (= 0.05) |
| Data source | `treatment.unknown_reject_rate` (cross-stage 7-day rolling, caller-aggregated from `arena_batch_metrics.unknown_reject_count / entered_count`) |
| Calculation | ```python<br>out["S6"] = STATUS_PASS if t_unknown < S6_UNKNOWN_REJECT_VETO else STATUS_FAIL<br>``` |
| INSUFFICIENT_HISTORY trigger | (none — absolute-threshold criterion; evaluated against current data only) |
| Observable evidence | `obs.unknown_reject_rate`; `obs.success_criteria_status["S6"]` |

### S7 — profile collapse must NOT occur

| Field | Value |
| --- | --- |
| Threshold | `treatment.profile_collapse_detected is False` |
| Data source | `treatment.profile_collapse_detected` (computed by `detect_profile_collapse(profile_weights, diversity_cap_min=DIVERSITY_CAP_MIN)` in `observe()`) |
| Calculation | ```python<br>out["S7"] = STATUS_FAIL if t_collapse else STATUS_PASS<br>``` |
| INSUFFICIENT_HISTORY trigger | (none — evaluated each round; `profile_weights=None` → `profile_collapse_detected=False` → S7 PASS by default with no data) |
| Observable evidence | `obs.profile_collapse_detected`; `obs.success_criteria_status["S7"]` |

### S8 — exploration floor active (diversity > 0)

| Field | Value |
| --- | --- |
| Threshold | `treatment.profile_diversity_score > 0` (proxy for "at least one profile at or above EXPLORATION_FLOOR=0.05") |
| Data source | `treatment.profile_diversity_score` (computed by `compute_profile_diversity(profile_weights)` in `observe()`) |
| Calculation | ```python<br>out["S8"] = STATUS_PASS if t_diversity > 0 else STATUS_FAIL<br>``` |
| INSUFFICIENT_HISTORY trigger | (none — `profile_weights=None` → `diversity_score=0.0` → S8 FAIL, callers must supply weights) |
| Observable evidence | `obs.profile_diversity_score`; `obs.success_criteria_status["S8"]` |

### S9 — no threshold changes (caller-supplied flag)

| Field | Value |
| --- | --- |
| Threshold | caller-supplied `no_threshold_change` flag is `True` |
| Data source | Controlled-diff CI verdict from 0-9M (A2_MIN_TRADES / ATR / TRAIL / FIXED grid watchlist) propagated by caller |
| Calculation | ```python<br>out["S9"] = STATUS_PASS if no_threshold_change else STATUS_FAIL<br>``` |
| INSUFFICIENT_HISTORY trigger | (none — caller-flag gate) |
| Observable evidence | `obs.success_criteria_status["S9"]`; the flag itself is not stored in the observation (callers are expected to log the diff separately) |

### S10 — no Arena pass/fail logic changes (caller-supplied flag)

| Field | Value |
| --- | --- |
| Threshold | caller-supplied `no_arena_change` flag is `True` |
| Data source | Controlled-diff CI verdict on `arena_pipeline.py`, `arena23_orchestrator.py`, `arena45_orchestrator.py`, `arena_gates.py` |
| Calculation | ```python<br>out["S10"] = STATUS_PASS if no_arena_change else STATUS_FAIL<br>``` |
| INSUFFICIENT_HISTORY trigger | (none) |
| Observable evidence | `obs.success_criteria_status["S10"]` |

### S11 — no champion promotion criteria changes (caller-supplied flag)

| Field | Value |
| --- | --- |
| Threshold | caller-supplied `no_promotion_change` flag is `True` |
| Data source | Controlled-diff CI verdict on `champion_pipeline.py` and champion-related SQL |
| Calculation | ```python<br>out["S11"] = STATUS_PASS if no_promotion_change else STATUS_FAIL<br>``` |
| INSUFFICIENT_HISTORY trigger | (none) |
| Observable evidence | `obs.success_criteria_status["S11"]` |

### S12 — no execution / capital / risk path changes (caller-supplied flag)

| Field | Value |
| --- | --- |
| Threshold | caller-supplied `no_execution_change` flag is `True` |
| Data source | Controlled-diff CI verdict on `alpha_signal_live.py`, `data_collector.py`, `alpha_dedup.py`, `alpha_ensemble.py`, `alpha_discovery.py`, capital allocator, risk module |
| Calculation | ```python<br>out["S12"] = STATUS_PASS if no_execution_change else STATUS_FAIL<br>``` |
| INSUFFICIENT_HISTORY trigger | (none) |
| Observable evidence | `obs.success_criteria_status["S12"]` |

### S13 — per-regime stability (caller-supplied)

| Field | Value |
| --- | --- |
| Threshold | caller-supplied `per_regime_stable: Optional[bool]` — `True` for PASS, `False` for FAIL, `None` for INSUFFICIENT_HISTORY |
| Data source | Caller-computed per-regime deployable_count median (per regime: bull / bear / range / vol-spike) using `<proj>_status` joined with regime label |
| Calculation | ```python<br>if per_regime_stable is None:<br>    out["S13"] = STATUS_INSUFFICIENT_HISTORY<br>else:<br>    out["S13"] = STATUS_PASS if per_regime_stable else STATUS_FAIL<br>``` |
| INSUFFICIENT_HISTORY trigger | `per_regime_stable is None` (default — caller did not supply a regime breakdown) |
| Observable evidence | `obs.success_criteria_status["S13"]` |

### S14 — composite score improves ≥ 1σ above noise

| Field | Value |
| --- | --- |
| Threshold | `treatment.composite_score - baseline.composite_score >= S14_COMPOSITE_DELTA_MIN_SIGMA * baseline.composite_score_stddev` (= 1.0 σ) |
| Data source | `treatment.composite_score` (computed in `observe()` via `compute_composite_score(a2, a3, deploy_density, w_a2=0.4, w_a3=0.4, w_deploy=0.2)`); `baseline.composite_score`; `baseline.composite_score_stddev` (caller-supplied 30-day σ) |
| Calculation | ```python<br>delta = t_composite - baseline.composite_score<br>sigma = baseline.composite_score_stddev<br>out["S14"] = STATUS_PASS if delta >= S14_COMPOSITE_DELTA_MIN_SIGMA * sigma else STATUS_FAIL<br>``` |
| INSUFFICIENT_HISTORY trigger | `baseline.sample_size_rounds < 20` **OR** `baseline.composite_score_stddev is None` **OR** `baseline.composite_score_stddev <= 0` |
| Observable evidence | `obs.composite_score`, `obs.baseline_composite_score`, `obs.composite_delta`; `obs.success_criteria_status["S14"]` |

---

## 5. Failure criteria — F1 through F9

`PASS` = no failure detected; `FAIL` = criterion triggered, rollback required.

The F-evaluator uses an epsilon `_eps = 1e-9` for `>= 5pp` thresholds
to absorb IEEE-754 rounding (e.g. `0.30 - 0.25 = 0.04999...9`).

### F1 — A2 improves but A3 collapses (≥ 5 pp drop)

| Field | Value |
| --- | --- |
| Trigger condition | `t_a2 > baseline.a2_pass_rate` **AND** `(baseline.a3_pass_rate - t_a3) >= 0.05 - 1e-9` |
| Calculation | ```python<br>a2_improves = t_a2 > baseline.a2_pass_rate<br>a3_collapse = (baseline.a3_pass_rate - t_a3) >= 0.05 - _eps<br>out["F1"] = STATUS_FAIL if (a2_improves and a3_collapse) else STATUS_PASS<br>``` |
| `rollback_required` action | `obs.failure_criteria_status["F1"] == STATUS_FAIL` → contributes True to `any(... == STATUS_FAIL)` → `rollback_required = True` |

### F2 — A2 improves but deployable_count falls

| Field | Value |
| --- | --- |
| Trigger condition | `t_a2 > baseline.a2_pass_rate` **AND** `t_deploy < baseline.deployable_count` |
| Calculation | ```python<br>a2_improves = t_a2 > baseline.a2_pass_rate<br>deploy_falls = t_deploy < baseline.deployable_count<br>out["F2"] = STATUS_FAIL if (a2_improves and deploy_falls) else STATUS_PASS<br>``` |
| `rollback_required` action | F2 FAIL → rollback_required True |

### F3 — OOS_FAIL increases ≥ 5 pp

| Field | Value |
| --- | --- |
| Trigger condition | `(t_oos - baseline.oos_fail_rate) >= 0.05 - 1e-9` |
| Calculation | ```python<br>oos_material = (t_oos - baseline.oos_fail_rate) >= 0.05 - _eps<br>out["F3"] = STATUS_FAIL if oos_material else STATUS_PASS<br>``` |
| `rollback_required` action | F3 FAIL → rollback_required True |

### F4 — UNKNOWN_REJECT > 0.05

| Field | Value |
| --- | --- |
| Trigger condition | `t_unknown > F4_UNKNOWN_REJECT_TRIGGER` (= 0.05) |
| Calculation | ```python<br>out["F4"] = STATUS_FAIL if t_unknown > F4_UNKNOWN_REJECT_TRIGGER else STATUS_PASS<br>``` |
| `rollback_required` action | F4 FAIL → rollback_required True. F4 is "永不 j13 override" per `0-9s-ready` §4.4 |

### F5 — profile collapse occurs

| Field | Value |
| --- | --- |
| Trigger condition | `treatment.profile_collapse_detected is True` |
| Calculation | ```python<br>out["F5"] = STATUS_FAIL if t_collapse else STATUS_PASS<br>``` |
| `rollback_required` action | F5 FAIL → rollback_required True |

### F6 — exploration floor violated (diversity ≤ 0)

| Field | Value |
| --- | --- |
| Trigger condition | `treatment.profile_diversity_score <= 0.0` (no profile at or above EXPLORATION_FLOOR=0.05) |
| Calculation | ```python<br>out["F6"] = STATUS_FAIL if t_diversity <= 0.0 else STATUS_PASS<br>``` |
| `rollback_required` action | F6 FAIL → rollback_required True. F6 is "永不 j13 override" per `0-9s-ready` §4.6 |

### F7 — attribution verdict regresses to RED

| Field | Value |
| --- | --- |
| Trigger condition | `str(attribution_verdict).upper() == VERDICT_RED` (caller-supplied; sourced from `zangetsu/tools/profile_attribution_audit.py`) |
| Calculation | ```python<br>out["F7"] = STATUS_FAIL if str(attribution_verdict).upper() == VERDICT_RED else STATUS_PASS<br>``` |
| `rollback_required` action | F7 FAIL → rollback_required True. Consumer ceases emitting ACTIONABLE plans (per `0-9r-impl-dry/04_attribution_audit_dependency.md`) |

### F8 — rollback cannot execute

| Field | Value |
| --- | --- |
| Trigger condition | caller-supplied `rollback_executable` flag is `False` |
| Calculation | ```python<br>out["F8"] = STATUS_PASS if rollback_executable else STATUS_FAIL<br>``` |
| `rollback_required` action | F8 FAIL → rollback_required True. CANARY permanently held until rollback path is repaired and re-drilled ≥ 3 times per `0-9s-ready` §4.8 |

### F9 — unexpected execution / capital / risk path touched

| Field | Value |
| --- | --- |
| Trigger condition | caller-supplied `execution_path_touched` flag is `True` (from controlled-diff CI watchlist) |
| Calculation | ```python<br>out["F9"] = STATUS_FAIL if execution_path_touched else STATUS_PASS<br>``` |
| `rollback_required` action | F9 FAIL → rollback_required True. Triggers governance audit + §17.5 review |

---

## 6. `rollback_required` derivation

After both evaluators run, `observe()` derives `rollback_required` as:

```python
obs.rollback_required = any(
    v == STATUS_FAIL for v in obs.failure_criteria_status.values()
)
```

Equivalent: any single `Fi` triggered → `rollback_required = True`.
Verified by `test_observe_rollback_required_when_failure_triggered`
(line 566) and `test_observe_no_rollback_when_clean` (line 578).

`safe_observe()` also forces `rollback_required = True` when any
exception escapes `observe()` (defense-in-depth: a corrupted evaluator
state must not silently produce a green observation).

---

## 7. Test mapping — each criterion to a pytest test

All tests live in `zangetsu/tests/test_sparse_canary_observer.py`.
Suite size: 71. Combined with `test_sparse_canary_readiness.py` (45):
116 / 116 PASS. Cross-suite: 409 PASS / 0 regression.

### Success criteria

| Criterion | Test name (line) | Validates |
| --- | --- | --- |
| S1 | `test_success_requires_sparse_rate_down_20_percent` (287) | ≥ 20% relative drop required |
| S2 | `test_success_requires_a2_pass_rate_up_3pp` (303) | ≥ 3 pp absolute improvement required |
| S3 | `test_success_blocks_a3_degradation_over_2pp` (313) | > 2 pp drop fails |
| S4 | `test_success_blocks_oos_fail_increase_over_3pp` (323) | > 3 pp increase fails |
| S5 | `test_success_requires_deployable_count_non_degradation` (329) | `treatment >= baseline` required |
| S6 | `test_success_requires_unknown_reject_below_005` (337) | `< 0.05` required |
| S7 | `test_success_blocks_profile_collapse` (345) | collapse → FAIL |
| S8 | `test_success_requires_exploration_floor_active` (352) | diversity > 0 required |
| S9–S12 | `test_success_s9_to_s12_rely_on_caller_flags` (379) | caller-supplied flags pass-through |
| S13 (default) | `test_success_s13_per_regime_default_insufficient` (403) | `per_regime_stable=None` → INSUFFICIENT_HISTORY |
| S13 (true) | `test_success_s13_per_regime_pass_when_caller_flags_true` (408) | `per_regime_stable=True` → PASS |
| S14 (PASS) | `test_success_s14_pass_when_composite_jumps_one_sigma` (365) | delta ≥ 1σ → PASS |
| S14 (FAIL) | `test_success_s14_fail_when_composite_stagnant` (372) | flat composite → FAIL |
| S14 (INSUFFICIENT) | `test_success_marks_composite_insufficient_history_when_needed` (359) | missing σ → INSUFFICIENT_HISTORY |
| Delta history gate (S1–S5, S14) | `test_success_no_history_marks_insufficient_for_delta_criteria` (415) | `sample_size_rounds < 20` → all delta criteria INSUFFICIENT_HISTORY |

### Failure criteria

| Criterion | Test name (line) | Validates |
| --- | --- | --- |
| F1 | `test_failure_a2_improves_but_a3_collapses` (427) | A2 ↑ AND A3 ↓ ≥ 5 pp → FAIL |
| F2 | `test_failure_a2_improves_but_deployable_falls` (436) | A2 ↑ AND deployable ↓ → FAIL |
| F3 | `test_failure_oos_fail_increases_materially` (444) | OOS ↑ ≥ 5 pp → FAIL |
| F4 | `test_failure_unknown_reject_above_005` (452) | unknown > 0.05 → FAIL |
| F5 | `test_failure_profile_collapse` (460) | collapse → FAIL |
| F6 | `test_failure_exploration_floor_violation` (467) | diversity ≤ 0 → FAIL |
| F7 | `test_failure_attribution_regresses_to_red` (474) | verdict RED → FAIL |
| F8 | `test_failure_rollback_unavailable` (483) | `rollback_executable=False` → FAIL |
| F9 | `test_failure_execution_capital_risk_path_touched` (492) | `execution_path_touched=True` → FAIL |
| Clean baseline | `test_failure_clean_treatment_passes_all` (501) | clean treatment → all F PASS |

### Top-level `observe()` integration

| Test | Line | Validates |
| --- | --- | --- |
| `test_observe_produces_dry_run_canary_observation` | 529 | mode / applied / version invariants |
| `test_observe_populates_success_criteria_status` | 545 | observe() wires evaluator output |
| `test_observe_populates_failure_criteria_status` | 556 | observe() wires evaluator output |
| `test_observe_rollback_required_when_failure_triggered` | 566 | rollback_required derivation |
| `test_observe_no_rollback_when_clean` | 578 | rollback_required = False on clean |
| `test_observe_does_not_mutate_input` | 590 | input dict snapshot unchanged |
| `test_observe_handles_empty_metrics` | 601 | empty input → safe defaults |
| `test_safe_observe_returns_default_on_error` | 611 | safe_observe → rollback_required True + alert |

### Status totals

```
test_sparse_canary_observer.py    71 PASS   0 fail
test_sparse_canary_readiness.py   45 PASS   0 fail
combined this PR                  116 PASS  0 fail
cross-suite (zangetsu repo)       409 PASS  0 regression
```

---

## 8. Order acceptance criteria mapping

TEAM ORDER 0-9S-CANARY §19 lists 31 acceptance criteria. This PR
satisfies criteria #1–12 and #14–31; criterion #13 (tests pass) is
satisfied by the 116 / 116 PASS result.

| §19 # | Criterion | Satisfied by |
| --- | --- | --- |
| 1 | Module exists at `zangetsu/services/sparse_canary_observer.py` | observer module shipped |
| 2 | Module is pure-Python, no IO at import | `03_sparse_canary_observer_design.md` §3 imports list |
| 3 | `CANARY_VERSION = "0-9S-CANARY"` constant exported | `sparse_canary_observer.py` line 75 |
| 4 | `MODE_DRY_RUN_CANARY = "DRY_RUN_CANARY"` constant exported | line 79 |
| 5 | `APPLIED_FALSE = False` constant exported | line 80 |
| 6 | `EVENT_TYPE_SPARSE_CANARY_OBSERVATION = "sparse_canary_observation"` | line 77 |
| 7 | `SparseCanaryObservation` dataclass with 35 fields | dataclass at line 134; `required_observation_fields()` returns canonical names |
| 8 | Three-layer dry-run invariant | §4 of design doc |
| 9 | No public `apply` / `commit` / `execute` symbol | `test_no_apply_method_exists` |
| 10 | Composite scoring with default 0.4 / 0.4 / 0.2 weights | `compute_composite_score()` + `test_default_composite_weights_sum_to_one` |
| 11 | Composite weight override path | `composite_weights` kwarg + `test_compute_composite_score_custom_weights` |
| 12 | Deployable density formula clamped `[0, 1]` | `compute_deployable_density()` + `test_compute_deployable_density` |
| 13 | All tests pass | 116 / 116 PASS |
| 14 | Profile diversity uses EXPLORATION_FLOOR=0.05 | `EXPLORATION_FLOOR` constant + `compute_profile_diversity` |
| 15 | Profile collapse uses DIVERSITY_CAP_MIN=2 | `DIVERSITY_CAP_MIN` constant + `detect_profile_collapse` |
| 16 | Consumer plan stability accepts both object and dict plans | `test_compute_consumer_plan_stability_handles_dict_plans` |
| 17 | S1–S14 evaluator function | `evaluate_success_criteria()` |
| 18 | F1–F9 evaluator function | `evaluate_failure_criteria()` |
| 19 | INSUFFICIENT_HISTORY for delta criteria when `sample_size_rounds < 20` | `_has_enough_history()` + `test_success_no_history_marks_insufficient_for_delta_criteria` |
| 20 | S14 INSUFFICIENT_HISTORY when σ missing or non-positive | `test_success_marks_composite_insufficient_history_when_needed` |
| 21 | rollback_required = any(F == FAIL) | `observe()` line 712–714 + `test_observe_rollback_required_when_failure_triggered` |
| 22 | safe_observe() returns rollback_required=True on exception | `test_safe_observe_returns_default_on_error` |
| 23 | observe() never mutates inputs | `test_observe_does_not_mutate_input` |
| 24 | observe() never raises | wrapped in outer try/except; `test_observe_handles_empty_metrics` |
| 25 | serialize_observation() emits valid JSON | `test_serialize_observation_emits_valid_json` |
| 26 | Observer not imported by generation runtime | `test_canary_observer_not_imported_by_generation_runtime` |
| 27 | Observer not imported by Arena runtime | `test_canary_observer_not_imported_by_arena_runtime` |
| 28 | Observer not imported by execution runtime | `test_canary_observer_not_imported_by_execution_runtime` |
| 29 | No threshold drift introduced | `test_no_threshold_change`, `test_a2_min_trades_still_25` |
| 30 | No Arena pass/fail / champion / deployable_count semantics drift | `test_arena_pass_fail_unchanged`, `test_champion_promotion_unchanged`, `test_deployable_count_semantics_unchanged` |
| 31 | Readiness checker shipped (CR1–CR15) | `zangetsu/tools/sparse_canary_readiness_check.py` + 45 tests |

---

## 9. Aggregation handling (downstream of this PR)

The observer emits per-round observation events; aggregation across a
multi-day CANARY window is **not** in this PR's scope. The activation
order `0-9S-CANARY-OBSERVE` is responsible for:

- Daily success-day count: all S1–S14 must be PASS (any S = FAIL or
  any F = FAIL within a day → not a success-day).
- Weekly success threshold: ≥ 5 success-days in 7 → weekly pass.
- 14-day window: ≥ 10 success-days **and** zero F-trigger over the
  whole window → enter 0-9T production rollout evaluation.
- F-trigger response: any F = FAIL → immediate rollback hot-swap +
  Telegram + Calcifer + AKASHA witness.

Aggregation rules quoted verbatim from
`0-9s-ready/02_canary_success_failure_criteria.md` §5; this PR does
not reimplement them.

---

## 10. Limitations and explicit non-goals

- This PR does NOT activate any CANARY observation window.
- This PR does NOT compute baselines automatically; baselines are
  caller-supplied (`CanaryBaseline` dataclass, populated upstream).
- This PR does NOT compute per-regime stability; `per_regime_stable`
  is caller-supplied.
- This PR does NOT compute composite-score noise σ; that is caller-
  supplied via `baseline.composite_score_stddev`.
- This PR does NOT wire alerts (Telegram / Calcifer); the
  `alerts_triggered` field is a caller-populated passthrough.
- This PR does NOT write to `<proj>_status` VIEW or any DB.
- This PR does NOT change any threshold, Arena gate, champion
  promotion criterion, deployable_count semantic, or execution /
  capital / risk path.

S/F evaluation logic is shipped, locked, and tested. Operational
effect requires a separate activation order.
