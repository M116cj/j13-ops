"""Typed parsers for shadow_outputs artifacts. Empty-state preserving."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import csv
import json
import pathlib

import pandas as pd


@dataclass
class ParseResult:
    path: pathlib.Path
    state: str  # OK | EMPTY | MISSING | ERROR
    rows: Optional[pd.DataFrame]
    note: Optional[str] = None


def _missing(p: pathlib.Path) -> ParseResult:
    return ParseResult(p, 'MISSING', None, note='file_not_found')


def parse_jsonl(p: pathlib.Path) -> ParseResult:
    p = pathlib.Path(p)
    if not p.exists():
        return _missing(p)
    rows = []
    try:
        with p.open('r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
    except Exception as exc:
        return ParseResult(p, 'ERROR', None, note=f'parse_error:{exc}')
    if not rows:
        return ParseResult(p, 'EMPTY', pd.DataFrame())
    df = pd.DataFrame(rows)
    return ParseResult(p, 'OK', df)


def parse_csv(p: pathlib.Path) -> ParseResult:
    p = pathlib.Path(p)
    if not p.exists():
        return _missing(p)
    try:
        df = pd.read_csv(p)
    except Exception as exc:
        return ParseResult(p, 'ERROR', None, note=f'parse_error:{exc}')
    if df.empty:
        return ParseResult(p, 'EMPTY', df)
    return ParseResult(p, 'OK', df)


def parse_json(p: pathlib.Path) -> ParseResult:
    p = pathlib.Path(p)
    if not p.exists():
        return _missing(p)
    try:
        with p.open('r', encoding='utf-8') as f:
            obj = json.load(f)
    except Exception as exc:
        return ParseResult(p, 'ERROR', None, note=f'parse_error:{exc}')
    if not obj:
        return ParseResult(p, 'EMPTY', pd.DataFrame())
    # Normalize JSON to a single-row DataFrame for convenience.
    df = pd.json_normalize(obj)
    return ParseResult(p, 'OK', df)


def latest_recovery_dir(recovery_root: pathlib.Path, name_glob: str = '*') -> Optional[pathlib.Path]:
    """Return the most recent recovery folder matching name_glob, or None."""
    p = pathlib.Path(recovery_root)
    if not p.exists():
        return None
    candidates = sorted([d for d in p.glob(name_glob) if d.is_dir()],
                        key=lambda d: d.name, reverse=True)
    return candidates[0] if candidates else None
