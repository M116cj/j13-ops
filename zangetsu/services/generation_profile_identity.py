"""Generation profile identity helper (TEAM ORDER 0-9O-A).

This module provides stable, canonical identity for a black-box ZANGETSU
generation profile. It is read-only and never alters alpha generation
behavior, search policy, thresholds, Arena pass/fail logic, champion
promotion, or execution.

Identity is derived from a profile config dictionary (e.g. GP loop shape,
entry / exit thresholds, cost model) via canonical JSON + SHA256. The
profile_id is a short, human-friendly prefix of the fingerprint.

Fallbacks (never block telemetry):

    UNKNOWN_PROFILE_ID          — when profile identity is not available
    UNAVAILABLE_FINGERPRINT     — when fingerprint cannot be computed

All exported helpers are exception-safe: they return the safe fallback
rather than propagate errors into the Arena runtime.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Optional

# Public constants shared with arena_pass_rate_telemetry.
UNKNOWN_PROFILE_ID = "UNKNOWN_PROFILE"
UNAVAILABLE_FINGERPRINT = "UNAVAILABLE"

# Fields that must NEVER contribute to a profile fingerprint because they
# change across runs without changing the profile itself.
_VOLATILE_FIELDS_EXCLUDED = frozenset(
    {
        "timestamp",
        "timestamp_start",
        "timestamp_end",
        "created_at",
        "updated_at",
        "last_updated_at",
        "run_id",
        "batch_id",
        "worker_id",
        "now",
        "ts",
        "clock",
        "nonce",
    }
)

_FINGERPRINT_PREFIX = "sha256:"
_PROFILE_ID_PREFIX = "gp_"
_PROFILE_ID_HEX_LEN = 16


def canonical_json(obj: Any) -> str:
    """Return a deterministic JSON string with sorted keys and compact
    separators. Non-serializable values raise — callers should wrap this
    in a safe helper. Volatile keys are NOT stripped here; strip them in
    ``_strip_volatile`` before calling this.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _strip_volatile(config: Mapping[str, Any]) -> dict:
    """Return a new dict with volatile keys removed, recursively."""
    out: dict = {}
    for key, value in config.items():
        if key in _VOLATILE_FIELDS_EXCLUDED:
            continue
        if isinstance(value, Mapping):
            out[key] = _strip_volatile(value)
        else:
            out[key] = value
    return out


def profile_fingerprint(profile_config: Optional[Mapping[str, Any]]) -> str:
    """Compute the canonical sha256 fingerprint of a profile config.

    Returns ``UNAVAILABLE_FINGERPRINT`` if the config is None, empty, or
    contains values that cannot be canonicalized. Never raises.
    """
    if profile_config is None:
        return UNAVAILABLE_FINGERPRINT
    try:
        stripped = _strip_volatile(profile_config)
        if not stripped:
            return UNAVAILABLE_FINGERPRINT
        payload = canonical_json(stripped)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return _FINGERPRINT_PREFIX + digest
    except Exception:
        return UNAVAILABLE_FINGERPRINT


def profile_id_from_fingerprint(fingerprint: str) -> str:
    """Derive a short profile_id from a fingerprint.

    Returns ``UNKNOWN_PROFILE_ID`` for unavailable fingerprints.
    """
    if not isinstance(fingerprint, str):
        return UNKNOWN_PROFILE_ID
    if fingerprint == UNAVAILABLE_FINGERPRINT:
        return UNKNOWN_PROFILE_ID
    if not fingerprint.startswith(_FINGERPRINT_PREFIX):
        return UNKNOWN_PROFILE_ID
    hex_part = fingerprint[len(_FINGERPRINT_PREFIX):]
    if len(hex_part) < _PROFILE_ID_HEX_LEN:
        return UNKNOWN_PROFILE_ID
    return _PROFILE_ID_PREFIX + hex_part[:_PROFILE_ID_HEX_LEN]


def resolve_profile_identity(
    profile_config: Optional[Mapping[str, Any]] = None,
    *,
    profile_name: Optional[str] = None,
) -> dict:
    """Return a dict with ``profile_id``, ``profile_fingerprint``, and
    ``profile_name``. Never raises. Missing inputs map to the
    UNKNOWN / UNAVAILABLE fallbacks.
    """
    try:
        fp = profile_fingerprint(profile_config)
        pid = profile_id_from_fingerprint(fp)
        name = profile_name if profile_name else pid
        return {
            "profile_id": pid,
            "profile_fingerprint": fp,
            "profile_name": name,
        }
    except Exception:
        return {
            "profile_id": UNKNOWN_PROFILE_ID,
            "profile_fingerprint": UNAVAILABLE_FINGERPRINT,
            "profile_name": profile_name or UNKNOWN_PROFILE_ID,
        }


def safe_resolve_profile_identity(
    profile_config: Optional[Mapping[str, Any]] = None,
    *,
    profile_name: Optional[str] = None,
) -> dict:
    """Exception-safe wrapper. Guaranteed to return a dict with the three
    identity fields. Telemetry callers should prefer this.
    """
    try:
        return resolve_profile_identity(
            profile_config, profile_name=profile_name
        )
    except Exception:
        return {
            "profile_id": UNKNOWN_PROFILE_ID,
            "profile_fingerprint": UNAVAILABLE_FINGERPRINT,
            "profile_name": profile_name or UNKNOWN_PROFILE_ID,
        }


def resolve_attribution_chain(
    passport: Optional[Mapping[str, Any]] = None,
    *,
    orchestrator_profile_id: Optional[str] = None,
    orchestrator_profile_fingerprint: Optional[str] = None,
) -> dict:
    """Resolve the canonical 0-9P attribution precedence chain.

    Precedence (highest first, per TEAM ORDER 0-9P §4 attribution
    contract):

        1. ``passport["arena1"]["generation_profile_id"]`` /
           ``...["generation_profile_fingerprint"]`` — A1 producer-side
           identity persisted into the candidate passport.
        2. ``passport["generation_profile_id"]`` /
           ``...["generation_profile_fingerprint"]`` — passport-level
           override (rare; supports future schema variants).
        3. ``orchestrator_profile_id`` /
           ``orchestrator_profile_fingerprint`` — A2/A3 orchestrator's
           consumer-profile fallback (set when the orchestrator boots).
        4. ``UNKNOWN_PROFILE_ID`` / ``UNAVAILABLE_FINGERPRINT`` — final
           fallback when all upstream sources are missing.

    The returned dict always carries three fields::

        {
            "profile_id":          <str>,
            "profile_fingerprint": <str>,
            "source": one of "passport_arena1" / "passport_root" /
                      "orchestrator" / "fallback",
        }

    The function never raises. Missing identity must not block telemetry
    or alter Arena decisions; callers may treat ``"fallback"`` source as
    "no attribution available".
    """
    try:
        if isinstance(passport, Mapping):
            arena1 = passport.get("arena1") or {}
            if isinstance(arena1, Mapping):
                pid = arena1.get("generation_profile_id")
                pfp = arena1.get("generation_profile_fingerprint")
                if pid:
                    return {
                        "profile_id": str(pid),
                        "profile_fingerprint": str(
                            pfp or UNAVAILABLE_FINGERPRINT
                        ),
                        "source": "passport_arena1",
                    }
            pid_root = passport.get("generation_profile_id")
            pfp_root = passport.get("generation_profile_fingerprint")
            if pid_root:
                return {
                    "profile_id": str(pid_root),
                    "profile_fingerprint": str(
                        pfp_root or UNAVAILABLE_FINGERPRINT
                    ),
                    "source": "passport_root",
                }
        if orchestrator_profile_id:
            return {
                "profile_id": str(orchestrator_profile_id),
                "profile_fingerprint": str(
                    orchestrator_profile_fingerprint
                    or UNAVAILABLE_FINGERPRINT
                ),
                "source": "orchestrator",
            }
        return {
            "profile_id": UNKNOWN_PROFILE_ID,
            "profile_fingerprint": UNAVAILABLE_FINGERPRINT,
            "source": "fallback",
        }
    except Exception:
        return {
            "profile_id": UNKNOWN_PROFILE_ID,
            "profile_fingerprint": UNAVAILABLE_FINGERPRINT,
            "source": "fallback",
        }
