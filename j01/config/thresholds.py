"""J01 threshold bundle (v0.1.0 — 2026-04-20).

All threshold changes require a matching decision record under
`j01/docs/decisions/`. Runtime overrides go through env vars
(`J01_<THRESHOLD_NAME>`) which the Zangetsu engine's config loader
reads; hard-coded defaults live here.
"""
from __future__ import annotations


# ── Fitness (consumed by j01/fitness.py) ──────────────────────────────
MIN_HALF_BARS = 100
MIN_ABS_IC = 5e-3
EPSILON_FLOOR = 1e-6
HEIGHT_PENALTY = 1e-3


# ── A2: OOS PnL gate on holdout first 1/3 ─────────────────────────────
A2_MIN_TRADES = 25
A2_MIN_TOTAL_PNL = 0.0


# ── A3: time-segment stability on holdout middle 1/3, 5 equal segments ─
A3_SEGMENTS = 5
A3_MIN_TRADES_PER_SEGMENT = 15
A3_WR_FLOOR = 0.45
A3_MIN_WR_PASSES = 4
A3_MIN_PNL_PASSES = 4


# ── A4: regime stability on holdout last 1/3 ──────────────────────────
A4_REGIME_WR_FLOOR = 0.40
A4_MIN_TRADES_PER_REGIME = 10
A4_MIN_OTHER_REGIMES_PASS = 1


# ── A5: 14-day live paper-trade shadow ────────────────────────────────
A5_WINDOW_DAYS = 14
A5_MIN_TRADES = 30
A5_WR_FLOOR = 0.45
A5_MIN_TOTAL_PNL = 0.0
A5_MAX_CONSECUTIVE_NEG_DAYS = 3


# ── Execution / horizon ──────────────────────────────────────────────
ALPHA_FORWARD_HORIZON = 60        # bars, matches alpha_signal.min_hold
COST_BPS = 5.0                    # round-trip cost in basis points
MAX_HOLD_BARS = 120                # 2x forward horizon; v0.7.2 horizon alignment
