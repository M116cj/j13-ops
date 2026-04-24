"""Tests for the LifecycleTraceEvent contract (0-9L §13.1)."""

from __future__ import annotations

import io
import json

import pytest

from zangetsu.services.candidate_trace import (
    EVENT_TYPE_CANDIDATE_LIFECYCLE,
    LifecycleTraceEvent,
    STAGE_EVENT_ENTRY,
    STAGE_EVENT_EXIT,
    STAGE_EVENT_HANDOFF,
    STAGE_EVENT_SKIP,
    STAGE_EVENT_ERROR,
    STATUS_ENTERED,
    STATUS_PASSED,
    STATUS_REJECTED,
    STATUS_SKIPPED,
    STATUS_ERROR,
    STATUS_COMPLETE,
    build_lifecycle_trace_event,
    emit_lifecycle_trace_event,
    parse_lifecycle_trace_event,
    valid_lifecycle_statuses,
    valid_stage_events,
    valid_trace_stages,
)


def test_event_type_constant_stable():
    assert EVENT_TYPE_CANDIDATE_LIFECYCLE == "candidate_lifecycle"


def test_stage_event_vocabulary_complete():
    assert set(valid_stage_events()) == {
        "ENTRY", "EXIT", "HANDOFF", "SKIP", "ERROR"
    }


def test_lifecycle_status_vocabulary_complete():
    assert set(valid_lifecycle_statuses()) == {
        "ENTERED", "PASSED", "REJECTED", "SKIPPED", "ERROR", "COMPLETE"
    }


def test_trace_stage_vocabulary_supports_A1_to_A5():
    stages = set(valid_trace_stages())
    for s in ("A0", "A1", "A2", "A3", "A4", "A5", "UNKNOWN"):
        assert s in stages


def test_builder_validates_required_event_type_implicit():
    # Builder always sets event_type to the canonical marker.
    ev = build_lifecycle_trace_event(
        arena_stage="A1", stage_event=STAGE_EVENT_ENTRY, status=STATUS_ENTERED,
    )
    assert ev.event_type == EVENT_TYPE_CANDIDATE_LIFECYCLE


def test_builder_rejects_invalid_arena_stage():
    with pytest.raises(ValueError):
        build_lifecycle_trace_event(
            arena_stage="A99", stage_event=STAGE_EVENT_ENTRY, status=STATUS_ENTERED
        )


def test_builder_rejects_invalid_stage_event():
    with pytest.raises(ValueError):
        build_lifecycle_trace_event(
            arena_stage="A1", stage_event="BOGUS", status=STATUS_ENTERED
        )


def test_builder_rejects_invalid_status():
    with pytest.raises(ValueError):
        build_lifecycle_trace_event(
            arena_stage="A1", stage_event=STAGE_EVENT_ENTRY, status="NOPE"
        )


def test_builder_autofills_timestamp_when_absent():
    ev = build_lifecycle_trace_event(
        arena_stage="A1", stage_event=STAGE_EVENT_ENTRY, status=STATUS_ENTERED,
    )
    assert ev.timestamp_utc
    # RFC3339-ish
    assert "T" in ev.timestamp_utc and ev.timestamp_utc.endswith("Z")


def test_event_to_dict_is_json_compatible():
    ev = build_lifecycle_trace_event(
        arena_stage="A1", stage_event=STAGE_EVENT_EXIT, status=STATUS_PASSED,
        candidate_id="abc123", alpha_id="abc123", formula_hash="abc123",
        source_pool="BTCUSDT",
    )
    d = ev.to_dict()
    # Must round-trip via json
    s = json.dumps(d)
    back = json.loads(s)
    assert back["event_type"] == EVENT_TYPE_CANDIDATE_LIFECYCLE
    assert back["arena_stage"] == "A1"


def test_event_to_json_serialization():
    ev = build_lifecycle_trace_event(
        arena_stage="A1", stage_event=STAGE_EVENT_ENTRY, status=STATUS_ENTERED,
        alpha_id="x", formula_hash="x",
    )
    s = ev.to_json()
    assert json.loads(s)["arena_stage"] == "A1"


def test_builder_supports_extras():
    ev = build_lifecycle_trace_event(
        arena_stage="A1", stage_event=STAGE_EVENT_ENTRY, status=STATUS_ENTERED,
        extras={"custom_a": 1, "custom_b": "hello"},
    )
    d = ev.to_dict()
    assert d["custom_a"] == 1
    assert d["custom_b"] == "hello"


def test_builder_supports_candidate_id_when_available():
    ev = build_lifecycle_trace_event(
        arena_stage="A2", stage_event=STAGE_EVENT_ENTRY, status=STATUS_ENTERED,
        candidate_id="70381",
    )
    assert ev.candidate_id == "70381"


def test_parser_accepts_valid_event_dict():
    ev = build_lifecycle_trace_event(
        arena_stage="A1", stage_event=STAGE_EVENT_ENTRY, status=STATUS_ENTERED,
    )
    parsed = parse_lifecycle_trace_event(ev.to_dict())
    assert parsed is not None
    assert parsed.arena_stage == "A1"


def test_parser_accepts_json_string_input():
    ev = build_lifecycle_trace_event(
        arena_stage="A3", stage_event=STAGE_EVENT_EXIT, status=STATUS_COMPLETE,
    )
    s = ev.to_json()
    parsed = parse_lifecycle_trace_event(s)
    assert parsed is not None
    assert parsed.status == STATUS_COMPLETE


def test_parser_tolerates_extra_fields_stored_as_extras():
    raw = {
        "event_type": EVENT_TYPE_CANDIDATE_LIFECYCLE,
        "arena_stage": "A1",
        "stage_event": STAGE_EVENT_ENTRY,
        "status": STATUS_ENTERED,
        "timestamp_utc": "2026-04-24T00:00:00Z",
        "future_field_42": "ok",
    }
    parsed = parse_lifecycle_trace_event(raw)
    assert parsed is not None
    assert parsed.extras["future_field_42"] == "ok"


def test_parser_rejects_wrong_event_type():
    raw = {"event_type": "not_lifecycle", "arena_stage": "A1",
           "stage_event": STAGE_EVENT_ENTRY, "status": STATUS_ENTERED}
    assert parse_lifecycle_trace_event(raw) is None


def test_parser_rejects_malformed_dict():
    assert parse_lifecycle_trace_event({"event_type": "candidate_lifecycle"}) is None


def test_parser_rejects_unknown_stage():
    raw = {"event_type": EVENT_TYPE_CANDIDATE_LIFECYCLE, "arena_stage": "A99",
           "stage_event": STAGE_EVENT_ENTRY, "status": STATUS_ENTERED}
    assert parse_lifecycle_trace_event(raw) is None


def test_parser_rejects_broken_json_string_gracefully():
    assert parse_lifecycle_trace_event("not { valid json") is None
    assert parse_lifecycle_trace_event(None) is None


def test_emitter_non_blocking_on_writer_failure():
    """emit_lifecycle_trace_event must never raise even if writer raises."""
    def _raising_writer(s):
        raise RuntimeError("writer failure")
    ev = build_lifecycle_trace_event(
        arena_stage="A1", stage_event=STAGE_EVENT_ENTRY, status=STATUS_ENTERED,
    )
    result = emit_lifecycle_trace_event(ev, writer=_raising_writer)
    assert result is False  # emission failed
    # Test passes by not propagating the exception.


def test_emitter_returns_true_on_clean_write():
    captured: list = []
    ev = build_lifecycle_trace_event(
        arena_stage="A1", stage_event=STAGE_EVENT_HANDOFF, status=STATUS_PASSED,
        next_stage="A2",
    )
    assert emit_lifecycle_trace_event(ev, writer=captured.append) is True
    assert len(captured) == 1
    d = json.loads(captured[0])
    assert d["next_stage"] == "A2"


def test_event_schema_supports_a1_through_a5_for_future_stages():
    """Demonstrate that the same contract can emit A2/A3/A4/A5 events."""
    for stage in ("A1", "A2", "A3", "A4", "A5"):
        ev = build_lifecycle_trace_event(
            arena_stage=stage, stage_event=STAGE_EVENT_ENTRY, status=STATUS_ENTERED,
        )
        assert ev.arena_stage == stage
