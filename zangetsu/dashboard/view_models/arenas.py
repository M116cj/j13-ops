"""Arena view-models. A1/A2 pull from shadow_batch_results; A3/A4/A5 NO_DATA in shadow."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class ArenaSummary:
    name: str
    state: str  # OK | NOT_AVAILABLE | NO_DATA
    n_received: Optional[int]
    n_passed: Optional[int]
    n_rejected: Optional[int]
    n_not_evaluated: Optional[int]
    n_error: Optional[int]
    pass_rate: Optional[float]
    reject_rate: Optional[float]
    dominant_reject_reason: Optional[str]
    side_split: Optional[dict]
    by_symbol: Optional[pd.DataFrame]
    note: Optional[str] = None


def build_a1(batch_view) -> ArenaSummary:
    art = batch_view.artifacts.get('shadow_batch_results')
    if art is None or art.state != 'OK':
        return ArenaSummary('A1', 'NO_DATA', None, None, None, None, None, None, None,
                            None, None, None, note=art.note if art else 'no_artifact')
    df = art.rows
    if df is None or df.empty:
        return ArenaSummary('A1', 'NO_DATA', 0, 0, 0, 0, 0, 0.0, 0.0, None, None, None,
                            note='empty_results')
    n = len(df)
    a1_pass = (df['a1_pass'] == True).sum() if 'a1_pass' in df.columns else None
    n_pass = int(a1_pass) if a1_pass is not None else None
    n_rej = int(n - n_pass) if n_pass is not None else None
    by_symbol = df.groupby('symbol').size().reset_index(name='n') if 'symbol' in df.columns else None
    side_split = df['intended_side_mode'].value_counts().to_dict() if 'intended_side_mode' in df.columns else {}
    return ArenaSummary('A1', 'OK', n, n_pass, n_rej, 0, 0,
                        n_pass / n if n_pass is not None else None,
                        n_rej / n if n_rej is not None else None,
                        None, side_split, by_symbol)


def build_a2(batch_view) -> ArenaSummary:
    art = batch_view.artifacts.get('shadow_batch_results')
    if art is None or art.state != 'OK':
        return ArenaSummary('A2', 'NO_DATA', None, None, None, None, None, None, None,
                            None, None, None, note=art.note if art else 'no_artifact')
    df = art.rows
    if df is None or df.empty:
        return ArenaSummary('A2', 'NO_DATA', 0, 0, 0, 0, 0, 0.0, 0.0, None, None, None,
                            note='empty_results')
    n = len(df)
    n_pass = int((df['status'] == 'PASSED').sum())
    n_rej = int((df['status'] == 'REJECTED').sum())
    n_not = int((df['status'] == 'NOT_EVALUATED').sum())
    n_err = int((df['status'] == 'ERROR').sum())
    rejected = df[df['status'] == 'REJECTED']
    dominant = (rejected['reject_reason'].value_counts().idxmax()
                if 'reject_reason' in rejected.columns and not rejected.empty else None)
    by_symbol = df.groupby('symbol').agg(
        n=('candidate_id', 'count'),
        passed=('status', lambda s: (s == 'PASSED').sum()),
        rejected=('status', lambda s: (s == 'REJECTED').sum()),
    ).reset_index() if 'symbol' in df.columns else None
    side_split = df['intended_side_mode'].value_counts().to_dict() if 'intended_side_mode' in df.columns else {}
    return ArenaSummary('A2', 'OK', n, n_pass, n_rej, n_not, n_err,
                        n_pass / n, n_rej / n, dominant, side_split, by_symbol)


def build_a3(batch_view) -> ArenaSummary:
    """A3 requires segmented holdout; not present in 0-9AB/AC/AD shadow runs."""
    return ArenaSummary('A3', 'NOT_AVAILABLE', None, None, None, None, None, None, None,
                        None, None, None, note='A3 segmented holdout not run in current SHADOW orders')
