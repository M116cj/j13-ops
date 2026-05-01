"""Sticky top status bar — terminal-style."""
from __future__ import annotations
import streamlit as st
from datetime import datetime, timezone


def _badge(state: str, text: str | None = None) -> str:
    cls = {'FRESH': 'green', 'STALE': 'yellow', 'OLD': 'red',
           'MISSING': 'gray', 'ERROR': 'red', 'OK': 'green',
           'NO DATA': 'gray', 'NOT_AVAILABLE': 'gray'}.get(state, 'gray')
    return f'<span class="badge badge-{cls}">{text or state}</span>'


def _item(label: str, value, mono: bool = True) -> str:
    val_html = f'<span class="val">{value}</span>'
    return f'<span class="item"><span class="label">{label}</span>{val_html}</span>'


def render(bv, ov, head_sha: str | None = None) -> None:
    folder = ov.folder_name or 'NO BATCH'
    gen_id = ov.generation_id or 'NO DATA'
    axis = ','.join(ov.axes) if ov.axes else 'NO DATA'
    a2 = ov.a2_min_trades if ov.a2_min_trades is not None else 'NO DATA'
    fr = bv.freshness.get('run_summary')
    fr_state = fr.state if fr else 'UNKNOWN'
    unk = ov.unknown_reject if ov.unknown_reject is not None else 'NO DATA'
    not_eval = ov.not_evaluated if ov.not_evaluated is not None else 'NO DATA'
    err = ov.error if ov.error is not None else 'NO DATA'

    parts = [
        f'<span class="item"><span class="label">ZANGETSU TERMINAL</span> <span class="val" style="font-weight:700;color:#38bdf8">v2</span></span>',
        _item('HEAD', head_sha[:8] if head_sha else 'NO DATA'),
        _item('MODE', 'SHADOW'),
        _item('AXIS', axis),
        _item('BATCH', folder),
        _item('GEN_ID', gen_id),
        _item('FRESHNESS', _badge(fr_state)),
        _item('A2_MIN_TRADES', a2),
        _item('UNKNOWN_REJECT', _badge('green' if unk == 0 else 'yellow' if isinstance(unk, int) and unk < 5 else 'red', str(unk))),
        _item('NOT_EVALUATED', _badge('green' if not_eval == 0 else 'yellow', str(not_eval))),
        _item('ERROR', _badge('green' if err == 0 else 'red', str(err))),
        _item('UTC', datetime.now(tz=timezone.utc).strftime('%H:%M:%S')),
    ]
    bar = '<div class="zt-status-bar">' + ''.join(parts) + '</div>'
    st.markdown(bar, unsafe_allow_html=True)
