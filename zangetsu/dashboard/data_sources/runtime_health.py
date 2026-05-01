"""Freshness logic — never zero, never silent."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import os
import pathlib
import time

from ..config import FRESH_AGE_S, STALE_AGE_S


@dataclass
class FreshnessReport:
    path: str
    exists: bool
    state: str  # FRESH | STALE | MISSING | ERROR
    age_seconds: Optional[float]
    mtime_iso: Optional[str]
    note: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'path': self.path, 'exists': self.exists, 'state': self.state,
            'age_seconds': self.age_seconds, 'mtime_iso': self.mtime_iso,
            'note': self.note,
        }


def freshness_for(p: pathlib.Path) -> FreshnessReport:
    p = pathlib.Path(p)
    if not p.exists():
        return FreshnessReport(str(p), False, 'MISSING', None, None,
                               note='file_not_found')
    try:
        st = p.stat()
        age = time.time() - st.st_mtime
        from datetime import datetime, timezone
        mtime_iso = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
        if age <= FRESH_AGE_S:
            state = 'FRESH'
        elif age <= STALE_AGE_S:
            state = 'STALE'
        else:
            state = 'OLD'
        return FreshnessReport(str(p), True, state, age, mtime_iso)
    except OSError as exc:
        return FreshnessReport(str(p), False, 'ERROR', None, None, note=str(exc))
