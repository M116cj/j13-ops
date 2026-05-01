"""Candidate Explorer view-model with filters."""
from __future__ import annotations

import pandas as pd


def candidates_dataframe(batch_view) -> pd.DataFrame:
    art = batch_view.artifacts.get('shadow_batch_results')
    if art is None or art.state != 'OK' or art.rows is None:
        return pd.DataFrame()
    return art.rows.copy()


def apply_filters(df: pd.DataFrame, *, axis=None, status=None, symbol=None,
                  side_mode=None, reject_reason=None, search=None) -> pd.DataFrame:
    if df.empty:
        return df
    out = df
    if axis:
        out = out[out['axis_id'] == axis]
    if status:
        out = out[out['status'] == status]
    if symbol:
        out = out[out['symbol'] == symbol]
    if side_mode:
        out = out[out['intended_side_mode'] == side_mode]
    if reject_reason:
        out = out[out['reject_reason'] == reject_reason]
    if search:
        s = str(search).lower()
        mask = (out['candidate_id'].astype(str).str.lower().str.contains(s, na=False)
                | out['alpha_hash'].astype(str).str.lower().str.contains(s, na=False))
        out = out[mask]
    return out
