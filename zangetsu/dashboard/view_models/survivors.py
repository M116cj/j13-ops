"""Survivor / Near-Survivor — strict separation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class SurvivorView:
    state: str
    survivors: Optional[pd.DataFrame]   # strictly status == PASSED
    near_survivors: Optional[pd.DataFrame]  # strictly REJECTED with -5<=net<=0
    note: Optional[str] = None


def build_survivors(batch_view) -> SurvivorView:
    surv_art = batch_view.artifacts.get('survivor_report')
    near_art = batch_view.artifacts.get('near_survivor_report')
    if (surv_art is None or surv_art.state == 'MISSING' or
            near_art is None or near_art.state == 'MISSING'):
        return SurvivorView('NO_DATA', None, None, note='survivor_artifact_missing')
    survivors = surv_art.rows if surv_art.state in {'OK', 'EMPTY'} else None
    near = near_art.rows if near_art.state in {'OK', 'EMPTY'} else None
    return SurvivorView('OK', survivors, near)
