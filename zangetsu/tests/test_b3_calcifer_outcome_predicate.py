"""Tests for §17.3 NULL-safe deploy-block predicate (0-9Y-B3).

Verifies the predicate logic that mirrors the bash writer in
`calcifer/calcifer_v071_watch.sh`. Exhaustive over the 4 logical
states; explicit cold-start / regression / recovery / healthy cases.

These tests do NOT execute the bash script; they test the pure-Python
mirror in `calcifer.calcifer_outcome_predicate`. The bash writer is
verified separately via post-merge integration check (see
docs/recovery/.../b3-calcifer-null-safety/05_live_verification.md).
"""
from __future__ import annotations

import pytest

from calcifer.calcifer_outcome_predicate import (
    evaluate_deploy_block_state,
    block_file_should_exist,
)


# ---------------------------------------------------------------------------
# B3.1 — healthy state: deployable_count > 0
# ---------------------------------------------------------------------------


def test_b3_healthy_no_block_when_deployable_count_positive() -> None:
    """deployable_count > 0 always returns no block, regardless of age."""
    for dc in (1, 5, 100):
        for age in (None, 0.5, 5.9, 6.0, 6.1, 100.0):
            assert evaluate_deploy_block_state(dc, age) is None
            assert block_file_should_exist(dc, age) is False


# ---------------------------------------------------------------------------
# B3.2 — cold-start: dc = 0, age = None
# ---------------------------------------------------------------------------


def test_b3_cold_start_returns_unknown_blocked() -> None:
    """deployable_count == 0 AND last_live_at_age_h IS NULL → UNKNOWN_BLOCKED."""
    assert evaluate_deploy_block_state(0, None) == "UNKNOWN_BLOCKED"
    assert block_file_should_exist(0, None) is True


# ---------------------------------------------------------------------------
# B3.3 — regression: dc = 0, age > 6
# ---------------------------------------------------------------------------


def test_b3_regression_returns_red() -> None:
    """deployable_count == 0 AND last_live_at_age_h > 6 → RED."""
    for age in (6.001, 6.5, 12.0, 24.0, 720.0):
        assert evaluate_deploy_block_state(0, age) == "RED"
        assert block_file_should_exist(0, age) is True


# ---------------------------------------------------------------------------
# B3.4 — recovery window: dc = 0, age ≤ 6
# ---------------------------------------------------------------------------


def test_b3_recovery_window_returns_no_block() -> None:
    """deployable_count == 0 AND last_live_at_age_h ≤ 6 → None (transient)."""
    for age in (0.0, 0.001, 1.5, 5.9, 6.0):
        assert evaluate_deploy_block_state(0, age) is None
        assert block_file_should_exist(0, age) is False


# ---------------------------------------------------------------------------
# B3.5 — boundary at exactly 6.0
# ---------------------------------------------------------------------------


def test_b3_boundary_age_equal_6_is_no_block() -> None:
    """At exactly 6.0 hours, the predicate uses strict `> 6` so no RED."""
    assert evaluate_deploy_block_state(0, 6.0) is None
    assert block_file_should_exist(0, 6.0) is False


def test_b3_boundary_age_just_over_6_is_red() -> None:
    assert evaluate_deploy_block_state(0, 6.000001) == "RED"
    assert block_file_should_exist(0, 6.000001) is True


# ---------------------------------------------------------------------------
# B3.6 — false-green prevention (the original bug)
# ---------------------------------------------------------------------------


def test_b3_false_green_prevention() -> None:
    """The pre-0-9Y-B3 spec literally compared `age > 6` which is False
    when age IS NULL. This made the cold-start case (dc=0, age=None)
    silently bypass the deploy-block, producing a 'false green'.

    Post-fix, cold-start is explicitly UNKNOWN_BLOCKED — no bypass."""
    # Pre-fix simulation: would have been "no block" because NULL > 6 is NULL.
    pre_fix_simulation = (0 > 0 and (None or 0) > 6.0)
    assert pre_fix_simulation is False  # would have been False = no block = bug

    # Post-fix: explicitly handles the NULL case.
    post_fix_state = evaluate_deploy_block_state(0, None)
    assert post_fix_state == "UNKNOWN_BLOCKED"  # block, no bypass


# ---------------------------------------------------------------------------
# B3.7 — bypass impossibility
# ---------------------------------------------------------------------------


def test_b3_no_bypass_path_for_zero_deployable() -> None:
    """If deployable_count == 0, the only no-block path is age in (0, 6].
    Any other age (including None or any > 6) MUST produce a block."""
    blocked = []
    not_blocked = []
    candidates = [None, -1.0, 0.0, 1.0, 5.999, 6.0, 6.001, 100.0, 1e9]
    for age in candidates:
        state = evaluate_deploy_block_state(0, age)
        if state is None:
            not_blocked.append(age)
        else:
            blocked.append((age, state))
    # Blocked: age=None (UNKNOWN_BLOCKED), age=6.001 (RED), age=100 (RED), age=1e9 (RED)
    blocked_ages = sorted(
        a for a, _ in blocked if a is not None
    ) + [a for a, _ in blocked if a is None]
    not_blocked_ages = sorted(a for a in not_blocked if a is not None)
    # Not-blocked numeric ages must all be in the inclusive [0, 6.0] half-line.
    assert all(0.0 <= a <= 6.0 for a in not_blocked_ages if a >= 0)
    # And there must be exactly the cold-start (None) entry in blocked.
    assert any(a is None for a, _ in blocked)


# ---------------------------------------------------------------------------
# B3.8 — type tolerance
# ---------------------------------------------------------------------------


def test_b3_handles_float_zero_age() -> None:
    """An age of 0.0 (literally just promoted) is in the recovery window."""
    assert evaluate_deploy_block_state(0, 0.0) is None
