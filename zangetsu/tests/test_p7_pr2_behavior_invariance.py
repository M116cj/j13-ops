"""Behavior invariance tests for P7-PR2 (0-9K).

Enforces the core P7-PR2 contract: the lifecycle reconstruction + deployable_count
provenance module must be PASSIVE — no Arena runtime module is pulled as an
import side effect, Arena thresholds remain pinned, and the Arena decision
path continues to produce identical outcomes for edge inputs.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys

import pytest


def _fresh_import(modname: str):
    sys.modules.pop(modname, None)
    return importlib.import_module(modname)


# ---------------------------------------------------------------------------
# 1. New 0-9K modules must not pull Arena runtime
# ---------------------------------------------------------------------------


def _purge_arena_runtime_imports():
    for m in list(sys.modules):
        if m.startswith("zangetsu.services.arena_") and m not in {
            "zangetsu.services.arena_rejection_taxonomy",
            "zangetsu.services.arena_telemetry",
        }:
            sys.modules.pop(m, None)


def test_reconstruction_import_does_not_pull_arena_runtime():
    _purge_arena_runtime_imports()
    _fresh_import("zangetsu.services.candidate_lifecycle_reconstruction")
    for forbidden in (
        "zangetsu.services.arena_pipeline",
        "zangetsu.services.arena23_orchestrator",
        "zangetsu.services.arena45_orchestrator",
        "zangetsu.services.arena13_feedback",
    ):
        assert forbidden not in sys.modules, (
            f"0-9K reconstruction module pulled Arena runtime: {forbidden}"
        )


def test_candidate_trace_extension_does_not_pull_arena_runtime():
    _purge_arena_runtime_imports()
    _fresh_import("zangetsu.services.candidate_trace")
    for forbidden in (
        "zangetsu.services.arena_pipeline",
        "zangetsu.services.arena23_orchestrator",
        "zangetsu.services.arena45_orchestrator",
        "zangetsu.services.arena13_feedback",
    ):
        assert forbidden not in sys.modules


# ---------------------------------------------------------------------------
# 2. Arena gate thresholds unchanged — same pin as P7-PR1 behavior invariance
# ---------------------------------------------------------------------------

PINNED_THRESHOLDS = {
    "A2_MIN_TRADES": 25,
    "A3_SEGMENTS": 5,
    "A3_MIN_TRADES_PER_SEGMENT": 15,
    "A3_MIN_WR_PASSES": 4,
    "A3_MIN_PNL_PASSES": 4,
    "A3_WR_FLOOR": 0.45,
}


def test_arena_gates_thresholds_still_pinned_under_p7_pr2():
    ag = importlib.import_module("zangetsu.services.arena_gates")
    for name, expected in PINNED_THRESHOLDS.items():
        actual = getattr(ag, name, None)
        assert actual == expected, (
            f"{name} changed from {expected!r} to {actual!r} — "
            "P7-PR2 must not mutate thresholds (0-9K §17)."
        )


# ---------------------------------------------------------------------------
# 3. arena2_pass decision path unchanged
# ---------------------------------------------------------------------------


def _mk_trade(pnl: float, i: int):
    from zangetsu.services.arena_gates import Trade
    return Trade(pnl=pnl, entry_idx=i, exit_idx=i + 1)


def test_arena2_pass_behavior_unchanged_too_few_trades():
    from zangetsu.services.arena_gates import arena2_pass, A2_MIN_TRADES
    r = arena2_pass([_mk_trade(1.0, i) for i in range(A2_MIN_TRADES - 1)])
    assert r.passed is False
    assert r.reason == "too_few_trades"


def test_arena2_pass_behavior_unchanged_non_positive_pnl():
    from zangetsu.services.arena_gates import arena2_pass, A2_MIN_TRADES
    r = arena2_pass([_mk_trade(0.0, i) for i in range(A2_MIN_TRADES)])
    assert r.passed is False
    assert r.reason == "non_positive_pnl"


def test_arena2_pass_behavior_unchanged_edge_accept():
    from zangetsu.services.arena_gates import arena2_pass, A2_MIN_TRADES
    r = arena2_pass([_mk_trade(0.01, i) for i in range(A2_MIN_TRADES)])
    assert r.passed is True
    assert r.reason == "ok"


# ---------------------------------------------------------------------------
# 4. Required modules present
# ---------------------------------------------------------------------------


def test_no_arena_runtime_file_added_or_removed_under_0_9k():
    """All Arena runtime modules still exist; P7-PR2 only added new modules."""
    required_runtime = [
        "zangetsu.services.arena_gates",
        "zangetsu.services.arena_pipeline",
        "zangetsu.services.arena13_feedback",
        "zangetsu.services.arena23_orchestrator",
        "zangetsu.services.arena45_orchestrator",
    ]
    for mod in required_runtime:
        assert importlib.util.find_spec(mod) is not None

    required_p7_pr1 = [
        "zangetsu.services.arena_rejection_taxonomy",
        "zangetsu.services.arena_telemetry",
        "zangetsu.services.candidate_trace",
    ]
    for mod in required_p7_pr1:
        assert importlib.util.find_spec(mod) is not None

    required_p7_pr2 = [
        "zangetsu.services.candidate_lifecycle_reconstruction",
    ]
    for mod in required_p7_pr2:
        assert importlib.util.find_spec(mod) is not None


# ---------------------------------------------------------------------------
# 5. CandidateLifecycle additions are backward-compatible with P7-PR1 usage
# ---------------------------------------------------------------------------


def test_candidate_lifecycle_minimum_construction_still_works():
    """P7-PR1 tests construct CandidateLifecycle with only a few fields.
    The 0-9K extensions MUST NOT break that minimal-construction pattern."""
    from zangetsu.services.candidate_trace import CandidateLifecycle, STATUS_PASS
    lc = CandidateLifecycle(candidate_id="x")
    assert lc.candidate_id == "x"
    # New fields all have safe defaults
    assert lc.deployable_count_contribution == 0
    assert lc.provenance_quality == "UNAVAILABLE"
    assert lc.missing_fields == []

    # Full-pass construction (as used by P7-PR1 tests) still deployable
    lc2 = CandidateLifecycle(
        candidate_id="y",
        arena_0_status=STATUS_PASS,
        arena_1_status=STATUS_PASS,
        arena_2_status=STATUS_PASS,
        arena_3_status=STATUS_PASS,
    )
    assert lc2.is_deployable() is True


def test_p7_pr1_derive_deployable_count_function_still_works():
    """The original P7-PR1 derive_deployable_count() must continue to work
    (it coexists with the new 0-9K derive_deployable_count_with_provenance())."""
    from zangetsu.services.candidate_trace import (
        CandidateLifecycle,
        STATUS_PASS,
        STATUS_REJECT,
        derive_deployable_count,
    )
    lcs = [
        CandidateLifecycle(
            candidate_id="p",
            arena_0_status=STATUS_PASS,
            arena_1_status=STATUS_PASS,
            arena_2_status=STATUS_PASS,
            arena_3_status=STATUS_PASS,
        ),
        CandidateLifecycle(
            candidate_id="r",
            arena_2_status=STATUS_REJECT,
            reject_stage="A2",
            reject_reason="OOS_FAIL",
        ),
    ]
    r = derive_deployable_count(lcs)
    assert r["deployable_count"] == 1
    assert r["total_candidates"] == 2
