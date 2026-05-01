"""Arena funnel: Generated → A1 → A2 → Survivors → Near-survivors.

A3+ shown as NOT_REACHED if no data — never as 0.
"""
from __future__ import annotations
import plotly.graph_objects as go
import streamlit as st


def render(bv, ov, a1, a2) -> None:
    st.markdown('<div class="zt-card"><div class="zt-card-title">Arena funnel</div></div>',
                unsafe_allow_html=True)
    n_total = ov.candidates_total or 0
    n_a1_in = a1.n_received or 0
    n_a1_pass = a1.n_passed or 0
    n_a2_in = a2.n_received or 0
    n_a2_pass = a2.n_passed or 0
    sv = bv.artifacts.get('survivor_report')
    near = bv.artifacts.get('near_survivor_report')
    n_surv = (len(sv.rows) if (sv and sv.state == 'OK' and sv.rows is not None) else 0)
    n_near = (len(near.rows) if (near and near.state == 'OK' and near.rows is not None) else 0)

    # Funnel
    fig = go.Figure(go.Funnel(
        y=['GENERATED', 'A1 ENTERED', 'A1 PASSED', 'A2 ENTERED', 'A2 PASSED', 'SURVIVORS'],
        x=[n_total, n_a1_in, n_a1_pass, n_a2_in, n_a2_pass, n_surv],
        textposition='inside',
        textinfo='value+percent initial',
        marker=dict(color=['#38bdf8', '#0ea5e9', '#0284c7', '#0369a1', '#075985', '#22c55e']),
    ))
    fig.update_layout(
        template='plotly_dark', paper_bgcolor='#0b0f17', plot_bgcolor='#0b0f17',
        margin=dict(l=10, r=10, t=10, b=10), height=320,
        font=dict(family='ui-monospace, JetBrains Mono', size=12, color='#e2e8f0'),
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # A3 panel — NOT_REACHED, not zero
    a3 = bv.artifacts.get('shadow_batch_results')
    a3_state = 'NOT_REACHED' if (a3 and a3.state == 'OK') else 'NO DATA'
    near_label = f'{n_near}'
    st.markdown(
        f'<div class="zt-card" style="display:flex;gap:18px;align-items:center;">'
        f'<span class="zt-muted">A3:</span> <span class="zt-tag zt-tag-na">{a3_state}</span>'
        f'<span class="zt-muted">A4:</span> <span class="zt-tag zt-tag-na">NOT_REACHED</span>'
        f'<span class="zt-muted">A5:</span> <span class="zt-tag zt-tag-na">NOT_REACHED</span>'
        f'<span class="zt-muted" style="margin-left:auto;">SURVIVORS</span>'
        f'<span class="zt-tag zt-tag-pass">{n_surv}</span>'
        f'<span class="zt-muted">NEAR-SURVIVORS</span>'
        f'<span class="zt-tag zt-tag-near">{near_label}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
