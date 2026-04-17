"""Zangetsu V9 Market State — Five-factor market description layer.

Provides the MarketState dataclass and the v2 regime detection engine.
The 13-regime framework is preserved; detection is rebuilt on 5 factors:
momentum, volatility, volume, funding rate, open interest.
"""
from dataclasses import dataclass, field
from typing import Optional
import numpy as np


# ═══════════════════════════════════════════════════════════════════
# L1 Macro Constraints (unchanged from arena_pipeline.py)
# ═══════════════════════════════════════════════════════════════════

L1_ALLOWED = {
    "BULL":    ["BULL_TREND","BULL_PULLBACK","DISTRIBUTION","TOPPING","CONSOLIDATION","SQUEEZE","PARABOLIC"],
    "BEAR":    ["BEAR_TREND","BEAR_RALLY","ACCUMULATION","BOTTOMING","CONSOLIDATION","SQUEEZE","LIQUIDITY_CRISIS"],
    "NEUTRAL": ["CONSOLIDATION","CHOPPY_VOLATILE","SQUEEZE"],
}

ALL_REGIMES = [
    "BULL_TREND", "BEAR_TREND", "CONSOLIDATION", "BULL_PULLBACK", "BEAR_RALLY",
    "ACCUMULATION", "DISTRIBUTION", "SQUEEZE", "CHOPPY_VOLATILE",
    "TOPPING", "BOTTOMING", "LIQUIDITY_CRISIS", "PARABOLIC",
]


@dataclass
class MarketState:
    """Per-bar five-factor market state snapshot."""
    # Bounded scores
    momentum: float = 0.0       # [-1, 1]
    volatility: float = 0.0     # [0, 1]
    volume: float = 0.0         # [0, 1]
    funding: float = 0.0        # [-1, 1]
    open_interest: float = 0.0  # [-1, 1]

    # Data availability
    has_funding: bool = False
    has_oi: bool = False

    # Extreme flags
    ext_vol: bool = False
    ext_move: bool = False
    ext_fund: bool = False
    ext_oi: bool = False

    # Regime output
    regime: str = "CONSOLIDATION"
    regime_l1: str = "NEUTRAL"
    regime_confidence: float = 0.0

    def to_dict(self) -> dict:
        """Serialize for champion passport storage."""
        return {
            "regime": self.regime,
            "regime_confidence": round(self.regime_confidence, 3),
            "regime_l1": self.regime_l1,
            "factors": {
                "mom": round(self.momentum, 3),
                "vol": round(self.volatility, 3),
                "vm": round(self.volume, 3),
                "fund": round(self.funding, 3),
                "oi": round(self.open_interest, 3),
            },
            "has_funding": self.has_funding,
            "has_oi": self.has_oi,
            "extreme": {
                "vol": self.ext_vol,
                "move": self.ext_move,
                "fund": self.ext_fund,
                "oi": self.ext_oi,
            },
        }


def get_current_regime_v2(
    mom: float,
    vol: float,
    vm: float,
    fund: Optional[float],
    oi: Optional[float],
    ext_flags: dict,
) -> tuple:
    """Five-factor regime detection.

    Args:
        mom: momentum score [-1, 1]
        vol: volatility score [0, 1]
        vm: volume score [0, 1]
        fund: funding score [-1, 1] or None (spot)
        oi: open interest score [-1, 1] or None (spot)
        ext_flags: dict of bool (ext_vol, ext_move, ext_fund, ext_oi)

    Returns:
        (regime: str, l1: str, confidence: float)
    """
    f = fund if fund is not None else 0.0
    o = oi if oi is not None else 0.0
    has_deriv = fund is not None and oi is not None

    ext_v = ext_flags.get("ext_vol", False)
    ext_m = ext_flags.get("ext_move", False)
    ext_f = ext_flags.get("ext_fund", False)

    # ── L1: Macro direction ──
    if mom > 0.3:
        l1 = "BULL"
    elif mom < -0.3:
        l1 = "BEAR"
    else:
        l1 = "NEUTRAL"

    # ── L2: 5-factor rule engine (ordered by specificity) ──

    # --- Extreme regimes (must check first) ---
    if mom > 0.7 and vol > 0.8 and vm > 0.7:
        regime, conf = "PARABOLIC", min(mom, vol, vm)
    elif mom < -0.7 and vol > 0.8 and vm > 0.7:
        regime, conf = "LIQUIDITY_CRISIS", min(abs(mom), vol, vm)

    # --- Derivative-dependent (funding + OI required) ---
    elif has_deriv and 0.1 < mom < 0.5 and f > 0.5 and o < -0.3 and vm > 0.5:
        regime, conf = "DISTRIBUTION", (f + abs(o) + vm) / 3
    elif has_deriv and 0.0 < mom < 0.4 and vol > 0.4 and f > 0.3 and o < 0.0:
        regime, conf = "TOPPING", (f + vol) / 2
    elif has_deriv and -0.5 < mom < -0.1 and f < -0.5 and o > 0.3 and vm > 0.5:
        regime, conf = "ACCUMULATION", (abs(f) + o + vm) / 3
    elif has_deriv and -0.4 < mom < 0.0 and vol < 0.4 and f < -0.3 and o > 0.0:
        regime, conf = "BOTTOMING", (abs(f) + abs(o)) / 2

    # --- Volatility-defined ---
    elif vol < 0.15 and abs(mom) < 0.2 and oi is not None and o > 0.3:
        regime, conf = "SQUEEZE", (1 - vol) * 0.5 + o * 0.5
    elif vol > 0.6 and abs(mom) < 0.3:
        regime, conf = "CHOPPY_VOLATILE", vol

    # --- Trend regimes ---
    elif mom > 0.5:
        regime, conf = "BULL_TREND", mom
    elif mom < -0.5:
        regime, conf = "BEAR_TREND", abs(mom)
    elif 0.1 < mom <= 0.5:
        regime, conf = "BULL_PULLBACK", mom
    elif -0.5 <= mom < -0.1:
        regime, conf = "BEAR_RALLY", abs(mom)

    # --- Default ---
    else:
        regime, conf = "CONSOLIDATION", max(0.1, 1 - abs(mom) - vol)

    # ── L1 constraint enforcement ──
    allowed = L1_ALLOWED.get(l1, [])
    if regime not in allowed:
        regime, conf = "CONSOLIDATION", conf * 0.5

    # ── Extreme flag override ──
    if regime == "CONSOLIDATION" and (ext_v or ext_m):
        regime = "CHOPPY_VOLATILE"
        conf = vol

    return regime, l1, float(np.clip(conf, 0.0, 1.0))


def build_market_state(
    mom: float,
    vol: float,
    vm: float,
    fund: Optional[float],
    oi: Optional[float],
    ext_flags: dict,
) -> MarketState:
    """Build a complete MarketState from pre-computed factor scores."""
    regime, l1, conf = get_current_regime_v2(mom, vol, vm, fund, oi, ext_flags)
    return MarketState(
        momentum=mom,
        volatility=vol,
        volume=vm,
        funding=fund if fund is not None else 0.0,
        open_interest=oi if oi is not None else 0.0,
        has_funding=fund is not None,
        has_oi=oi is not None,
        ext_vol=ext_flags.get("ext_vol", False),
        ext_move=ext_flags.get("ext_move", False),
        ext_fund=ext_flags.get("ext_fund", False),
        ext_oi=ext_flags.get("ext_oi", False),
        regime=regime,
        regime_l1=l1,
        regime_confidence=conf,
    )
