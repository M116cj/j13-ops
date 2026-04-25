"""Profile Attribution Coverage and Replay Validation (TEAM ORDER 0-9P-AUDIT).

Offline / read-only audit. Consumes either:

  - aggregate ``arena_batch_metrics`` events (dict-shaped, stage-tagged), or
  - candidate passports (used only for replay-validation tests),

and produces an :class:`AttributionAuditResult` with coverage rates,
profile-level breakdowns, mismatch counts, and a GREEN / YELLOW / RED
verdict that gates the next stack phase (PR-C / 0-9R-IMPL-DRY).

Strict guarantees:

  - **Read-only.** Never mutates inputs; never writes runtime state.
  - **No runtime side effects.** Does not import
    ``arena_pipeline`` / ``arena23_orchestrator`` /
    ``arena45_orchestrator`` / ``feedback_budget_allocator``. Reads
    only the canonical 0-9P helper
    ``generation_profile_identity.resolve_attribution_chain``.
  - **Deterministic.** Sorted iteration over keys; output is hashable
    snapshot.
  - **Never raises.** Pathological inputs produce best-effort partial
    results with reasons appended to ``verdict_reasons``.

Thresholds (per TEAM ORDER 0-9P-AUDIT §5):

  GREEN:
      unknown_profile_rate     < 5%
      profile_mismatch_rate    < 1%
      fingerprint_unavailable_rate < 5%
  YELLOW:
      unknown_profile_rate     5%-20%
      profile_mismatch_rate    1%-5%
      fingerprint_unavailable_rate 5%-20%
  RED:
      unknown_profile_rate     > 20%
      profile_mismatch_rate    > 5%
      fingerprint_unavailable_rate > 20%

Worst-of-three drives the overall verdict.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
)

from zangetsu.services.generation_profile_identity import (
    UNAVAILABLE_FINGERPRINT,
    UNKNOWN_PROFILE_ID,
    resolve_attribution_chain,
)


AUDIT_VERSION = "0-9P-AUDIT"

VERDICT_GREEN = "GREEN"
VERDICT_YELLOW = "YELLOW"
VERDICT_RED = "RED"

# Thresholds (rates, 0..1).
GREEN_UNKNOWN_MAX = 0.05
GREEN_MISMATCH_MAX = 0.01
GREEN_FINGERPRINT_UNAVAIL_MAX = 0.05

YELLOW_UNKNOWN_MAX = 0.20
YELLOW_MISMATCH_MAX = 0.05
YELLOW_FINGERPRINT_UNAVAIL_MAX = 0.20


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


@dataclass
class AttributionAuditResult:
    """Snapshot of one audit run."""

    audit_version: str = AUDIT_VERSION
    total_events: int = 0
    total_a1_events: int = 0
    total_a2_events: int = 0
    total_a3_events: int = 0

    # Source classification.
    passport_identity_count: int = 0
    orchestrator_fallback_count: int = 0
    unknown_profile_count: int = 0
    unavailable_fingerprint_count: int = 0

    # Rates.
    passport_identity_rate: float = 0.0
    orchestrator_fallback_rate: float = 0.0
    unknown_profile_rate: float = 0.0
    fingerprint_unavailable_rate: float = 0.0

    # Cross-stage profile alignment.
    a1_to_a2_profile_match_count: int = 0
    a2_to_a3_profile_match_count: int = 0
    profile_mismatch_count: int = 0
    profile_mismatch_rate: float = 0.0

    # Per-profile stage counts: ``{stage: {profile_id: count}}``.
    stage_counts_by_profile: Dict[str, Dict[str, int]] = field(default_factory=dict)
    reject_reason_distribution_by_profile: Dict[str, Dict[str, int]] = field(default_factory=dict)
    signal_too_sparse_rate_by_profile: Dict[str, float] = field(default_factory=dict)
    oos_fail_rate_by_profile: Dict[str, float] = field(default_factory=dict)
    deployable_count_by_profile: Dict[str, int] = field(default_factory=dict)

    # Verdict.
    verdict: str = VERDICT_RED
    verdict_reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        try:
            return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)
        except Exception:
            return ""


# ---------------------------------------------------------------------------
# Event classification helpers
# ---------------------------------------------------------------------------


def classify_attribution_source(event: Mapping[str, Any]) -> str:
    """Return ``"passport"`` / ``"orchestrator"`` / ``"unknown"``.

    Heuristic: an aggregate batch event carries a single resolved
    ``generation_profile_id`` and ``generation_profile_fingerprint``.
    Without the original passport we cannot tell whether the resolver
    hit level 1 vs level 2 vs level 3 deterministically, but we can
    distinguish the three coarse classes:

      - profile_id == UNKNOWN_PROFILE_ID → "unknown"
      - profile_id != UNKNOWN_PROFILE_ID AND attribution_source field
        is present → use that field directly
      - profile_id != UNKNOWN_PROFILE_ID AND no attribution_source
        present → assume "passport" (safe-but-conservative — at
        replay-time we can refine via :func:`replay_validate`).

    The function is exception-safe.
    """
    try:
        if not isinstance(event, Mapping):
            return "unknown"
        pid = event.get("generation_profile_id")
        if not pid or pid == UNKNOWN_PROFILE_ID:
            return "unknown"
        src = event.get("attribution_source")
        if src in ("passport_arena1", "passport_root", "passport"):
            return "passport"
        if src == "orchestrator":
            return "orchestrator"
        if src == "fallback":
            return "unknown"
        # No attribution_source field — treat as passport (conservative).
        return "passport"
    except Exception:
        return "unknown"


def _safe_get_stage(event: Mapping[str, Any]) -> str:
    try:
        s = str(event.get("arena_stage") or "").upper()
        if s in ("A1", "A2", "A3"):
            return s
        return "OTHER"
    except Exception:
        return "OTHER"


def _safe_get_profile_id(event: Mapping[str, Any]) -> str:
    try:
        return str(event.get("generation_profile_id") or UNKNOWN_PROFILE_ID)
    except Exception:
        return UNKNOWN_PROFILE_ID


def _safe_get_fingerprint(event: Mapping[str, Any]) -> str:
    try:
        return str(event.get("generation_profile_fingerprint") or UNAVAILABLE_FINGERPRINT)
    except Exception:
        return UNAVAILABLE_FINGERPRINT


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Verdict logic
# ---------------------------------------------------------------------------


def classify_verdict(
    *,
    unknown_profile_rate: float,
    profile_mismatch_rate: float,
    fingerprint_unavailable_rate: float,
) -> Tuple[str, List[str]]:
    """Return ``(verdict, reasons)`` for the supplied rates.

    Worst-of-three: if any single rate is RED → overall RED. Else if any
    single rate is YELLOW → overall YELLOW. Else GREEN.
    """
    reasons: List[str] = []
    has_red = False
    has_yellow = False

    def _classify(value: float, green_cut: float, yellow_cut: float, label: str) -> None:
        nonlocal has_red, has_yellow
        if value > yellow_cut:
            has_red = True
            reasons.append(
                f"{label}={value:.4f} exceeds YELLOW max={yellow_cut:.4f}"
            )
        elif value > green_cut:
            has_yellow = True
            reasons.append(
                f"{label}={value:.4f} between GREEN/YELLOW (>{green_cut:.4f})"
            )

    _classify(unknown_profile_rate, GREEN_UNKNOWN_MAX, YELLOW_UNKNOWN_MAX, "unknown_profile_rate")
    _classify(profile_mismatch_rate, GREEN_MISMATCH_MAX, YELLOW_MISMATCH_MAX, "profile_mismatch_rate")
    _classify(fingerprint_unavailable_rate, GREEN_FINGERPRINT_UNAVAIL_MAX, YELLOW_FINGERPRINT_UNAVAIL_MAX, "fingerprint_unavailable_rate")

    if has_red:
        return VERDICT_RED, reasons
    if has_yellow:
        return VERDICT_YELLOW, reasons
    return VERDICT_GREEN, reasons


def verdict_blocks_consumer_phase(verdict: str) -> bool:
    """Return True if the supplied verdict blocks PR-C / 0-9R-IMPL-DRY."""
    return verdict == VERDICT_RED


# ---------------------------------------------------------------------------
# Top-level audit
# ---------------------------------------------------------------------------


def audit(events: Iterable[Mapping[str, Any]]) -> AttributionAuditResult:
    """Build an :class:`AttributionAuditResult` from a stream of
    aggregate ``arena_batch_metrics`` events.

    Inputs are never mutated. Pathological events (non-mappings,
    malformed counts) are skipped silently with a one-line note in
    ``verdict_reasons``. Exception-safe.
    """
    result = AttributionAuditResult()
    if events is None:
        result.verdict = VERDICT_RED
        result.verdict_reasons.append("audit input was None")
        return result

    # Per-stage profile-id streams ordered by appearance — used for
    # cross-stage match counting.
    stage_profile_seq: Dict[str, List[str]] = {"A1": [], "A2": [], "A3": []}
    fingerprints_by_profile: Dict[str, List[str]] = {}

    skipped = 0
    for ev in events:
        try:
            if not isinstance(ev, Mapping):
                skipped += 1
                continue
            stage = _safe_get_stage(ev)
            pid = _safe_get_profile_id(ev)
            fp = _safe_get_fingerprint(ev)
            entered = max(0, _safe_int(ev.get("entered_count"), 0))
            passed = max(0, _safe_int(ev.get("passed_count"), 0))
            rejected = max(0, _safe_int(ev.get("rejected_count"), 0))
            dist = ev.get("reject_reason_distribution") or {}
            deployable = ev.get("deployable_count")

            result.total_events += 1
            if stage == "A1":
                result.total_a1_events += 1
            elif stage == "A2":
                result.total_a2_events += 1
            elif stage == "A3":
                result.total_a3_events += 1

            src = classify_attribution_source(ev)
            if src == "passport":
                result.passport_identity_count += 1
            elif src == "orchestrator":
                result.orchestrator_fallback_count += 1
            else:
                result.unknown_profile_count += 1

            if not fp or fp == UNAVAILABLE_FINGERPRINT:
                result.unavailable_fingerprint_count += 1

            if stage in stage_profile_seq:
                stage_profile_seq[stage].append(pid)

            stage_slot = result.stage_counts_by_profile.setdefault(stage, {})
            stage_slot[pid] = stage_slot.get(pid, 0) + 1

            reason_slot = result.reject_reason_distribution_by_profile.setdefault(pid, {})
            try:
                for reason, count in dict(dist).items():
                    n = max(0, _safe_int(count, 0))
                    if n <= 0:
                        continue
                    reason_slot[str(reason)] = reason_slot.get(str(reason), 0) + n
            except Exception:
                pass

            if isinstance(deployable, int) and deployable > 0:
                result.deployable_count_by_profile[pid] = (
                    result.deployable_count_by_profile.get(pid, 0) + deployable
                )

            fingerprints_by_profile.setdefault(pid, []).append(fp)
        except Exception:
            skipped += 1
            continue

    if skipped > 0:
        result.verdict_reasons.append(
            f"skipped {skipped} malformed event(s) during audit"
        )

    # Rates.
    n = max(1, result.total_events)
    result.passport_identity_rate = result.passport_identity_count / n
    result.orchestrator_fallback_rate = result.orchestrator_fallback_count / n
    result.unknown_profile_rate = result.unknown_profile_count / n
    result.fingerprint_unavailable_rate = result.unavailable_fingerprint_count / n

    # Cross-stage match counts — naive sequential pairing per stage.
    a1, a2, a3 = stage_profile_seq["A1"], stage_profile_seq["A2"], stage_profile_seq["A3"]
    result.a1_to_a2_profile_match_count = sum(
        1 for x, y in zip(a1, a2) if x == y and x != UNKNOWN_PROFILE_ID
    )
    result.a2_to_a3_profile_match_count = sum(
        1 for x, y in zip(a2, a3) if x == y and x != UNKNOWN_PROFILE_ID
    )
    a1_a2_pairs = min(len(a1), len(a2))
    a2_a3_pairs = min(len(a2), len(a3))
    pair_total = a1_a2_pairs + a2_a3_pairs
    pair_matches = (
        result.a1_to_a2_profile_match_count + result.a2_to_a3_profile_match_count
    )
    result.profile_mismatch_count = max(0, pair_total - pair_matches)
    result.profile_mismatch_rate = (
        result.profile_mismatch_count / pair_total if pair_total > 0 else 0.0
    )

    # Per-profile sparse / oos rates.
    for pid, reason_dist in result.reject_reason_distribution_by_profile.items():
        sparse = reason_dist.get("SIGNAL_TOO_SPARSE", 0)
        oos = reason_dist.get("OOS_FAIL", 0)
        unknown = reason_dist.get("UNKNOWN_REJECT", 0)
        total_rejects = sparse + oos + unknown
        if total_rejects > 0:
            result.signal_too_sparse_rate_by_profile[pid] = sparse / total_rejects
            result.oos_fail_rate_by_profile[pid] = oos / total_rejects
        else:
            result.signal_too_sparse_rate_by_profile[pid] = 0.0
            result.oos_fail_rate_by_profile[pid] = 0.0

    verdict, reasons = classify_verdict(
        unknown_profile_rate=result.unknown_profile_rate,
        profile_mismatch_rate=result.profile_mismatch_rate,
        fingerprint_unavailable_rate=result.fingerprint_unavailable_rate,
    )
    result.verdict = verdict
    result.verdict_reasons.extend(reasons)
    return result


def safe_audit(events: Iterable[Mapping[str, Any]]) -> AttributionAuditResult:
    """Exception-safe wrapper. Always returns a valid
    :class:`AttributionAuditResult`. On unexpected failure the result
    has ``verdict == VERDICT_RED`` and ``verdict_reasons`` records the
    underlying exception class name."""
    try:
        return audit(events)
    except Exception as exc:  # noqa: BLE001
        result = AttributionAuditResult()
        result.verdict = VERDICT_RED
        result.verdict_reasons.append(
            f"audit raised {type(exc).__name__} — caller should investigate"
        )
        return result


# ---------------------------------------------------------------------------
# Replay validation
# ---------------------------------------------------------------------------


@dataclass
class ReplayValidationResult:
    total_passports: int = 0
    matched_passport_arena1: int = 0
    matched_passport_root: int = 0
    matched_orchestrator: int = 0
    matched_fallback: int = 0
    expected_match_count: int = 0
    expected_match_rate: float = 0.0
    sources_observed: List[str] = field(default_factory=list)


def replay_validate(
    passports: Iterable[Mapping[str, Any]],
    *,
    expected_profile_id: Optional[str] = None,
    orchestrator_profile_id: Optional[str] = None,
    orchestrator_profile_fingerprint: Optional[str] = None,
) -> ReplayValidationResult:
    """Run :func:`resolve_attribution_chain` over a set of passports
    and tally which precedence level was hit. If
    ``expected_profile_id`` is supplied, count how many resolved ids
    match it. Exception-safe.
    """
    out = ReplayValidationResult()
    if passports is None:
        return out
    sources: Dict[str, int] = {
        "passport_arena1": 0,
        "passport_root": 0,
        "orchestrator": 0,
        "fallback": 0,
    }
    for p in passports:
        try:
            res = resolve_attribution_chain(
                p,
                orchestrator_profile_id=orchestrator_profile_id,
                orchestrator_profile_fingerprint=orchestrator_profile_fingerprint,
            )
            out.total_passports += 1
            src = str(res.get("source") or "fallback")
            if src in sources:
                sources[src] += 1
            if expected_profile_id and res.get("profile_id") == expected_profile_id:
                out.expected_match_count += 1
        except Exception:
            continue

    out.matched_passport_arena1 = sources["passport_arena1"]
    out.matched_passport_root = sources["passport_root"]
    out.matched_orchestrator = sources["orchestrator"]
    out.matched_fallback = sources["fallback"]
    out.sources_observed = sorted(s for s, n in sources.items() if n > 0)
    if expected_profile_id and out.total_passports > 0:
        out.expected_match_rate = out.expected_match_count / out.total_passports
    return out


# ---------------------------------------------------------------------------
# JSON-line log parser (offline log replay)
# ---------------------------------------------------------------------------


def parse_event_log_lines(
    lines: Iterable[str],
) -> List[Dict[str, Any]]:
    """Best-effort parser for newline-separated JSON event logs.

    Skips empty lines and malformed JSON; never raises.
    """
    out: List[Dict[str, Any]] = []
    for raw in lines or ():
        try:
            if not isinstance(raw, str):
                continue
            line = raw.strip()
            if not line:
                continue
            obj = json.loads(line)
            if isinstance(obj, dict):
                out.append(obj)
        except Exception:
            continue
    return out


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def required_audit_fields() -> Tuple[str, ...]:
    """Stable list of fields on :class:`AttributionAuditResult`.

    Used by tests to lock the schema."""
    return (
        "audit_version",
        "total_events",
        "total_a1_events",
        "total_a2_events",
        "total_a3_events",
        "passport_identity_count",
        "orchestrator_fallback_count",
        "unknown_profile_count",
        "unavailable_fingerprint_count",
        "passport_identity_rate",
        "orchestrator_fallback_rate",
        "unknown_profile_rate",
        "fingerprint_unavailable_rate",
        "a1_to_a2_profile_match_count",
        "a2_to_a3_profile_match_count",
        "profile_mismatch_count",
        "profile_mismatch_rate",
        "stage_counts_by_profile",
        "reject_reason_distribution_by_profile",
        "signal_too_sparse_rate_by_profile",
        "oos_fail_rate_by_profile",
        "deployable_count_by_profile",
        "verdict",
        "verdict_reasons",
    )
