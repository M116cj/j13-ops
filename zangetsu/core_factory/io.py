"""Shadow IO: JSONL/CSV writers under evidence-folder only."""

from __future__ import annotations

import csv
import json
import pathlib
from dataclasses import asdict
from typing import Iterable


def _ensure_dir(path: str | pathlib.Path) -> pathlib.Path:
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def write_jsonl(records: Iterable[dict], path: str | pathlib.Path) -> int:
    p = _ensure_dir(path)
    n = 0
    with p.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")
            n += 1
    return n


def write_csv(rows: Iterable[dict], path: str | pathlib.Path, fieldnames: list[str]) -> int:
    p = _ensure_dir(path)
    n = 0
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)
            n += 1
    return n


def write_json(obj: dict, path: str | pathlib.Path) -> None:
    p = _ensure_dir(path)
    with p.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
