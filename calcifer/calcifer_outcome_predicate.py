"""§17.3 deploy-block predicate — NULL-safe (0-9Y-B3).

Pure helper that mirrors the bash predicate in
`calcifer/calcifer_v071_watch.sh` so the logic is unit-testable.

The bash script is the canonical writer (Calcifer v0.7.1 cron job runs it
every 15 min). This module exists as a single-source-of-truth for the
predicate semantics and is imported only by the test suite.

Semantics (post-0-9Y-B3):

    deployable_count > 0
        → no deploy-block (commit allowed)
    deployable_count == 0 AND last_live_at_age_h IS NULL
        → UNKNOWN_BLOCKED (cold-start: no live champion ever)
    deployable_count == 0 AND last_live_at_age_h > 6
        → RED (regression: had live champion >6h ago)
    deployable_count == 0 AND last_live_at_age_h ≤ 6
        → no deploy-block (recovery window; transient)

Both RED and UNKNOWN_BLOCKED block `feat(<proj>/vN)` commits per
§17.3 enforcement. The distinction is informational only.
"""
from __future__ import annotations

from typing import Optional


def evaluate_deploy_block_state(
    deployable_count: int,
    last_live_at_age_h: Optional[float],
) -> Optional[str]:
    """Return the deploy-block status string, or None if no block.

    Args:
        deployable_count: integer ≥ 0 read from `zangetsu_status.deployable_count`
        last_live_at_age_h: float > 0 OR None — read from `zangetsu_status.last_live_at_age_h`

    Returns:
        "UNKNOWN_BLOCKED" if cold-start (dc=0, age=None)
        "RED" if regression (dc=0, age>6)
        None if no block (dc>0, OR dc=0 with age<=6)
    """
    if deployable_count > 0:
        return None
    if last_live_at_age_h is None:
        return "UNKNOWN_BLOCKED"
    if last_live_at_age_h > 6.0:
        return "RED"
    return None


def block_file_should_exist(
    deployable_count: int,
    last_live_at_age_h: Optional[float],
) -> bool:
    """Convenience: True iff /tmp/calcifer_deploy_block.json should exist."""
    return evaluate_deploy_block_state(deployable_count, last_live_at_age_h) is not None
