import streamlit as st
from zangetsu.dashboard.data_sources.batch_artifacts import load_latest_batch
from zangetsu.dashboard.view_models.arenas import build_a2
from zangetsu.dashboard.components.charts import bar_top_n
from zangetsu.dashboard.components.freshness_badge import render_badge

st.set_page_config(page_title='Arena A2', page_icon='🥈', layout='wide')
st.title('Arena A2 — economic gate (trades ≥ 25 AND post-cost net > 0)')

bv = load_latest_batch()
if bv.folder is None:
    st.error('No recovery batch found.')
    st.stop()
a2 = build_a2(bv)
fr = bv.freshness.get('shadow_batch_results')
if fr is not None:
    st.markdown(f'**Source**: {fr.path}  · '
                f'{render_badge(fr.state, fr.age_seconds)}',
                unsafe_allow_html=True)

if a2.state != 'OK':
    st.warning(f'{a2.state} — {a2.note}')
    st.stop()

cols = st.columns(4)
cols[0].metric('Received', a2.n_received)
cols[1].metric('PASSED', a2.n_passed)
cols[2].metric('REJECTED', a2.n_rejected)
cols[3].metric('NOT_EVALUATED', a2.n_not_evaluated)
cols2 = st.columns(4)
cols2[0].metric('ERROR', a2.n_error)
cols2[1].metric('Pass rate', f'{a2.pass_rate:.2%}')
cols2[2].metric('Reject rate', f'{a2.reject_rate:.2%}')
cols2[3].metric('Dominant reject', a2.dominant_reject_reason or 'n/a')

st.divider()
c1, c2 = st.columns(2)
if a2.side_split:
    c1.subheader('Side split')
    c1.plotly_chart(bar_top_n(a2.side_split, title='Intended side mode'), use_container_width=True)
if a2.by_symbol is not None:
    c2.subheader('By symbol')
    c2.dataframe(a2.by_symbol, use_container_width=True)
