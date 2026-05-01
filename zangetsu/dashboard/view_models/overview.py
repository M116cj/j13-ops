"""Overview view-model: build KPI cards + funnel from BatchView."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class OverviewKpis:
    folder_name: Optional[str]
    generation_id: Optional[str]
    axes: list[str]
    timeframe: Optional[str]
    a2_min_trades: Optional[int]
    candidates_total: Optional[int]
    passed: Optional[int]
    rejected: Optional[int]
    not_evaluated: Optional[int]
    error: Optional[int]
    unknown_reject: Optional[int]
    overall_feedback_status: Optional[str]
    duration_seconds: Optional[float]
    state: str  # OK | NO_DATA | ERROR


def build_overview(batch_view) -> OverviewKpis:
    rs = batch_view.run_summary_raw
    if rs is None:
        return OverviewKpis(
            folder_name=batch_view.folder_name,
            generation_id=None, axes=[], timeframe=None, a2_min_trades=None,
            candidates_total=None, passed=None, rejected=None,
            not_evaluated=None, error=None, unknown_reject=None,
            overall_feedback_status=None, duration_seconds=None,
            state='NO_DATA',
        )
    summary = rs.get('overall_reject_summary', {}) or {}
    return OverviewKpis(
        folder_name=batch_view.folder_name,
        generation_id=rs.get('generation_id'),
        axes=list(rs.get('axes', []) or []),
        timeframe=rs.get('timeframe'),
        a2_min_trades=rs.get('a2_min_trades'),
        candidates_total=rs.get('candidates_total'),
        passed=summary.get('passed_total'),
        rejected=summary.get('rejected_total'),
        not_evaluated=summary.get('not_evaluated_total'),
        error=summary.get('error_total'),
        unknown_reject=summary.get('unknown_reject_count'),
        overall_feedback_status=rs.get('overall_feedback_status'),
        duration_seconds=rs.get('evaluation_seconds'),
        state='OK',
    )
