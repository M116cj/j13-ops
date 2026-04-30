"""zangetsu.core_factory — 0-9AB shadow tournament package.

Shadow-only. Production runtime must NOT import this package.
"""

from .constants import (
    A2_MIN_TRADES,
    AXIS_IDS,
    AXIS_ROLES,
    GENERATION_ID_DEFAULT,
    ROUND_TRIP_COST_BPS,
)

__all__ = [
    'A2_MIN_TRADES',
    'AXIS_IDS',
    'AXIS_ROLES',
    'GENERATION_ID_DEFAULT',
    'ROUND_TRIP_COST_BPS',
]
