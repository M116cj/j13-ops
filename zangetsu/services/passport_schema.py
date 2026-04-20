"""passport_schema.py — single source of truth for V9/V10 champion passport dispatch.

Zangetsu champion rows carry a `passport` JSON blob and an `engine_hash` string.
Schema diverged V9 → V10:
  V9  : engine_hash ∈ {NULL, 'zv5_v9*'}, passport.arena1 has `configs` (list) + `config_hash`
  V10 : engine_hash starts with 'zv5_v10', passport.arena1 has `alpha_expression` (str) + `alpha_hash`

Downstream modules that consumed only V9 shape silently produced false-negatives
on V10 rows (2026-04-18 P0-G incident at arena45_orchestrator.py:L385; A13 feedback
query family; a45 run_elo_round / swiss_pair / Gate 5 dedup).

This module centralises dispatch so V11+ cannot silently regress. All new reads
of passport schema fields MUST go through these helpers. A grep-based lint
(see CI) forbids raw `engine_hash == 'zv9'` / `passport[...]['configs']` outside
this file.

Contract:
    is_v10(row_or_passport) -> bool
    get_alpha(passport)     -> dict | None   # see below
    get_dedup_key(passport) -> str           # non-empty, or raises ValueError

Q1 coverage:
  1. Input boundary  — None / missing keys / empty strings normalised.
  2. Silent failure  — get_dedup_key RAISES rather than returning "" (which
                       was the bug that let a45 swiss_pair skip V10 pairs).
  3. External dep    — pure dict access, no I/O.
  4. Concurrency     — stateless, no shared mutable state.
  5. Scope           — schema dispatch only; NO policy, NO SQL, NO logging.
"""
from __future__ import annotations

from typing import Any, Optional

V10_ENGINE_PREFIX = "zv5_v10"
V9_ENGINE_PREFIX = "zv5_v9"


def _engine_hash(obj: Any) -> str:
    """Normalise engine_hash read. Accepts either a DB row dict with
    engine_hash at top level, or a passport dict (which itself has no
    engine_hash — caller must pass the row).
    """
    if obj is None:
        return ""
    if isinstance(obj, dict):
        return str(obj.get("engine_hash") or "")
    return ""


def is_v10(row_or_passport: Any) -> bool:
    """True if the row's engine_hash starts with the V10 prefix.

    Accepts either a DB row (with engine_hash field) or a plain passport dict.
    For a bare passport dict, the decision falls back to checking whether
    arena1.alpha_expression is populated (structural heuristic), because a
    passport in isolation carries no engine_hash.
    """
    eh = _engine_hash(row_or_passport)
    if eh:
        return eh.startswith(V10_ENGINE_PREFIX)
    # fallback: inspect arena1 shape
    if isinstance(row_or_passport, dict):
        arena1 = row_or_passport.get("arena1", {}) or {}
        if isinstance(arena1, dict) and arena1.get("alpha_expression"):
            return True
    return False


def get_alpha(passport: Any) -> Optional[dict]:
    """Unified reader for the alpha-payload portion of a passport.

    Returns a dict describing the alpha:
        {"kind": "v10", "alpha_expression": str, "alpha_hash": str | None}
        {"kind": "v9",  "configs": list, "config_hash": str | None}
    or None if neither V10 expression nor V9 configs are present.

    Does NOT look at engine_hash — structural only, so it works on pure
    passport dicts (no wrapping row needed).
    """
    if not isinstance(passport, dict):
        return None
    arena1 = passport.get("arena1", {}) or {}
    if not isinstance(arena1, dict):
        return None

    # V10 shape — alpha_expression is typically a dict (AST json); preserve original type.
    # Gemini 2026-04-19: str() cast broke reconstruct_signal_from_passport downstream.
    alpha_expr = arena1.get("alpha_expression")
    if alpha_expr:
        return {
            "kind": "v10",
            "alpha_expression": alpha_expr,
            "alpha_hash": arena1.get("alpha_hash") or None,
        }

    # V9 shape
    configs = arena1.get("configs")
    if configs:
        return {
            "kind": "v9",
            "configs": list(configs) if not isinstance(configs, list) else configs,
            "config_hash": arena1.get("config_hash") or None,
        }

    return None


def get_dedup_key(passport: Any) -> str:
    """Return a non-empty dedup key. RAISES ValueError if unresolvable.

    This replaces the V9-centric `config_hash` reads in a45.py swiss_pair /
    Gate 5 dedup that produced empty strings for V10, silently collapsing
    all V10 alphas into one equivalence class.

    Prefers V10 alpha_hash, falls back to V9 config_hash. Whichever kind,
    must be non-empty. Empty-string or missing → raise (so callers loudly
    fail rather than skip a pairing).
    """
    spec = get_alpha(passport)
    if spec is None:
        raise ValueError(
            f"passport carries no alpha payload "
            f"(engine_hash={_engine_hash(passport)!r}, keys={list(passport.keys()) if isinstance(passport, dict) else None})"
        )
    key = spec.get("alpha_hash") if spec["kind"] == "v10" else spec.get("config_hash")
    if not key:
        raise ValueError(
            f"passport {spec['kind']} alpha payload has no dedup key "
            f"(alpha_hash/config_hash missing or empty)"
        )
    return str(key)


# Convenience for call sites that need to branch cheaply
def dispatch(passport_or_row: Any) -> str:
    """Return 'v10' / 'v9' / 'unknown'. Does NOT raise."""
    spec = get_alpha(passport_or_row if isinstance(passport_or_row, dict) and "arena1" in passport_or_row
                     else (passport_or_row.get("passport", {}) if isinstance(passport_or_row, dict) else {}))
    if spec is None:
        if is_v10(passport_or_row):
            return "v10"
        return "unknown"
    return spec["kind"]
