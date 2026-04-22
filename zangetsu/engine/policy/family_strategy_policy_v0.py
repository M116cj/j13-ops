"""Family-Aware Strategy Policy Layer v0 — decision-layer module.

Responsibilities (DECISION LAYER ONLY — no execution logic):
  1. Load + schema-validate the registry yaml
  2. Normalize family_id via the explicit alias table (no fuzzy matching)
  3. Resolve (family_id, mode) -> policy dict
  4. Distinguish three route states: active / fallback / blocked

This module MUST NOT:
  - Run or duplicate any signal/backtest/runner logic
  - Embed any family -> parameter mapping constant
  - Perform partial / contains / fuzzy name matching

Per task 421-4 acceptance criteria (AC1): the registry yaml is the single
source of truth. This resolver is a pure function over (registry, family_id,
mode) -> policy dict.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict

import yaml

log = logging.getLogger(__name__)

DEFAULT_REGISTRY_PATH = Path("/home/j13/j13-ops/zangetsu/config/family_strategy_policy_v0.yaml")

_REQUIRED_TOP_KEYS = {"policy_version", "defaults", "aliases", "families"}
_REQUIRED_DEFAULTS_KEYS = {
    "fallback_mode_default",
    "fallback_rank_window",
    "fallback_entry_threshold",
    "fallback_min_hold",
    "fallback_exit_threshold",
}
_REQUIRED_VALIDATED_FAMILY_KEYS = {
    "validated",
    "rank_window",
    "entry_threshold",
    "min_hold",
    "exit_threshold",
    "route_status",
    "evidence_tag",
}
_REQUIRED_UNVALIDATED_FAMILY_KEYS = {"validated", "route_status", "evidence_tag"}
# A candidate_test entry is validated=false but DOES ship parameters to inject.
# It is only legal in overlay registries (task-local experimentation), never in
# the main v0 production registry.
_REQUIRED_CANDIDATE_TEST_FAMILY_KEYS = {
    "validated",
    "route_status",
    "evidence_tag",
    "rank_window",
    "entry_threshold",
    "min_hold",
    "exit_threshold",
}

_ALLOWED_MODES = {"research", "production"}
_OVERLAY_ALLOWED_ROUTE_STATUSES = {"candidate_test", "candidate_exception"}
_OVERLAY_ALLOWED_KINDS = {"candidate_test", "candidate_exception"}

# Required keys for an allow_list entry in a candidate_exception overlay.
_REQUIRED_ALLOW_LIST_KEYS = {"symbol", "formula"}

# candidate_exception families additionally require allow_list.
_REQUIRED_CANDIDATE_EXCEPTION_FAMILY_KEYS = (
    _REQUIRED_CANDIDATE_TEST_FAMILY_KEYS | {"allow_list"}
)


class PolicyRegistryError(Exception):
    """Raised when the registry schema is invalid. Resolver aborts."""


class PolicyBlockedError(Exception):
    """Raised when production mode receives an unvalidated family. Fail-closed."""


def load_registry(path: Path = DEFAULT_REGISTRY_PATH, *, overlay: bool = False) -> Dict[str, Any]:
    """Load + schema-validate the registry. Abort on any invariant violation.

    overlay=True relaxes the route_status rule to allow candidate_test entries
    (task-local experimentation). Main registries must pass overlay=False.
    """
    p = Path(path)
    if not p.exists():
        raise PolicyRegistryError(f"registry not found: {p}")
    try:
        reg = yaml.safe_load(p.read_text())
    except yaml.YAMLError as e:
        raise PolicyRegistryError(f"registry yaml parse failed: {e}")
    _validate_schema(reg, source=str(p), overlay=overlay)
    return reg


def load_with_overlay(
    main_path: Path = DEFAULT_REGISTRY_PATH,
    overlay_path: Path | None = None,
) -> Dict[str, Any]:
    """Load main registry + optional overlay. Return a dict:
        {"main": main_registry, "overlay": overlay_registry_or_None,
         "main_path": str, "overlay_path": str_or_None}.

    Overlay family_ids MUST NOT collide with main registry family_ids — that
    prevents silent redefinition of validated production routes (j13 hard rule A).
    """
    main = load_registry(main_path, overlay=False)
    if overlay_path is None:
        return {"main": main, "overlay": None,
                "main_path": str(main_path), "overlay_path": None}
    ov = load_registry(overlay_path, overlay=True)
    # Collision check: overlays may only ADD families, not shadow main ones.
    collisions = set(ov["families"].keys()) & set(main["families"].keys())
    if collisions:
        raise PolicyRegistryError(
            f"overlay {overlay_path} redefines main-registry families "
            f"{sorted(collisions)} — overlays may only ADD families, not shadow"
        )
    # Policy version must agree (both v0).
    if ov["policy_version"] != main["policy_version"]:
        raise PolicyRegistryError(
            f"overlay policy_version {ov['policy_version']!r} != main "
            f"{main['policy_version']!r}"
        )
    # Optional but recommended: overlay_kind declared and valid.
    if "overlay_kind" in ov:
        kind = ov["overlay_kind"]
        if kind not in _OVERLAY_ALLOWED_KINDS:
            raise PolicyRegistryError(
                f"overlay {overlay_path}: unknown overlay_kind={kind!r}; "
                f"must be one of {sorted(_OVERLAY_ALLOWED_KINDS)}"
            )
    return {"main": main, "overlay": ov,
            "main_path": str(main_path), "overlay_path": str(overlay_path)}


def _check_overlay_expiry(overlay: Dict[str, Any], family_id: str) -> Dict[str, Any]:
    """Check expiry fields on an overlay family entry.

    Returns a dict: {expired: bool, warnings: [str], expiry_meta: {...}}.
    Semantics per j13 2026-04-22:
      - If expires_at (absolute ISO8601) is present AND already past -> expired=True.
      - If only event-based fields are present -> warnings, not blocking.
      - If no expiry fields at all -> pass silently.
    """
    import datetime as _dt
    fam = overlay["families"].get(family_id, {})
    warnings = []
    expired = False
    expires_at = fam.get("expires_at") or fam.get("expiry_date_hint")
    if expires_at:
        try:
            iso = expires_at.rstrip("Z").rstrip()
            dt = _dt.datetime.fromisoformat(iso)
            now = _dt.datetime.utcnow()
            if dt < now:
                expired = True
        except ValueError:
            warnings.append(f"could not parse expires_at={expires_at!r}")
    if "expiry_after_event" in fam and "expires_at" not in fam:
        warnings.append(
            f"event-only expiry ({fam['expiry_after_event']!r}) — "
            f"resolver cannot auto-block; human review required"
        )
    if "review_after_event" in fam and "review_by_date_hint" not in fam:
        warnings.append(
            f"event-only review hint ({fam['review_after_event']!r}) — informational"
        )
    return {
        "expired": expired,
        "warnings": warnings,
        "expiry_meta": {
            "expires_at": fam.get("expires_at"),
            "expiry_after_event": fam.get("expiry_after_event"),
            "review_by_date_hint": fam.get("review_by_date_hint"),
            "review_after_event": fam.get("review_after_event"),
        },
    }


def _match_allow_list(
    allow_list: list,
    symbol: str,
    formula: str,
    alpha_hash: str | None = None,
) -> Dict[str, Any]:
    """Primary match by formula string; alpha_hash is a defensive verifier.

    Rules (j13 boundary §3):
      - Match is by (symbol, formula_string) — canonical.
      - If alpha_hash is provided AND the matched entry declares an alpha_hash,
        they must agree. Mismatch -> warning (not a hard block here; caller
        decides). Hash-only match with formula miss -> warning, not a pass.
      - We return detailed match metadata to let the caller decide.
    """
    warnings = []
    matched_entry = None
    matched_index = -1
    hash_only_hits = []
    for i, entry in enumerate(allow_list):
        es = entry.get("symbol")
        ef = entry.get("formula")
        if es == symbol and ef == formula:
            matched_entry = entry
            matched_index = i
            break
    if matched_entry is not None and alpha_hash is not None:
        declared = matched_entry.get("alpha_hash")
        if declared is not None and declared != alpha_hash:
            warnings.append(
                f"allow_list hit by formula but alpha_hash mismatch: "
                f"input hash={alpha_hash!r} vs declared={declared!r}"
            )
    if matched_entry is None and alpha_hash is not None:
        for i, entry in enumerate(allow_list):
            if entry.get("alpha_hash") == alpha_hash and entry.get("symbol") == symbol:
                hash_only_hits.append((i, entry))
        if hash_only_hits:
            warnings.append(
                f"hash-only match detected for symbol={symbol!r} hash={alpha_hash!r} "
                f"but formula string does not match — NOT a valid pass. "
                f"Candidates: {[e[1].get('formula') for e in hash_only_hits]}"
            )
    return {
        "hit": matched_entry is not None,
        "matched_index": matched_index,
        "matched_entry": matched_entry,
        "warnings": warnings,
    }


def resolve_with_allow_list(
    family_id: str,
    mode: str,
    symbol: str,
    formula: str,
    alpha_hash: str | None = None,
    registry: Dict[str, Any] | None = None,
    overlay_registry: Dict[str, Any] | None = None,
    registry_path: Path = DEFAULT_REGISTRY_PATH,
    overlay_registry_path: Path | None = None,
) -> Dict[str, Any]:
    """Resolve policy for a specific (symbol, formula) cell, honoring
    candidate_exception overlay allow_lists.

    Lookup:
      1. If overlay is a candidate_exception family and (symbol, formula) is
         in its allow_list, return the overlay's parameters with
         route_status='candidate_exception' and exception_* metadata.
      2. Otherwise, fallthrough to the main-registry route for family_id
         (which is typically 'volume' in current use).

    j13 hard rule B: candidate_exception families cannot be invoked directly
    via family_id. If the caller passes the overlay's internal family_id
    (e.g. 'volume_c6_approved_exceptions') we REJECT with PolicyRegistryError.
    The caller must pass family_id='volume' with --exception-overlay separately.
    """
    if mode not in _ALLOWED_MODES:
        raise PolicyRegistryError(f"mode must be one of {_ALLOWED_MODES}, got {mode!r}")
    if registry is None:
        registry = load_registry(registry_path)
    if overlay_registry is None and overlay_registry_path is not None:
        overlay_registry = load_registry(overlay_registry_path, overlay=True)

    # Reject direct invocation of candidate_exception as family.
    if overlay_registry is not None and family_id in overlay_registry["families"]:
        target = overlay_registry["families"][family_id]
        if target.get("route_status") == "candidate_exception":
            raise PolicyRegistryError(
                f"candidate_exception family {family_id!r} cannot be invoked "
                f"directly via --family-id (j13 hard rule B). Pass a main-registry "
                f"family (e.g. 'volume') together with --exception-overlay "
                f"{overlay_registry_path}."
            )

    # Resolve the base policy against the main registry (ignoring overlay
    # for candidate_test here — this API is scoped to exception overlays).
    base = resolve_family_strategy_policy(
        family_id, mode=mode, registry=registry,
        overlay_registry=None,
        overlay_registry_path=None,
    )

    # Now search for a candidate_exception overlay family whose allow_list
    # hits on (symbol, formula).
    exception_hit = None
    overlay_warnings: list = []
    expiry_meta = None
    if overlay_registry is not None:
        for ov_fam_id, ov_fam in overlay_registry["families"].items():
            if ov_fam.get("route_status") != "candidate_exception":
                continue
            match = _match_allow_list(
                ov_fam["allow_list"], symbol=symbol, formula=formula,
                alpha_hash=alpha_hash,
            )
            overlay_warnings.extend(match["warnings"])
            if match["hit"]:
                exp = _check_overlay_expiry(overlay_registry, ov_fam_id)
                expiry_meta = exp["expiry_meta"]
                overlay_warnings.extend(exp["warnings"])
                if exp["expired"]:
                    # Expired -> fail-closed for this pair: do NOT promote.
                    overlay_warnings.append(
                        f"overlay family {ov_fam_id!r} expired at {expiry_meta.get('expires_at')} "
                        f"— exception NOT applied; falling through to main route"
                    )
                    continue
                exception_hit = {
                    "overlay_family_id": ov_fam_id,
                    "matched_entry": match["matched_entry"],
                    "matched_index": match["matched_index"],
                    "overlay_family_def": ov_fam,
                }
                break

    if exception_hit is not None:
        ov_fam = exception_hit["overlay_family_def"]
        entry = exception_hit["matched_entry"]
        result = {
            "input_family_id": family_id,
            "normalized_family_id": base["normalized_family_id"],
            "normalization_applied": base["normalization_applied"],
            "normalization_reason": base["normalization_reason"],
            "requested_family_id": family_id,
            "resolved_family_id": base["resolved_family_id"],
            "mode": mode,
            "validated": False,  # exception overlay is never 'validated'
            "evidence_tag": ov_fam["evidence_tag"],
            "policy_version": overlay_registry["policy_version"],
            "registry_source": "exception_overlay",
            "overlay_path": str(overlay_registry_path) if overlay_registry_path else None,
            "route_status": "candidate_exception",
            "route_reason": (
                f"exception_allow_list_hit:{exception_hit['overlay_family_id']}:"
                f"{symbol}:{formula}"
            ),
            "rank_window": int(ov_fam["rank_window"]),
            "entry_threshold": float(ov_fam["entry_threshold"]),
            "min_hold": int(ov_fam["min_hold"]),
            "exit_threshold": float(ov_fam["exit_threshold"]),
            "exception_allow_list_hit": True,
            "exception_overlay_name": exception_hit["overlay_family_id"],
            "exception_pair_key": f"{symbol}::{formula}",
            "exception_evidence_tag": ov_fam["evidence_tag"],
            "exception_matched_entry_index": exception_hit["matched_index"],
            "exception_expiry_meta": expiry_meta,
            "fallthrough_to_main": False,
            "overlay_warnings": overlay_warnings,
        }
        return result

    # No allow_list hit — fallthrough to main route with exception=False metadata.
    return {
        **base,
        "registry_source": "main",
        "overlay_path": str(overlay_registry_path) if overlay_registry_path else None,
        "exception_allow_list_hit": False,
        "exception_overlay_name": None,
        "exception_pair_key": f"{symbol}::{formula}",
        "exception_evidence_tag": None,
        "exception_matched_entry_index": -1,
        "exception_expiry_meta": None,
        "fallthrough_to_main": True,
        "overlay_warnings": overlay_warnings,
    }


def _validate_schema(reg: Any, source: str, *, overlay: bool = False) -> None:
    if not isinstance(reg, dict):
        raise PolicyRegistryError(f"registry {source}: top-level must be a mapping")
    missing_top = _REQUIRED_TOP_KEYS - reg.keys()
    if missing_top:
        raise PolicyRegistryError(f"registry {source}: missing top keys {sorted(missing_top)}")
    if reg["policy_version"] != "v0":
        raise PolicyRegistryError(
            f"registry {source}: policy_version must be 'v0', got {reg['policy_version']!r}"
        )

    defaults = reg["defaults"]
    if not isinstance(defaults, dict):
        raise PolicyRegistryError(f"registry {source}: defaults must be a mapping")
    missing_def = _REQUIRED_DEFAULTS_KEYS - defaults.keys()
    if missing_def:
        raise PolicyRegistryError(f"registry {source}: defaults missing {sorted(missing_def)}")
    if defaults["fallback_mode_default"] != "safe_fallback":
        raise PolicyRegistryError(
            f"registry {source}: defaults.fallback_mode_default must be 'safe_fallback' "
            f"(got {defaults['fallback_mode_default']!r})"
        )

    aliases = reg["aliases"]
    if not isinstance(aliases, dict):
        raise PolicyRegistryError(f"registry {source}: aliases must be a mapping")
    for k, v in aliases.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise PolicyRegistryError(
                f"registry {source}: aliases entries must be str->str (got {k!r}->{v!r})"
            )

    families = reg["families"]
    if not isinstance(families, dict):
        raise PolicyRegistryError(f"registry {source}: families must be a mapping")
    if not families:
        raise PolicyRegistryError(f"registry {source}: families must be non-empty")

    for fam_id, fam in families.items():
        if not isinstance(fam, dict):
            raise PolicyRegistryError(f"registry {source}: families[{fam_id!r}] must be a mapping")
        if "validated" not in fam:
            raise PolicyRegistryError(
                f"registry {source}: families[{fam_id!r}] missing 'validated'"
            )
        if fam["validated"] is True:
            missing = _REQUIRED_VALIDATED_FAMILY_KEYS - fam.keys()
            if missing:
                raise PolicyRegistryError(
                    f"registry {source}: validated family {fam_id!r} missing {sorted(missing)}"
                )
            if fam["route_status"] != "active":
                raise PolicyRegistryError(
                    f"registry {source}: validated family {fam_id!r} must have "
                    f"route_status='active' (got {fam['route_status']!r})"
                )
        else:
            route_status = fam.get("route_status")
            if overlay and route_status == "candidate_test":
                missing = _REQUIRED_CANDIDATE_TEST_FAMILY_KEYS - fam.keys()
                if missing:
                    raise PolicyRegistryError(
                        f"overlay registry {source}: candidate_test family {fam_id!r} "
                        f"missing {sorted(missing)}"
                    )
            elif overlay and route_status == "candidate_exception":
                missing = _REQUIRED_CANDIDATE_EXCEPTION_FAMILY_KEYS - fam.keys()
                if missing:
                    raise PolicyRegistryError(
                        f"overlay registry {source}: candidate_exception family "
                        f"{fam_id!r} missing {sorted(missing)}"
                    )
                al = fam["allow_list"]
                if not isinstance(al, list) or not al:
                    raise PolicyRegistryError(
                        f"overlay registry {source}: candidate_exception family "
                        f"{fam_id!r} allow_list must be a non-empty list"
                    )
                for i, entry in enumerate(al):
                    if not isinstance(entry, dict):
                        raise PolicyRegistryError(
                            f"overlay {source}: allow_list[{i}] must be a mapping"
                        )
                    miss = _REQUIRED_ALLOW_LIST_KEYS - entry.keys()
                    if miss:
                        raise PolicyRegistryError(
                            f"overlay {source}: allow_list[{i}] missing {sorted(miss)}"
                        )
            else:
                missing = _REQUIRED_UNVALIDATED_FAMILY_KEYS - fam.keys()
                if missing:
                    raise PolicyRegistryError(
                        f"registry {source}: unvalidated family {fam_id!r} missing {sorted(missing)}"
                    )
                if route_status != "unvalidated":
                    raise PolicyRegistryError(
                        f"registry {source}: unvalidated family {fam_id!r} must have "
                        f"route_status='unvalidated' (got {route_status!r}) — "
                        f"candidate_test is only permitted in overlay registries"
                    )

    # Every alias target must resolve to a declared family.
    for alias, target in aliases.items():
        if target not in families:
            raise PolicyRegistryError(
                f"registry {source}: alias {alias!r} -> {target!r} but family {target!r} "
                f"not declared in families"
            )


def _normalize_family_id(
    registry: Dict[str, Any], family_id: str
) -> Dict[str, Any]:
    """Explicit alias-table lookup. NO fuzzy / contains / partial matching."""
    aliases = registry["aliases"]
    families = registry["families"]
    if not isinstance(family_id, str):
        raise PolicyRegistryError(f"family_id must be a string, got {type(family_id).__name__}")
    # Exact lookup only.
    if family_id in aliases:
        normalized = aliases[family_id]
        applied = family_id != normalized
        reason = f"alias:{family_id}->{normalized}" if applied else "canonical_name"
        return {
            "input_family_id": family_id,
            "normalized_family_id": normalized,
            "normalization_applied": applied,
            "normalization_reason": reason,
        }
    # Not in alias table -> normalize to 'unknown' placeholder if declared.
    if "unknown" in families:
        return {
            "input_family_id": family_id,
            "normalized_family_id": "unknown",
            "normalization_applied": True,
            "normalization_reason": f"unrecognized:{family_id}->unknown",
        }
    raise PolicyRegistryError(
        f"family_id {family_id!r} not in alias table and registry has no 'unknown' placeholder"
    )


def resolve_family_strategy_policy(
    family_id: str,
    mode: str = "research",
    registry: Dict[str, Any] | None = None,
    registry_path: Path = DEFAULT_REGISTRY_PATH,
    overlay_registry: Dict[str, Any] | None = None,
    overlay_registry_path: Path | None = None,
) -> Dict[str, Any]:
    """Resolve a family policy decision.

    Lookup order (explicit, no implicit fallback):
      1. If family_id is declared in overlay_registry.families -> use overlay
      2. Else delegate to main registry (alias table -> families)

    On production + unvalidated family returns route_status='blocked' with
    None params; caller must honor fail-closed. For inspection-free raise,
    see `resolve_or_raise`.
    """
    if mode not in _ALLOWED_MODES:
        raise PolicyRegistryError(f"mode must be one of {_ALLOWED_MODES}, got {mode!r}")

    if registry is None:
        registry = load_registry(registry_path)

    # Overlay loading if not provided but path given.
    if overlay_registry is None and overlay_registry_path is not None:
        overlay_registry = load_registry(overlay_registry_path, overlay=True)

    # Precedence 1 — overlay hit (direct family_id match, no alias resolution
    # against main table; overlay entries carry their own identifier).
    if overlay_registry is not None and family_id in overlay_registry["families"]:
        fam = overlay_registry["families"][family_id]
        base = {
            "input_family_id": family_id,
            "normalized_family_id": family_id,
            "normalization_applied": False,
            "normalization_reason": "overlay_direct_hit",
            "requested_family_id": family_id,
            "resolved_family_id": family_id,
            "validated": bool(fam["validated"]),
            "evidence_tag": fam["evidence_tag"],
            "policy_version": overlay_registry["policy_version"],
            "mode": mode,
            "registry_source": "overlay",
            "overlay_path": overlay_registry.get("__source_path__") or str(overlay_registry_path or ""),
        }
        route_status = fam["route_status"]
        if route_status == "candidate_test":
            return {
                **base,
                "route_status": "candidate_test",
                "route_reason": f"overlay_candidate_test:{family_id}",
                "rank_window": int(fam["rank_window"]),
                "entry_threshold": float(fam["entry_threshold"]),
                "min_hold": int(fam["min_hold"]),
                "exit_threshold": float(fam["exit_threshold"]),
            }
        raise PolicyRegistryError(
            f"overlay family {family_id!r} has unsupported route_status={route_status!r}; "
            f"overlay only supports 'candidate_test' for now"
        )

    # Precedence 2 — main registry.
    norm = _normalize_family_id(registry, family_id)
    normalized_id = norm["normalized_family_id"]
    families = registry["families"]
    defaults = registry["defaults"]
    policy_version = registry["policy_version"]

    fam = families[normalized_id]

    base = {
        "input_family_id": norm["input_family_id"],
        "normalized_family_id": normalized_id,
        "normalization_applied": norm["normalization_applied"],
        "normalization_reason": norm["normalization_reason"],
        "requested_family_id": norm["input_family_id"],
        "resolved_family_id": normalized_id,
        "validated": bool(fam["validated"]),
        "evidence_tag": fam["evidence_tag"],
        "policy_version": policy_version,
        "mode": mode,
        "registry_source": "main",
        "overlay_path": str(overlay_registry_path) if overlay_registry_path else None,
    }

    if fam["validated"] is True:
        return {
            **base,
            "route_status": "active",
            "route_reason": f"validated_family:{normalized_id}",
            "rank_window": int(fam["rank_window"]),
            "entry_threshold": float(fam["entry_threshold"]),
            "min_hold": int(fam["min_hold"]),
            "exit_threshold": float(fam["exit_threshold"]),
        }

    # Unvalidated family.
    if mode == "production":
        return {
            **base,
            "route_status": "blocked",
            "route_reason": "unvalidated_family_fail_closed",
            "rank_window": None,
            "entry_threshold": None,
            "min_hold": None,
            "exit_threshold": None,
        }

    # mode == research -> safe fallback.
    return {
        **base,
        "route_status": "fallback",
        "route_reason": "unvalidated_family_safe_fallback",
        "rank_window": int(defaults["fallback_rank_window"]),
        "entry_threshold": float(defaults["fallback_entry_threshold"]),
        "min_hold": int(defaults["fallback_min_hold"]),
        "exit_threshold": float(defaults["fallback_exit_threshold"]),
    }


def resolve_or_raise(
    family_id: str, mode: str = "research", **kwargs: Any
) -> Dict[str, Any]:
    """Convenience wrapper that raises PolicyBlockedError on fail-closed."""
    policy = resolve_family_strategy_policy(family_id, mode=mode, **kwargs)
    if policy["route_status"] == "blocked":
        raise PolicyBlockedError(
            f"family_id={family_id!r} (normalized={policy['normalized_family_id']!r}) "
            f"is unvalidated and mode=production: {policy['route_reason']}"
        )
    return policy


def format_banner(policy: Dict[str, Any]) -> str:
    """Produce the startup banner lines required by task 421-4 §11.1."""
    lines = [
        "===== family-strategy-policy v0 =====",
        f"requested_family_id   = {policy['requested_family_id']!r}",
        f"normalized_family_id  = {policy['normalized_family_id']!r}",
        f"resolved_family_id    = {policy['resolved_family_id']!r}",
        f"normalization_applied = {policy['normalization_applied']}",
        f"normalization_reason  = {policy['normalization_reason']!r}",
        f"mode                  = {policy['mode']!r}",
        f"route_status          = {policy['route_status']!r}",
        f"route_reason          = {policy['route_reason']!r}",
        f"validated             = {policy['validated']}",
        f"evidence_tag          = {policy['evidence_tag']!r}",
        f"policy_version        = {policy['policy_version']!r}",
        f"registry_source       = {policy.get('registry_source', 'main')!r}",
        f"overlay_path          = {policy.get('overlay_path')!r}",
        f"exception_hit         = {policy.get('exception_allow_list_hit', False)}",
        f"exception_pair_key    = {policy.get('exception_pair_key')!r}",
        f"rank_window           = {policy['rank_window']}",
        f"entry_threshold       = {policy['entry_threshold']}",
        f"min_hold              = {policy['min_hold']}",
        f"exit_threshold        = {policy['exit_threshold']}",
        "=====================================",
    ]
    return "\n".join(lines)
