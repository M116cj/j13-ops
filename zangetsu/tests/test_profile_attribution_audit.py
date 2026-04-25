"""Tests for TEAM ORDER 0-9P-AUDIT — Profile Attribution Coverage and
Replay Validation.

Covers:
  - Audit result schema lock.
  - Source-classification semantics.
  - Coverage rate computation.
  - GREEN / YELLOW / RED verdict thresholds.
  - RED verdict blocks PR-C consumer phase.
  - Replay validation across the 4-level precedence chain.
  - Audit / replay are read-only and don't import generation runtime
    or Arena runtime with side effects.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from zangetsu.tools.profile_attribution_audit import (
    AUDIT_VERSION,
    AttributionAuditResult,
    GREEN_FINGERPRINT_UNAVAIL_MAX,
    GREEN_MISMATCH_MAX,
    GREEN_UNKNOWN_MAX,
    ReplayValidationResult,
    VERDICT_GREEN,
    VERDICT_RED,
    VERDICT_YELLOW,
    YELLOW_FINGERPRINT_UNAVAIL_MAX,
    YELLOW_MISMATCH_MAX,
    YELLOW_UNKNOWN_MAX,
    audit,
    classify_attribution_source,
    classify_verdict,
    parse_event_log_lines,
    replay_validate,
    required_audit_fields,
    safe_audit,
    verdict_blocks_consumer_phase,
)
from zangetsu.services.generation_profile_identity import (
    UNAVAILABLE_FINGERPRINT,
    UNKNOWN_PROFILE_ID,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _event(stage, *, pid="gp_aaaa1111bbbb2222", fp="sha256:" + "a" * 64,
           src=None, entered=10, passed=2, rejected=8, dist=None,
           deployable=None):
    ev = {
        "arena_stage": stage,
        "generation_profile_id": pid,
        "generation_profile_fingerprint": fp,
        "entered_count": entered,
        "passed_count": passed,
        "rejected_count": rejected,
        "skipped_count": max(0, entered - passed - rejected),
        "error_count": 0,
        "in_flight_count": 0,
        "reject_reason_distribution": dist or {},
        "deployable_count": deployable,
    }
    if src is not None:
        ev["attribution_source"] = src
    return ev


# ---------------------------------------------------------------------------
# 1. Schema
# ---------------------------------------------------------------------------


def test_audit_result_schema_contains_required_fields():
    fields = required_audit_fields()
    for must_have in (
        "audit_version", "total_events",
        "total_a1_events", "total_a2_events", "total_a3_events",
        "passport_identity_count", "orchestrator_fallback_count",
        "unknown_profile_count", "unavailable_fingerprint_count",
        "passport_identity_rate", "orchestrator_fallback_rate",
        "unknown_profile_rate", "fingerprint_unavailable_rate",
        "a1_to_a2_profile_match_count", "a2_to_a3_profile_match_count",
        "profile_mismatch_count", "profile_mismatch_rate",
        "stage_counts_by_profile", "reject_reason_distribution_by_profile",
        "signal_too_sparse_rate_by_profile", "oos_fail_rate_by_profile",
        "deployable_count_by_profile",
        "verdict", "verdict_reasons",
    ):
        assert must_have in fields, f"missing required field {must_have!r}"


def test_audit_result_audit_version_is_pinned():
    r = audit([])
    assert r.audit_version == "0-9P-AUDIT"
    assert r.audit_version == AUDIT_VERSION


def test_audit_result_serializes_to_json():
    r = audit([_event("A1")])
    text = r.to_json()
    payload = json.loads(text)
    assert payload["audit_version"] == "0-9P-AUDIT"


# ---------------------------------------------------------------------------
# 2. Source classification
# ---------------------------------------------------------------------------


def test_classify_passport_when_attribution_source_passport_arena1():
    ev = _event("A2", src="passport_arena1")
    assert classify_attribution_source(ev) == "passport"


def test_classify_orchestrator_when_attribution_source_orchestrator():
    ev = _event("A2", src="orchestrator")
    assert classify_attribution_source(ev) == "orchestrator"


def test_classify_unknown_when_profile_id_unknown():
    ev = _event("A2", pid=UNKNOWN_PROFILE_ID)
    assert classify_attribution_source(ev) == "unknown"


def test_classify_unknown_when_attribution_source_fallback():
    ev = _event("A2", src="fallback")
    assert classify_attribution_source(ev) == "unknown"


def test_classify_passport_when_no_attribution_source_present_and_pid_known():
    ev = _event("A2")
    ev.pop("attribution_source", None)
    assert classify_attribution_source(ev) == "passport"


def test_classify_handles_non_mapping_input():
    assert classify_attribution_source(None) == "unknown"
    assert classify_attribution_source(42) == "unknown"
    assert classify_attribution_source("garbage") == "unknown"


# ---------------------------------------------------------------------------
# 3. Coverage rate computation
# ---------------------------------------------------------------------------


def test_attribution_audit_counts_passport_identity():
    events = [_event("A1", src="passport_arena1")] * 8 + [_event("A1", pid=UNKNOWN_PROFILE_ID)] * 2
    r = audit(events)
    assert r.passport_identity_count == 8
    assert r.unknown_profile_count == 2
    assert r.total_events == 10


def test_attribution_audit_counts_orchestrator_fallback():
    events = [_event("A2", src="orchestrator")] * 5 + [_event("A2", src="passport_arena1")] * 5
    r = audit(events)
    assert r.orchestrator_fallback_count == 5
    assert r.passport_identity_count == 5


def test_attribution_audit_counts_unknown_profile():
    events = [_event("A2", pid=UNKNOWN_PROFILE_ID)] * 4 + [_event("A2")] * 6
    r = audit(events)
    assert r.unknown_profile_count == 4


def test_attribution_audit_counts_unavailable_fingerprint():
    events = [_event("A1", fp=UNAVAILABLE_FINGERPRINT)] * 3 + [_event("A1")] * 7
    r = audit(events)
    assert r.unavailable_fingerprint_count == 3


def test_attribution_audit_computes_unknown_profile_rate():
    events = [_event("A1", pid=UNKNOWN_PROFILE_ID)] * 1 + [_event("A1")] * 9
    r = audit(events)
    assert abs(r.unknown_profile_rate - 0.1) < 1e-9


def test_attribution_audit_computes_passport_identity_rate():
    events = [_event("A1")] * 9 + [_event("A1", pid=UNKNOWN_PROFILE_ID)]
    r = audit(events)
    assert abs(r.passport_identity_rate - 0.9) < 1e-9


def test_attribution_audit_computes_fingerprint_unavailable_rate():
    events = [_event("A1", fp=UNAVAILABLE_FINGERPRINT)] * 2 + [_event("A1")] * 8
    r = audit(events)
    assert abs(r.fingerprint_unavailable_rate - 0.2) < 1e-9


def test_attribution_audit_per_stage_counts():
    events = [_event("A1")] * 3 + [_event("A2")] * 2 + [_event("A3")]
    r = audit(events)
    assert r.total_a1_events == 3
    assert r.total_a2_events == 2
    assert r.total_a3_events == 1


def test_attribution_audit_stage_counts_by_profile():
    events = [
        _event("A1", pid="gp_a"),
        _event("A1", pid="gp_a"),
        _event("A2", pid="gp_b"),
    ]
    r = audit(events)
    assert r.stage_counts_by_profile["A1"]["gp_a"] == 2
    assert r.stage_counts_by_profile["A2"]["gp_b"] == 1


def test_attribution_audit_reject_distribution_by_profile():
    events = [
        _event("A2", pid="gp_a", dist={"SIGNAL_TOO_SPARSE": 5, "OOS_FAIL": 1}),
        _event("A2", pid="gp_a", dist={"SIGNAL_TOO_SPARSE": 3}),
    ]
    r = audit(events)
    assert r.reject_reason_distribution_by_profile["gp_a"]["SIGNAL_TOO_SPARSE"] == 8
    assert r.reject_reason_distribution_by_profile["gp_a"]["OOS_FAIL"] == 1


def test_attribution_audit_sparse_rate_by_profile():
    events = [
        _event("A2", pid="gp_a", dist={"SIGNAL_TOO_SPARSE": 8, "OOS_FAIL": 2}),
    ]
    r = audit(events)
    assert abs(r.signal_too_sparse_rate_by_profile["gp_a"] - 0.8) < 1e-9


def test_attribution_audit_oos_rate_by_profile():
    events = [
        _event("A3", pid="gp_a", dist={"OOS_FAIL": 7, "SIGNAL_TOO_SPARSE": 3}),
    ]
    r = audit(events)
    assert abs(r.oos_fail_rate_by_profile["gp_a"] - 0.7) < 1e-9


def test_attribution_audit_deployable_count_by_profile():
    events = [
        _event("A2", pid="gp_a", deployable=2),
        _event("A2", pid="gp_a", deployable=3),
        _event("A2", pid="gp_b", deployable=None),
    ]
    r = audit(events)
    assert r.deployable_count_by_profile["gp_a"] == 5
    assert "gp_b" not in r.deployable_count_by_profile


def test_audit_handles_empty_input():
    r = audit([])
    assert r.total_events == 0
    assert r.passport_identity_rate == 0.0


def test_audit_handles_none_input():
    r = audit(None)
    assert r.total_events == 0
    assert r.verdict == VERDICT_RED


def test_audit_skips_malformed_events():
    events = [None, 42, "garbage", _event("A1")]
    r = audit(events)
    assert r.total_events == 1
    # Skipped entries recorded in verdict_reasons.
    assert any("skipped" in x for x in r.verdict_reasons)


# ---------------------------------------------------------------------------
# 4. Verdict thresholds (GREEN / YELLOW / RED)
# ---------------------------------------------------------------------------


def test_attribution_audit_green_classification():
    # All clean.
    verdict, _ = classify_verdict(
        unknown_profile_rate=0.02,
        profile_mismatch_rate=0.005,
        fingerprint_unavailable_rate=0.02,
    )
    assert verdict == VERDICT_GREEN


def test_attribution_audit_yellow_classification():
    # unknown_rate in YELLOW band.
    verdict, _ = classify_verdict(
        unknown_profile_rate=0.10,
        profile_mismatch_rate=0.005,
        fingerprint_unavailable_rate=0.02,
    )
    assert verdict == VERDICT_YELLOW


def test_attribution_audit_red_classification():
    # mismatch above YELLOW max.
    verdict, _ = classify_verdict(
        unknown_profile_rate=0.02,
        profile_mismatch_rate=0.10,  # > 0.05
        fingerprint_unavailable_rate=0.02,
    )
    assert verdict == VERDICT_RED


def test_red_classification_blocks_consumer_phase():
    assert verdict_blocks_consumer_phase(VERDICT_RED) is True
    assert verdict_blocks_consumer_phase(VERDICT_YELLOW) is False
    assert verdict_blocks_consumer_phase(VERDICT_GREEN) is False


def test_green_threshold_constants_align_with_order():
    # Order §5 specifies: GREEN unknown < 5%, mismatch < 1%, fingerprint < 5%
    assert GREEN_UNKNOWN_MAX == pytest.approx(0.05)
    assert GREEN_MISMATCH_MAX == pytest.approx(0.01)
    assert GREEN_FINGERPRINT_UNAVAIL_MAX == pytest.approx(0.05)


def test_yellow_threshold_constants_align_with_order():
    # Order §5 specifies YELLOW max boundaries: 20% / 5% / 20%
    assert YELLOW_UNKNOWN_MAX == pytest.approx(0.20)
    assert YELLOW_MISMATCH_MAX == pytest.approx(0.05)
    assert YELLOW_FINGERPRINT_UNAVAIL_MAX == pytest.approx(0.20)


def test_classify_verdict_reasons_explain_failure():
    _, reasons = classify_verdict(
        unknown_profile_rate=0.10,
        profile_mismatch_rate=0.005,
        fingerprint_unavailable_rate=0.02,
    )
    assert any("unknown_profile_rate" in r for r in reasons)


def test_audit_red_verdict_when_unknown_dominates():
    events = [_event("A1", pid=UNKNOWN_PROFILE_ID)] * 30 + [_event("A1")] * 5
    r = audit(events)
    assert r.verdict == VERDICT_RED


def test_audit_green_verdict_when_clean_data():
    # 30 events all with passport_arena1 source and known fingerprints.
    events = [_event("A1", src="passport_arena1")] * 30
    r = audit(events)
    # No mismatches because A2/A3 streams are empty.
    assert r.verdict == VERDICT_GREEN


# ---------------------------------------------------------------------------
# 5. Cross-stage profile match counts
# ---------------------------------------------------------------------------


def test_a1_to_a2_profile_match_count_when_aligned():
    events = [
        _event("A1", pid="gp_a"),
        _event("A2", pid="gp_a"),
        _event("A1", pid="gp_b"),
        _event("A2", pid="gp_b"),
    ]
    r = audit(events)
    assert r.a1_to_a2_profile_match_count == 2


def test_a2_to_a3_profile_match_count_when_aligned():
    events = [
        _event("A2", pid="gp_a"),
        _event("A3", pid="gp_a"),
    ]
    r = audit(events)
    assert r.a2_to_a3_profile_match_count == 1


def test_profile_mismatch_count_increases_on_mismatch():
    events = [
        _event("A1", pid="gp_a"),
        _event("A2", pid="gp_b"),  # mismatch vs A1
        _event("A2", pid="gp_a"),
        _event("A3", pid="gp_c"),  # mismatch vs A2
    ]
    r = audit(events)
    assert r.profile_mismatch_count >= 1


def test_profile_mismatch_rate_zero_on_perfect_alignment():
    events = [
        _event("A1", pid="gp_a"),
        _event("A2", pid="gp_a"),
        _event("A3", pid="gp_a"),
    ]
    r = audit(events)
    assert r.profile_mismatch_rate == 0.0


# ---------------------------------------------------------------------------
# 6. Replay validation
# ---------------------------------------------------------------------------


def test_replay_groups_metrics_by_profile():
    passports = [
        {"arena1": {"generation_profile_id": "gp_a"}},
        {"arena1": {"generation_profile_id": "gp_a"}},
        {"arena1": {"generation_profile_id": "gp_b"}},
    ]
    res = replay_validate(passports)
    assert res.matched_passport_arena1 == 3
    assert res.total_passports == 3


def test_replay_preserves_a1_a2_a3_stage_counts():
    # When events for all stages share the same profile_id, audit
    # yields equal stage counts for that profile.
    events = [_event("A1", pid="gp_a")] * 5 + [_event("A2", pid="gp_a")] * 5 + [_event("A3", pid="gp_a")] * 5
    r = audit(events)
    assert r.stage_counts_by_profile["A1"]["gp_a"] == 5
    assert r.stage_counts_by_profile["A2"]["gp_a"] == 5
    assert r.stage_counts_by_profile["A3"]["gp_a"] == 5


def test_replay_keeps_unknown_profile_visible():
    passports = [
        {"arena1": {"generation_profile_id": "gp_a"}},
        {},  # no identity → fallback
        {"arena1": {}},
    ]
    res = replay_validate(passports)
    assert res.matched_passport_arena1 == 1
    assert res.matched_fallback >= 2


def test_replay_validate_with_orchestrator_fallback():
    passports = [{}]
    res = replay_validate(
        passports,
        orchestrator_profile_id="gp_orch",
    )
    assert res.matched_orchestrator == 1


def test_replay_validate_handles_empty_input():
    res = replay_validate([])
    assert res.total_passports == 0


def test_replay_validate_handles_none_input():
    res = replay_validate(None)
    assert res.total_passports == 0


def test_replay_validate_expected_match_rate():
    passports = [
        {"arena1": {"generation_profile_id": "gp_a"}},
        {"arena1": {"generation_profile_id": "gp_a"}},
        {"arena1": {"generation_profile_id": "gp_b"}},
    ]
    res = replay_validate(passports, expected_profile_id="gp_a")
    assert abs(res.expected_match_rate - (2 / 3)) < 1e-9


# ---------------------------------------------------------------------------
# 7. JSON-line log parsing
# ---------------------------------------------------------------------------


def test_parse_event_log_lines_skips_malformed():
    lines = [
        "",
        "not json",
        json.dumps({"arena_stage": "A1", "generation_profile_id": "gp_a"}),
        "{broken",
        json.dumps([1, 2]),  # not a dict
        json.dumps({"arena_stage": "A2"}),
    ]
    parsed = parse_event_log_lines(lines)
    assert len(parsed) == 2


def test_parse_event_log_lines_handles_none():
    assert parse_event_log_lines(None) == []


# ---------------------------------------------------------------------------
# 8. Read-only / runtime isolation
# ---------------------------------------------------------------------------


def test_audit_does_not_modify_runtime_state():
    events = [_event("A1")]
    snapshot = json.dumps(events, sort_keys=True)
    audit(events)
    assert json.dumps(events, sort_keys=True) == snapshot


def test_audit_does_not_import_generation_runtime():
    import zangetsu.tools.profile_attribution_audit as mod
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    # Allow imports from generation_profile_identity (constants only)
    # but forbid runtime modules.
    assert "from zangetsu.services.arena_pipeline" not in src
    assert "from zangetsu.services.alpha_engine" not in src


def test_audit_does_not_import_arena_runtime_with_side_effects():
    import zangetsu.tools.profile_attribution_audit as mod
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    assert "import zangetsu.services.arena_pipeline" not in src
    assert "import zangetsu.services.arena23_orchestrator" not in src
    assert "import zangetsu.services.arena45_orchestrator" not in src


def test_audit_safe_wrapper_returns_red_on_internal_error():
    class _BadIter:
        def __iter__(self):
            raise RuntimeError("boom")

    r = safe_audit(_BadIter())
    assert r.verdict == VERDICT_RED
    assert any("audit raised" in x for x in r.verdict_reasons)


# ---------------------------------------------------------------------------
# 9. Behavior invariance (source-text)
# ---------------------------------------------------------------------------


_SERVICES = pathlib.Path(__file__).resolve().parent.parent / "services"


def test_audit_does_not_modify_runtime_files():
    # No runtime .py file imports / executes the audit module.
    # Allowed references: docstring / commentary mentions in
    # downstream dry-run-only modules (e.g. the 0-9R-IMPL-DRY consumer
    # mentions the audit verdict labels in its module docstring) — but
    # never an actual import line.
    for path in _SERVICES.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if (
                stripped.startswith("from zangetsu.tools.profile_attribution_audit")
                or stripped.startswith("import zangetsu.tools.profile_attribution_audit")
            ):
                pytest.fail(
                    f"{path.name} unexpectedly imports profile_attribution_audit"
                )


def test_no_threshold_constants_changed():
    a23 = (_SERVICES / "arena23_orchestrator.py").read_text(encoding="utf-8")
    assert "bt.total_trades < 25" in a23  # A2_MIN_TRADES preserved
    assert "ATR_STOP_MULTS = [2.0, 3.0, 4.0]" in a23
    assert "TRAIL_PCTS = [0.003, 0.005, 0.008, 0.01, 0.015, 0.02]" in a23
    assert "FIXED_TARGETS = [0.005, 0.008, 0.01, 0.015, 0.02, 0.03]" in a23


def test_arena_pass_fail_unchanged():
    from zangetsu.services import arena_gates
    for fn in ("arena2_pass", "arena3_pass", "arena4_pass"):
        assert hasattr(arena_gates, fn)


def test_champion_promotion_unchanged():
    a45 = (_SERVICES / "arena45_orchestrator.py").read_text(encoding="utf-8")
    assert a45.count("UPDATE champion_pipeline_fresh SET status = 'DEPLOYABLE'") == 1


def test_audit_module_has_no_apply_method():
    import zangetsu.tools.profile_attribution_audit as mod
    publics = [n for n in dir(mod) if not n.startswith("_")]
    for name in publics:
        assert not name.lower().startswith("apply"), (
            f"audit module exports apply-shaped name {name!r}"
        )
