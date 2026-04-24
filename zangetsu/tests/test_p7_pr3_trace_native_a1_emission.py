"""Tests for A1 trace-native emission (0-9L §13.2).

The arena_pipeline.py emits 3 A1 events (ENTRY / EXIT_REJECT / EXIT_PASS+HANDOFF)
via a small exception-safe helper. These tests exercise the helper contract
without invoking the full production arena_pipeline (which requires a DB +
data cache + many env vars). The helper is what guarantees behavior invariance.
"""

from __future__ import annotations

import json

import pytest

from zangetsu.services.candidate_trace import (
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
    build_lifecycle_trace_event,
    emit_lifecycle_trace_event,
    parse_lifecycle_trace_event,
)


def test_a1_entry_event_contains_candidate_id_via_alpha_hash():
    ev = build_lifecycle_trace_event(
        arena_stage="A1", stage_event=STAGE_EVENT_ENTRY, status=STATUS_ENTERED,
        candidate_id="ah_c0ffee", alpha_id="ah_c0ffee", formula_hash="ah_c0ffee",
        source_pool="BTCUSDT",
    )
    assert ev.candidate_id == "ah_c0ffee"
    assert ev.alpha_id == "ah_c0ffee"
    assert ev.formula_hash == "ah_c0ffee"


def test_a1_entry_event_supports_alpha_id_when_available():
    ev = build_lifecycle_trace_event(
        arena_stage="A1", stage_event=STAGE_EVENT_ENTRY, status=STATUS_ENTERED,
        alpha_id="alpha-42",
    )
    assert ev.alpha_id == "alpha-42"


def test_a1_entry_event_supports_formula_hash_when_available():
    ev = build_lifecycle_trace_event(
        arena_stage="A1", stage_event=STAGE_EVENT_ENTRY, status=STATUS_ENTERED,
        formula_hash="fh_1234",
    )
    assert ev.formula_hash == "fh_1234"


def test_a1_entry_has_arena_stage_a1():
    ev = build_lifecycle_trace_event(
        arena_stage="A1", stage_event=STAGE_EVENT_ENTRY, status=STATUS_ENTERED,
    )
    assert ev.arena_stage == "A1"
    assert ev.stage_event == STAGE_EVENT_ENTRY


def test_a1_exit_pass_creates_status_passed():
    ev = build_lifecycle_trace_event(
        arena_stage="A1", stage_event=STAGE_EVENT_EXIT, status=STATUS_PASSED,
        alpha_id="x",
    )
    assert ev.stage_event == STAGE_EVENT_EXIT
    assert ev.status == STATUS_PASSED


def test_a1_exit_reject_creates_status_rejected():
    ev = build_lifecycle_trace_event(
        arena_stage="A1", stage_event=STAGE_EVENT_EXIT, status=STATUS_REJECTED,
        alpha_id="x", reject_reason="SIGNAL_TOO_SPARSE",
    )
    assert ev.stage_event == STAGE_EVENT_EXIT
    assert ev.status == STATUS_REJECTED


def test_a1_exit_reject_carries_reject_reason_when_available():
    ev = build_lifecycle_trace_event(
        arena_stage="A1", stage_event=STAGE_EVENT_EXIT, status=STATUS_REJECTED,
        alpha_id="x", reject_reason="SIGNAL_TOO_SPARSE",
    )
    assert ev.reject_reason == "SIGNAL_TOO_SPARSE"


def test_a1_handoff_to_a2_creates_next_stage_a2():
    ev = build_lifecycle_trace_event(
        arena_stage="A1", stage_event=STAGE_EVENT_HANDOFF, status=STATUS_PASSED,
        alpha_id="x", next_stage="A2",
    )
    assert ev.stage_event == STAGE_EVENT_HANDOFF
    assert ev.next_stage == "A2"


def test_a1_exit_skip_does_not_carry_reject_reason():
    """A1_EXIT_SKIP is distinct from REJECT — no reject_reason by default."""
    ev = build_lifecycle_trace_event(
        arena_stage="A1", stage_event=STAGE_EVENT_SKIP, status=STATUS_SKIPPED,
        alpha_id="x",
    )
    assert ev.status == STATUS_SKIPPED
    assert ev.reject_reason is None


def test_a1_exit_error_event_constructible():
    ev = build_lifecycle_trace_event(
        arena_stage="A1", stage_event=STAGE_EVENT_ERROR, status=STATUS_ERROR,
        alpha_id="x", notes="alpha compile failed: SyntaxError",
    )
    assert ev.status == STATUS_ERROR
    assert ev.notes.startswith("alpha compile failed")


def test_helper_wraps_emission_and_survives_logger_failure():
    """Confirm that an emitter used via a callback (like log.info) never
    propagates exceptions back to caller. This is the contract the
    `_emit_a1_lifecycle_safe()` helper in arena_pipeline.py relies on."""

    # Simulate a logger.info that raises
    def bad_logger(s):
        raise RuntimeError("disk full")

    ev = build_lifecycle_trace_event(
        arena_stage="A1", stage_event=STAGE_EVENT_ENTRY, status=STATUS_ENTERED,
    )
    # emit_lifecycle_trace_event must return False, not raise.
    result = emit_lifecycle_trace_event(ev, writer=bad_logger)
    assert result is False


def test_a1_emission_round_trip_via_parser():
    """An emitted A1 event must parse back to an equivalent event."""
    captured: list = []
    ev = build_lifecycle_trace_event(
        arena_stage="A1", stage_event=STAGE_EVENT_HANDOFF, status=STATUS_PASSED,
        alpha_id="ah_abc123", formula_hash="ah_abc123", source_pool="ETHUSDT",
        next_stage="A2",
    )
    emit_lifecycle_trace_event(ev, writer=captured.append)
    assert len(captured) == 1
    back = parse_lifecycle_trace_event(captured[0])
    assert back is not None
    assert back.arena_stage == "A1"
    assert back.stage_event == STAGE_EVENT_HANDOFF
    assert back.next_stage == "A2"
    assert back.alpha_id == "ah_abc123"


def test_emission_schema_present_in_arena_pipeline_module():
    """Sanity check: arena_pipeline.py imports the trace contract helpers
    AND exposes the _emit_a1_lifecycle_safe helper. Touching that helper
    is the concrete P7-PR3 runtime integration point."""
    import importlib
    arena_pipeline = importlib.import_module("zangetsu.services.arena_pipeline")
    assert hasattr(arena_pipeline, "_emit_a1_lifecycle_safe")
    assert getattr(arena_pipeline, "_LIFECYCLE_TRACE_AVAILABLE", False) is True


def test_emit_a1_helper_is_exception_safe_when_no_log():
    """The arena_pipeline helper accepts log=None and must not raise."""
    import importlib
    arena_pipeline = importlib.import_module("zangetsu.services.arena_pipeline")
    # Should complete silently with no log object.
    arena_pipeline._emit_a1_lifecycle_safe(
        stage_event="ENTRY", status="ENTERED",
        alpha_hash="xxx", source_pool="BTC", log=None,
    )


def test_emit_a1_helper_is_exception_safe_when_log_raises():
    import importlib
    arena_pipeline = importlib.import_module("zangetsu.services.arena_pipeline")

    class _BadLog:
        def info(self, s):
            raise RuntimeError("logger dead")

    # Must not raise
    arena_pipeline._emit_a1_lifecycle_safe(
        stage_event="ENTRY", status="ENTERED",
        alpha_hash="xxx", source_pool="BTC", log=_BadLog(),
    )
