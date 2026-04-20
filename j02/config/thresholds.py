"""J02 threshold bundle (v0.1.0 — 2026-04-20).

Starts with defaults matching J01; diverges as observed behavior
accumulates. Changes require a `j02/docs/decisions/` ADR.
"""
from __future__ import annotations


# ── Fitness (consumed by j02/fitness.py) ──────────────────────────────
K_FOLDS = 5
MIN_FOLD_BARS = 100
MIN_ABS_IC = 3e-3
LAMBDA_STD = 1.0
HEIGHT_PENALTY = 1e-3


# ── A2 ────────────────────────────────────────────────────────────────
A2_MIN_TRADES = 25
A2_MIN_TOTAL_PNL = 0.0


# ── A3 ────────────────────────────────────────────────────────────────
A3_SEGMENTS = 5
A3_MIN_TRADES_PER_SEGMENT = 15
A3_WR_FLOOR = 0.45
A3_MIN_WR_PASSES = 4
A3_MIN_PNL_PASSES = 4


# ── A4 ────────────────────────────────────────────────────────────────
A4_REGIME_WR_FLOOR = 0.40
A4_MIN_TRADES_PER_REGIME = 10
A4_MIN_OTHER_REGIMES_PASS = 1


# ── A5 ────────────────────────────────────────────────────────────────
A5_WINDOW_DAYS = 14
A5_MIN_TRADES = 30
A5_WR_FLOOR = 0.45
A5_MIN_TOTAL_PNL = 0.0
A5_MAX_CONSECUTIVE_NEG_DAYS = 3


# ── Execution / horizon ──────────────────────────────────────────────
ALPHA_FORWARD_HORIZON = 60
COST_BPS = 5.0
MAX_HOLD_BARS = 60
