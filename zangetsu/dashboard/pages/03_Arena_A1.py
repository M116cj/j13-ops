import streamlit as st
from zangetsu.dashboard.data_sources.batch_artifacts import load_latest_batch
from zangetsu.dashboard.view_models.arenas import build_a1
from zangetsu.dashboard.components.charts import bar_top_n
from zangetsu.dashboard.components.freshness_badge import render_badge

st.set_page_config(page_title='Arena A1', page_icon='🥇', layout='wide')
st.title('Arena A1 — minimum-trade gate (sanity)')

bv = load_latest_batch()
if bv.folder is None:
    st.error('No recovery batch found.')
    st.stop()
a1 = build_a1(bv)
fr = bv.freshness.get('shadow_batch_results')
if fr is not None:
    st.markdown(f'**Source**: {fr.path}  · '
                f'{render_badge(fr.state, fr.age_seconds)}',
                unsafe_allow_html=True)

if a1.state == 'NO_DATA':
    st.warning(f'NO DATA — {a1.note or "no shadow_batch_results"}')
    st.stop()
if a1.state == 'NOT_AVAILABLE':
    st.info(f'NOT AVAILABLE — {a1.note}')
    st.stop()

cols = st.columns(4)
cols[0].metric('Received', a1.n_received)
cols[1].metric('A1 pass', a1.n_passed if a1.n_passed is not None else 'NO DATA')
cols[2].metric('A1 reject', a1.n_rejected if a1.n_rejected is not None else 'NO DATA')
cols[3].metric('A1 pass rate', f'{(a1.pass_rate or 0):.2%}' if a1.pass_rate is not None else 'NO DATA')

st.divider()
c1, c2 = st.columns(2)
if a1.side_split:
    c1.subheader('Side split')
    c1.plotly_chart(bar_top_n(a1.side_split, title='Intended side mode'), use_container_width=True)
if a1.by_symbol is not None:
    c2.subheader('By symbol')
    c2.dataframe(a1.by_symbol, use_container_width=True)
