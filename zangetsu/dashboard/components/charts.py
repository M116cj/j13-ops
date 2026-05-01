"""Reusable Plotly figures for the dashboard."""
from __future__ import annotations
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px


def funnel_chart(stages: list[tuple[str, int]]) -> go.Figure:
    if not stages:
        return go.Figure()
    fig = go.Figure(go.Funnel(
        y=[s[0] for s in stages], x=[s[1] for s in stages],
        textinfo='value+percent initial',
    ))
    fig.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=300)
    return fig


def bar_top_n(items: dict, *, title: str, n: int = 10, orient: str = 'h') -> go.Figure:
    if not items:
        return go.Figure().update_layout(title=f'{title} (no data)')
    pairs = sorted(items.items(), key=lambda kv: kv[1], reverse=True)[:n]
    labels = [str(p[0]) for p in pairs]
    values = [p[1] for p in pairs]
    if orient == 'h':
        fig = go.Figure(go.Bar(y=labels, x=values, orientation='h'))
        fig.update_layout(yaxis={'categoryorder': 'total ascending'})
    else:
        fig = go.Figure(go.Bar(x=labels, y=values))
    fig.update_layout(title=title, margin=dict(l=20, r=20, t=40, b=20), height=320)
    return fig


def status_donut(counts: dict) -> go.Figure:
    if not counts:
        return go.Figure().update_layout(title='Status (no data)')
    labels = list(counts.keys())
    values = [counts[k] for k in labels]
    fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.55))
    fig.update_layout(title='Candidate status', margin=dict(l=20, r=20, t=40, b=20), height=320)
    return fig


def reject_reason_stacked(df: pd.DataFrame, group_col: str, count_col: str = 'n',
                          reason_col: str = 'reject_reason') -> go.Figure:
    if df is None or df.empty:
        return go.Figure().update_layout(title='Reject reasons (no data)')
    fig = px.bar(df, x=group_col, y=count_col, color=reason_col, barmode='stack')
    fig.update_layout(margin=dict(l=20, r=20, t=40, b=20), height=380)
    return fig
