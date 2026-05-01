"""Compact KPI strip — terminal cards."""
from __future__ import annotations
import streamlit as st


def _kpi_card(label: str, value, sub: str | None = None, kind: str = '') -> str:
    cls = f'zt-kpi {kind}'.strip()
    val = 'NO DATA' if value is None else value
    if value is None:
        cls += ' zt-na'
    sub_html = f'<div class="sub">{sub}</div>' if sub else ''
    return f'<div class="{cls}"><div class="label">{label}</div><div class="val">{val}</div>{sub_html}</div>'


def render(ov, surv_count: int | None, near_count: int | None,
           dominant_reject: str | None) -> None:
    pass_rate = None
    if ov.passed is not None and ov.candidates_total:
        pass_rate = f'{(ov.passed / max(1, ov.candidates_total)) * 100:.2f}%'
    cards = [
        _kpi_card('CANDIDATES', ov.candidates_total),
        _kpi_card('PASSED', ov.passed, kind='zt-good' if (ov.passed or 0) > 0 else ''),
        _kpi_card('REJECTED', ov.rejected, kind='zt-bad' if (ov.rejected or 0) > 0 else ''),
        _kpi_card('NEAR', near_count if near_count is not None else 'NO DATA', kind='zt-warn'),
        _kpi_card('PASS RATE', pass_rate),
        _kpi_card('UNKNOWN_REJECT', ov.unknown_reject,
                  kind='zt-good' if ov.unknown_reject == 0 else 'zt-bad'),
        _kpi_card('NOT_EVAL', ov.not_evaluated,
                  kind='zt-good' if ov.not_evaluated == 0 else 'zt-warn'),
        _kpi_card('ERROR', ov.error,
                  kind='zt-good' if ov.error == 0 else 'zt-bad'),
        _kpi_card('DOMINANT REJ', dominant_reject or 'NO DATA'),
        _kpi_card('AXIS', ','.join(ov.axes) if ov.axes else 'NO DATA'),
    ]
    cols = st.columns(len(cards))
    for col, html in zip(cols, cards):
        col.markdown(html, unsafe_allow_html=True)
