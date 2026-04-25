"""Tests for TEAM ORDER P7-PR4B — A2 / A3 Aggregate Arena Batch Metrics.

Covers:

  - 12.1 / 12.2  schema (A2 / A3)
  - 12.3        counter conservation (A2 / A3)
  - 12.4        rate calculation (A2 / A3)
  - 12.5        rejection distribution (A2 / A3)
  - 12.6        generation_profile_metrics aggregation across A1/A2/A3
  - 12.7        deployable_count linkage (authoritative source only)
  - 12.8        failure-safety (emitter / builder)
  - 12.9        governance / behavior invariance

All tests are pure-Python; no DB / Arena runtime is touched.
"""

from __future__ import annotations

import json

import pytest

from zangetsu.services.arena_pass_rate_telemetry import (
    ArenaBatchMetrics,
    ArenaStageMetrics,
    EVENT_TYPE_ARENA_BATCH_METRICS,
    UNAVAILABLE_FINGERPRINT,
    UNKNOWN_PROFILE_ID,
    aggregate_stage_metrics,
    build_a2_batch_metrics,
    build_a3_batch_metrics,
    build_arena_batch_metrics,
    build_arena_stage_summary,
    compute_pass_rate,
    compute_reject_rate,
    normalize_arena_stage,
    required_batch_fields,
    required_summary_fields,
    safe_emit_a2_batch_metrics,
    safe_emit_a3_batch_metrics,
    validate_counter_conservation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_a2_acc(profile_id="UNKNOWN_PROFILE", profile_fp="UNAVAILABLE"):
    return ArenaStageMetrics(
        arena_stage="A2",
        run_id="r-a2",
        batch_id="b-a2",
        generation_profile_id=profile_id,
        generation_profile_fingerprint=profile_fp,
    )


def _seed_a3_acc(profile_id="UNKNOWN_PROFILE", profile_fp="UNAVAILABLE"):
    return ArenaStageMetrics(
        arena_stage="A3",
        run_id="r-a3",
        batch_id="b-a3",
        generation_profile_id=profile_id,
        generation_profile_fingerprint=profile_fp,
    )


def _stage_event(stage, *, entered, passed, rejected, distribution=None,
                  deployable=None, profile_id=UNKNOWN_PROFILE_ID,
                  profile_fp=UNAVAILABLE_FINGERPRINT, run_id="r"):
    skipped = max(0, entered - passed - rejected)
    return {
        "event_type": EVENT_TYPE_ARENA_BATCH_METRICS,
        "telemetry_version": "1",
        "run_id": run_id,
        "batch_id": f"{stage}-b",
        "generation_profile_id": profile_id,
        "generation_profile_fingerprint": profile_fp,
        "arena_stage": stage,
        "entered_count": entered,
        "passed_count": passed,
        "rejected_count": rejected,
        "skipped_count": skipped,
        "error_count": 0,
        "in_flight_count": 0,
        "pass_rate": compute_pass_rate(passed, entered),
        "reject_rate": compute_reject_rate(rejected, entered),
        "top_reject_reason": "UNKNOWN_REJECT",
        "reject_reason_distribution": distribution or {},
        "deployable_count": deployable,
        "timestamp_start": "2026-04-24T00:00:00Z",
        "timestamp_end": "2026-04-24T00:01:00Z",
        "source": "arena_pipeline",
    }


# ---------------------------------------------------------------------------
# 12.1 A2 schema tests
# ---------------------------------------------------------------------------


def test_a2_arena_batch_metrics_schema_contains_required_fields():
    fields = required_batch_fields()
    for must_have in (
        "telemetry_version", "run_id", "batch_id",
        "generation_profile_id", "generation_profile_fingerprint",
        "arena_stage",
        "entered_count", "passed_count", "rejected_count",
        "skipped_count", "error_count", "in_flight_count",
        "pass_rate", "reject_rate",
        "top_reject_reason", "reject_reason_distribution",
        "deployable_count",
        "timestamp_start", "timestamp_end",
        "source",
    ):
        assert must_have in fields


def test_a2_arena_stage_summary_schema_contains_required_fields():
    fields = required_summary_fields()
    for must_have in (
        "telemetry_version", "run_id", "batch_id", "arena_stage",
        "entered_count", "passed_count", "rejected_count",
        "skipped_count", "error_count", "in_flight_count",
        "pass_rate", "reject_rate",
        "top_3_reject_reasons", "bottleneck_score",
        "timestamp", "source",
    ):
        assert must_have in fields


def test_a2_metrics_include_generation_profile_identity():
    acc = _seed_a2_acc(profile_id="gp_aaaabbbbccccdddd",
                       profile_fp="sha256:" + "0" * 64)
    acc.on_entered(); acc.on_passed()
    acc.on_entered(); acc.on_rejected("SIGNAL_TOO_SPARSE")
    event = build_a2_batch_metrics(acc)
    assert event.arena_stage == "A2"
    assert event.generation_profile_id == "gp_aaaabbbbccccdddd"
    assert event.generation_profile_fingerprint.startswith("sha256:")


def test_a2_metrics_fallback_to_unknown_profile():
    acc = _seed_a2_acc()  # defaults to UNKNOWN / UNAVAILABLE
    acc.on_entered(); acc.on_passed()
    event = build_a2_batch_metrics(acc)
    assert event.generation_profile_id == UNKNOWN_PROFILE_ID
    assert event.generation_profile_fingerprint == UNAVAILABLE_FINGERPRINT


# ---------------------------------------------------------------------------
# 12.2 A3 schema tests
# ---------------------------------------------------------------------------


def test_a3_arena_batch_metrics_schema_contains_required_fields():
    # Identical to A2 but assert via a built A3 event rather than the
    # static fields tuple, to confirm the canonical fields end up on the
    # serialized dict for the A3 builder specifically.
    acc = _seed_a3_acc()
    acc.on_entered(); acc.on_rejected("OOS_FAIL")
    event = build_a3_batch_metrics(acc)
    d = event.to_dict()
    for k in required_batch_fields():
        assert k in d, f"A3 event missing required field {k!r}"
    assert d["arena_stage"] == "A3"


def test_a3_arena_stage_summary_schema_contains_required_fields():
    acc = _seed_a3_acc()
    acc.on_entered(); acc.on_rejected("OOS_FAIL")
    a3_batch = build_a3_batch_metrics(acc)
    summary = build_arena_stage_summary(
        "A3", run_id="r-a3", batches=[a3_batch],
    )
    d = summary.to_dict()
    for k in required_summary_fields():
        assert k in d


def test_a3_metrics_include_generation_profile_identity():
    acc = _seed_a3_acc(profile_id="gp_1111222233334444",
                       profile_fp="sha256:" + "1" * 64)
    acc.on_entered(); acc.on_passed()
    event = build_a3_batch_metrics(acc)
    assert event.arena_stage == "A3"
    assert event.generation_profile_id == "gp_1111222233334444"


def test_a3_metrics_fallback_to_unknown_profile():
    acc = _seed_a3_acc()
    acc.on_entered(); acc.on_rejected("OOS_FAIL")
    event = build_a3_batch_metrics(acc)
    assert event.generation_profile_id == UNKNOWN_PROFILE_ID
    assert event.generation_profile_fingerprint == UNAVAILABLE_FINGERPRINT


# ---------------------------------------------------------------------------
# 12.3 Counter conservation tests
# ---------------------------------------------------------------------------


def test_a2_closed_counter_conservation():
    ok, _ = validate_counter_conservation(
        entered_count=100, passed_count=10, rejected_count=80,
        skipped_count=5, error_count=5, open_stage=False,
    )
    assert ok


def test_a2_open_counter_conservation():
    ok, _ = validate_counter_conservation(
        entered_count=100, passed_count=10, rejected_count=70,
        skipped_count=5, error_count=5, in_flight_count=10,
        open_stage=True,
    )
    assert ok


def test_a2_counter_residual_routes_to_counter_inconsistency():
    # passes and rejects don't sum to entered AND open_stage=False ⇒
    # validation must surface a violation rather than raise.
    ok, reason = validate_counter_conservation(
        entered_count=100, passed_count=50, rejected_count=10,
        skipped_count=0, error_count=0, open_stage=False,
    )
    assert ok is False
    assert "conservation" in (reason or "")


def test_a3_closed_counter_conservation():
    ok, _ = validate_counter_conservation(
        entered_count=50, passed_count=5, rejected_count=43,
        skipped_count=1, error_count=1, open_stage=False,
    )
    assert ok


def test_a3_open_counter_conservation():
    ok, _ = validate_counter_conservation(
        entered_count=50, passed_count=5, rejected_count=40,
        skipped_count=1, error_count=1, in_flight_count=3,
        open_stage=True,
    )
    assert ok


def test_a3_counter_residual_routes_to_counter_inconsistency():
    ok, reason = validate_counter_conservation(
        entered_count=50, passed_count=20, rejected_count=10,
        skipped_count=0, error_count=0, open_stage=False,
    )
    assert ok is False
    assert "conservation" in (reason or "")


# ---------------------------------------------------------------------------
# 12.4 Rate calculation tests
# ---------------------------------------------------------------------------


def test_a2_pass_rate_calculation():
    acc = _seed_a2_acc()
    for _ in range(10):
        acc.on_entered()
    for _ in range(2):
        acc.on_passed()
    for _ in range(8):
        acc.on_rejected("SIGNAL_TOO_SPARSE")
    event = build_a2_batch_metrics(acc)
    assert abs(event.pass_rate - 0.2) < 1e-9


def test_a2_reject_rate_calculation():
    acc = _seed_a2_acc()
    for _ in range(20):
        acc.on_entered()
    for _ in range(20):
        acc.on_rejected("SIGNAL_TOO_SPARSE")
    event = build_a2_batch_metrics(acc)
    assert abs(event.reject_rate - 1.0) < 1e-9


def test_a2_zero_entered_count_rate_handling():
    acc = _seed_a2_acc()
    # No entries at all — rates default to 0.0 per repository convention.
    event = build_a2_batch_metrics(acc)
    assert event.entered_count == 0
    assert event.pass_rate == 0.0
    assert event.reject_rate == 0.0


def test_a3_pass_rate_calculation():
    acc = _seed_a3_acc()
    for _ in range(40):
        acc.on_entered()
    for _ in range(4):
        acc.on_passed()
    for _ in range(36):
        acc.on_rejected("OOS_FAIL")
    event = build_a3_batch_metrics(acc)
    assert abs(event.pass_rate - 0.1) < 1e-9


def test_a3_reject_rate_calculation():
    acc = _seed_a3_acc()
    for _ in range(40):
        acc.on_entered()
    for _ in range(36):
        acc.on_rejected("OOS_FAIL")
    for _ in range(4):
        acc.on_passed()
    event = build_a3_batch_metrics(acc)
    assert abs(event.reject_rate - 0.9) < 1e-9


def test_a3_zero_entered_count_rate_handling():
    acc = _seed_a3_acc()
    event = build_a3_batch_metrics(acc)
    assert event.entered_count == 0
    assert event.pass_rate == 0.0
    assert event.reject_rate == 0.0


# ---------------------------------------------------------------------------
# 12.5 Rejection distribution tests
# ---------------------------------------------------------------------------


def test_a2_rejection_distribution_counts_signal_too_sparse():
    acc = _seed_a2_acc()
    for _ in range(20):
        acc.on_entered()
        acc.on_rejected("SIGNAL_TOO_SPARSE")
    event = build_a2_batch_metrics(acc)
    assert event.reject_reason_distribution.get("SIGNAL_TOO_SPARSE") == 20
    assert event.top_reject_reason == "SIGNAL_TOO_SPARSE"


def test_a2_unknown_reject_remains_visible():
    acc = _seed_a2_acc()
    acc.on_entered(); acc.on_rejected("UNKNOWN_REJECT")
    event = build_a2_batch_metrics(acc)
    assert "UNKNOWN_REJECT" in event.reject_reason_distribution


def test_a2_top_reject_reason_selection():
    acc = _seed_a2_acc()
    for _ in range(5):
        acc.on_entered(); acc.on_rejected("SIGNAL_TOO_SPARSE")
    for _ in range(10):
        acc.on_entered(); acc.on_rejected("INVALID_FORMULA")
    event = build_a2_batch_metrics(acc)
    assert event.top_reject_reason == "INVALID_FORMULA"


def test_a3_rejection_distribution_counts_oos_fail():
    acc = _seed_a3_acc()
    for _ in range(15):
        acc.on_entered()
        acc.on_rejected("OOS_FAIL")
    event = build_a3_batch_metrics(acc)
    assert event.reject_reason_distribution.get("OOS_FAIL") == 15
    assert event.top_reject_reason == "OOS_FAIL"


def test_a3_unknown_reject_remains_visible():
    acc = _seed_a3_acc()
    acc.on_entered(); acc.on_rejected("UNKNOWN_REJECT")
    event = build_a3_batch_metrics(acc)
    assert "UNKNOWN_REJECT" in event.reject_reason_distribution


def test_a3_top_reject_reason_selection():
    acc = _seed_a3_acc()
    for _ in range(3):
        acc.on_entered(); acc.on_rejected("SIGNAL_TOO_SPARSE")
    for _ in range(8):
        acc.on_entered(); acc.on_rejected("OOS_FAIL")
    event = build_a3_batch_metrics(acc)
    assert event.top_reject_reason == "OOS_FAIL"


# ---------------------------------------------------------------------------
# 12.6 generation_profile_metrics aggregation tests
# ---------------------------------------------------------------------------


def test_generation_profile_metrics_aggregates_a1_a2_a3_counts():
    from zangetsu.services.generation_profile_metrics import (
        aggregate_batches_for_profile,
    )

    batches = [
        _stage_event("A1", entered=100, passed=20, rejected=80),
        _stage_event("A2", entered=20, passed=4, rejected=16,
                      distribution={"SIGNAL_TOO_SPARSE": 16}),
        _stage_event("A3", entered=4, passed=1, rejected=3,
                      distribution={"OOS_FAIL": 3}),
    ]
    m = aggregate_batches_for_profile(batches, run_id="r")
    assert m.total_entered_a1 == 100
    assert m.total_passed_a1 == 20
    assert m.total_entered_a2 == 20
    assert m.total_passed_a2 == 4
    assert m.total_entered_a3 == 4
    assert m.total_passed_a3 == 1


def test_generation_profile_metrics_computes_avg_a2_pass_rate():
    from zangetsu.services.generation_profile_metrics import (
        aggregate_batches_for_profile,
    )

    batches = [
        _stage_event("A2", entered=20, passed=5, rejected=15),
        _stage_event("A2", entered=20, passed=3, rejected=17),
    ]
    m = aggregate_batches_for_profile(batches, run_id="r")
    # avg of (5/20, 3/20) = 0.2
    assert abs(m.avg_a2_pass_rate - 0.2) < 1e-9


def test_generation_profile_metrics_computes_avg_a3_pass_rate():
    from zangetsu.services.generation_profile_metrics import (
        aggregate_batches_for_profile,
    )

    batches = [
        _stage_event("A3", entered=10, passed=1, rejected=9),
        _stage_event("A3", entered=10, passed=3, rejected=7),
    ]
    m = aggregate_batches_for_profile(batches, run_id="r")
    # avg of (0.1, 0.3) = 0.2
    assert abs(m.avg_a3_pass_rate - 0.2) < 1e-9


def test_generation_profile_metrics_computes_signal_too_sparse_rate_from_a2():
    from zangetsu.services.generation_profile_metrics import (
        aggregate_batches_for_profile,
    )

    batches = [
        _stage_event("A2", entered=20, passed=2, rejected=18,
                      distribution={"SIGNAL_TOO_SPARSE": 18}),
    ]
    m = aggregate_batches_for_profile(batches, run_id="r")
    assert m.signal_too_sparse_count == 18
    assert abs(m.signal_too_sparse_rate - 1.0) < 1e-9


def test_generation_profile_metrics_computes_oos_fail_rate_from_a3():
    from zangetsu.services.generation_profile_metrics import (
        aggregate_batches_for_profile,
    )

    batches = [
        _stage_event("A3", entered=10, passed=1, rejected=9,
                      distribution={"OOS_FAIL": 9}),
    ]
    m = aggregate_batches_for_profile(batches, run_id="r")
    assert m.oos_fail_count == 9
    assert abs(m.oos_fail_rate - 1.0) < 1e-9


def test_generation_profile_metrics_confidence_upgrades_when_a2_a3_available():
    from zangetsu.services.generation_profile_metrics import (
        CONFIDENCE_A1_A2_A3_AVAILABLE,
        CONFIDENCE_LOW_SAMPLE_SIZE,
        CONFIDENCE_LOW_UNTIL_A2_A3,
        aggregate_batches_for_profile,
    )

    # Case 1 — only A1: still LOW_UNTIL_A2_A3
    only_a1 = [_stage_event("A1", entered=10, passed=2, rejected=8)]
    m1 = aggregate_batches_for_profile(only_a1, run_id="r")
    assert m1.confidence == CONFIDENCE_LOW_UNTIL_A2_A3

    # Case 2 — A1+A2+A3 but only a few rounds: LOW_SAMPLE_SIZE
    # (3 batches total < MIN_SAMPLE_SIZE_ROUNDS = 20)
    small = [
        _stage_event("A1", entered=10, passed=2, rejected=8),
        _stage_event("A2", entered=2, passed=1, rejected=1),
        _stage_event("A3", entered=1, passed=0, rejected=1),
    ]
    m2 = aggregate_batches_for_profile(small, run_id="r")
    assert m2.confidence == CONFIDENCE_LOW_SAMPLE_SIZE

    # Case 3 — A1/A2/A3 with >= 20 batches: full confidence
    big = []
    for _ in range(25):
        big.append(_stage_event("A1", entered=10, passed=2, rejected=8))
    big.append(_stage_event("A2", entered=2, passed=1, rejected=1))
    big.append(_stage_event("A3", entered=1, passed=0, rejected=1))
    m3 = aggregate_batches_for_profile(big, run_id="r")
    assert m3.confidence == CONFIDENCE_A1_A2_A3_AVAILABLE


def test_generation_profile_metrics_still_requires_min_sample_size_20_for_actionability():
    from zangetsu.services.generation_profile_metrics import (
        EXPLORATION_FLOOR,
        aggregate_batches_for_profile,
    )

    # Tight A2/A3 metrics, but only 5 batches → not actionable.
    small = []
    for _ in range(5):
        small.append(_stage_event("A1", entered=10, passed=2, rejected=8))
        small.append(_stage_event("A2", entered=2, passed=1, rejected=1))
        small.append(_stage_event("A3", entered=1, passed=0, rejected=1))
    m = aggregate_batches_for_profile(small, run_id="r")
    assert m.min_sample_size_met is False
    # Recommendation must remain at the exploration floor when sample
    # size is insufficient — actionable scoring requires ≥ 20 rounds.
    assert m.next_budget_weight_dry_run == EXPLORATION_FLOOR


# ---------------------------------------------------------------------------
# 12.7 Deployable count tests
# ---------------------------------------------------------------------------


def test_deployable_count_uses_authoritative_source():
    # The aggregator only honors deployable_count when explicitly supplied
    # as a non-None integer in the batch event. It never derives this
    # value from passed_count.
    from zangetsu.services.generation_profile_metrics import (
        aggregate_batches_for_profile,
    )

    batches = [
        _stage_event("A2", entered=10, passed=5, rejected=5, deployable=2),
        _stage_event("A3", entered=5, passed=4, rejected=1, deployable=3),
    ]
    m = aggregate_batches_for_profile(batches, run_id="r")
    assert m.total_deployable_count == 5  # 2 + 3


def test_a2_a3_pass_metrics_do_not_inflate_deployable_count():
    # When deployable_count is explicitly None, the aggregator must NOT
    # synthesize a deployable_count from A2/A3 pass counts.
    from zangetsu.services.generation_profile_metrics import (
        aggregate_batches_for_profile,
    )

    batches = [
        _stage_event("A2", entered=20, passed=10, rejected=10, deployable=None),
        _stage_event("A3", entered=10, passed=5, rejected=5, deployable=None),
    ]
    m = aggregate_batches_for_profile(batches, run_id="r")
    assert m.total_deployable_count == 0
    assert m.avg_deployable_count == 0.0


def test_missing_deployable_count_is_marked_unavailable():
    # Build an A2 ArenaBatchMetrics with no deployable_count supplied —
    # field defaults to None (= UNAVAILABLE per dataclass contract).
    acc = _seed_a2_acc()
    acc.on_entered(); acc.on_passed()
    event = build_a2_batch_metrics(acc)
    assert event.deployable_count is None


# ---------------------------------------------------------------------------
# 12.8 Failure-safety tests
# ---------------------------------------------------------------------------


def _failing_writer(_line):
    raise RuntimeError("writer blew up")


def test_a2_metrics_emitter_failure_is_swallowed():
    acc = _seed_a2_acc()
    acc.on_entered(); acc.on_passed()

    class _FailingLog:
        def info(self, _line):
            raise RuntimeError("boom")

    # Must not raise — failures return False silently.
    ok = safe_emit_a2_batch_metrics(acc, log=_FailingLog())
    assert ok is False


def test_a2_metrics_builder_failure_is_swallowed():
    # Passing a bogus accumulator surface that lacks expected attributes
    # must not propagate. The wrapper returns False rather than raising.

    class _BogusAcc:
        # No attributes, no methods — build_arena_batch_metrics will fail.
        pass

    ok = safe_emit_a2_batch_metrics(_BogusAcc())
    assert ok is False


def test_a2_runtime_behavior_invariant_when_telemetry_fails():
    # Simulate a failing telemetry path: the only contract is that the
    # emission returns False without raising. Consumer logic above (Arena
    # decisions) must therefore proceed unchanged.
    ok = safe_emit_a2_batch_metrics(None)  # None acc
    assert ok is False


def test_a3_metrics_emitter_failure_is_swallowed():
    acc = _seed_a3_acc()
    acc.on_entered(); acc.on_passed()

    class _FailingLog:
        def info(self, _line):
            raise RuntimeError("boom")

    ok = safe_emit_a3_batch_metrics(acc, log=_FailingLog())
    assert ok is False


def test_a3_metrics_builder_failure_is_swallowed():
    class _BogusAcc:
        pass

    ok = safe_emit_a3_batch_metrics(_BogusAcc())
    assert ok is False


def test_a3_runtime_behavior_invariant_when_telemetry_fails():
    ok = safe_emit_a3_batch_metrics(None)
    assert ok is False


# ---------------------------------------------------------------------------
# 12.9 Governance / behavior invariance tests
# ---------------------------------------------------------------------------


def test_no_threshold_constants_changed():
    # Ensure no Arena threshold constants leaked into the telemetry
    # module's public namespace. This prevents accidental coupling
    # between trace-only helpers and runtime gates.
    import zangetsu.services.arena_pass_rate_telemetry as mod
    public = {
        n for n in dir(mod) if not n.startswith("_")
    }
    forbidden_substrings = (
        "MIN_TRADES", "ENTRY_THR", "EXIT_THR",
        "ATR_STOP_MULT", "TRAIL_PCT", "FIXED_TARGET",
        "PROMOTE_WILSON_LB", "PROMOTE_MIN_TRADES",
    )
    for name in public:
        for forbid in forbidden_substrings:
            assert forbid not in name.upper(), (
                f"telemetry module leaked threshold-like name {name!r}"
            )


def test_a2_min_trades_still_pinned():
    # P7-PR4B is trace-only — A2_MIN_TRADES (== 25 inside the V10 path)
    # must remain untouched. We verify by reading the orchestrator
    # source and asserting the literal predicate is still present.
    import pathlib
    src = pathlib.Path(__file__).resolve().parent.parent / "services" / "arena23_orchestrator.py"
    text = src.read_text(encoding="utf-8")
    # The V10 branch enforces ``bt.total_trades < 25`` for A2 reject.
    assert "bt.total_trades < 25" in text


def test_a3_thresholds_still_pinned():
    # A3 uses the same ``< 25`` minimum-trades floor in its V10 branch
    # plus the ATR_STOP_MULTS / TRAIL_PCTS / FIXED_TARGETS grids. We
    # cannot import the orchestrator here — its module body chdirs to a
    # production-only path — so we read the source text and assert the
    # exact literals are still present.
    import pathlib
    src = pathlib.Path(__file__).resolve().parent.parent / "services" / "arena23_orchestrator.py"
    text = src.read_text(encoding="utf-8")
    assert "ATR_STOP_MULTS = [2.0, 3.0, 4.0]" in text
    assert "TRAIL_PCTS = [0.003, 0.005, 0.008, 0.01, 0.015, 0.02]" in text
    assert "FIXED_TARGETS = [0.005, 0.008, 0.01, 0.015, 0.02, 0.03]" in text


def test_arena_pass_fail_behavior_unchanged():
    # P7-PR4B does not export any predicate that bypasses arena_gates.
    # Ensure the gates module is still the Arena pass/fail authority by
    # asserting its public API is intact.
    from zangetsu.services import arena_gates
    for fn in ("arena2_pass", "arena3_pass", "arena4_pass"):
        assert hasattr(arena_gates, fn), f"arena_gates.{fn} missing"


def test_champion_promotion_unchanged():
    # The promotion path lives in arena45_orchestrator.maybe_promote_to_deployable.
    # Ensure it is still the only declared promotion entry-point.
    import pathlib
    src = pathlib.Path(__file__).resolve().parent.parent / "services" / "arena45_orchestrator.py"
    text = src.read_text(encoding="utf-8")
    # Promotion-to-DEPLOYABLE write is still authoritative + singular.
    assert text.count("UPDATE champion_pipeline_fresh SET status = 'DEPLOYABLE'") == 1


def test_deployable_count_semantics_unchanged():
    # The aggregate aggregator must NOT count a passed A2/A3 candidate as
    # deployable. The contract is verified via the dedicated test
    # ``test_a2_a3_pass_metrics_do_not_inflate_deployable_count`` above
    # AND by asserting the telemetry module has zero references to
    # 'DEPLOYABLE' status.
    import zangetsu.services.arena_pass_rate_telemetry as mod
    src = mod.__file__
    with open(src, "r", encoding="utf-8") as f:
        text = f.read()
    assert "'DEPLOYABLE'" not in text
    assert '"DEPLOYABLE"' not in text


def test_generation_budget_unchanged():
    # The dry-run budget allocator is still bounded by EXPLORATION_FLOOR
    # when sample size is insufficient. (Real budget allocation happens
    # in a future order; this test ensures P7-PR4B did not flip a switch
    # by accident.)
    from zangetsu.services.generation_profile_metrics import (
        EXPLORATION_FLOOR,
        compute_dry_run_budget_weight,
    )
    # Insufficient sample → exact floor.
    assert compute_dry_run_budget_weight(0.99, min_sample_size_met=False) == EXPLORATION_FLOOR
    # Sufficient sample → ≥ floor, ≤ 1.0.
    w = compute_dry_run_budget_weight(0.5, min_sample_size_met=True)
    assert EXPLORATION_FLOOR <= w <= 1.0


def test_profile_score_still_read_only():
    # ``profile_score`` is a diagnostic field — it must never gain a
    # path back into arena_gates / generation. We assert by checking
    # that arena_gates and arena_pipeline do not import the profile
    # metrics module.
    import pathlib
    services = pathlib.Path(__file__).resolve().parent.parent / "services"
    for fname in ("arena_gates.py", "arena_pipeline.py"):
        src = (services / fname).read_text(encoding="utf-8")
        assert "generation_profile_metrics" not in src, (
            f"{fname} unexpectedly imports generation_profile_metrics — "
            f"profile_score must remain read-only"
        )


# ---------------------------------------------------------------------------
# Stage-aware helper specific tests (extension surface)
# ---------------------------------------------------------------------------


def test_normalize_arena_stage_canonical_inputs():
    assert normalize_arena_stage("a2") == "A2"
    assert normalize_arena_stage("A3") == "A3"
    assert normalize_arena_stage("ARENA2") == "A2"
    assert normalize_arena_stage(None) == "UNKNOWN"
    assert normalize_arena_stage("") == "UNKNOWN"
    assert normalize_arena_stage("ZZZ") == "UNKNOWN"


def test_aggregate_stage_metrics_rolls_up_by_stage():
    events = [
        _stage_event("A2", entered=10, passed=2, rejected=8,
                      distribution={"SIGNAL_TOO_SPARSE": 8}),
        _stage_event("A2", entered=10, passed=3, rejected=7,
                      distribution={"SIGNAL_TOO_SPARSE": 5, "INVALID_FORMULA": 2}),
        _stage_event("A3", entered=5, passed=1, rejected=4,
                      distribution={"OOS_FAIL": 4}),
    ]
    rolled = aggregate_stage_metrics(events)
    assert "A2" in rolled and "A3" in rolled
    assert rolled["A2"]["entered_count"] == 20
    assert rolled["A2"]["reject_reason_distribution"]["SIGNAL_TOO_SPARSE"] == 13
    assert rolled["A2"]["reject_reason_distribution"]["INVALID_FORMULA"] == 2
    assert abs(rolled["A2"]["pass_rate"] - 5 / 20) < 1e-9
    assert rolled["A3"]["entered_count"] == 5
    assert abs(rolled["A3"]["pass_rate"] - 1 / 5) < 1e-9


def test_aggregate_stage_metrics_handles_empty_input():
    assert aggregate_stage_metrics([]) == {}


def test_aggregate_stage_metrics_handles_malformed_events():
    # Malformed entries (non-mapping, missing keys) must not propagate.
    events = [
        "garbage",
        None,
        {"arena_stage": "A2", "entered_count": "not_an_int"},
        _stage_event("A2", entered=10, passed=2, rejected=8),
    ]
    rolled = aggregate_stage_metrics(events)
    # A2 got at least one valid contribution; non-mapping inputs were
    # skipped silently.
    assert "A2" in rolled
    # entered_count came from the one valid event (10) plus the
    # malformed integer-coerce entry (which is fine to skip).
    assert rolled["A2"]["entered_count"] >= 10
