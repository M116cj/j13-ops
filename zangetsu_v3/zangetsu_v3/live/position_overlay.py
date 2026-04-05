"""Position overlay for 13-state fine regime.

Certain short-lived or dangerous regimes reduce position size
via damper multipliers applied to the base position.
"""

from zangetsu_v3.regime.rule_labeler import Regime

__all__ = ["OVERLAY_DAMPERS", "position_overlay"]

OVERLAY_DAMPERS = {
    Regime.CHOPPY_VOLATILE:  0.5,   # half size
    Regime.TOPPING:          0.3,   # major reduction
    Regime.BOTTOMING:        0.3,
    Regime.LIQUIDITY_CRISIS: 0.0,   # completely stop
    Regime.PARABOLIC:        0.3,
}


def position_overlay(fine_regime: int, base_size: float) -> float:
    """Apply damper based on 13-state fine regime.

    Returns adjusted position size.
    """
    damper = OVERLAY_DAMPERS.get(fine_regime, 1.0)
    return base_size * damper
