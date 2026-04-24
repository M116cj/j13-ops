"""Behavior invariance tests for P7-PR1 (zangetsu Arena).

Enforces the core P7-PR1 contract (0-9E §11):

    "P7-PR1 may add visibility.
     P7-PR1 must not change candidate survival outcome."

Strategy:
    1. Prove the three new modules (taxonomy, telemetry, candidate_trace)
       are PASSIVE: importing them does not import Arena runtime modules.
    2. Prove that Arena runtime thresholds declared in arena_gates.py
       (A2_MIN_TRADES, A3_MIN_TRADES_PER_SEGMENT, A3_MIN_WR_PASSES,
       A3_MIN_PNL_PASSES, A3_WR_FLOOR, A3_SEGMENTS) remain at the exact
       values committed in main @ 966cd593. Any change to these would
       indicate a threshold mutation — strictly forbidden by 0-9E §2 / §9.
    3. Prove that the decision path in arena_gates.arena2_pass() is
       unchanged for a deterministic test vector.

If any of these assertions fails, P7-PR1 has mutated decision behavior
and the PR must be rejected.
"""

from __future__ import annotations

import importlib
import sys

import pytest


# ---------------------------------------------------------------------------
# 1. New modules must be PASSIVE (do not import Arena runtime as side effect)
# ---------------------------------------------------------------------------


def _fresh_import(modname: str):
    """Force a clean import of a module (removes cached entry first)."""
    sys.modules.pop(modname, None)
    return importlib.import_module(modname)


def test_taxonomy_import_does_not_pull_arena_runtime():
    # Clear any Arena modules that may have been imported by earlier tests.
    before = set(m for m in sys.modules if m.startswith("zangetsu.services.arena_"))
    for m in list(before):
        # Only purge the runtime modules; keep our own (they don't import runtime).
        if m not in {
            "zangetsu.services.arena_rejection_taxonomy",
            "zangetsu.services.arena_telemetry",
        }:
            sys.modules.pop(m, None)
    _fresh_import("zangetsu.services.arena_rejection_taxonomy")
    # Check: arena_pipeline / arena23_orchestrator / arena13_feedback must NOT
    # have been imported as a side effect.
    assert "zangetsu.services.arena_pipeline" not in sys.modules
    assert "zangetsu.services.arena23_orchestrator" not in sys.modules
    assert "zangetsu.services.arena13_feedback" not in sys.modules


def test_telemetry_import_does_not_pull_arena_runtime():
    for m in list(sys.modules):
        if m.startswith("zangetsu.services.arena_") and m not in {
            "zangetsu.services.arena_rejection_taxonomy",
            "zangetsu.services.arena_telemetry",
        }:
            sys.modules.pop(m, None)
    _fresh_import("zangetsu.services.arena_telemetry")
    assert "zangetsu.services.arena_pipeline" not in sys.modules
    assert "zangetsu.services.arena23_orchestrator" not in sys.modules
    assert "zangetsu.services.arena13_feedback" not in sys.modules
    assert "zangetsu.services.arena45_orchestrator" not in sys.modules


def test_candidate_trace_import_does_not_pull_arena_runtime():
    for m in list(sys.modules):
        if m.startswith("zangetsu.services.arena_") and m != "zangetsu.services.candidate_trace":
            sys.modules.pop(m, None)
    _fresh_import("zangetsu.services.candidate_trace")
    assert "zangetsu.services.arena_pipeline" not in sys.modules
    assert "zangetsu.services.arena23_orchestrator" not in sys.modules
    assert "zangetsu.services.arena13_feedback" not in sys.modules


# ---------------------------------------------------------------------------
# 2. Arena runtime thresholds unchanged (compare to main @ 966cd593 values)
# ---------------------------------------------------------------------------

# These values are pinned from arena_gates.py as committed in main @ 966cd593.
# Changing these values is explicitly forbidden by 0-9E §9 / §18.13.
PINNED_THRESHOLDS = {
    "A2_MIN_TRADES": 25,
    "A3_SEGMENTS": 5,
    "A3_MIN_TRADES_PER_SEGMENT": 15,
    "A3_MIN_WR_PASSES": 4,
    "A3_MIN_PNL_PASSES": 4,
    "A3_WR_FLOOR": 0.45,
}


def test_arena_gates_thresholds_unchanged():
    """Arena gate thresholds must equal the values committed in main @ 966cd593."""
    ag = importlib.import_module("zangetsu.services.arena_gates")
    for name, expected in PINNED_THRESHOLDS.items():
        actual = getattr(ag, name, None)
        assert actual is not None, f"arena_gates.{name} missing — forbidden structural change"
        assert actual == expected, (
            f"arena_gates.{name} changed from pinned {expected!r} to {actual!r}; "
            "this is a forbidden threshold mutation under 0-9E §9."
        )


# ---------------------------------------------------------------------------
# 3. Decision behavior on a deterministic vector is unchanged
# ---------------------------------------------------------------------------


def _mk_trade(pnl: float, i: int):
    from zangetsu.services.arena_gates import Trade
    return Trade(pnl=pnl, entry_idx=i, exit_idx=i + 1)


def test_arena2_pass_rejects_under_min_trades():
    from zangetsu.services.arena_gates import arena2_pass, A2_MIN_TRADES

    trades = [_mk_trade(1.0, i) for i in range(A2_MIN_TRADES - 1)]
    r = arena2_pass(trades)
    assert r.passed is False
    assert r.reason == "too_few_trades"


def test_arena2_pass_rejects_non_positive_pnl():
    from zangetsu.services.arena_gates import arena2_pass, A2_MIN_TRADES

    # Exactly A2_MIN_TRADES trades, total PnL = 0 → non_positive_pnl reject.
    trades = [_mk_trade(0.0, i) for i in range(A2_MIN_TRADES)]
    r = arena2_pass(trades)
    assert r.passed is False
    assert r.reason == "non_positive_pnl"


def test_arena2_pass_accepts_on_edge_of_minimum():
    from zangetsu.services.arena_gates import arena2_pass, A2_MIN_TRADES

    # Exactly A2_MIN_TRADES trades, strictly positive PnL → PASS.
    trades = [_mk_trade(0.01, i) for i in range(A2_MIN_TRADES)]
    r = arena2_pass(trades)
    assert r.passed is True
    assert r.reason == "ok"


# ---------------------------------------------------------------------------
# 4. Taxonomy classifier maps existing reason strings exactly as Arena emits them
# ---------------------------------------------------------------------------


def test_classifier_recognizes_all_arena_gates_emitted_reasons():
    """If taxonomy diverges from arena_gates runtime strings, behavior invariance is at risk."""
    from zangetsu.services.arena_gates import arena2_pass
    from zangetsu.services.arena_rejection_taxonomy import RAW_TO_REASON, classify

    # Produce each possible arena2 reject reason and verify classifier maps it.
    few = [_mk_trade(1.0, i) for i in range(1)]
    r1 = arena2_pass(few)
    assert r1.reason in RAW_TO_REASON, f"arena_gates emits {r1.reason!r} but taxonomy missing"
    classified_reason, _, _ = classify(raw_reason=r1.reason, arena_stage="A2")
    assert classified_reason.value != "UNKNOWN_REJECT", (
        f"Classifier falls back to UNKNOWN for known arena_gates reason {r1.reason!r}"
    )

    zero = [_mk_trade(0.0, i) for i in range(25)]
    r2 = arena2_pass(zero)
    assert r2.reason in RAW_TO_REASON
    classified_reason, _, _ = classify(raw_reason=r2.reason, arena_stage="A2")
    assert classified_reason.value != "UNKNOWN_REJECT"


# ---------------------------------------------------------------------------
# 5. Module file count invariant (no Arena runtime file added/removed)
# ---------------------------------------------------------------------------


def test_no_arena_runtime_file_added_or_removed():
    """P7-PR1 must add only the three new telemetry modules to zangetsu/services/,
    not modify or remove any existing Arena runtime module.

    This test does not have access to the pre-commit state directly, but we can
    assert that the expected Arena runtime module list is present (catches a
    destructive removal) and that our three new modules are present (catches
    an incomplete commit). A separate controlled-diff check enforces the
    additive-only invariant at repo level.
    """
    required_runtime = [
        "zangetsu.services.arena_gates",
        "zangetsu.services.arena_pipeline",
        "zangetsu.services.arena13_feedback",
        "zangetsu.services.arena23_orchestrator",
        "zangetsu.services.arena45_orchestrator",
    ]
    for mod in required_runtime:
        assert importlib.util.find_spec(mod) is not None, (
            f"Arena runtime module {mod} missing — possible destructive change."
        )

    required_new = [
        "zangetsu.services.arena_rejection_taxonomy",
        "zangetsu.services.arena_telemetry",
        "zangetsu.services.candidate_trace",
    ]
    for mod in required_new:
        assert importlib.util.find_spec(mod) is not None, (
            f"P7-PR1 new module {mod} missing — incomplete commit."
        )
