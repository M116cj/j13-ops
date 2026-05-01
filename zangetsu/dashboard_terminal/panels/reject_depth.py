"""Reject-depth panel — looks like an order-book depth ladder."""
from __future__ import annotations
import streamlit as st


def render(rs_summary: dict | None) -> None:
    st.markdown('<div class="zt-card-title" style="margin-top:6px;">Reject depth</div>',
                unsafe_allow_html=True)
    if not rs_summary:
        st.markdown('<div class="zt-muted zt-mono" style="font-size:12px;">NO DATA</div>',
                    unsafe_allow_html=True)
        return
    overall = rs_summary.get('overall', {})
    by_reason = overall.get('rejected_by_reason') or {}
    total = sum(by_reason.values()) or 1
    rows = sorted(by_reason.items(), key=lambda kv: kv[1], reverse=True)
    html = ['<div class="zt-card">']
    for reason, count in rows:
        share = count / total
        bar_w = max(2.0, share * 100)
        pct = f'{share * 100:.1f}%'
        html.append(
            f'<div class="zt-depth-row">'
            f'<span class="lbl">{reason}</span>'
            f'<span class="bar-wrap"><span class="bar" style="width:{bar_w:.1f}%"></span></span>'
            f'<span class="pct">{pct} <span class="zt-muted">({count})</span></span>'
            f'</div>'
        )
    unk = overall.get('unknown_reject_count', 0)
    html.append(
        f'<div class="zt-depth-row" style="margin-top:6px;">'
        f'<span class="lbl zt-muted">UNKNOWN_REJECT</span>'
        f'<span class="bar-wrap"></span>'
        f'<span class="pct"><span class="zt-tag {("zt-tag-pass" if unk == 0 else "zt-tag-rej")}">{unk}</span></span>'
        f'</div>'
    )
    html.append('</div>')
    st.markdown(''.join(html), unsafe_allow_html=True)
