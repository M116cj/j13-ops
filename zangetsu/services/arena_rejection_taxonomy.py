"""Arena Rejection Taxonomy (P7-PR1 / MOD-7 / Phase 7).

Defines the canonical rejection-reason vocabulary for ZANGETSU Arena
candidate rejection. Produces a single source of truth for:

  (a) WHY a candidate was rejected (reason enum + human description),
  (b) AT WHICH Arena stage (A0/A1/A2/A3/A4 or UNKNOWN),
  (c) WHICH category the reason belongs to (formula/data/backtest/...),
  (d) HOW SEVERE it is (INFO/WARN/BLOCKING/FATAL),
  (e) WHICH raw strings emitted by existing Arena runtime code map to it.

INSTRUMENTATION-ONLY guarantee (0-9E §8 / §9):
    This module is PASSIVE. It adds no new side effect to Arena
    decision flow. It does NOT import Arena runtime. It does NOT
    read or mutate thresholds, alpha formulas, or champion promotion
    rules. Callers (SHADOW-mode wrappers, future P7-PR2+ integration)
    can invoke ``classify()`` to assign a canonical reason to a raw
    log/stats string without altering the original outcome.

Contract stability:
    - ``RejectionReason`` enum members are stable string values.
    - ``RAW_TO_REASON`` is additive: new mappings may be added; existing
      mappings may not be removed without a separate authorized order.
    - ``classify()`` never raises — returns ``UNKNOWN_REJECT`` as fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Mapping, Optional, Tuple


class RejectionReason(str, Enum):
    """Canonical rejection reasons (0-9E §6 — 18 mandatory values)."""

    INVALID_FORMULA = "INVALID_FORMULA"
    UNSUPPORTED_OPERATOR = "UNSUPPORTED_OPERATOR"
    WINDOW_INSUFFICIENT = "WINDOW_INSUFFICIENT"
    NON_CAUSAL_RISK = "NON_CAUSAL_RISK"
    NAN_INF_OUTPUT = "NAN_INF_OUTPUT"
    LOW_BACKTEST_SCORE = "LOW_BACKTEST_SCORE"
    HIGH_DRAWDOWN = "HIGH_DRAWDOWN"
    HIGH_TURNOVER = "HIGH_TURNOVER"
    COST_NEGATIVE = "COST_NEGATIVE"
    FRESH_FAIL = "FRESH_FAIL"
    OOS_FAIL = "OOS_FAIL"
    REGIME_FAIL = "REGIME_FAIL"
    SIGNAL_TOO_SPARSE = "SIGNAL_TOO_SPARSE"
    SIGNAL_TOO_DENSE = "SIGNAL_TOO_DENSE"
    CORRELATION_DUPLICATE = "CORRELATION_DUPLICATE"
    PROMOTION_BLOCKED = "PROMOTION_BLOCKED"
    GOVERNANCE_BLOCKED = "GOVERNANCE_BLOCKED"
    UNKNOWN_REJECT = "UNKNOWN_REJECT"


class RejectionCategory(str, Enum):
    """Canonical rejection categories (0-9E §6 — 14 mandatory)."""

    FORMULA_QUALITY = "FORMULA_QUALITY"
    DATA_QUALITY = "DATA_QUALITY"
    CAUSALITY = "CAUSALITY"
    BACKTEST_SCORE = "BACKTEST_SCORE"
    RISK = "RISK"
    COST = "COST"
    FRESH_VALIDATION = "FRESH_VALIDATION"
    OOS_VALIDATION = "OOS_VALIDATION"
    REGIME = "REGIME"
    SIGNAL_DENSITY = "SIGNAL_DENSITY"
    CORRELATION = "CORRELATION"
    PROMOTION = "PROMOTION"
    GOVERNANCE = "GOVERNANCE"
    UNKNOWN = "UNKNOWN"


class RejectionSeverity(str, Enum):
    """Canonical severity levels (0-9E §6)."""

    INFO = "INFO"
    WARN = "WARN"
    BLOCKING = "BLOCKING"
    FATAL = "FATAL"


class ArenaStage(str, Enum):
    """Arena pipeline stages. UNKNOWN when stage cannot be determined."""

    A0 = "A0"
    A1 = "A1"
    A2 = "A2"
    A3 = "A3"
    A4 = "A4"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RejectionMetadata:
    """Immutable metadata for a canonical rejection reason."""

    reason: RejectionReason
    category: RejectionCategory
    severity: RejectionSeverity
    default_arena_stage: ArenaStage
    description: str


# Canonical metadata table. Each of the 18 reasons has exactly one entry.
REJECTION_METADATA: Dict[RejectionReason, RejectionMetadata] = {
    RejectionReason.INVALID_FORMULA: RejectionMetadata(
        reason=RejectionReason.INVALID_FORMULA,
        category=RejectionCategory.FORMULA_QUALITY,
        severity=RejectionSeverity.BLOCKING,
        default_arena_stage=ArenaStage.A0,
        description="Alpha formula failed to compile, parse, or evaluate to a usable signal.",
    ),
    RejectionReason.UNSUPPORTED_OPERATOR: RejectionMetadata(
        reason=RejectionReason.UNSUPPORTED_OPERATOR,
        category=RejectionCategory.FORMULA_QUALITY,
        severity=RejectionSeverity.BLOCKING,
        default_arena_stage=ArenaStage.A0,
        description="Formula references an operator not in the DSL support list.",
    ),
    RejectionReason.WINDOW_INSUFFICIENT: RejectionMetadata(
        reason=RejectionReason.WINDOW_INSUFFICIENT,
        category=RejectionCategory.DATA_QUALITY,
        severity=RejectionSeverity.BLOCKING,
        default_arena_stage=ArenaStage.A0,
        description="Backtest window is too short to evaluate the formula reliably.",
    ),
    RejectionReason.NON_CAUSAL_RISK: RejectionMetadata(
        reason=RejectionReason.NON_CAUSAL_RISK,
        category=RejectionCategory.CAUSALITY,
        severity=RejectionSeverity.FATAL,
        default_arena_stage=ArenaStage.A0,
        description="Formula references future-data paths that would leak lookahead.",
    ),
    RejectionReason.NAN_INF_OUTPUT: RejectionMetadata(
        reason=RejectionReason.NAN_INF_OUTPUT,
        category=RejectionCategory.DATA_QUALITY,
        severity=RejectionSeverity.BLOCKING,
        default_arena_stage=ArenaStage.A0,
        description="Formula produces NaN or Inf output values outside safe handling.",
    ),
    RejectionReason.LOW_BACKTEST_SCORE: RejectionMetadata(
        reason=RejectionReason.LOW_BACKTEST_SCORE,
        category=RejectionCategory.BACKTEST_SCORE,
        severity=RejectionSeverity.BLOCKING,
        default_arena_stage=ArenaStage.A1,
        description="Backtest Sharpe/PnL/winrate below the A1 acceptance floor.",
    ),
    RejectionReason.HIGH_DRAWDOWN: RejectionMetadata(
        reason=RejectionReason.HIGH_DRAWDOWN,
        category=RejectionCategory.RISK,
        severity=RejectionSeverity.BLOCKING,
        default_arena_stage=ArenaStage.A1,
        description="Maximum drawdown exceeds the A1 risk ceiling.",
    ),
    RejectionReason.HIGH_TURNOVER: RejectionMetadata(
        reason=RejectionReason.HIGH_TURNOVER,
        category=RejectionCategory.COST,
        severity=RejectionSeverity.BLOCKING,
        default_arena_stage=ArenaStage.A1,
        description="Trade turnover too high; costs erode edge below acceptance.",
    ),
    RejectionReason.COST_NEGATIVE: RejectionMetadata(
        reason=RejectionReason.COST_NEGATIVE,
        category=RejectionCategory.COST,
        severity=RejectionSeverity.BLOCKING,
        default_arena_stage=ArenaStage.A2,
        description="Net PnL after costs is non-positive on the evaluated window.",
    ),
    RejectionReason.FRESH_FAIL: RejectionMetadata(
        reason=RejectionReason.FRESH_FAIL,
        category=RejectionCategory.FRESH_VALIDATION,
        severity=RejectionSeverity.BLOCKING,
        default_arena_stage=ArenaStage.A2,
        description="Freshly appended data slice fails the A2 acceptance test.",
    ),
    RejectionReason.OOS_FAIL: RejectionMetadata(
        reason=RejectionReason.OOS_FAIL,
        category=RejectionCategory.OOS_VALIDATION,
        severity=RejectionSeverity.BLOCKING,
        default_arena_stage=ArenaStage.A2,
        description="Out-of-sample holdout PnL / stability falls below A2 gate floor.",
    ),
    RejectionReason.REGIME_FAIL: RejectionMetadata(
        reason=RejectionReason.REGIME_FAIL,
        category=RejectionCategory.REGIME,
        severity=RejectionSeverity.BLOCKING,
        default_arena_stage=ArenaStage.A4,
        description="Regime-tagged slice fails stability across bull/bear/range regimes.",
    ),
    RejectionReason.SIGNAL_TOO_SPARSE: RejectionMetadata(
        reason=RejectionReason.SIGNAL_TOO_SPARSE,
        category=RejectionCategory.SIGNAL_DENSITY,
        severity=RejectionSeverity.BLOCKING,
        default_arena_stage=ArenaStage.A2,
        description="Signal fires too few trades for statistical significance.",
    ),
    RejectionReason.SIGNAL_TOO_DENSE: RejectionMetadata(
        reason=RejectionReason.SIGNAL_TOO_DENSE,
        category=RejectionCategory.SIGNAL_DENSITY,
        severity=RejectionSeverity.WARN,
        default_arena_stage=ArenaStage.A2,
        description="Signal fires abnormally often; likely near-always-in position.",
    ),
    RejectionReason.CORRELATION_DUPLICATE: RejectionMetadata(
        reason=RejectionReason.CORRELATION_DUPLICATE,
        category=RejectionCategory.CORRELATION,
        severity=RejectionSeverity.BLOCKING,
        default_arena_stage=ArenaStage.A2,
        description="Candidate duplicates an existing champion above correlation ceiling.",
    ),
    RejectionReason.PROMOTION_BLOCKED: RejectionMetadata(
        reason=RejectionReason.PROMOTION_BLOCKED,
        category=RejectionCategory.PROMOTION,
        severity=RejectionSeverity.BLOCKING,
        default_arena_stage=ArenaStage.A3,
        description="Promotion rule (capacity, quota, cooldown, quarantine) blocked deployment.",
    ),
    RejectionReason.GOVERNANCE_BLOCKED: RejectionMetadata(
        reason=RejectionReason.GOVERNANCE_BLOCKED,
        category=RejectionCategory.GOVERNANCE,
        severity=RejectionSeverity.FATAL,
        default_arena_stage=ArenaStage.UNKNOWN,
        description="Governance rule (weight sanity, controlled-diff, audit) rejected the write.",
    ),
    RejectionReason.UNKNOWN_REJECT: RejectionMetadata(
        reason=RejectionReason.UNKNOWN_REJECT,
        category=RejectionCategory.UNKNOWN,
        severity=RejectionSeverity.WARN,
        default_arena_stage=ArenaStage.UNKNOWN,
        description="Rejection reason could not be mapped to a canonical category.",
    ),
}


# Maps raw reject-strings emitted by existing Arena runtime (zangetsu/services/arena*.py
# and arena_gates.py as of main @ 966cd593) to canonical reasons. This mapping is
# derived by inspection of Arena source — it does NOT execute or modify Arena code.
RAW_TO_REASON: Dict[str, RejectionReason] = {
    # arena_gates.py — GateResult.reason values
    "too_few_trades": RejectionReason.SIGNAL_TOO_SPARSE,
    "non_positive_pnl": RejectionReason.COST_NEGATIVE,
    "wrong_segment_count": RejectionReason.WINDOW_INSUFFICIENT,
    # arena_pipeline.py — A1 reject counters (see stats dict at arena_pipeline.py:517)
    "reject_few_trades": RejectionReason.SIGNAL_TOO_SPARSE,
    "reject_neg_pnl": RejectionReason.COST_NEGATIVE,
    "reject_val_constant": RejectionReason.INVALID_FORMULA,
    "reject_val_error": RejectionReason.INVALID_FORMULA,
    "reject_val_few_trades": RejectionReason.SIGNAL_TOO_SPARSE,
    "reject_val_neg_pnl": RejectionReason.COST_NEGATIVE,
    "reject_val_low_sharpe": RejectionReason.LOW_BACKTEST_SCORE,
    "reject_val_low_wr": RejectionReason.LOW_BACKTEST_SCORE,
    # arena23_orchestrator.py — log strings at A2/A3 reject paths
    "alpha_invalid_or_flat": RejectionReason.INVALID_FORMULA,
    "no economically valid combos": RejectionReason.COST_NEGATIVE,
    "all ATR+TP combos non-positive": RejectionReason.COST_NEGATIVE,
    "validation split fail": RejectionReason.OOS_FAIL,
    "train/val PnL divergence": RejectionReason.OOS_FAIL,
    "zero-MAD filter": RejectionReason.SIGNAL_TOO_SPARSE,
    "alpha_compile_error": RejectionReason.INVALID_FORMULA,
    # arena13_feedback.py — weight-sanity gate
    "a13_weight_sanity_rejected": RejectionReason.GOVERNANCE_BLOCKED,
    "weight sanity REJECTED": RejectionReason.GOVERNANCE_BLOCKED,
}


def classify(
    raw_reason: Optional[str] = None,
    arena_stage: Optional[str] = None,
    hint: Optional[Mapping[str, object]] = None,
) -> Tuple[RejectionReason, RejectionCategory, ArenaStage]:
    """Classify a raw rejection into (reason, category, arena_stage).

    Never raises. Falls back to ``UNKNOWN_REJECT`` only when no deterministic
    mapping is available.

    Args:
        raw_reason: Raw reject-string from Arena runtime (case-insensitive
            substring match is used; exact key lookup is tried first).
        arena_stage: Optional hint string ("A0".."A4"). Case-insensitive.
            If metadata's default_arena_stage is UNKNOWN, this overrides it.
        hint: Optional dict with supplementary fields that may help
            classification, e.g. {"sharpe": 0.1, "trades": 3}. Not used for
            default classification but recorded for callers who want to
            extend classification in future orders.

    Returns:
        Tuple of ``(RejectionReason, RejectionCategory, ArenaStage)``.
        ``UNKNOWN_REJECT`` only when the raw_reason cannot be matched and
        no deterministic alternative exists.
    """
    stage = _parse_stage(arena_stage)
    if raw_reason is None or not str(raw_reason).strip():
        # No raw reason supplied — return UNKNOWN but preserve stage hint.
        meta = REJECTION_METADATA[RejectionReason.UNKNOWN_REJECT]
        resolved_stage = stage if stage != ArenaStage.UNKNOWN else meta.default_arena_stage
        return (RejectionReason.UNKNOWN_REJECT, meta.category, resolved_stage)

    raw_lower = str(raw_reason).strip().lower()

    # 1. Exact-key match (case-insensitive) — deterministic table lookup.
    for key, reason in RAW_TO_REASON.items():
        if key.lower() == raw_lower:
            meta = REJECTION_METADATA[reason]
            resolved_stage = stage if stage != ArenaStage.UNKNOWN else meta.default_arena_stage
            return (reason, meta.category, resolved_stage)

    # 2. Substring match (handles log-line variations like "A2 REJECTED ... too_few_trades").
    for key, reason in RAW_TO_REASON.items():
        if key.lower() in raw_lower:
            meta = REJECTION_METADATA[reason]
            resolved_stage = stage if stage != ArenaStage.UNKNOWN else meta.default_arena_stage
            return (reason, meta.category, resolved_stage)

    # 3. Fallback: UNKNOWN_REJECT with whatever stage we could infer.
    meta = REJECTION_METADATA[RejectionReason.UNKNOWN_REJECT]
    return (RejectionReason.UNKNOWN_REJECT, meta.category, stage)


def _parse_stage(raw: Optional[str]) -> ArenaStage:
    """Parse a string into an ``ArenaStage``; return UNKNOWN if unparseable."""
    if not raw:
        return ArenaStage.UNKNOWN
    s = str(raw).strip().upper()
    for st in ArenaStage:
        if s == st.value:
            return st
    # Tolerate "arena2", "A-2", "stage A2" etc.
    for st in ArenaStage:
        if st.value in s:
            return st
    return ArenaStage.UNKNOWN


def all_reasons() -> Tuple[RejectionReason, ...]:
    """Return every canonical rejection reason in declaration order."""
    return tuple(RejectionReason)


def metadata_for(reason: RejectionReason) -> RejectionMetadata:
    """Return immutable metadata for a canonical rejection reason."""
    return REJECTION_METADATA[reason]
