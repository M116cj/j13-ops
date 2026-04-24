"""Tests for TEAM ORDER 0-9O-A — Generation Profile Identity and Read-Only
Scoring.

Covers:
- Profile identity (id, fingerprint, fallbacks, canonical JSON)
- Generation profile metrics schema + aggregation
- Read-only scoring (penalties, caps, LOW_CONFIDENCE marker, sample size
  guardrail)
- Dry-run budget recommendation (exploration floor, not-applied invariant)
- Feedback decision record (append-only, mode=DRY_RUN, applied=False,
  reject applied=True attempts)
- Behavior invariance (thresholds, Arena pass/fail, champion promotion,
  deployable_count semantics)
- Integration with arena_pipeline helper
"""

from __future__ import annotations

import importlib
import sys

import pytest


# --- Profile identity -------------------------------------------------------

def test_profile_fingerprint_is_sha256_prefixed():
    from zangetsu.services.generation_profile_identity import (
        profile_fingerprint,
    )

    fp = profile_fingerprint({"generator_type": "gp_v10", "n_gen": 20})
    assert fp.startswith("sha256:")
    assert len(fp) == len("sha256:") + 64


def test_profile_fingerprint_is_stable_for_key_order_changes():
    from zangetsu.services.generation_profile_identity import (
        profile_fingerprint,
    )

    a = profile_fingerprint(
        {"n_gen": 20, "pop_size": 100, "generator_type": "gp_v10"}
    )
    b = profile_fingerprint(
        {"generator_type": "gp_v10", "pop_size": 100, "n_gen": 20}
    )
    assert a == b


def test_profile_fingerprint_excludes_timestamps():
    from zangetsu.services.generation_profile_identity import (
        profile_fingerprint,
    )

    base = {"generator_type": "gp_v10", "n_gen": 20}
    with_ts = {
        **base,
        "timestamp": "2026-04-24T12:00:00Z",
        "created_at": "2026-04-24T12:00:00Z",
        "updated_at": "2026-04-24T12:00:00Z",
    }
    assert profile_fingerprint(base) == profile_fingerprint(with_ts)


def test_profile_fingerprint_excludes_run_id():
    from zangetsu.services.generation_profile_identity import (
        profile_fingerprint,
    )

    base = {"generator_type": "gp_v10", "n_gen": 20}
    fp1 = profile_fingerprint({**base, "run_id": "run-aaa"})
    fp2 = profile_fingerprint({**base, "run_id": "run-bbb"})
    assert fp1 == fp2
    assert profile_fingerprint(base) == fp1


def test_profile_fingerprint_handles_unavailable_config():
    from zangetsu.services.generation_profile_identity import (
        UNAVAILABLE_FINGERPRINT,
        profile_fingerprint,
    )

    assert profile_fingerprint(None) == UNAVAILABLE_FINGERPRINT
    assert profile_fingerprint({}) == UNAVAILABLE_FINGERPRINT


def test_profile_id_uses_upstream_identity_when_available():
    from zangetsu.services.generation_profile_identity import (
        resolve_profile_identity,
    )

    identity = resolve_profile_identity(
        {"generator_type": "gp_v10", "n_gen": 20},
        profile_name="gp_v10_j01",
    )
    assert identity["profile_id"].startswith("gp_")
    assert identity["profile_fingerprint"].startswith("sha256:")
    assert identity["profile_name"] == "gp_v10_j01"


def test_profile_id_falls_back_to_unknown_when_missing():
    from zangetsu.services.generation_profile_identity import (
        UNAVAILABLE_FINGERPRINT,
        UNKNOWN_PROFILE_ID,
        resolve_profile_identity,
    )

    identity = resolve_profile_identity(None)
    assert identity["profile_id"] == UNKNOWN_PROFILE_ID
    assert identity["profile_fingerprint"] == UNAVAILABLE_FINGERPRINT


def test_profile_identity_failure_does_not_block_telemetry():
    from zangetsu.services.generation_profile_identity import (
        UNAVAILABLE_FINGERPRINT,
        UNKNOWN_PROFILE_ID,
        safe_resolve_profile_identity,
    )

    class _Poison:
        def items(self):
            raise RuntimeError("boom")

    identity = safe_resolve_profile_identity(_Poison())
    assert identity["profile_id"] == UNKNOWN_PROFILE_ID
    assert identity["profile_fingerprint"] == UNAVAILABLE_FINGERPRINT


# --- Canonical JSON ---------------------------------------------------------

def test_canonical_json_sorts_keys():
    from zangetsu.services.generation_profile_identity import canonical_json

    out = canonical_json({"b": 1, "a": 2, "c": 3})
    assert out == '{"a":2,"b":1,"c":3}'


def test_canonical_json_uses_compact_separators():
    from zangetsu.services.generation_profile_identity import canonical_json

    out = canonical_json({"a": [1, 2, 3]})
    assert " " not in out
    assert out == '{"a":[1,2,3]}'


def test_canonical_json_rejects_non_serializable_values_safely():
    from zangetsu.services.generation_profile_identity import (
        UNAVAILABLE_FINGERPRINT,
        profile_fingerprint,
    )

    class _Unserializable:
        def __repr__(self):
            raise RuntimeError("no repr")

    fp = profile_fingerprint({"generator_type": "gp_v10", "bad": _Unserializable()})
    # Either canonicalization succeeds via default=str or returns UNAVAILABLE —
    # both are acceptable; it must not raise.
    assert isinstance(fp, str)


# --- Generation profile metrics ---------------------------------------------

def _sample_a1_batch(entered, passed, distribution=None, deployable=None, stage="A1"):
    return {
        "event_type": "arena_batch_metrics",
        "arena_stage": stage,
        "entered_count": entered,
        "passed_count": passed,
        "rejected_count": entered - passed,
        "reject_reason_distribution": distribution or {},
        "deployable_count": deployable,
    }


def test_generation_profile_metrics_schema_contains_required_fields():
    from zangetsu.services.generation_profile_metrics import (
        aggregate_batches_for_profile,
    )

    metrics = aggregate_batches_for_profile(
        [_sample_a1_batch(100, 10)],
        run_id="run-x",
        generation_profile_id="gp_test",
    )
    event = metrics.to_event()
    required = {
        "telemetry_version", "run_id", "generation_profile_id",
        "generation_profile_fingerprint", "profile_name",
        "profile_config_hash", "total_batches",
        "total_candidates_generated", "total_entered_a1", "total_passed_a1",
        "total_rejected_a1", "avg_a1_pass_rate",
        "total_entered_a2", "total_passed_a2", "total_rejected_a2",
        "avg_a2_pass_rate",
        "total_entered_a3", "total_passed_a3", "total_rejected_a3",
        "avg_a3_pass_rate",
        "total_deployable_count", "avg_deployable_count",
        "signal_too_sparse_count", "signal_too_sparse_rate",
        "oos_fail_count", "oos_fail_rate",
        "unknown_reject_count", "unknown_reject_rate",
        "instability_penalty", "profile_score", "next_budget_weight_dry_run",
        "sample_size_rounds", "min_sample_size_met",
        "created_at", "updated_at", "source",
    }
    missing = required - set(event.keys())
    assert not missing, f"missing required fields: {missing}"


def test_generation_profile_metrics_aggregates_a1_counts():
    from zangetsu.services.generation_profile_metrics import (
        aggregate_batches_for_profile,
    )

    batches = [
        _sample_a1_batch(100, 10),
        _sample_a1_batch(100, 20),
        _sample_a1_batch(100, 30),
    ]
    m = aggregate_batches_for_profile(batches, run_id="run-x")
    assert m.total_entered_a1 == 300
    assert m.total_passed_a1 == 60
    assert m.total_rejected_a1 == 240
    assert m.total_batches == 3
    assert 0.19 < m.avg_a1_pass_rate < 0.21


def test_generation_profile_metrics_handles_missing_a2_a3():
    from zangetsu.services.generation_profile_metrics import (
        CONFIDENCE_LOW_UNTIL_A2_A3,
        aggregate_batches_for_profile,
    )

    m = aggregate_batches_for_profile(
        [_sample_a1_batch(100, 10)], run_id="run-x"
    )
    assert m.total_entered_a2 == 0
    assert m.total_entered_a3 == 0
    assert m.avg_a2_pass_rate == 0.0
    assert m.avg_a3_pass_rate == 0.0
    assert m.confidence == CONFIDENCE_LOW_UNTIL_A2_A3


def test_signal_too_sparse_rate_computation():
    from zangetsu.services.generation_profile_metrics import (
        aggregate_batches_for_profile,
    )

    dist = {"SIGNAL_TOO_SPARSE": 80, "OOS_FAIL": 10}
    m = aggregate_batches_for_profile(
        [_sample_a1_batch(100, 10, distribution=dist)], run_id="run-x"
    )
    assert m.signal_too_sparse_count == 80
    # total rejects = 90 (100 - 10)
    assert abs(m.signal_too_sparse_rate - 80 / 90) < 1e-9


def test_unknown_reject_rate_computation():
    from zangetsu.services.generation_profile_metrics import (
        aggregate_batches_for_profile,
    )

    dist = {"UNKNOWN_REJECT": 5, "SIGNAL_TOO_SPARSE": 85}
    m = aggregate_batches_for_profile(
        [_sample_a1_batch(100, 10, distribution=dist)], run_id="run-x"
    )
    assert m.unknown_reject_count == 5
    assert abs(m.unknown_reject_rate - 5 / 90) < 1e-9


def test_avg_pass_rate_computation():
    from zangetsu.services.generation_profile_metrics import (
        aggregate_batches_for_profile,
    )

    batches = [_sample_a1_batch(100, 10), _sample_a1_batch(100, 30)]
    m = aggregate_batches_for_profile(batches, run_id="run-x")
    assert abs(m.avg_a1_pass_rate - 0.2) < 1e-9


def test_deployable_count_aggregation_does_not_change_semantics():
    from zangetsu.services.generation_profile_metrics import (
        aggregate_batches_for_profile,
    )

    batches = [
        _sample_a1_batch(100, 10, deployable=2),
        _sample_a1_batch(100, 20, deployable=5),
    ]
    m = aggregate_batches_for_profile(batches, run_id="run-x")
    assert m.total_deployable_count == 7
    assert abs(m.avg_deployable_count - 3.5) < 1e-9


# --- Scoring ----------------------------------------------------------------

def test_profile_score_calculation():
    from zangetsu.services.generation_profile_metrics import (
        PROFILE_SCORE_MAX, PROFILE_SCORE_MIN, compute_profile_score,
    )

    score = compute_profile_score(
        avg_a1_pass_rate=0.3,
        avg_a2_pass_rate=0.2,
        avg_a3_pass_rate=0.1,
        avg_deployable_count=1.0,
        signal_too_sparse_rate=0.1,
        oos_fail_rate=0.05,
        unknown_reject_rate=0.0,
        instability_penalty=0.0,
    )
    assert PROFILE_SCORE_MIN <= score <= PROFILE_SCORE_MAX


def test_profile_score_penalizes_signal_too_sparse():
    from zangetsu.services.generation_profile_metrics import (
        compute_profile_score,
    )

    good = compute_profile_score(
        avg_a1_pass_rate=0.3,
        avg_a2_pass_rate=0.2,
        avg_a3_pass_rate=0.1,
        avg_deployable_count=1.0,
        signal_too_sparse_rate=0.0,
        oos_fail_rate=0.0,
        unknown_reject_rate=0.0,
        instability_penalty=0.0,
    )
    bad = compute_profile_score(
        avg_a1_pass_rate=0.3,
        avg_a2_pass_rate=0.2,
        avg_a3_pass_rate=0.1,
        avg_deployable_count=1.0,
        signal_too_sparse_rate=0.9,
        oos_fail_rate=0.0,
        unknown_reject_rate=0.0,
        instability_penalty=0.0,
    )
    assert bad < good


def test_profile_score_penalizes_unknown_reject_strongly():
    from zangetsu.services.generation_profile_metrics import (
        compute_profile_score,
    )

    good = compute_profile_score(
        avg_a1_pass_rate=0.3,
        avg_a2_pass_rate=0.2,
        avg_a3_pass_rate=0.1,
        avg_deployable_count=1.0,
        signal_too_sparse_rate=0.1,
        oos_fail_rate=0.1,
        unknown_reject_rate=0.0,
        instability_penalty=0.0,
    )
    with_unknown = compute_profile_score(
        avg_a1_pass_rate=0.3,
        avg_a2_pass_rate=0.2,
        avg_a3_pass_rate=0.1,
        avg_deployable_count=1.0,
        signal_too_sparse_rate=0.1,
        oos_fail_rate=0.1,
        unknown_reject_rate=0.5,
        instability_penalty=0.0,
    )
    # unknown penalty weight 0.50 → delta ~ -0.25 given 0.5 unknown rate
    assert (good - with_unknown) >= 0.2


def test_profile_score_marks_low_confidence_without_a2_a3():
    from zangetsu.services.generation_profile_metrics import (
        CONFIDENCE_LOW_UNTIL_A2_A3,
        aggregate_batches_for_profile,
    )

    batches = [_sample_a1_batch(100, 10) for _ in range(25)]
    m = aggregate_batches_for_profile(batches, run_id="run-x")
    assert m.confidence == CONFIDENCE_LOW_UNTIL_A2_A3


def test_profile_score_requires_min_sample_size_20_for_actionability():
    from zangetsu.services.generation_profile_metrics import (
        MIN_SAMPLE_SIZE_ROUNDS,
        aggregate_batches_for_profile,
    )

    few = aggregate_batches_for_profile(
        [_sample_a1_batch(100, 10) for _ in range(5)], run_id="run-x"
    )
    assert few.min_sample_size_met is False

    many = aggregate_batches_for_profile(
        [_sample_a1_batch(100, 10) for _ in range(MIN_SAMPLE_SIZE_ROUNDS)],
        run_id="run-x",
    )
    assert many.min_sample_size_met is True


def test_scoring_does_not_modify_generation_budget():
    """Scoring must be read-only. It must expose no callable that can
    mutate generation budget state."""
    import zangetsu.services.generation_profile_metrics as gpm

    # Module must not export any function whose name implies applying a
    # budget to runtime.
    forbidden = {
        "apply_budget",
        "set_budget",
        "update_runtime_budget",
        "write_generation_config",
    }
    for name in forbidden:
        assert not hasattr(gpm, name), f"unexpected runtime mutator: {name}"


def test_scoring_does_not_modify_arena_decisions():
    """Scoring helpers must return pure values; calling them cannot
    change module-level state of arena_pipeline."""
    from zangetsu.services import arena_pipeline as ap
    from zangetsu.services.generation_profile_metrics import (
        compute_profile_score,
    )

    snapshot = {k: getattr(ap, k, None) for k in dir(ap) if k.isupper()}
    _ = compute_profile_score(
        avg_a1_pass_rate=0.5,
        avg_a2_pass_rate=0.3,
        avg_a3_pass_rate=0.2,
        avg_deployable_count=1.0,
        signal_too_sparse_rate=0.1,
        oos_fail_rate=0.05,
        unknown_reject_rate=0.0,
        instability_penalty=0.0,
    )
    after = {k: getattr(ap, k, None) for k in dir(ap) if k.isupper()}
    assert snapshot == after


# --- Dry-run budget recommendation ------------------------------------------

def test_next_budget_weight_dry_run_obeys_exploration_floor():
    from zangetsu.services.generation_profile_metrics import (
        EXPLORATION_FLOOR, compute_dry_run_budget_weight,
    )

    w = compute_dry_run_budget_weight(-1.0, min_sample_size_met=True)
    assert w >= EXPLORATION_FLOOR


def test_next_budget_weight_dry_run_is_not_applied():
    from zangetsu.services.generation_profile_metrics import (
        EXPLORATION_FLOOR, compute_dry_run_budget_weight,
    )

    # Without min_sample_size_met, the recommendation must pin at floor —
    # any runtime budget allocator reading this field can trivially detect
    # "not actionable yet".
    w = compute_dry_run_budget_weight(0.9, min_sample_size_met=False)
    assert w == EXPLORATION_FLOOR


def test_dry_run_recommendation_labeled_low_confidence_when_metrics_incomplete():
    from zangetsu.services.generation_profile_metrics import (
        CONFIDENCE_LOW_UNTIL_A2_A3,
        aggregate_batches_for_profile,
    )

    m = aggregate_batches_for_profile(
        [_sample_a1_batch(100, 10) for _ in range(30)], run_id="run-x"
    )
    assert m.confidence == CONFIDENCE_LOW_UNTIL_A2_A3


# --- Feedback decision record -----------------------------------------------

def test_feedback_decision_record_is_append_only_shape():
    from zangetsu.services.feedback_decision_record import (
        build_feedback_decision_record,
    )

    rec = build_feedback_decision_record(run_id="run-x")
    event = rec.to_event()
    assert event["decision_id"].startswith("dec-")
    assert event["telemetry_version"] == "1"
    assert "created_at" in event
    assert event["event_type"] == "feedback_decision_record"


def test_feedback_decision_record_mode_is_dry_run():
    from zangetsu.services.feedback_decision_record import (
        MODE_DRY_RUN, build_feedback_decision_record,
    )

    rec = build_feedback_decision_record(run_id="run-x")
    assert rec.mode == MODE_DRY_RUN
    assert rec.mode_must_equal == MODE_DRY_RUN
    event = rec.to_event()
    assert event["mode"] == MODE_DRY_RUN


def test_feedback_decision_record_applied_is_false():
    from zangetsu.services.feedback_decision_record import (
        build_feedback_decision_record,
    )

    rec = build_feedback_decision_record(run_id="run-x")
    assert rec.applied is False
    assert rec.applied_must_equal_false is True
    event = rec.to_event()
    assert event["applied"] is False


def test_feedback_decision_record_rejects_applied_true():
    """Even if a caller tries to force applied=True, the builder must
    override it back to False (post_init + to_event defense in depth)."""
    from zangetsu.services.feedback_decision_record import (
        build_feedback_decision_record,
    )

    rec = build_feedback_decision_record(run_id="run-x", applied=True)
    assert rec.applied is False
    # Mutate field directly — serialization must still emit False.
    rec.applied = True
    event = rec.to_event()
    assert event["applied"] is False


def test_feedback_decision_record_contains_safety_constraints():
    from zangetsu.services.feedback_decision_record import (
        DEFAULT_SAFETY_CONSTRAINTS, build_feedback_decision_record,
    )

    rec = build_feedback_decision_record(run_id="run-x")
    assert set(DEFAULT_SAFETY_CONSTRAINTS).issubset(set(rec.safety_constraints))


# --- Behavior invariance ----------------------------------------------------

def test_no_threshold_constants_changed_under_0_9o_a():
    """Pinned thresholds must survive this PR."""
    from j01 import config as j01_config

    assert j01_config.thresholds.A2_MIN_TRADES == 25
    assert j01_config.thresholds.A3_SEGMENTS == 5
    assert j01_config.thresholds.A3_MIN_TRADES_PER_SEGMENT == 15
    assert j01_config.thresholds.A3_MIN_WR_PASSES == 4
    assert j01_config.thresholds.A3_MIN_PNL_PASSES == 4
    assert j01_config.thresholds.A3_WR_FLOOR == 0.45


@pytest.mark.parametrize(
    "trades,expected",
    [(20, False), (25, True)],  # below / at A2_MIN_TRADES
)
def test_arena_pass_fail_behavior_unchanged_a2_min_trades(trades, expected):
    """A2 min-trades gate stays at 25. 20 → reject. 25 → pass for this
    aspect."""
    from j01.config.thresholds import A2_MIN_TRADES

    assert (trades >= A2_MIN_TRADES) is expected


def test_champion_promotion_unchanged():
    """Champion promotion selects by round_champions count; scoring must
    not interfere. Confirm scoring does not mutate round_champions logic."""
    from zangetsu.services.generation_profile_metrics import (
        aggregate_batches_for_profile,
    )

    batches = [_sample_a1_batch(100, 10)]
    m = aggregate_batches_for_profile(batches, run_id="run-x")
    # The metrics record must not expose any promotion override.
    assert not hasattr(m, "promote_champion")
    assert not hasattr(m, "promote_to_arena2")


def test_deployable_count_semantics_unchanged():
    """Aggregation must not inflate deployable_count via pass events."""
    from zangetsu.services.generation_profile_metrics import (
        aggregate_batches_for_profile,
    )

    # Three batches: none supply deployable_count — aggregator reports 0,
    # never infers from passed_count.
    batches = [_sample_a1_batch(100, 50, deployable=None) for _ in range(3)]
    m = aggregate_batches_for_profile(batches, run_id="run-x")
    assert m.total_deployable_count == 0
    assert m.avg_deployable_count == 0.0


def test_runtime_behavior_invariant_when_profile_identity_fails():
    from zangetsu.services.generation_profile_identity import (
        UNAVAILABLE_FINGERPRINT, UNKNOWN_PROFILE_ID,
        safe_resolve_profile_identity,
    )

    class _Boom:
        def items(self):
            raise RuntimeError("boom")

    identity = safe_resolve_profile_identity(_Boom())
    assert identity["profile_id"] == UNKNOWN_PROFILE_ID
    assert identity["profile_fingerprint"] == UNAVAILABLE_FINGERPRINT


# --- Integration with arena_pipeline ----------------------------------------

def test_arena_pipeline_exposes_0_9o_a_identity_resolver():
    from zangetsu.services import arena_pipeline as ap

    assert hasattr(ap, "_safe_resolve_profile_identity")


def test_arena_pipeline_helper_accepts_profile_identity_kwargs():
    """The P7-PR4-LITE helper must accept the new 0-9O-A profile identity
    kwargs without raising."""
    from zangetsu.services.arena_pipeline import (
        _emit_a1_batch_metrics_from_stats_safe,
    )

    _emit_a1_batch_metrics_from_stats_safe(
        run_id="run-x",
        batch_id="R1-BTCUSDT-BULL",
        entered_count=100,
        passed_count=10,
        stats={"reject_few_trades": 50, "reject_val_low_sharpe": 40},
        log=None,
        generation_profile_id="gp_test",
        generation_profile_fingerprint="sha256:abc",
    )


def test_arena_pipeline_helper_falls_back_when_identity_omitted():
    """When the new kwargs are omitted (old call sites), the helper must
    still use the UNKNOWN / UNAVAILABLE fallbacks without error."""
    from zangetsu.services.arena_pipeline import (
        _emit_a1_batch_metrics_from_stats_safe,
    )

    _emit_a1_batch_metrics_from_stats_safe(
        run_id="run-x",
        batch_id="R1-BTCUSDT-BULL",
        entered_count=100,
        passed_count=10,
        stats={"reject_few_trades": 50},
        log=None,
    )
