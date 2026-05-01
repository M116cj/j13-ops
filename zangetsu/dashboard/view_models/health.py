"""System health view-model: per-source freshness + parser state + last refresh time."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timezone


@dataclass
class HealthRow:
    source_key: str
    path: str
    parse_state: str
    freshness_state: str
    age_seconds: Optional[float]
    mtime_iso: Optional[str]
    note: Optional[str] = None


def build_health(batch_view) -> list[HealthRow]:
    rows: list[HealthRow] = []
    for key, art in batch_view.artifacts.items():
        fr = batch_view.freshness.get(key)
        rows.append(HealthRow(
            source_key=key,
            path=str(art.path),
            parse_state=art.state,
            freshness_state=(fr.state if fr else 'UNKNOWN'),
            age_seconds=(fr.age_seconds if fr else None),
            mtime_iso=(fr.mtime_iso if fr else None),
            note=(art.note or (fr.note if fr else None)),
        ))
    return rows


def now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec='seconds')
