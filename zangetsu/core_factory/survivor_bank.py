"""Survivor / near-survivor classification.

Rules (per order §6, §8):
- Survivor = status == PASSED.
- Near-survivor = status == REJECTED with non_positive_net AND net_bps within
  NEAR_SURVIVOR_NET_BPS_FLOOR of break-even. (i.e. -5 bps <= net_bps <= 0)
- NOT_EVALUATED candidates cannot be survivors or near-survivors.
- ERROR candidates cannot be survivors or near-survivors.
"""

from __future__ import annotations

from typing import Iterable

from .constants import NEAR_SURVIVOR_NET_BPS_FLOOR


def is_survivor(row: dict) -> bool:
    return row.get('status') == 'PASSED'


def is_near_survivor(row: dict) -> bool:
    if row.get('status') != 'REJECTED':
        return False
    net = float(row.get('net_bps', 0.0))
    return NEAR_SURVIVOR_NET_BPS_FLOOR <= net <= 0.0


def split_survivors(rows: Iterable[dict]) -> dict:
    survivors: list[dict] = []
    near: list[dict] = []
    for r in rows:
        if is_survivor(r):
            survivors.append(r)
        elif is_near_survivor(r):
            near.append(r)
    return {'survivors': survivors, 'near_survivors': near}
