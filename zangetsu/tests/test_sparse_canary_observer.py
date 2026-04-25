"""Tests for TEAM ORDER 0-9S-CANARY — Sparse-Candidate Dry-Run CANARY
Observer.

Covers:
  - 12.2 schema lock
  - dry-run invariants (mode / applied / canary_version)
  - composite scoring math
  - profile diversity / collapse detection
  - 12.3 success criteria S1-S14
  - 12.4 failure criteria F1-F9
  - 12.5 runtime isolation
  - 12.6 behavior invariance
"""

from __future__ import annotations

import json
import pathlib

import pytest

from zangetsu.services.sparse_canary_observer import (
    APPLIED_FALSE,
    CANARY_VERSION,
    CanaryBaseline,
    DEFAULT_COMPOSITE_W_A2,
    DEFAULT_COMPOSITE_W_A3,
    DEFAULT_COMPOSITE_W_DEPLOY,
    EVENT_TYPE_SPARSE_CANARY_OBSERVATION,
    EXPLORATION_FLOOR,
    MODE_DRY_RUN_CANARY,
    SparseCanaryObservation,
    STATUS_FAIL,
    STATUS_INSUFFICIENT_HISTORY,
    STATUS_NOT_EVALUATED,
    STATUS_PASS,
    VERDICT_GREEN,
    VERDICT_RED,
    VERDICT_UNAVAILABLE,
    VERDICT_YELLOW,
    compute_composite_score,
    compute_consumer_plan_stability,
    compute_deployable_density,
    compute_profile_diversity,
    detect_profile_collapse,
    evaluate_failure_criteria,
    evaluate_success_criteria,
    observe,
    required_observation_fields,
    safe_observe,
    serialize_observation,
)
from zangetsu.services.feedback_budget_consumer import (
    PLAN_STATUS_ACTIONABLE,
    PLAN_STATUS_BLOCKED,
    PLAN_STATUS_NON_ACTIONABLE,
    SparseCandidateDryRunPlan,
)


_SERVICES = pathlib.Path(__file__).resolve().parent.parent / "services"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _baseline(
    a2=0.20, a3=0.30, sparse=0.50, oos=0.10, unknown=0.02,
    deploy=10, composite=0.32, stddev=0.02, sample=25,
):
    return CanaryBaseline(
        a2_pass_rate=a2,
        a3_pass_rate=a3,
        signal_too_sparse_rate=sparse,
        oos_fail_rate=oos,
        unknown_reject_rate=unknown,
        deployable_count=deploy,
        composite_score=composite,
        composite_score_stddev=stddev,
        sample_size_rounds=sample,
    )


def _treatment_metrics(
    a1=0.40, a2=0.30, a3=0.30, sparse=0.30, oos=0.10, unknown=0.02,
    deploy=12, passed_a3=20,
):
    return {
        "a1_pass_rate": a1,
        "a2_pass_rate": a2,
        "a3_pass_rate": a3,
        "signal_too_sparse_rate": sparse,
        "oos_fail_rate": oos,
        "unknown_reject_rate": unknown,
        "deployable_count": deploy,
        "passed_a3": passed_a3,
    }


# ---------------------------------------------------------------------------
# 1. Schema + dry-run invariants
# ---------------------------------------------------------------------------


def test_sparse_canary_observation_schema_contains_required_fields():
    fields = required_observation_fields()
    for must_have in (
        "telemetry_version", "canary_id", "run_id", "created_at",
        "mode", "applied", "canary_version",
        "readiness_verdict", "attribution_verdict",
        "observation_window_start", "observation_window_end",
        "observation_window_complete",
        "rounds_observed", "profiles_observed",
        "unknown_reject_rate", "signal_too_sparse_rate",
        "a1_pass_rate", "a2_pass_rate", "a3_pass_rate",
        "oos_fail_rate", "deployable_count", "deployable_density",
        "composite_score", "baseline_composite_score", "composite_delta",
        "profile_diversity_score", "profile_collapse_detected",
        "consumer_plan_stability",
        "success_criteria_status", "failure_criteria_status",
        "rollback_required", "alerts_triggered", "evidence_paths",
        "source",
    ):
        assert must_have in fields, f"missing {must_have!r}"


def test_sparse_canary_observation_mode_is_dry_run_canary():
    obs = SparseCanaryObservation(run_id="r")
    assert obs.mode == "DRY_RUN_CANARY"


def test_sparse_canary_observation_applied_false():
    obs = SparseCanaryObservation(run_id="r")
    assert obs.applied is False


def test_sparse_canary_observation_version_is_0_9s_canary():
    obs = SparseCanaryObservation(run_id="r")
    assert obs.canary_version == "0-9S-CANARY"


def test_observation_invariants_resilient_to_caller_kwargs():
    obs = SparseCanaryObservation(
        run_id="r",
        mode="APPLIED",
        applied=True,
        canary_version="HACKED",
    )
    assert obs.mode == "DRY_RUN_CANARY"
    assert obs.applied is False
    assert obs.canary_version == "0-9S-CANARY"


def test_observation_invariants_resilient_to_post_construction_mutation():
    obs = SparseCanaryObservation(run_id="r")
    obs.mode = "APPLIED"
    obs.applied = True
    obs.canary_version = "HACKED"
    e = obs.to_event()
    assert e["mode"] == "DRY_RUN_CANARY"
    assert e["applied"] is False
    assert e["canary_version"] == "0-9S-CANARY"


def test_observation_event_type_is_sparse_canary_observation():
    obs = SparseCanaryObservation(run_id="r")
    assert obs.to_event()["event_type"] == EVENT_TYPE_SPARSE_CANARY_OBSERVATION


def test_serialize_observation_emits_valid_json():
    obs = observe(
        run_id="r",
        treatment_metrics=_treatment_metrics(),
        baseline=_baseline(),
    )
    payload = json.loads(serialize_observation(obs))
    assert payload["mode"] == "DRY_RUN_CANARY"
    assert payload["applied"] is False
    assert payload["canary_version"] == "0-9S-CANARY"


def test_observation_no_apply_method():
    import zangetsu.services.sparse_canary_observer as mod
    publics = [n for n in dir(mod) if not n.startswith("_")]
    for name in publics:
        assert not name.lower().startswith("apply"), (
            f"observer module exports apply-shaped name {name!r}"
        )


# ---------------------------------------------------------------------------
# 2. Composite scoring + helpers
# ---------------------------------------------------------------------------


def test_compute_composite_score_default_weights():
    s = compute_composite_score(0.5, 0.5, 0.5)
    # 0.4*0.5 + 0.4*0.5 + 0.2*0.5 = 0.5
    assert abs(s - 0.5) < 1e-9


def test_compute_composite_score_clamps_to_unit():
    assert compute_composite_score(2.0, 2.0, 2.0) == 1.0
    assert compute_composite_score(-1.0, -1.0, -1.0) == 0.0


def test_compute_composite_score_handles_bad_input():
    assert compute_composite_score(float("nan"), 0.5, 0.5) >= 0
    assert compute_composite_score(None, None, None) == 0.0  # type: ignore[arg-type]


def test_compute_composite_score_custom_weights():
    s = compute_composite_score(1.0, 0.0, 0.0, w_a2=0.7, w_a3=0.2, w_deploy=0.1)
    assert abs(s - 0.7) < 1e-9


def test_default_composite_weights_sum_to_one():
    assert abs(DEFAULT_COMPOSITE_W_A2 + DEFAULT_COMPOSITE_W_A3 + DEFAULT_COMPOSITE_W_DEPLOY - 1.0) < 1e-9


def test_compute_deployable_density():
    assert compute_deployable_density(5, 10) == 0.5
    assert compute_deployable_density(5, 0) == 0.0  # clamp on zero passed
    assert compute_deployable_density(50, 10) == 1.0  # clamp at 1.0


def test_compute_profile_diversity():
    weights = {"gp_a": 0.3, "gp_b": 0.3, "gp_c": 0.4}
    assert compute_profile_diversity(weights) == 1.0  # all >= floor


def test_compute_profile_diversity_below_floor():
    weights = {"gp_a": 0.95, "gp_b": 0.04}  # gp_b < 0.05
    assert abs(compute_profile_diversity(weights) - 0.5) < 1e-9


def test_compute_profile_diversity_empty():
    assert compute_profile_diversity({}) == 0.0


def test_detect_profile_collapse_when_one_profile_dominates():
    # Only one profile at floor (gp_a = 1.0); gp_b = 0
    weights = {"gp_a": 1.0, "gp_b": 0.0}
    assert detect_profile_collapse(weights) is True


def test_detect_profile_collapse_when_diverse():
    weights = {"gp_a": 0.3, "gp_b": 0.3, "gp_c": 0.4}
    assert detect_profile_collapse(weights) is False


def test_detect_profile_collapse_empty():
    assert detect_profile_collapse({}) is False


def test_compute_consumer_plan_stability_with_actionable_plans():
    plans = [
        SparseCandidateDryRunPlan(run_id="r", plan_status=PLAN_STATUS_ACTIONABLE),
        SparseCandidateDryRunPlan(run_id="r", plan_status=PLAN_STATUS_ACTIONABLE),
        SparseCandidateDryRunPlan(run_id="r", plan_status=PLAN_STATUS_NON_ACTIONABLE),
        SparseCandidateDryRunPlan(run_id="r", plan_status=PLAN_STATUS_BLOCKED),
    ]
    s = compute_consumer_plan_stability(plans)
    assert abs(s - 0.5) < 1e-9


def test_compute_consumer_plan_stability_handles_dict_plans():
    plans = [
        {"plan_status": PLAN_STATUS_ACTIONABLE},
        {"plan_status": PLAN_STATUS_NON_ACTIONABLE},
    ]
    assert abs(compute_consumer_plan_stability(plans) - 0.5) < 1e-9


def test_compute_consumer_plan_stability_handles_empty():
    assert compute_consumer_plan_stability([]) == 0.0
    assert compute_consumer_plan_stability(None) == 0.0


# ---------------------------------------------------------------------------
# 3. Success criteria S1-S14
# ---------------------------------------------------------------------------


def test_success_requires_sparse_rate_down_20_percent():
    # baseline sparse=0.5, treatment sparse=0.30 → 40% relative drop → PASS
    out = evaluate_success_criteria(
        _treatment_metrics(sparse=0.30),
        _baseline(sparse=0.50),
    )
    assert out["S1"] == STATUS_PASS

    # treatment sparse=0.45 → only 10% drop → FAIL
    out = evaluate_success_criteria(
        _treatment_metrics(sparse=0.45),
        _baseline(sparse=0.50),
    )
    assert out["S1"] == STATUS_FAIL


def test_success_requires_a2_pass_rate_up_3pp():
    # baseline a2=0.20, treatment a2=0.25 → +5pp → PASS
    out = evaluate_success_criteria(_treatment_metrics(a2=0.25), _baseline(a2=0.20))
    assert out["S2"] == STATUS_PASS

    # +1pp → FAIL
    out = evaluate_success_criteria(_treatment_metrics(a2=0.21), _baseline(a2=0.20))
    assert out["S2"] == STATUS_FAIL


def test_success_blocks_a3_degradation_over_2pp():
    # baseline a3=0.30, treatment a3=0.27 → -3pp → FAIL
    out = evaluate_success_criteria(_treatment_metrics(a3=0.27), _baseline(a3=0.30))
    assert out["S3"] == STATUS_FAIL

    # -1pp → PASS
    out = evaluate_success_criteria(_treatment_metrics(a3=0.29), _baseline(a3=0.30))
    assert out["S3"] == STATUS_PASS


def test_success_blocks_oos_fail_increase_over_3pp():
    # baseline oos=0.10, treatment oos=0.14 → +4pp → FAIL
    out = evaluate_success_criteria(_treatment_metrics(oos=0.14), _baseline(oos=0.10))
    assert out["S4"] == STATUS_FAIL


def test_success_requires_deployable_count_non_degradation():
    out = evaluate_success_criteria(_treatment_metrics(deploy=11), _baseline(deploy=10))
    assert out["S5"] == STATUS_PASS

    out = evaluate_success_criteria(_treatment_metrics(deploy=8), _baseline(deploy=10))
    assert out["S5"] == STATUS_FAIL


def test_success_requires_unknown_reject_below_005():
    out = evaluate_success_criteria(_treatment_metrics(unknown=0.04), _baseline())
    assert out["S6"] == STATUS_PASS

    out = evaluate_success_criteria(_treatment_metrics(unknown=0.06), _baseline())
    assert out["S6"] == STATUS_FAIL


def test_success_blocks_profile_collapse():
    treatment = _treatment_metrics()
    treatment["profile_collapse_detected"] = True
    out = evaluate_success_criteria(treatment, _baseline())
    assert out["S7"] == STATUS_FAIL


def test_success_requires_exploration_floor_active():
    treatment = _treatment_metrics()
    treatment["profile_diversity_score"] = 0.0
    out = evaluate_success_criteria(treatment, _baseline())
    assert out["S8"] == STATUS_FAIL


def test_success_marks_composite_insufficient_history_when_needed():
    # baseline.sample_size_rounds=5 < 20 → INSUFFICIENT_HISTORY
    out = evaluate_success_criteria(_treatment_metrics(), _baseline(sample=5))
    assert out["S14"] == STATUS_INSUFFICIENT_HISTORY


def test_success_s14_pass_when_composite_jumps_one_sigma():
    treatment = _treatment_metrics()
    treatment["composite_score"] = 0.40  # delta = 0.40 - 0.32 = 0.08 = 4σ when stddev=0.02
    out = evaluate_success_criteria(treatment, _baseline(composite=0.32, stddev=0.02))
    assert out["S14"] == STATUS_PASS


def test_success_s14_fail_when_composite_stagnant():
    treatment = _treatment_metrics()
    treatment["composite_score"] = 0.32  # delta=0
    out = evaluate_success_criteria(treatment, _baseline(composite=0.32, stddev=0.02))
    assert out["S14"] == STATUS_FAIL


def test_success_s9_to_s12_rely_on_caller_flags():
    out = evaluate_success_criteria(
        _treatment_metrics(),
        _baseline(),
        no_threshold_change=False,
    )
    assert out["S9"] == STATUS_FAIL

    out = evaluate_success_criteria(
        _treatment_metrics(), _baseline(), no_arena_change=False,
    )
    assert out["S10"] == STATUS_FAIL

    out = evaluate_success_criteria(
        _treatment_metrics(), _baseline(), no_promotion_change=False,
    )
    assert out["S11"] == STATUS_FAIL

    out = evaluate_success_criteria(
        _treatment_metrics(), _baseline(), no_execution_change=False,
    )
    assert out["S12"] == STATUS_FAIL


def test_success_s13_per_regime_default_insufficient():
    out = evaluate_success_criteria(_treatment_metrics(), _baseline())
    assert out["S13"] == STATUS_INSUFFICIENT_HISTORY


def test_success_s13_per_regime_pass_when_caller_flags_true():
    out = evaluate_success_criteria(
        _treatment_metrics(), _baseline(), per_regime_stable=True,
    )
    assert out["S13"] == STATUS_PASS


def test_success_no_history_marks_insufficient_for_delta_criteria():
    # sample=5 < 20 → S1-S5 INSUFFICIENT_HISTORY
    out = evaluate_success_criteria(_treatment_metrics(), _baseline(sample=5))
    for s in ("S1", "S2", "S3", "S4", "S5"):
        assert out[s] == STATUS_INSUFFICIENT_HISTORY


# ---------------------------------------------------------------------------
# 4. Failure criteria F1-F9
# ---------------------------------------------------------------------------


def test_failure_a2_improves_but_a3_collapses():
    # a2 up, a3 -5pp → F1 FAIL (failure detected)
    out = evaluate_failure_criteria(
        _treatment_metrics(a2=0.30, a3=0.25),
        _baseline(a2=0.20, a3=0.30),
    )
    assert out["F1"] == STATUS_FAIL


def test_failure_a2_improves_but_deployable_falls():
    out = evaluate_failure_criteria(
        _treatment_metrics(a2=0.30, deploy=8),
        _baseline(a2=0.20, deploy=10),
    )
    assert out["F2"] == STATUS_FAIL


def test_failure_oos_fail_increases_materially():
    out = evaluate_failure_criteria(
        _treatment_metrics(oos=0.16),
        _baseline(oos=0.10),
    )
    assert out["F3"] == STATUS_FAIL


def test_failure_unknown_reject_above_005():
    out = evaluate_failure_criteria(
        _treatment_metrics(unknown=0.06),
        _baseline(),
    )
    assert out["F4"] == STATUS_FAIL


def test_failure_profile_collapse():
    treatment = _treatment_metrics()
    treatment["profile_collapse_detected"] = True
    out = evaluate_failure_criteria(treatment, _baseline())
    assert out["F5"] == STATUS_FAIL


def test_failure_exploration_floor_violation():
    treatment = _treatment_metrics()
    treatment["profile_diversity_score"] = 0.0
    out = evaluate_failure_criteria(treatment, _baseline())
    assert out["F6"] == STATUS_FAIL


def test_failure_attribution_regresses_to_red():
    out = evaluate_failure_criteria(
        _treatment_metrics(),
        _baseline(),
        attribution_verdict=VERDICT_RED,
    )
    assert out["F7"] == STATUS_FAIL


def test_failure_rollback_unavailable():
    out = evaluate_failure_criteria(
        _treatment_metrics(),
        _baseline(),
        rollback_executable=False,
    )
    assert out["F8"] == STATUS_FAIL


def test_failure_execution_capital_risk_path_touched():
    out = evaluate_failure_criteria(
        _treatment_metrics(),
        _baseline(),
        execution_path_touched=True,
    )
    assert out["F9"] == STATUS_FAIL


def test_failure_clean_treatment_passes_all():
    out = evaluate_failure_criteria(
        _treatment_metrics(a2=0.30, a3=0.30, oos=0.10, unknown=0.02, deploy=12),
        _baseline(a2=0.20, a3=0.30, oos=0.10, unknown=0.02, deploy=10),
        attribution_verdict=VERDICT_GREEN,
    )
    # F1 false (a3 didn't collapse); F2 false (deploy increased);
    # F3 false (oos same); F4 false (0.02 < 0.05); F5/F6 false;
    # F7 false (GREEN); F8 false (rollback executable); F9 false.
    # But F6 needs explicit profile_diversity_score in the dict,
    # which defaults to 0.0 in our helper → F6 FAIL.
    # Update the test treatment to include diversity > 0.
    treatment = _treatment_metrics(a2=0.30, a3=0.30, oos=0.10, unknown=0.02, deploy=12)
    treatment["profile_diversity_score"] = 0.8
    treatment["profile_collapse_detected"] = False
    out = evaluate_failure_criteria(
        treatment,
        _baseline(a2=0.20, a3=0.30, oos=0.10, unknown=0.02, deploy=10),
        attribution_verdict=VERDICT_GREEN,
    )
    assert all(v == STATUS_PASS for v in out.values())


# ---------------------------------------------------------------------------
# 5. observe() top-level
# ---------------------------------------------------------------------------


def test_observe_produces_dry_run_canary_observation():
    obs = observe(
        run_id="r-c1",
        treatment_metrics=_treatment_metrics(),
        baseline=_baseline(),
        readiness_verdict="PASS",
        attribution_verdict=VERDICT_GREEN,
    )
    assert obs.mode == "DRY_RUN_CANARY"
    assert obs.applied is False
    assert obs.canary_version == "0-9S-CANARY"
    assert obs.run_id == "r-c1"
    assert obs.readiness_verdict == "PASS"
    assert obs.attribution_verdict == VERDICT_GREEN


def test_observe_populates_success_criteria_status():
    obs = observe(
        run_id="r-c1",
        treatment_metrics=_treatment_metrics(),
        baseline=_baseline(),
    )
    # Should have all S1-S14 keys.
    for i in range(1, 15):
        assert f"S{i}" in obs.success_criteria_status


def test_observe_populates_failure_criteria_status():
    obs = observe(
        run_id="r-c1",
        treatment_metrics=_treatment_metrics(),
        baseline=_baseline(),
    )
    for i in range(1, 10):
        assert f"F{i}" in obs.failure_criteria_status


def test_observe_rollback_required_when_failure_triggered():
    treatment = _treatment_metrics()
    treatment["profile_collapse_detected"] = False
    obs = observe(
        run_id="r-c1",
        treatment_metrics=_treatment_metrics(unknown=0.10),
        baseline=_baseline(),
    )
    # F4 should fail (unknown=0.10 > 0.05) → rollback_required=True
    assert obs.rollback_required is True


def test_observe_no_rollback_when_clean():
    obs = observe(
        run_id="r-c1",
        treatment_metrics=_treatment_metrics(unknown=0.02),
        baseline=_baseline(),
        profile_weights={"gp_a": 0.3, "gp_b": 0.3, "gp_c": 0.4},
        attribution_verdict=VERDICT_GREEN,
    )
    # No F should fail.
    assert obs.rollback_required is False


def test_observe_does_not_mutate_input():
    treatment = _treatment_metrics()
    snapshot = json.dumps(treatment, sort_keys=True)
    observe(
        run_id="r-c1",
        treatment_metrics=treatment,
        baseline=_baseline(),
    )
    assert json.dumps(treatment, sort_keys=True) == snapshot


def test_observe_handles_empty_metrics():
    obs = observe(
        run_id="r-c1",
        treatment_metrics={},
        baseline=_baseline(sample=0),
    )
    assert obs.mode == "DRY_RUN_CANARY"
    assert obs.applied is False


def test_safe_observe_returns_default_on_error():
    # Force exception by passing an unsupported kwarg.
    obs = safe_observe(run_id="r", does_not_exist=42)
    assert obs.mode == "DRY_RUN_CANARY"
    assert obs.applied is False
    assert obs.rollback_required is True
    assert any("observe_raised" in a for a in obs.alerts_triggered)


def test_observe_consumer_plan_stability_passthrough():
    plans = [
        SparseCandidateDryRunPlan(run_id="r", plan_status=PLAN_STATUS_ACTIONABLE)
        for _ in range(3)
    ]
    obs = observe(
        run_id="r-c1",
        treatment_metrics=_treatment_metrics(),
        baseline=_baseline(),
        consumer_plans=plans,
    )
    assert abs(obs.consumer_plan_stability - 1.0) < 1e-9


def test_observe_alerts_and_evidence_passthrough():
    obs = observe(
        run_id="r-c1",
        treatment_metrics=_treatment_metrics(),
        baseline=_baseline(),
        alerts_triggered=["telegram_warn"],
        evidence_paths=["/tmp/canary-snap.json"],
    )
    assert "telegram_warn" in obs.alerts_triggered
    assert "/tmp/canary-snap.json" in obs.evidence_paths


# ---------------------------------------------------------------------------
# 6. Runtime isolation tests
# ---------------------------------------------------------------------------


def test_canary_observer_not_imported_by_generation_runtime():
    text = (_SERVICES / "arena_pipeline.py").read_text(encoding="utf-8")
    assert "sparse_canary_observer" not in text


def test_canary_observer_not_imported_by_arena_runtime():
    for fname in ("arena23_orchestrator.py", "arena45_orchestrator.py", "arena_gates.py"):
        text = (_SERVICES / fname).read_text(encoding="utf-8")
        assert "sparse_canary_observer" not in text


def test_canary_observer_not_imported_by_execution_runtime():
    for fname in ("alpha_signal_live.py", "alpha_dedup.py",
                  "alpha_ensemble.py", "alpha_discovery.py", "data_collector.py"):
        path = _SERVICES / fname
        if path.exists():
            text = path.read_text(encoding="utf-8")
            assert "sparse_canary_observer" not in text


def test_feedback_consumer_not_imported_by_generation_runtime():
    text = (_SERVICES / "arena_pipeline.py").read_text(encoding="utf-8")
    assert "feedback_budget_consumer" not in text


def test_allocator_output_not_consumed_by_generation_runtime():
    text = (_SERVICES / "arena_pipeline.py").read_text(encoding="utf-8")
    assert "DryRunBudgetAllocation" not in text
    assert "allocate_dry_run_budget" not in text


def test_no_apply_method_exists():
    import zangetsu.services.sparse_canary_observer as mod
    publics = [n for n in dir(mod) if not n.startswith("_")]
    for name in publics:
        assert not name.lower().startswith("apply"), name


def test_no_runtime_switchable_apply_mode_exists():
    import zangetsu.services.sparse_canary_observer as mod
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    # mode is hard-coded; no runtime config flip
    assert "MODE_DRY_RUN_CANARY" in src
    # No `if mode == "APPLY"` paths
    assert 'mode == "APPLY"' not in src


def test_observer_output_not_consumed_by_runtime():
    for path in _SERVICES.glob("*.py"):
        if path.name == "sparse_canary_observer.py":
            continue
        text = path.read_text(encoding="utf-8")
        assert "SparseCanaryObservation" not in text, (
            f"{path.name} unexpectedly references SparseCanaryObservation"
        )


# ---------------------------------------------------------------------------
# 7. Behavior invariance tests
# ---------------------------------------------------------------------------


def test_no_alpha_generation_change():
    text = (_SERVICES / "arena_pipeline.py").read_text(encoding="utf-8")
    assert "ENTRY_THR" in text  # still references the V10 thresholds
    assert "EXIT_THR" in text
    assert "MIN_HOLD" in text
    assert "COOLDOWN" in text


def test_no_threshold_change():
    text = (_SERVICES / "arena23_orchestrator.py").read_text(encoding="utf-8")
    assert "ATR_STOP_MULTS = [2.0, 3.0, 4.0]" in text
    assert "TRAIL_PCTS = [0.003, 0.005, 0.008, 0.01, 0.015, 0.02]" in text
    assert "FIXED_TARGETS = [0.005, 0.008, 0.01, 0.015, 0.02, 0.03]" in text


def test_a2_min_trades_still_25():
    text = (_SERVICES / "arena23_orchestrator.py").read_text(encoding="utf-8")
    assert "bt.total_trades < 25" in text


def test_arena_pass_fail_unchanged():
    from zangetsu.services import arena_gates
    for fn in ("arena2_pass", "arena3_pass", "arena4_pass"):
        assert hasattr(arena_gates, fn)


def test_champion_promotion_unchanged():
    text = (_SERVICES / "arena45_orchestrator.py").read_text(encoding="utf-8")
    assert text.count("UPDATE champion_pipeline_fresh SET status = 'DEPLOYABLE'") == 1


def test_deployable_count_semantics_unchanged():
    import zangetsu.services.sparse_canary_observer as mod
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    assert "'DEPLOYABLE'" not in src
    assert '"DEPLOYABLE"' not in src


def test_observer_does_not_redefine_arena_thresholds():
    import zangetsu.services.sparse_canary_observer as mod
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    forbidden = ("A2_MIN_TRADES", "ATR_STOP_MULT", "TRAIL_PCT", "FIXED_TARGET")
    for token in forbidden:
        assert token not in src


def test_execution_capital_risk_unchanged():
    # The observer source must not import live / risk / capital paths.
    import zangetsu.services.sparse_canary_observer as mod
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    forbidden_imports = (
        "from zangetsu.live",
        "import zangetsu.live",
        "from zangetsu.engine",
        "import zangetsu.engine",
    )
    for fragment in forbidden_imports:
        assert fragment not in src
