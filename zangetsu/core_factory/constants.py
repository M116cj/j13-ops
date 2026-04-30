"""Constants for the 0-9AB core factory shadow tournament.

Shadow-only. Not imported by production runtime.
"""

from __future__ import annotations

GENERATION_ID_DEFAULT: str = "0-9ab-shadow-v1"

A2_MIN_TRADES: int = 25  # Mirrors zangetsu.services.arena_gates; never override.

DEFAULT_SYMBOLS: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
DEFAULT_TIMEFRAME: str = "15m"

CANDIDATES_PER_AXIS_DEFAULT: int = 128
UNIQUE_FORMULA_TARGET_PER_AXIS: int = 32

ROUND_TRIP_COST_BPS: float = 14.5  # From 0-9Z structural cost feasibility
NEAR_SURVIVOR_NET_BPS_FLOOR: float = -5.0  # within 5 bps of break-even

AXIS_IDS: tuple[str, ...] = ("H", "C", "D", "E", "A")
AXIS_ROLES: dict[str, str] = {
    "H": "primary",
    "C": "shadow",
    "D": "shadow",
    "E": "fallback",
    "A": "deferred",
}

ALLOWED_BLOCKER_REASONS: tuple[str, ...] = (
    "GENERATOR_PATH_BLOCKED",
    "COMBINATION_GRAMMAR_BLOCKED",
    "AXIS_COMPONENT_UNAVAILABLE",
    "INVALID_CANDIDATE",
    "UNSUPPORTED_OPERATOR",
    "ECONOMIC_ARENA_HANDOFF_BLOCKED",
    "SAFE_EVALUATION_MODE_UNAVAILABLE",
    "RESULT_REPORTING_BLOCKED",
)

ALLOWED_FINAL_VERDICTS: tuple[str, ...] = (
    "AXIS_H_SELECTED_FOR_SCALEUP",
    "AXIS_C_SELECTED_FOR_SCALEUP",
    "AXIS_D_SELECTED_FOR_SCALEUP",
    "MULTI_AXIS_CONTINUE_ONE_MORE_ROUND",
    "CORE_FACTORY_PATH_BLOCKED",
    "ALL_AXES_FAIL_ECONOMIC_ARENA",
    "RESTORE_ABORTED_FOR_FORBIDDEN_DIFF",
)
