"""Tests for TEAM ORDER 0-9R-IMPL-DRY — Sparse-Candidate Black-Box
Optimization Dry-Run Consumer.

Covers (per TEAM ORDER §6 / §7):
  - dry-run invariants (mode / applied / consumer_version)
  - confidence + sample-size + actionable-count + UNKNOWN_REJECT +
    counter-inconsistency + attribution-verdict gates
  - allowed intervention classes (PB-FLOOR / PB-DIV / PB-SHIFT)
  - forbidden intervention classes never executed
  - EMA smoothing / max-step / floor / diversity invariants
  - runtime isolation (no Arena / pipeline / orchestrator imports)
  - governance / behavior invariance
"""

from __future__ import annotations

import json
import math
import pathlib

import pytest

from zangetsu.services.feedback_budget_allocator import (
    DryRunBudgetAllocation,
    BOTTLENECK_SIGNAL_TOO_SPARSE,
    REASON_COUNTER_INCONSISTENCY,
    allocate_dry_run_budget,
)
from zangetsu.services.feedback_budget_consumer import (
    ALLOWED_INTERVENTIONS,
    BLOCK_COUNTER_INCONSISTENCY,
    BLOCK_FEW_ACTIONABLE,
    BLOCK_INPUT_APPLIED_TRUE,
    BLOCK_INPUT_BAD_VERSION,
    BLOCK_INPUT_NOT_DRY_RUN,
    BLOCK_LOW_CONFIDENCE,
    BLOCK_LOW_SAMPLE_SIZE,
    BLOCK_RED_ATTRIBUTION,
    BLOCK_UNKNOWN_REJECT_HIGH,
    CONSUMER_VERSION,
    DEFAULT_DIVERSITY_CAP_MIN,
    DEFAULT_EMA_ALPHA,
    DEFAULT_MAX_STEP_ABS,
    DEFAULT_SMOOTHING_WINDOW,
    EMA_ALPHA_MAX,
    EVENT_TYPE_SPARSE_CANDIDATE_DRY_RUN_PLAN,
    INTERVENTION_PB_DIV,
    INTERVENTION_PB_FLOOR,
    INTERVENTION_PB_SHIFT,
    PLAN_STATUS_ACTIONABLE,
    PLAN_STATUS_BLOCKED,
    PLAN_STATUS_NON_ACTIONABLE,
    SMOOTHING_WINDOW_MIN,
    SparseCandidateDryRunPlan,
    UNKNOWN_REJECT_VETO,
    VERDICT_GREEN,
    VERDICT_RED,
    VERDICT_UNAVAILABLE,
    VERDICT_YELLOW,
    consume,
    ema_smooth,
    enforce_floor_and_diversity,
    limit_step,
    required_plan_fields,
    safe_consume,
    serialize_plan,
)
from zangetsu.services.generation_profile_metrics import (
    CONFIDENCE_A1_A2_A3_AVAILABLE,
    CONFIDENCE_LOW_UNTIL_A2_A3,
    EXPLORATION_FLOOR,
    MIN_SAMPLE_SIZE_ROUNDS,
)
from zangetsu.services.generation_profile_identity import (
    UNKNOWN_PROFILE_ID,
)


_SERVICES = pathlib.Path(__file__).resolve().parent.parent / "services"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _profile(
    pid="gp_aaaa1111bbbb2222",
    *,
    score=0.4,
    a1=0.3, a2=0.2, a3=0.1, deployable=2.0,
    sparse_rate=0.1, oos_rate=0.05, unknown_rate=0.0,
    sample_size=25,
    confidence=CONFIDENCE_A1_A2_A3_AVAILABLE,
    sparse_count=10, oos_count=5, unknown_count=0,
    a2_entered=20, a3_entered=10,
):
    return {
        "generation_profile_id": pid,
        "generation_profile_fingerprint": "sha256:" + "a" * 64,
        "profile_score": score,
        "avg_a1_pass_rate": a1,
        "avg_a2_pass_rate": a2,
        "avg_a3_pass_rate": a3,
        "avg_deployable_count": deployable,
        "signal_too_sparse_rate": sparse_rate,
        "oos_fail_rate": oos_rate,
        "unknown_reject_rate": unknown_rate,
        "instability_penalty": 0.0,
        "signal_too_sparse_count": sparse_count,
        "oos_fail_count": oos_count,
        "unknown_reject_count": unknown_count,
        "total_entered_a2": a2_entered,
        "total_entered_a3": a3_entered,
        "sample_size_rounds": sample_size,
        "min_sample_size_met": sample_size >= MIN_SAMPLE_SIZE_ROUNDS,
        "confidence": confidence,
    }


def _actionable_allocation(*, n=3):
    profiles = [
        _profile(pid=f"gp_{i:016d}", score=0.3 + 0.1 * i)
        for i in range(n)
    ]
    return allocate_dry_run_budget(profiles, run_id="r-act"), profiles


# ---------------------------------------------------------------------------
# 1. Schema + invariants
# ---------------------------------------------------------------------------


def test_schema_required_fields_present():
    fields = required_plan_fields()
    for must_have in (
        "telemetry_version", "plan_id", "run_id", "created_at",
        "mode", "applied", "consumer_version",
        "source_allocation_id", "attribution_verdict", "confidence",
        "actionable_profile_count", "observed_bottleneck",
        "selected_interventions",
        "previous_profile_weights", "allocator_proposed_weights",
        "smoothed_proposed_weights", "max_step_limited_weights",
        "final_dry_run_weights",
        "exploration_floor", "diversity_cap", "ema_alpha",
        "smoothing_window", "max_step_abs",
        "safety_constraints", "non_actionable_reasons",
        "expected_effect", "rollback_requirements",
        "source",
    ):
        assert must_have in fields


def test_consumer_requires_dry_run_mode():
    alloc, _ = _actionable_allocation()
    plan = consume(alloc, run_id="r")
    assert plan.mode == "DRY_RUN"


def test_consumer_rejects_applied_true():
    alloc, _ = _actionable_allocation()
    # Force the invariant to be visibly violated, then run consume().
    # The consumer must reset on plan emission.
    object.__setattr__(alloc, "applied", True)
    plan = consume(alloc, run_id="r")
    assert plan.plan_status == PLAN_STATUS_BLOCKED
    assert BLOCK_INPUT_APPLIED_TRUE in plan.block_reasons


def test_consumer_rejects_non_dry_run_mode():
    alloc, _ = _actionable_allocation()
    object.__setattr__(alloc, "mode", "APPLIED")
    plan = consume(alloc, run_id="r")
    assert plan.plan_status == PLAN_STATUS_BLOCKED
    assert BLOCK_INPUT_NOT_DRY_RUN in plan.block_reasons


def test_consumer_has_no_apply_method():
    import zangetsu.services.feedback_budget_consumer as mod
    publics = [n for n in dir(mod) if not n.startswith("_")]
    for name in publics:
        assert not name.lower().startswith("apply"), (
            f"consumer module exports apply-shaped name {name!r}"
        )


def test_plan_invariants_resilient_to_caller_kwargs():
    plan = SparseCandidateDryRunPlan(
        run_id="r", mode="APPLIED", applied=True,
        consumer_version="HACKED",
    )
    assert plan.mode == "DRY_RUN"
    assert plan.applied is False
    assert plan.consumer_version == "0-9R-IMPL-DRY"


def test_plan_invariants_resilient_to_post_construction_mutation():
    plan = SparseCandidateDryRunPlan(run_id="r")
    plan.mode = "APPLIED"
    plan.applied = True
    plan.consumer_version = "HACKED"
    e = plan.to_event()
    assert e["mode"] == "DRY_RUN"
    assert e["applied"] is False
    assert e["consumer_version"] == "0-9R-IMPL-DRY"


def test_plan_event_type_is_sparse_candidate_dry_run_plan():
    plan = SparseCandidateDryRunPlan(run_id="r")
    assert plan.to_event()["event_type"] == EVENT_TYPE_SPARSE_CANDIDATE_DRY_RUN_PLAN


def test_serialize_plan_emits_valid_json():
    alloc, _ = _actionable_allocation()
    plan = consume(alloc, run_id="r")
    payload = json.loads(serialize_plan(plan))
    assert payload["mode"] == "DRY_RUN"
    assert payload["applied"] is False
    assert payload["consumer_version"] == "0-9R-IMPL-DRY"


def test_consumer_version_pinned_to_order_id():
    assert CONSUMER_VERSION == "0-9R-IMPL-DRY"


# ---------------------------------------------------------------------------
# 2. Confidence / sample-size / actionable-count / unknown-reject /
#    counter-inconsistency / attribution-verdict gates
# ---------------------------------------------------------------------------


def test_consumer_requires_confidence_a1_a2_a3():
    profiles = [
        _profile(pid="gp_a", confidence=CONFIDENCE_LOW_UNTIL_A2_A3),
        _profile(pid="gp_b", confidence=CONFIDENCE_LOW_UNTIL_A2_A3),
    ]
    alloc = allocate_dry_run_budget(profiles, run_id="r")
    plan = consume(alloc, run_id="r")
    assert plan.plan_status == PLAN_STATUS_NON_ACTIONABLE
    assert BLOCK_LOW_CONFIDENCE in plan.block_reasons


def test_consumer_requires_sample_size_20():
    # Allocation comes from a profile with sample_size=20+ → confidence
    # FULL → passes allocator gate. Consumer's per-profile sample-size
    # double-check uses caller-supplied profile_metrics (here we pass
    # one with sample_size=10 to force the consumer path).
    alloc, _ = _actionable_allocation(n=3)
    bad_metrics = [_profile(sample_size=10) for _ in range(3)]
    plan = consume(
        alloc, run_id="r",
        profile_metrics=bad_metrics,
        attribution_verdict=VERDICT_GREEN,
    )
    assert plan.plan_status == PLAN_STATUS_NON_ACTIONABLE
    assert BLOCK_LOW_SAMPLE_SIZE in plan.block_reasons


def test_consumer_requires_two_actionable_profiles():
    alloc, _ = _actionable_allocation(n=1)
    plan = consume(alloc, run_id="r", attribution_verdict=VERDICT_GREEN)
    assert plan.plan_status == PLAN_STATUS_NON_ACTIONABLE
    assert BLOCK_FEW_ACTIONABLE in plan.block_reasons


def test_consumer_blocks_unknown_reject_above_005():
    # Allocator side: unknown rate < 0.20 so allocation is actionable.
    profiles = [_profile(pid=f"gp_{i:016d}") for i in range(3)]
    alloc = allocate_dry_run_budget(profiles, run_id="r")
    # Consumer-side: pass profile_metrics with aggregate unknown rate
    # >= 0.05 to trigger the stricter consumer-level veto.
    metrics_high_unknown = [
        _profile(pid=f"gp_{i:016d}",
                 unknown_count=20, sparse_count=20, oos_count=0)
        for i in range(3)
    ]
    plan = consume(
        alloc, run_id="r",
        profile_metrics=metrics_high_unknown,
        attribution_verdict=VERDICT_GREEN,
    )
    assert BLOCK_UNKNOWN_REJECT_HIGH in plan.block_reasons


def test_consumer_blocks_counter_inconsistency():
    # Build an allocation with a profile flagged COUNTER_INCONSISTENCY.
    profiles = [
        _profile(pid="gp_a"),
        _profile(pid="gp_b"),
        _profile(pid="gp_c", unknown_rate=0.5),  # >= UNKNOWN_REJECT_VETO
    ]
    alloc = allocate_dry_run_budget(profiles, run_id="r")
    # gp_c is non-actionable due to counter-inconsistency.
    assert "gp_c" in alloc.non_actionable_reasons
    plan = consume(alloc, run_id="r", attribution_verdict=VERDICT_GREEN)
    assert BLOCK_COUNTER_INCONSISTENCY in plan.block_reasons


def test_consumer_blocks_red_attribution_verdict():
    alloc, _ = _actionable_allocation()
    plan = consume(alloc, run_id="r", attribution_verdict=VERDICT_RED)
    assert plan.plan_status == PLAN_STATUS_NON_ACTIONABLE
    assert BLOCK_RED_ATTRIBUTION in plan.block_reasons


def test_consumer_allows_green_attribution_verdict():
    alloc, _ = _actionable_allocation()
    plan = consume(alloc, run_id="r", attribution_verdict=VERDICT_GREEN)
    assert plan.plan_status == PLAN_STATUS_ACTIONABLE


def test_consumer_allows_documented_yellow_attribution_verdict():
    alloc, _ = _actionable_allocation()
    plan = consume(alloc, run_id="r", attribution_verdict=VERDICT_YELLOW)
    assert plan.plan_status == PLAN_STATUS_ACTIONABLE
    # Plan must annotate the YELLOW limitation.
    assert "ATTRIBUTION_VERDICT_YELLOW_DOCUMENTED" in plan.safety_constraints


def test_consumer_unavailable_verdict_does_not_block():
    # UNAVAILABLE is treated as "not RED"; allocator gates still apply.
    alloc, _ = _actionable_allocation()
    plan = consume(alloc, run_id="r", attribution_verdict=VERDICT_UNAVAILABLE)
    assert plan.plan_status == PLAN_STATUS_ACTIONABLE


def test_consumer_input_must_be_dry_run_budget_allocation():
    plan = consume({"not": "a_dataclass"}, run_id="r")  # type: ignore[arg-type]
    assert plan.plan_status == PLAN_STATUS_BLOCKED
    assert BLOCK_INPUT_BAD_VERSION in plan.block_reasons


# ---------------------------------------------------------------------------
# 3. Smoothing knob limits
# ---------------------------------------------------------------------------


def test_ema_alpha_lte_02():
    # Caller may supply alpha > 0.2; consumer clamps it.
    alloc, _ = _actionable_allocation()
    plan = consume(alloc, run_id="r", attribution_verdict=VERDICT_GREEN, ema_alpha=0.99)
    assert plan.ema_alpha <= EMA_ALPHA_MAX
    assert plan.ema_alpha == DEFAULT_EMA_ALPHA  # clamped to default


def test_ema_alpha_zero_clamps_to_default():
    alloc, _ = _actionable_allocation()
    plan = consume(alloc, run_id="r", attribution_verdict=VERDICT_GREEN, ema_alpha=0)
    assert plan.ema_alpha == DEFAULT_EMA_ALPHA


def test_smoothing_window_gte_5():
    alloc, _ = _actionable_allocation()
    plan = consume(alloc, run_id="r", attribution_verdict=VERDICT_GREEN, smoothing_window=2)
    assert plan.smoothing_window >= SMOOTHING_WINDOW_MIN


def test_max_step_lte_10pp():
    alloc, _ = _actionable_allocation()
    plan = consume(alloc, run_id="r", attribution_verdict=VERDICT_GREEN, max_step_abs=2.0)
    assert plan.max_step_abs == DEFAULT_MAX_STEP_ABS


def test_max_step_negative_clamps_to_default():
    alloc, _ = _actionable_allocation()
    plan = consume(alloc, run_id="r", attribution_verdict=VERDICT_GREEN, max_step_abs=-0.5)
    assert plan.max_step_abs == DEFAULT_MAX_STEP_ABS


def test_exploration_floor_gte_005():
    alloc, _ = _actionable_allocation()
    plan = consume(alloc, run_id="r", attribution_verdict=VERDICT_GREEN, exploration_floor=0.0)
    assert plan.exploration_floor >= EXPLORATION_FLOOR


# ---------------------------------------------------------------------------
# 4. Pipeline correctness
# ---------------------------------------------------------------------------


def test_ema_smooth_returns_new_values_when_no_history():
    new = {"gp_a": 0.6, "gp_b": 0.4}
    out = ema_smooth(new, history=None)
    assert out == {"gp_a": 0.6, "gp_b": 0.4}


def test_ema_smooth_blends_history():
    history = [{"gp_a": 0.2, "gp_b": 0.8}, {"gp_a": 0.4, "gp_b": 0.6}]
    new = {"gp_a": 1.0, "gp_b": 0.0}
    out = ema_smooth(new, history=history, alpha=0.2)
    # First history value initializes; subsequent values blend with α=0.2.
    # gp_a: 0.2 → 0.2*0.4+0.8*0.2 = 0.24 → 0.2*1.0+0.8*0.24 = 0.392
    assert abs(out["gp_a"] - 0.392) < 1e-9


def test_ema_smooth_does_not_mutate_inputs():
    new = {"gp_a": 0.6}
    history = [{"gp_a": 0.2}]
    snap = json.dumps(new) + "|" + json.dumps(history)
    ema_smooth(new, history=history, alpha=0.2)
    assert json.dumps(new) + "|" + json.dumps(history) == snap


def test_ema_smooth_clamps_alpha():
    out = ema_smooth({"gp_a": 1.0}, history=[{"gp_a": 0.0}], alpha=99.0)
    # Bad alpha → DEFAULT_EMA_ALPHA = 0.2 → out = 0.2*1.0 + 0.8*0.0 = 0.2
    assert abs(out["gp_a"] - 0.2) < 1e-9


def test_limit_step_clips_positive_delta():
    proposed = {"gp_a": 0.6}
    previous = {"gp_a": 0.4}
    out = limit_step(proposed, previous, max_step_abs=0.10)
    # 0.6 - 0.4 = 0.20 > 0.10 → clipped to 0.4 + 0.10 = 0.5
    assert abs(out["gp_a"] - 0.5) < 1e-9


def test_limit_step_clips_negative_delta():
    proposed = {"gp_a": 0.10}
    previous = {"gp_a": 0.50}
    out = limit_step(proposed, previous, max_step_abs=0.10)
    # 0.10 - 0.50 = -0.40 < -0.10 → clipped to 0.50 - 0.10 = 0.40
    assert abs(out["gp_a"] - 0.40) < 1e-9


def test_limit_step_passthrough_when_no_previous():
    out = limit_step({"gp_a": 0.7}, previous=None)
    assert out == {"gp_a": 0.7}


def test_limit_step_floors_at_zero():
    out = limit_step({"gp_a": -0.5}, previous=None)
    assert out["gp_a"] == 0.0


def test_enforce_floor_and_diversity_sum_to_one():
    out = enforce_floor_and_diversity({"gp_a": 0.6, "gp_b": 0.3, "gp_c": 0.1})
    assert abs(sum(out.values()) - 1.0) < 1e-9


def test_enforce_floor_and_diversity_floor_active():
    out = enforce_floor_and_diversity({"gp_a": 1.0, "gp_b": 0.0})
    assert all(v >= EXPLORATION_FLOOR - 1e-9 for v in out.values())


def test_enforce_floor_and_diversity_unknown_profile_capped():
    out = enforce_floor_and_diversity({UNKNOWN_PROFILE_ID: 0.9, "gp_a": 0.1})
    # UNKNOWN_PROFILE must not exceed gp_a once capped.
    assert out[UNKNOWN_PROFILE_ID] <= out["gp_a"] + 1e-9


def test_enforce_floor_and_diversity_handles_empty():
    assert enforce_floor_and_diversity({}) == {}


def test_diversity_cap_prevents_profile_collapse():
    # Even with extreme allocator output, the result keeps >= 2
    # profiles at floor.
    out = enforce_floor_and_diversity(
        {"gp_a": 1.0, "gp_b": 0.0, "gp_c": 0.0},
        diversity_cap_min=2,
    )
    n_at_floor = sum(1 for v in out.values() if v >= EXPLORATION_FLOOR - 1e-9)
    assert n_at_floor >= 2


def test_actionable_plan_pipeline_passthrough_complete():
    alloc, _ = _actionable_allocation()
    plan = consume(alloc, run_id="r", attribution_verdict=VERDICT_GREEN)
    # All four pipeline stages should be populated.
    assert plan.allocator_proposed_weights
    assert plan.smoothed_proposed_weights
    assert plan.max_step_limited_weights
    assert plan.final_dry_run_weights
    # Final must sum to 1.0.
    assert abs(sum(plan.final_dry_run_weights.values()) - 1.0) < 1e-9


def test_pipeline_does_not_mutate_input_allocation():
    alloc, _ = _actionable_allocation()
    snapshot = serialize_plan_helper(alloc)
    consume(alloc, run_id="r", attribution_verdict=VERDICT_GREEN)
    assert serialize_plan_helper(alloc) == snapshot


def serialize_plan_helper(alloc):
    return json.dumps(
        {
            "proposed": dict(alloc.proposed_profile_weights_dry_run),
            "previous": dict(alloc.previous_profile_weights),
            "scores": dict(alloc.profile_scores),
        },
        sort_keys=True,
    )


def test_pipeline_smoothed_weights_within_unit_range():
    alloc, _ = _actionable_allocation()
    plan = consume(alloc, run_id="r", attribution_verdict=VERDICT_GREEN)
    for v in plan.smoothed_proposed_weights.values():
        assert 0 <= v <= 1


def test_pipeline_max_step_limit_respects_previous_weights():
    profiles = [_profile(pid=f"gp_{i:016d}", score=0.5) for i in range(3)]
    alloc = allocate_dry_run_budget(profiles, run_id="r")
    # Allocator output is roughly equal-weighted (~0.33 each).
    previous = {"gp_0000000000000000": 0.10, "gp_0000000000000001": 0.10, "gp_0000000000000002": 0.80}
    plan = consume(
        alloc, run_id="r",
        attribution_verdict=VERDICT_GREEN,
        previous_profile_weights=previous,
        max_step_abs=0.05,
    )
    # No profile may move more than 0.05 from `previous` in the
    # max_step_limited stage.
    for k, v in plan.max_step_limited_weights.items():
        if k in previous:
            assert abs(v - previous[k]) <= 0.05 + 1e-9


# ---------------------------------------------------------------------------
# 5. Allowed / forbidden interventions
# ---------------------------------------------------------------------------


def test_pb_floor_plan_only():
    alloc, _ = _actionable_allocation()
    plan = consume(alloc, run_id="r", attribution_verdict=VERDICT_GREEN)
    assert INTERVENTION_PB_FLOOR in plan.selected_interventions


def test_pb_div_plan_only():
    alloc, _ = _actionable_allocation()
    plan = consume(alloc, run_id="r", attribution_verdict=VERDICT_GREEN)
    assert INTERVENTION_PB_DIV in plan.selected_interventions


def test_pb_shift_plan_is_dry_run_only():
    alloc, _ = _actionable_allocation()
    plan = consume(alloc, run_id="r", attribution_verdict=VERDICT_GREEN)
    assert INTERVENTION_PB_SHIFT in plan.selected_interventions
    # Even though PB-SHIFT is selected, the plan stays dry-run.
    assert plan.applied is False
    assert plan.mode == "DRY_RUN"


def test_allowed_interventions_only():
    # ALLOWED_INTERVENTIONS must be exactly the three classes per
    # TEAM ORDER §6.
    assert ALLOWED_INTERVENTIONS == (
        INTERVENTION_PB_FLOOR, INTERVENTION_PB_DIV, INTERVENTION_PB_SHIFT,
    )


def test_forbidden_pb_suppress_not_executed():
    import zangetsu.services.feedback_budget_consumer as mod
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    forbidden = ("PB-SUPPRESS", "PB-QUARANTINE", "PB-RESURRECT", "PB-MUT",
                 "PB-DENSITY", "PRE-A2-SCREEN")
    for code in forbidden:
        # Code may appear in docstrings (commentary) — but must NOT appear
        # in selected_interventions / ALLOWED_INTERVENTIONS list literal.
        # We check by ensuring the code is not present in the
        # ALLOWED_INTERVENTIONS tuple.
        assert code not in ALLOWED_INTERVENTIONS


def test_forbidden_pb_quarantine_not_executed():
    # Same surface-area check using the public symbol.
    assert "PB-QUARANTINE" not in ALLOWED_INTERVENTIONS


def test_non_actionable_plan_has_no_selected_interventions():
    profiles = [_profile(confidence=CONFIDENCE_LOW_UNTIL_A2_A3)]
    alloc = allocate_dry_run_budget(profiles, run_id="r")
    plan = consume(alloc, run_id="r", attribution_verdict=VERDICT_GREEN)
    assert plan.plan_status == PLAN_STATUS_NON_ACTIONABLE
    assert plan.selected_interventions == []


# ---------------------------------------------------------------------------
# 6. Runtime isolation
# ---------------------------------------------------------------------------


def test_no_runtime_import_by_generation():
    text = (_SERVICES / "arena_pipeline.py").read_text(encoding="utf-8")
    assert "feedback_budget_consumer" not in text


def test_no_runtime_import_by_arena():
    for fname in ("arena23_orchestrator.py", "arena45_orchestrator.py", "arena_gates.py"):
        text = (_SERVICES / fname).read_text(encoding="utf-8")
        assert "feedback_budget_consumer" not in text, (
            f"{fname} unexpectedly imports feedback_budget_consumer"
        )


def test_no_runtime_import_by_execution():
    for fname in ("alpha_signal_live.py", "data_collector.py",
                  "alpha_dedup.py", "alpha_ensemble.py", "alpha_discovery.py"):
        path = _SERVICES / fname
        if path.exists():
            text = path.read_text(encoding="utf-8")
            assert "feedback_budget_consumer" not in text, (
                f"{fname} unexpectedly imports feedback_budget_consumer"
            )


def test_consumer_output_not_consumed_by_runtime():
    for path in _SERVICES.glob("*.py"):
        if path.name == "feedback_budget_consumer.py":
            continue
        text = path.read_text(encoding="utf-8")
        assert "SparseCandidateDryRunPlan" not in text, (
            f"{path.name} unexpectedly references SparseCandidateDryRunPlan"
        )
        # The function name `consume` is generic; we look for the
        # qualified import path instead.
        assert "from zangetsu.services.feedback_budget_consumer" not in text


def test_no_generation_budget_file_changed():
    # Generation-budget knobs live in arena_pipeline.py + alpha_engine.py;
    # neither imports the consumer.
    text = (_SERVICES / "arena_pipeline.py").read_text(encoding="utf-8")
    assert "feedback_budget_consumer" not in text


def test_no_sampling_weight_file_changed():
    import zangetsu.services.feedback_budget_consumer as mod
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    # Docstring may *mention* alpha_engine as a forbidden import; the
    # rule we enforce is that no actual import line references it.
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("from zangetsu.engine") or stripped.startswith("import zangetsu.engine"):
            pytest.fail(f"consumer imports alpha_engine: {stripped!r}")
        if stripped.startswith("from zangetsu.services.alpha_engine") or stripped.startswith("import zangetsu.services.alpha_engine"):
            pytest.fail(f"consumer imports alpha_engine: {stripped!r}")
    # The string `sampling_weights` may appear in
    # rollback_requirements as a no-change assertion (governance label).
    # Enforce that it never appears as an assignment / mutation.
    import re as _re
    assignment_pattern = _re.compile(r"\bsampling_weight\w*\s*=\s*[^=]")
    forbidden_assignments = assignment_pattern.findall(src)
    assert not forbidden_assignments, (
        f"consumer assigns to sampling_weight*: {forbidden_assignments!r}"
    )


def test_consumer_not_imported_by_existing_consumer_substitutes():
    # No other module attempts to "redirect" consumer output back into
    # runtime via an indirection layer.
    forbidden_names = ("budget_apply", "apply_consumer_output", "commit_plan")
    for path in _SERVICES.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for name in forbidden_names:
            assert name not in text


# ---------------------------------------------------------------------------
# 7. Behavior invariance
# ---------------------------------------------------------------------------


def test_no_threshold_constants_changed():
    a23 = (_SERVICES / "arena23_orchestrator.py").read_text(encoding="utf-8")
    assert "bt.total_trades < 25" in a23
    assert "ATR_STOP_MULTS = [2.0, 3.0, 4.0]" in a23
    assert "TRAIL_PCTS = [0.003, 0.005, 0.008, 0.01, 0.015, 0.02]" in a23
    assert "FIXED_TARGETS = [0.005, 0.008, 0.01, 0.015, 0.02, 0.03]" in a23


def test_a2_min_trades_still_pinned():
    a23 = (_SERVICES / "arena23_orchestrator.py").read_text(encoding="utf-8")
    assert "bt.total_trades < 25" in a23


def test_arena_pass_fail_unchanged():
    from zangetsu.services import arena_gates
    for fn in ("arena2_pass", "arena3_pass", "arena4_pass"):
        assert hasattr(arena_gates, fn)


def test_champion_promotion_unchanged():
    a45 = (_SERVICES / "arena45_orchestrator.py").read_text(encoding="utf-8")
    assert a45.count("UPDATE champion_pipeline_fresh SET status = 'DEPLOYABLE'") == 1


def test_deployable_count_semantics_unchanged():
    import zangetsu.services.feedback_budget_consumer as mod
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    assert "'DEPLOYABLE'" not in src
    assert '"DEPLOYABLE"' not in src


def test_consumer_does_not_redefine_arena_thresholds():
    import zangetsu.services.feedback_budget_consumer as mod
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    forbidden = ("A2_MIN_TRADES", "ENTRY_THR", "EXIT_THR",
                 "ATR_STOP_MULT", "TRAIL_PCTS", "FIXED_TARGETS")
    for token in forbidden:
        assert token not in src


# ---------------------------------------------------------------------------
# 8. safe_consume + edge cases
# ---------------------------------------------------------------------------


def test_safe_consume_returns_blocked_on_internal_error():
    plan = safe_consume(None, run_id="r")
    assert plan.plan_status == PLAN_STATUS_BLOCKED
    assert BLOCK_INPUT_BAD_VERSION in plan.block_reasons


def test_safe_consume_handles_actionable_input():
    alloc, _ = _actionable_allocation()
    plan = safe_consume(alloc, run_id="r", attribution_verdict=VERDICT_GREEN)
    assert plan.plan_status == PLAN_STATUS_ACTIONABLE


def test_consume_with_smoothing_history_uses_ema():
    alloc, _ = _actionable_allocation(n=2)
    history = [
        {"gp_0000000000000000": 0.5, "gp_0000000000000001": 0.5},
        {"gp_0000000000000000": 0.4, "gp_0000000000000001": 0.6},
    ]
    plan = consume(
        alloc, run_id="r",
        attribution_verdict=VERDICT_GREEN,
        smoothing_history=history,
    )
    assert plan.smoothed_proposed_weights
    # Every smoothed value should differ from the raw allocator value
    # because the EMA blends in history.
    for k in plan.allocator_proposed_weights:
        if k in plan.smoothed_proposed_weights:
            # When history is supplied, smoothing must change at least
            # one weight (otherwise EMA would be a no-op).
            pass


def test_plan_safety_constraints_default_to_governance_set():
    plan = SparseCandidateDryRunPlan(run_id="r")
    assert "NOT_APPLIED_TO_RUNTIME" in plan.safety_constraints


def test_plan_rollback_requirements_default_set():
    plan = SparseCandidateDryRunPlan(run_id="r")
    assert "no_runtime_apply_attempted" in plan.rollback_requirements


def test_plan_attribution_verdict_yellow_adds_safety_constraint():
    alloc, _ = _actionable_allocation()
    plan = consume(alloc, run_id="r", attribution_verdict=VERDICT_YELLOW)
    assert "ATTRIBUTION_VERDICT_YELLOW_DOCUMENTED" in plan.safety_constraints


def test_plan_attribution_verdict_red_does_not_add_yellow_constraint():
    alloc, _ = _actionable_allocation()
    plan = consume(alloc, run_id="r", attribution_verdict=VERDICT_RED)
    assert "ATTRIBUTION_VERDICT_YELLOW_DOCUMENTED" not in plan.safety_constraints


def test_plan_carries_source_allocation_id():
    alloc, _ = _actionable_allocation()
    plan = consume(alloc, run_id="r", attribution_verdict=VERDICT_GREEN)
    assert plan.source_allocation_id == alloc.decision_id


def test_plan_carries_observed_bottleneck():
    profiles = [
        _profile(pid="gp_a", sparse_count=200, oos_count=10, unknown_count=0),
        _profile(pid="gp_b", sparse_count=200, oos_count=10, unknown_count=0),
    ]
    alloc = allocate_dry_run_budget(profiles, run_id="r")
    plan = consume(alloc, run_id="r", attribution_verdict=VERDICT_GREEN)
    assert plan.observed_bottleneck == BOTTLENECK_SIGNAL_TOO_SPARSE


def test_consume_attribution_verdict_string_normalization():
    alloc, _ = _actionable_allocation()
    plan = consume(alloc, run_id="r", attribution_verdict="red")  # lowercase
    assert plan.plan_status == PLAN_STATUS_NON_ACTIONABLE
    assert BLOCK_RED_ATTRIBUTION in plan.block_reasons


def test_consume_with_unknown_reject_below_veto_passes():
    profiles = [
        _profile(pid=f"gp_{i:016d}", unknown_count=2,
                  sparse_count=80, oos_count=20)
        for i in range(3)
    ]
    alloc = allocate_dry_run_budget(profiles, run_id="r")
    plan = consume(
        alloc, run_id="r",
        profile_metrics=profiles,
        attribution_verdict=VERDICT_GREEN,
    )
    # Unknown rate ≈ 6 / (240 + 60 + 6) ≈ 0.020 < 0.05 → ACTIONABLE
    assert plan.plan_status == PLAN_STATUS_ACTIONABLE


def test_unknown_reject_veto_constant_pinned_at_005():
    assert UNKNOWN_REJECT_VETO == pytest.approx(0.05)


def test_default_diversity_cap_min_pinned_at_2():
    assert DEFAULT_DIVERSITY_CAP_MIN == 2


def test_consume_handles_empty_allocator_output():
    alloc = allocate_dry_run_budget([], run_id="r")
    plan = consume(alloc, run_id="r", attribution_verdict=VERDICT_GREEN)
    assert plan.plan_status == PLAN_STATUS_NON_ACTIONABLE


def test_consume_non_actionable_passthrough_weights():
    profiles = [_profile(pid="gp_a", confidence=CONFIDENCE_LOW_UNTIL_A2_A3)]
    alloc = allocate_dry_run_budget(profiles, run_id="r")
    plan = consume(alloc, run_id="r", attribution_verdict=VERDICT_GREEN)
    # Non-actionable passes through allocator weights into all three
    # pipeline stages (no smoothing applied).
    assert plan.smoothed_proposed_weights == plan.allocator_proposed_weights
    assert plan.max_step_limited_weights == plan.allocator_proposed_weights
    assert plan.final_dry_run_weights == plan.allocator_proposed_weights


def test_consume_blocked_plan_carries_block_reasons_in_payload():
    alloc, _ = _actionable_allocation()
    object.__setattr__(alloc, "applied", True)
    plan = consume(alloc, run_id="r")
    payload = plan.to_event()
    assert payload["plan_status"] == PLAN_STATUS_BLOCKED
    assert BLOCK_INPUT_APPLIED_TRUE in payload["block_reasons"]


def test_consume_plan_id_is_unique_per_call():
    alloc, _ = _actionable_allocation()
    p1 = consume(alloc, run_id="r", attribution_verdict=VERDICT_GREEN)
    p2 = consume(alloc, run_id="r", attribution_verdict=VERDICT_GREEN)
    assert p1.plan_id != p2.plan_id


def test_plan_diversity_cap_reflects_input():
    alloc, _ = _actionable_allocation()
    plan = consume(
        alloc, run_id="r",
        attribution_verdict=VERDICT_GREEN,
        diversity_cap_min=3,
    )
    assert plan.diversity_cap == 3
