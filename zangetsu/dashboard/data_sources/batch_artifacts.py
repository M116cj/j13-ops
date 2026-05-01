"""Batch artifact loader — points at the latest mining recovery folder."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import json
import pathlib

from ..config import RECOVERY_ROOT
from .parsers import ParseResult, latest_recovery_dir, parse_csv, parse_json, parse_jsonl
from .runtime_health import FreshnessReport, freshness_for


REQUIRED_FILES = (
    ('candidate_manifest', 'candidate_manifest.jsonl', parse_jsonl),
    ('shadow_batch_results', 'shadow_batch_results.jsonl', parse_jsonl),
    ('reject_reason_summary', 'reject_reason_summary.json', parse_json),
    ('long_short_summary', 'long_short_summary.csv', parse_csv),
    ('survivor_report', 'survivor_report.csv', parse_csv),
    ('near_survivor_report', 'near_survivor_report.csv', parse_csv),
    ('feedback_weights', 'feedback_weights.json', parse_json),
    ('next_batch_weights', 'next_batch_weights.json', parse_json),
    ('formula_collision_report', 'formula_collision_report.csv', parse_csv),
    ('axis_scoreboard', 'axis_scoreboard.csv', parse_csv),
    ('run_summary', 'run_summary.json', parse_json),
)


@dataclass
class BatchView:
    folder: Optional[pathlib.Path]
    folder_name: Optional[str]
    artifacts: dict[str, ParseResult]
    freshness: dict[str, FreshnessReport]
    run_summary_raw: Optional[dict]


def load_latest_batch() -> BatchView:
    folder = latest_recovery_dir(RECOVERY_ROOT, name_glob='*-shadow*')
    if folder is None:
        # Fall back to most-recent folder of any kind under recovery
        folder = latest_recovery_dir(RECOVERY_ROOT, name_glob='*')
    return load_batch_from_folder(folder)


def load_batch_from_folder(folder: Optional[pathlib.Path]) -> BatchView:
    if folder is None:
        return BatchView(folder=None, folder_name=None,
                         artifacts={}, freshness={}, run_summary_raw=None)
    out_dir = folder / 'shadow_outputs'
    artifacts: dict[str, ParseResult] = {}
    freshness: dict[str, FreshnessReport] = {}
    for key, filename, parser in REQUIRED_FILES:
        p = out_dir / filename
        artifacts[key] = parser(p)
        freshness[key] = freshness_for(p)
    # Load run_summary as raw dict for KPI cards (artifacts['run_summary'] is the json_normalize variant).
    rs_path = out_dir / 'run_summary.json'
    raw = None
    if rs_path.exists():
        try:
            with rs_path.open('r', encoding='utf-8') as f:
                raw = json.load(f)
        except Exception:
            raw = None
    return BatchView(folder=folder, folder_name=folder.name,
                     artifacts=artifacts, freshness=freshness,
                     run_summary_raw=raw)


def list_recovery_folders() -> list[pathlib.Path]:
    p = pathlib.Path(RECOVERY_ROOT)
    if not p.exists():
        return []
    return sorted([d for d in p.iterdir() if d.is_dir()], key=lambda d: d.name)
