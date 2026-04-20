"""Canonical list of applied patches — written to every alpha's provenance.

Order matters (chronological). Any patch applied to the GP engine / arena
gates / backtester / indicator_cache layer MUST be appended here in the
same PR that introduces the change. Pre-commit hook verifies that any
code change touching `zangetsu/engine/`, `zangetsu/services/arena_gates.py`,
or the DB migration schema includes an append here.

Downstream: the `patches_applied` column on every fresh / staging row
is set to this list at worker startup. Data science queries can then
filter alphas by what patch regime they were produced under.

Do NOT remove entries. Deprecated patches get a trailing `@deprecated`
token — they are never deleted from history.
"""
from __future__ import annotations

PATCHES_APPLIED: list[str] = [
    # 2026-04-19: indicator cache injection in orchestrator singleton engine
    "F_prime_indicator_cache",
    # 2026-04-20: forward-return horizon aligned to alpha_signal.min_hold
    "G_60bar_horizon",
    # 2026-04-20: narrowed bare except in arena13_feedback
    "C3_narrow_except",
    # 2026-04-20: arena45 DSR gate removed; fitness injected via strategy project
    "v0_7_0_engine_split",
    # 2026-04-20: strategy_id + deployable_tier + 3 per-strategy VIEWs
    "v0_7_0_strategy_id_migration",
    # 2026-04-20: governance upgrade — physical split + staging + provenance
    "v0_7_1_governance",
]


def patches_fingerprint() -> str:
    """Return a short hash of the current patches list.

    Used as an integrity check so provenance rows can be audited for
    consistency with the worker's code at INSERT time.
    """
    import hashlib
    return hashlib.sha256(
        "\n".join(PATCHES_APPLIED).encode("utf-8")
    ).hexdigest()[:16]
