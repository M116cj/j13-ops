"""Tests for TEAM ORDER 0-9O-B — Dry-Run Feedback Budget Allocator.

Covers:
  - 9.1  Schema
  - 9.2  Weight normalization
  - 9.3  Confidence gate
  - 9.4  Penalty handling
  - 9.5  Bottleneck explanation
  - 9.6  Feedback decision record integration
  - 9.7  Runtime isolation
  - 9.8  Governance / behavior invariance
"""

from __future__ import annotations

import importlib
import json
import pathlib

import pytest

from zangetsu.services.feedback_budget_allocator import (
    ALLOCATOR_VERSION,
    BOTTLENECK_LOW_SAMPLE,
    BOTTLENECK_MISSING_A2_A3,
    BOTTLENECK_NO_ACTIONABLE,
    BOTTLENECK_OOS_FAIL,
    BOTTLENECK_SIGNAL_TOO_SPARSE,
    BOTTLENECK_UNKNOWN_REJECT,
    CONFIDENCE_NO_ACTIONABLE_PROFILE,
    DryRunBudgetAllocation,
    EVENT_TYPE_DRY_RUN_BUDGET_ALLOCATION,
    REASON_COUNTER_INCONSISTENCY,
    REASON_LOW_CONFIDENCE,
    REASON_LOW_SAMPLE_SIZE,
    REASON_MISSING_A2_A3,
    REASON_MISSING_FIELDS,
    UNKNOWN_REJECT_VETO,
    allocate_dry_run_budget,
    classify_bottleneck,
    compute_proposed_weights,
    equal_weight_fallback,
    evaluate_profile_actionability,
    required_allocation_fields,
    safe_allocate_dry_run_budget,
    serialize_allocation,
    to_feedback_decision_record,
)
from zangetsu.services.generation_profile_metrics import (
    CONFIDENCE_A1_A2_A3_AVAILABLE,
    CONFIDENCE_LOW_SAMPLE_SIZE,
    CONFIDENCE_LOW_UNTIL_A2_A3,
    EXPLORATION_FLOOR,
    MIN_SAMPLE_SIZE_ROUNDS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _profile(
    pid="gp_aaaa1111bbbb2222",
    *,
    score=0.4,
    a1=0.3,
    a2=0.2,
    a3=0.1,
    deployable=2.0,
    sparse_rate=0.1,
    oos_rate=0.05,
    unknown_rate=0.0,
    sample_size=20,
    confidence=CONFIDENCE_A1_A2_A3_AVAILABLE,
    sparse_count=10,
    oos_count=5,
    unknown_count=0,
    a2_entered=20,
    a3_entered=10,
    **overrides,
):
    """Return a dict with the canonical generation_profile_metrics shape."""
    base = {
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
        "next_budget_weight_dry_run": EXPLORATION_FLOOR,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 9.1 Schema tests
# ---------------------------------------------------------------------------


def test_dry_run_budget_allocation_schema_contains_required_fields():
    fields = required_allocation_fields()
    for must_have in (
        "telemetry_version", "decision_id", "run_id", "created_at",
        "mode", "applied", "confidence", "allocator_version",
        "input_profile_count", "actionable_profile_count",
        "non_actionable_profile_count",
        "exploration_floor", "min_sample_size_rounds",
        "previous_profile_weights", "proposed_profile_weights_dry_run",
        "profile_scores", "profile_ranks", "non_actionable_reasons",
        "observed_bottleneck", "top_reject_reasons",
        "expected_effect", "safety_constraints",
        "reason", "source",
    ):
        assert must_have in fields, f"required field {must_have!r} missing"


def test_allocator_output_mode_is_dry_run():
    alloc = allocate_dry_run_budget([_profile()], run_id="r")
    assert alloc.mode == "DRY_RUN"
    assert alloc.to_event()["mode"] == "DRY_RUN"


def test_allocator_output_applied_is_false():
    alloc = allocate_dry_run_budget([_profile()], run_id="r")
    assert alloc.applied is False
    assert alloc.to_event()["applied"] is False


def test_allocator_version_is_0_9o_b():
    alloc = allocate_dry_run_budget([_profile()], run_id="r")
    assert alloc.allocator_version == "0-9O-B"
    assert alloc.to_event()["allocator_version"] == "0-9O-B"


def test_allocator_event_type_is_dry_run_budget_allocation():
    alloc = allocate_dry_run_budget([_profile()], run_id="r")
    assert alloc.to_event()["event_type"] == EVENT_TYPE_DRY_RUN_BUDGET_ALLOCATION


def test_allocator_invariants_resilient_to_caller_kwargs():
    # Caller cannot construct an applied=true / mode=APPLIED record by
    # passing kwargs — post-init resets the invariants.
    alloc = DryRunBudgetAllocation(
        run_id="r", confidence=CONFIDENCE_A1_A2_A3_AVAILABLE,
        input_profile_count=0, actionable_profile_count=0,
        non_actionable_profile_count=0,
        mode="APPLIED", applied=True, allocator_version="HACKED",
    )
    assert alloc.mode == "DRY_RUN"
    assert alloc.applied is False
    assert alloc.allocator_version == "0-9O-B"
    e = alloc.to_event()
    assert e["mode"] == "DRY_RUN"
    assert e["applied"] is False
    assert e["allocator_version"] == "0-9O-B"


def test_allocator_invariants_resilient_to_post_construction_mutation():
    alloc = allocate_dry_run_budget([_profile()], run_id="r")
    alloc.mode = "APPLIED"
    alloc.applied = True
    e = alloc.to_event()
    assert e["mode"] == "DRY_RUN"
    assert e["applied"] is False


def test_serialize_allocation_emits_valid_json():
    alloc = allocate_dry_run_budget([_profile()], run_id="r")
    text = serialize_allocation(alloc)
    payload = json.loads(text)
    assert payload["mode"] == "DRY_RUN"
    assert payload["applied"] is False
    assert payload["allocator_version"] == "0-9O-B"


# ---------------------------------------------------------------------------
# 9.2 Weight normalization tests
# ---------------------------------------------------------------------------


def test_weights_sum_to_one():
    profiles = [
        _profile(pid=f"gp_{i:016d}", score=0.1 * i)
        for i in range(1, 5)
    ]
    alloc = allocate_dry_run_budget(profiles, run_id="r")
    total = sum(alloc.proposed_profile_weights_dry_run.values())
    assert abs(total - 1.0) < 1e-9


def test_weight_calculation_is_deterministic():
    profiles = [
        _profile(pid="gp_aaaa", score=0.3),
        _profile(pid="gp_bbbb", score=0.6),
        _profile(pid="gp_cccc", score=-0.2),
    ]
    a = allocate_dry_run_budget(profiles, run_id="r-1")
    b = allocate_dry_run_budget(profiles, run_id="r-1")
    assert a.proposed_profile_weights_dry_run == b.proposed_profile_weights_dry_run
    assert a.profile_ranks == b.profile_ranks


def test_weight_calculation_does_not_mutate_inputs():
    profiles = [_profile(pid="gp_aaaa", score=0.4)]
    snapshot = json.dumps(profiles, sort_keys=True)
    allocate_dry_run_budget(profiles, run_id="r")
    assert json.dumps(profiles, sort_keys=True) == snapshot


def test_exploration_floor_enforced():
    profiles = [
        _profile(pid="gp_winner", score=1.0),
        _profile(pid="gp_loser", score=-1.0),
    ]
    alloc = allocate_dry_run_budget(profiles, run_id="r")
    weights = alloc.proposed_profile_weights_dry_run
    assert all(w >= EXPLORATION_FLOOR - 1e-9 for w in weights.values())


def test_negative_scores_do_not_create_negative_weights():
    profiles = [
        _profile(pid="gp_neg", score=-1.0),
        _profile(pid="gp_pos", score=0.5),
    ]
    alloc = allocate_dry_run_budget(profiles, run_id="r")
    assert all(w >= 0 for w in alloc.proposed_profile_weights_dry_run.values())


def test_all_non_actionable_profiles_use_safe_fallback():
    profiles = [
        _profile(pid="gp_a", confidence=CONFIDENCE_LOW_UNTIL_A2_A3),
        _profile(pid="gp_b", confidence=CONFIDENCE_LOW_UNTIL_A2_A3),
    ]
    alloc = allocate_dry_run_budget(profiles, run_id="r")
    assert alloc.confidence == CONFIDENCE_NO_ACTIONABLE_PROFILE
    # Equal-weight fallback when no previous_profile_weights provided.
    weights = alloc.proposed_profile_weights_dry_run
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    assert len(set(weights.values())) == 1  # all equal


def test_unknown_profile_does_not_dominate_allocation():
    profiles = [
        _profile(pid="UNKNOWN_PROFILE", score=1.0),  # would dominate without cap
        _profile(pid="gp_other", score=0.0),
    ]
    alloc = allocate_dry_run_budget(profiles, run_id="r")
    weights = alloc.proposed_profile_weights_dry_run
    # UNKNOWN_PROFILE must not exceed gp_other once capped.
    assert weights["UNKNOWN_PROFILE"] <= weights["gp_other"] + 1e-9


def test_compute_proposed_weights_zero_score_uses_floor_only():
    profiles = [
        _profile(pid="gp_a", score=-1.0),
        _profile(pid="gp_b", score=-1.0),
    ]
    weights = compute_proposed_weights(profiles)
    # Both raw_weights are 0 — result must be even split (each gets 0.5,
    # which is well above EXPLORATION_FLOOR).
    assert weights["gp_a"] == pytest.approx(0.5)
    assert weights["gp_b"] == pytest.approx(0.5)


def test_compute_proposed_weights_handles_empty_input():
    weights = compute_proposed_weights([])
    assert weights == {}


def test_equal_weight_fallback_deterministic_and_normalized():
    weights = equal_weight_fallback(["gp_b", "gp_a", "gp_c"])
    assert list(weights.keys()) == ["gp_a", "gp_b", "gp_c"]
    assert abs(sum(weights.values()) - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# 9.3 Confidence gate tests
# ---------------------------------------------------------------------------


def test_confidence_a1_a2_a3_available_allows_actionable_dry_run():
    alloc = allocate_dry_run_budget(
        [_profile(confidence=CONFIDENCE_A1_A2_A3_AVAILABLE, sample_size=25)],
        run_id="r",
    )
    assert alloc.actionable_profile_count == 1
    assert alloc.confidence == CONFIDENCE_A1_A2_A3_AVAILABLE
    assert alloc.applied is False  # still dry-run, but actionable now


def test_low_confidence_blocks_actionable_recommendation():
    alloc = allocate_dry_run_budget(
        [_profile(confidence=CONFIDENCE_LOW_UNTIL_A2_A3)],
        run_id="r",
    )
    assert alloc.actionable_profile_count == 0
    assert alloc.confidence == CONFIDENCE_NO_ACTIONABLE_PROFILE
    pid = "gp_aaaa1111bbbb2222"
    assert REASON_MISSING_A2_A3 in alloc.non_actionable_reasons[pid]


def test_low_sample_size_blocks_actionable_recommendation():
    alloc = allocate_dry_run_budget(
        [_profile(confidence=CONFIDENCE_LOW_SAMPLE_SIZE, sample_size=5)],
        run_id="r",
    )
    assert alloc.actionable_profile_count == 0
    assert alloc.confidence == CONFIDENCE_NO_ACTIONABLE_PROFILE
    pid = "gp_aaaa1111bbbb2222"
    assert REASON_LOW_SAMPLE_SIZE in alloc.non_actionable_reasons[pid]


def test_min_sample_size_20_required():
    # Even with full A2/A3 confidence claimed, a small sample size is
    # rejected by the per-profile sample-size check.
    alloc = allocate_dry_run_budget(
        [_profile(
            confidence=CONFIDENCE_A1_A2_A3_AVAILABLE,
            sample_size=19,
        )],
        run_id="r",
    )
    assert alloc.actionable_profile_count == 0
    pid = "gp_aaaa1111bbbb2222"
    assert REASON_LOW_SAMPLE_SIZE in alloc.non_actionable_reasons[pid]


def test_missing_a2_a3_metrics_blocks_actionability():
    # confidence claimed full, but A2/A3 entered counts are zero.
    alloc = allocate_dry_run_budget(
        [_profile(
            confidence=CONFIDENCE_A1_A2_A3_AVAILABLE,
            sample_size=25,
            a2=0.0, a2_entered=0,
            a3=0.0, a3_entered=0,
        )],
        run_id="r",
    )
    pid = "gp_aaaa1111bbbb2222"
    assert REASON_MISSING_A2_A3 in alloc.non_actionable_reasons.get(pid, [])
    assert alloc.actionable_profile_count == 0


def test_counter_inconsistency_blocks_actionability():
    alloc = allocate_dry_run_budget(
        [_profile(
            confidence=CONFIDENCE_A1_A2_A3_AVAILABLE,
            sample_size=25,
            unknown_rate=UNKNOWN_REJECT_VETO + 0.01,
        )],
        run_id="r",
    )
    pid = "gp_aaaa1111bbbb2222"
    assert REASON_COUNTER_INCONSISTENCY in alloc.non_actionable_reasons[pid]
    assert alloc.actionable_profile_count == 0


def test_evaluate_profile_actionability_missing_fields():
    ok, reasons = evaluate_profile_actionability({"generation_profile_id": "x"})
    assert ok is False
    assert REASON_MISSING_FIELDS in reasons


# ---------------------------------------------------------------------------
# 9.4 Penalty tests
# ---------------------------------------------------------------------------


def test_signal_too_sparse_penalty_reduces_dry_run_weight():
    sparse = _profile(
        pid="gp_sparse", score=-0.5, sparse_rate=0.9, sparse_count=80,
    )
    clean = _profile(
        pid="gp_clean", score=0.5, sparse_rate=0.05, sparse_count=5,
    )
    alloc = allocate_dry_run_budget([sparse, clean], run_id="r")
    weights = alloc.proposed_profile_weights_dry_run
    assert weights["gp_clean"] > weights["gp_sparse"]


def test_oos_fail_penalty_reduces_dry_run_weight():
    oos_heavy = _profile(
        pid="gp_oos", score=-0.4, oos_rate=0.8, oos_count=70,
    )
    clean = _profile(
        pid="gp_clean", score=0.5, oos_rate=0.05, oos_count=5,
    )
    alloc = allocate_dry_run_budget([oos_heavy, clean], run_id="r")
    weights = alloc.proposed_profile_weights_dry_run
    assert weights["gp_clean"] > weights["gp_oos"]


def test_unknown_reject_penalty_strongly_reduces_confidence():
    bad = _profile(
        pid="gp_bad", score=0.4, unknown_rate=0.5,
        unknown_count=80,
    )
    alloc = allocate_dry_run_budget([bad], run_id="r")
    pid = "gp_bad"
    assert REASON_COUNTER_INCONSISTENCY in alloc.non_actionable_reasons[pid]


def test_counter_inconsistency_marks_profile_non_actionable():
    bad = _profile(
        pid="gp_bad", unknown_rate=UNKNOWN_REJECT_VETO + 0.05,
    )
    ok, reasons = evaluate_profile_actionability(bad)
    assert ok is False
    assert REASON_COUNTER_INCONSISTENCY in reasons


# ---------------------------------------------------------------------------
# 9.5 Bottleneck explanation tests
# ---------------------------------------------------------------------------


def test_detects_signal_too_sparse_dominant_bottleneck():
    profiles = [
        _profile(sparse_count=100, oos_count=10, unknown_count=5),
    ]
    bn, top = classify_bottleneck(profiles, actionable_count=1)
    assert bn == BOTTLENECK_SIGNAL_TOO_SPARSE
    assert top[0] == "SIGNAL_TOO_SPARSE"


def test_detects_oos_fail_dominant_bottleneck():
    profiles = [
        _profile(sparse_count=10, oos_count=100, unknown_count=5),
    ]
    bn, top = classify_bottleneck(profiles, actionable_count=1)
    assert bn == BOTTLENECK_OOS_FAIL
    assert top[0] == "OOS_FAIL"


def test_detects_unknown_reject_dominant_bottleneck():
    profiles = [
        _profile(sparse_count=10, oos_count=5, unknown_count=100),
    ]
    bn, top = classify_bottleneck(profiles, actionable_count=1)
    assert bn == BOTTLENECK_UNKNOWN_REJECT
    assert top[0] == "UNKNOWN_REJECT"


def test_detects_low_sample_size_bottleneck():
    profiles = [
        _profile(confidence=CONFIDENCE_LOW_SAMPLE_SIZE, sample_size=5),
    ]
    bn, _ = classify_bottleneck(profiles, actionable_count=0)
    assert bn == BOTTLENECK_LOW_SAMPLE


def test_detects_missing_a2_a3_bottleneck():
    profiles = [
        _profile(confidence=CONFIDENCE_LOW_UNTIL_A2_A3, sample_size=25),
    ]
    bn, _ = classify_bottleneck(profiles, actionable_count=0)
    assert bn == BOTTLENECK_MISSING_A2_A3


def test_detects_no_actionable_profile_bottleneck():
    bn, top = classify_bottleneck([], actionable_count=0)
    assert bn == BOTTLENECK_NO_ACTIONABLE
    assert top == []


def test_bottleneck_published_in_allocation_record():
    profiles = [
        _profile(
            pid="gp_a", confidence=CONFIDENCE_A1_A2_A3_AVAILABLE,
            sample_size=25,
            sparse_count=200, oos_count=20, unknown_count=10,
        ),
    ]
    alloc = allocate_dry_run_budget(profiles, run_id="r")
    assert alloc.observed_bottleneck == BOTTLENECK_SIGNAL_TOO_SPARSE
    assert alloc.top_reject_reasons[0] == "SIGNAL_TOO_SPARSE"


# ---------------------------------------------------------------------------
# 9.6 feedback_decision_record integration tests
# ---------------------------------------------------------------------------


def test_feedback_decision_record_stores_allocator_output():
    alloc = allocate_dry_run_budget([_profile()], run_id="r")
    rec = to_feedback_decision_record(alloc)
    payload = rec.to_event()
    assert payload["proposed_profile_weights_dry_run"] == \
        alloc.proposed_profile_weights_dry_run
    assert payload["profile_scores"] == alloc.profile_scores


def test_feedback_decision_record_mode_remains_dry_run():
    alloc = allocate_dry_run_budget([_profile()], run_id="r")
    rec = to_feedback_decision_record(alloc)
    assert rec.to_event()["mode"] == "DRY_RUN"


def test_feedback_decision_record_applied_false_enforced():
    alloc = allocate_dry_run_budget([_profile()], run_id="r")
    rec = to_feedback_decision_record(alloc)
    assert rec.to_event()["applied"] is False


def test_feedback_decision_record_rejects_or_overrides_applied_true():
    # Bypass the public builder and try to construct an applied record
    # via direct dataclass kwargs — invariant must still win.
    from zangetsu.services.feedback_decision_record import FeedbackDecisionRecord

    rec = FeedbackDecisionRecord(
        run_id="r", applied=True, mode="APPLIED",
    )
    e = rec.to_event()
    assert e["applied"] is False
    assert e["mode"] == "DRY_RUN"


def test_feedback_decision_record_has_no_apply_method():
    from zangetsu.services import feedback_decision_record as fdr
    # No public name in the module starts with apply_.
    publics = [n for n in dir(fdr) if not n.startswith("_")]
    for name in publics:
        assert not name.lower().startswith("apply"), (
            f"feedback_decision_record exports apply-shaped name {name!r}"
        )


def test_feedback_decision_record_contains_safety_constraints():
    alloc = allocate_dry_run_budget([_profile()], run_id="r")
    rec = to_feedback_decision_record(alloc)
    assert rec.safety_constraints
    assert "NOT_APPLIED_TO_RUNTIME" in rec.safety_constraints


# ---------------------------------------------------------------------------
# 9.7 Runtime isolation tests
# ---------------------------------------------------------------------------


_SERVICES_DIR = (
    pathlib.Path(__file__).resolve().parent.parent / "services"
)


def _service_text(name):
    return (_SERVICES_DIR / name).read_text(encoding="utf-8")


def test_allocator_not_imported_by_alpha_generation_runtime():
    text = _service_text("arena_pipeline.py")
    assert "feedback_budget_allocator" not in text


def test_allocator_not_imported_by_arena_runtime():
    for fname in ("arena23_orchestrator.py", "arena45_orchestrator.py", "arena_gates.py"):
        assert "feedback_budget_allocator" not in _service_text(fname), (
            f"{fname} unexpectedly imports feedback_budget_allocator"
        )


def test_allocator_not_imported_by_execution_runtime():
    for fname in (
        "alpha_signal_live.py",
        "data_collector.py",
        "alpha_dedup.py",
        "alpha_ensemble.py",
        "alpha_discovery.py",
    ):
        path = _SERVICES_DIR / fname
        if path.exists():
            assert "feedback_budget_allocator" not in path.read_text(
                encoding="utf-8"
            ), f"{fname} unexpectedly imports feedback_budget_allocator"


def test_allocator_output_not_consumed_by_generation_runtime():
    # No runtime / Arena / execution module references the allocator
    # output. The 0-9R-IMPL-DRY consumer (`feedback_budget_consumer.py`)
    # is the single legitimate downstream and is itself dry-run only —
    # it is allow-listed below. All other modules must remain clean.
    allowed = {"feedback_budget_allocator.py", "feedback_budget_consumer.py"}
    for path in _SERVICES_DIR.glob("*.py"):
        if path.name in allowed:
            continue
        text = path.read_text(encoding="utf-8")
        assert "DryRunBudgetAllocation" not in text, (
            f"{path.name} unexpectedly references DryRunBudgetAllocation"
        )
        assert "allocate_dry_run_budget" not in text, (
            f"{path.name} unexpectedly references allocate_dry_run_budget"
        )


def test_no_generation_budget_file_changed():
    # Generation-budget knobs live in arena_pipeline.py + alpha_engine.py
    # — the allocator must not have leaked into either.
    for fname in ("arena_pipeline.py",):
        text = _service_text(fname)
        assert "feedback_budget_allocator" not in text


def test_no_sampling_weight_file_changed():
    # Sampling weights are managed inside alpha_engine via GP loop knobs.
    # The allocator does not import alpha_engine.
    import zangetsu.services.feedback_budget_allocator as alloc_mod
    src = pathlib.Path(alloc_mod.__file__).read_text(encoding="utf-8")
    assert "alpha_engine" not in src
    assert "sampling_weight" not in src


# ---------------------------------------------------------------------------
# 9.8 Governance / behavior invariance tests
# ---------------------------------------------------------------------------


def test_no_threshold_constants_changed():
    import zangetsu.services.feedback_budget_allocator as mod
    public = {n for n in dir(mod) if not n.startswith("_")}
    forbidden_substrings = (
        "MIN_TRADES", "ENTRY_THR", "EXIT_THR",
        "ATR_STOP_MULT", "TRAIL_PCT", "FIXED_TARGET",
        "PROMOTE_WILSON_LB", "PROMOTE_MIN_TRADES",
    )
    for name in public:
        for forbid in forbidden_substrings:
            assert forbid not in name.upper()


def test_a2_min_trades_still_pinned():
    src = (_SERVICES_DIR / "arena23_orchestrator.py").read_text(encoding="utf-8")
    assert "bt.total_trades < 25" in src


def test_a3_thresholds_still_pinned():
    src = (_SERVICES_DIR / "arena23_orchestrator.py").read_text(encoding="utf-8")
    assert "ATR_STOP_MULTS = [2.0, 3.0, 4.0]" in src
    assert "TRAIL_PCTS = [0.003, 0.005, 0.008, 0.01, 0.015, 0.02]" in src
    assert "FIXED_TARGETS = [0.005, 0.008, 0.01, 0.015, 0.02, 0.03]" in src


def test_arena_pass_fail_behavior_unchanged():
    from zangetsu.services import arena_gates
    for fn in ("arena2_pass", "arena3_pass", "arena4_pass"):
        assert hasattr(arena_gates, fn)


def test_champion_promotion_unchanged():
    text = _service_text("arena45_orchestrator.py")
    assert text.count("UPDATE champion_pipeline_fresh SET status = 'DEPLOYABLE'") == 1


def test_deployable_count_semantics_unchanged():
    # Allocator does not redefine DEPLOYABLE.
    import zangetsu.services.feedback_budget_allocator as alloc_mod
    src = pathlib.Path(alloc_mod.__file__).read_text(encoding="utf-8")
    assert "'DEPLOYABLE'" not in src
    assert '"DEPLOYABLE"' not in src


def test_profile_score_remains_read_only():
    # The allocator must not write back into generation_profile_metrics.
    import zangetsu.services.feedback_budget_allocator as alloc_mod
    src = pathlib.Path(alloc_mod.__file__).read_text(encoding="utf-8")
    # Allow imports / docstring references; forbid `metrics.profile_score =`
    # assignments. The strict regex below catches any attribute write.
    import re
    assert not re.search(r"\bprofile_score\s*=\s*[^=]", src), (
        "allocator must not assign to profile_score"
    )


def test_next_budget_weight_dry_run_not_applied():
    alloc = allocate_dry_run_budget([_profile()], run_id="r")
    # The allocator's output never claims to have applied a budget.
    assert alloc.applied is False
    assert alloc.expected_effect.startswith("DRY_RUN")


# ---------------------------------------------------------------------------
# Extra: input adaptation edge cases
# ---------------------------------------------------------------------------


def test_allocator_handles_dataclass_input():
    from zangetsu.services.generation_profile_metrics import (
        GenerationProfileMetrics,
    )

    m = GenerationProfileMetrics(
        run_id="r",
        generation_profile_id="gp_xxxx",
        profile_score=0.4,
        avg_a1_pass_rate=0.3,
        avg_a2_pass_rate=0.2,
        avg_a3_pass_rate=0.1,
        total_entered_a2=20,
        total_entered_a3=10,
        sample_size_rounds=25,
        min_sample_size_met=True,
        confidence=CONFIDENCE_A1_A2_A3_AVAILABLE,
    )
    alloc = allocate_dry_run_budget([m], run_id="r")
    assert alloc.actionable_profile_count == 1


def test_allocator_handles_none_input():
    alloc = allocate_dry_run_budget([None, _profile()], run_id="r")
    # None coerces to a coercion-failure entry, not a crash.
    assert alloc.actionable_profile_count == 1


def test_allocator_handles_garbage_input():
    alloc = allocate_dry_run_budget(["garbage", 42, _profile()], run_id="r")
    # Still produces a valid record; non-coerceable entries are skipped.
    assert alloc.actionable_profile_count == 1
    assert "__coercion_failed__" in alloc.non_actionable_reasons


def test_safe_allocate_returns_value_on_success():
    alloc = safe_allocate_dry_run_budget([_profile()], run_id="r")
    assert alloc is not None
    assert alloc.applied is False


def test_previous_profile_weights_used_as_fallback():
    # Non-actionable, with previous weights → output mirrors previous (renormalized).
    profiles = [
        _profile(pid="gp_a", confidence=CONFIDENCE_LOW_UNTIL_A2_A3),
        _profile(pid="gp_b", confidence=CONFIDENCE_LOW_UNTIL_A2_A3),
    ]
    previous = {"gp_a": 0.6, "gp_b": 0.3}  # not normalized; allocator must renormalize
    alloc = allocate_dry_run_budget(
        profiles, run_id="r", previous_profile_weights=previous
    )
    weights = alloc.proposed_profile_weights_dry_run
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    assert weights["gp_a"] > weights["gp_b"]


def test_allocator_input_count_matches_coerceable_inputs():
    alloc = allocate_dry_run_budget([_profile(), None, _profile(pid="gp_x")], run_id="r")
    assert alloc.input_profile_count == 2
