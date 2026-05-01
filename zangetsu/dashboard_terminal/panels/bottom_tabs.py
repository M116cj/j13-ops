"""Bottom tabbed area: Candidates | Rejects | Survivors | Feedback | Health."""
from __future__ import annotations
import json
from typing import Optional
import pandas as pd
import streamlit as st

from zangetsu.dashboard.view_models.candidates import apply_filters
from zangetsu.dashboard.view_models.survivors import build_survivors
from zangetsu.dashboard.view_models.feedback import build_feedback
from zangetsu.dashboard.view_models.health import build_health


def render(bv, ov, df_results, df_manifest,
           selected_symbol: str, selected_side: str,
           selected_arena: str, search_text: str) -> Optional[str]:
    tab_cand, tab_rej, tab_surv, tab_feed, tab_health = st.tabs(
        ['CANDIDATES', 'REJECTS', 'SURVIVORS', 'FEEDBACK', 'HEALTH'])
    selected_id = None

    with tab_cand:
        if df_results is None or df_results.empty:
            st.markdown('<div class="zt-muted zt-mono">NO DATA</div>', unsafe_allow_html=True)
        else:
            filtered = apply_filters(
                df_results,
                axis=None, status=None,
                symbol=None if selected_symbol == '(any)' else selected_symbol,
                side_mode=None if selected_side == '(any)' else selected_side,
                reject_reason=None,
                search=search_text or None,
            )
            st.markdown(
                f'<div class="zt-muted zt-mono" style="font-size:11px;">'
                f'showing {len(filtered)} / {len(df_results)} candidates · '
                f'symbol={selected_symbol} side={selected_side} search={search_text or "-"}</div>',
                unsafe_allow_html=True)
            cols = [c for c in ['candidate_id', 'symbol', 'intended_side_mode',
                                'status', 'reject_reason', 'gross_bps', 'net_bps',
                                'trade_count', 'a1_pass', 'a2_pass', 'alpha_hash']
                    if c in filtered.columns]
            display = filtered[cols].head(2000) if cols else filtered.head(2000)
            ev = st.dataframe(display, use_container_width=True, height=320,
                              on_select='rerun', selection_mode='single-row')
            if ev and ev.selection and ev.selection.get('rows'):
                idx = ev.selection['rows'][0]
                if idx < len(display):
                    selected_id = str(display.iloc[idx].get('candidate_id'))

    with tab_rej:
        if df_results is None or df_results.empty:
            st.markdown('<div class="zt-muted zt-mono">NO DATA</div>', unsafe_allow_html=True)
        else:
            rej = df_results[df_results['status'] == 'REJECTED']
            if rej.empty:
                st.markdown('<div class="zt-muted zt-mono">NO REJECTED CANDIDATES</div>',
                            unsafe_allow_html=True)
            else:
                # Two columns: by-symbol stacked, by-side stacked
                c1, c2 = st.columns(2)
                by_sym = rej.groupby(['symbol', 'reject_reason']).size().reset_index(name='n')
                by_side = rej.groupby(['intended_side_mode', 'reject_reason']).size().reset_index(name='n')
                import plotly.express as px
                fig1 = px.bar(by_sym, x='symbol', y='n', color='reject_reason',
                              barmode='stack', template='plotly_dark')
                fig1.update_layout(paper_bgcolor='#0b0f17', plot_bgcolor='#0b0f17',
                                   margin=dict(l=10, r=10, t=20, b=10), height=300,
                                   font=dict(color='#e2e8f0'),
                                   legend=dict(orientation='h', y=-0.25, font=dict(size=10)))
                c1.plotly_chart(fig1, use_container_width=True, config={'displayModeBar': False})
                fig2 = px.bar(by_side, x='intended_side_mode', y='n', color='reject_reason',
                              barmode='stack', template='plotly_dark')
                fig2.update_layout(paper_bgcolor='#0b0f17', plot_bgcolor='#0b0f17',
                                   margin=dict(l=10, r=10, t=20, b=10), height=300,
                                   font=dict(color='#e2e8f0'),
                                   legend=dict(orientation='h', y=-0.25, font=dict(size=10)))
                c2.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False})

    with tab_surv:
        view = build_survivors(bv)
        if view.state == 'NO_DATA':
            st.markdown('<div class="zt-muted zt-mono">NO DATA — survivor artifact missing</div>',
                        unsafe_allow_html=True)
        else:
            c1, c2 = st.columns(2)
            c1.markdown('<div class="zt-card-title">SURVIVORS (PASSED)</div>', unsafe_allow_html=True)
            if view.survivors is not None and not view.survivors.empty:
                c1.dataframe(view.survivors, use_container_width=True, height=300)
            else:
                c1.markdown('<div class="zt-muted zt-mono">no survivors</div>',
                            unsafe_allow_html=True)
            c2.markdown('<div class="zt-card-title">NEAR-SURVIVORS (REJ, net∈[-5,0])</div>',
                        unsafe_allow_html=True)
            if view.near_survivors is not None and not view.near_survivors.empty:
                c2.dataframe(view.near_survivors.head(2000), use_container_width=True, height=300)
            else:
                c2.markdown('<div class="zt-muted zt-mono">no near-survivors</div>',
                            unsafe_allow_html=True)

    with tab_feed:
        fv = build_feedback(bv)
        if fv.state == 'NO_DATA':
            st.markdown('<div class="zt-muted zt-mono">NO DATA</div>', unsafe_allow_html=True)
        else:
            nb = (fv.next_batch_weights or {}).get('overall', {})
            actions = nb.get('recommended_actions') or []
            st.markdown('<div class="zt-card-title">NEXT-BATCH RECOMMENDATIONS</div>',
                        unsafe_allow_html=True)
            if actions:
                df_act = pd.DataFrame(actions)
                cols = [c for c in ['reason', 'failure_mode', 'action',
                                    'grammar_weight_delta', 'share'] if c in df_act.columns]
                st.dataframe(df_act[cols], use_container_width=True, height=200)
            else:
                st.markdown('<div class="zt-muted zt-mono">no recommendations</div>',
                            unsafe_allow_html=True)
            with st.expander('feedback_weights.json'):
                st.code(json.dumps(fv.feedback_weights or {}, indent=2), language='json')
            with st.expander('next_batch_weights.json'):
                st.code(json.dumps(fv.next_batch_weights or {}, indent=2), language='json')

    with tab_health:
        rows = build_health(bv)
        df_h = pd.DataFrame([{
            'source_key': r.source_key, 'parse': r.parse_state,
            'freshness': r.freshness_state,
            'age_h': round((r.age_seconds or 0) / 3600, 1) if r.age_seconds else None,
            'mtime': r.mtime_iso, 'note': r.note or '',
        } for r in rows])
        st.dataframe(df_h, use_container_width=True, height=320)

    return selected_id
