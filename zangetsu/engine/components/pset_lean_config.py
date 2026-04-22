"""Lean pset configuration — CD-05 hygiene.

Evidence: all 1551 champion_legacy_archive survivors used 0 indicator terminals.
GP was sampling from 126 terminal dead zone (21 indicators x 6 periods).

This module defines a reduced terminal set keeping only indicators + periods
referenced by hand/zoo formulas. 53 terminals vs 131 full (60% reduction).

Activation: set env ZANGETSU_PSET_MODE=lean before AlphaEngine init.
Default (unset or any other value) = full mode, no behavior change.

Safety: alpha_engine.py gates the switch behind env var. If this file is
missing, engine falls back to full mode.
"""
from __future__ import annotations

# Indicators referenced by scripts/alpha_zoo_injection.py (translated zoo)
# + scripts/cold_start_hand_alphas.py + scripts/seed_hand_alphas.yaml (hand set).
# Excluded (never referenced by any live/archive/hand/zoo formula):
#   cci, ppo, cmo, trix, mfi, realized_vol,
#   funding_rate, oi_change, oi_divergence
LEAN_INDICATOR_NAMES = [
    "rsi",
    "stochastic_k",
    "bollinger_bw",
    "funding_zscore",
    "vwap",
    "vwap_deviation",
    "normalized_atr",
    "obv",
    "relative_volume",
    "roc",
    "tsi",
    "zscore",
]

# Periods referenced by hand + zoo formulas. 7 and 30 never appear.
LEAN_PERIODS = [14, 20, 50, 100]

# OHLCV stays identical to full mode.
# Lean pset size: 12 indicators x 4 periods + 5 OHLCV = 53 terminals.
