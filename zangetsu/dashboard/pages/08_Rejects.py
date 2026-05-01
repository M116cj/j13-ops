import streamlit as st
from zangetsu.dashboard.data_sources.batch_artifacts import load_latest_batch
from zangetsu.dashboard.components.charts import bar_top_n, reject_reason_stacked
import pandas as pd

st.set_page_config(page_title='Rejects', page_icon='🔻', layout='wide')
st.title('Reject Reason Explorer')

bv = load_latest_batch()
results = bv.artifacts.get('shadow_batch_results')
if results is None or results.state != 'OK' or results.rows is None:
    st.warning('NO DATA — shadow_batch_results missing.')
    st.stop()
df = results.rows
rej = df[df['status'] == 'REJECTED'].copy()
if rej.empty:
    st.info('No rejected candidates in this batch.')
    st.stop()

cols = st.columns(4)
cols[0].metric('Rejected total', len(rej))
cols[1].metric('UNKNOWN_REJECT',
               int((rej['reject_reason'] == 'UNKNOWN_REJECT').sum()))
cols[2].metric('Symbols', rej['symbol'].nunique() if 'symbol' in rej.columns else 'NO DATA')
cols[3].metric('Sides', rej['intended_side_mode'].nunique() if 'intended_side_mode' in rej.columns else 'NO DATA')

st.divider()
c1, c2 = st.columns(2)
c1.subheader('Total reject reason distribution')
c1.plotly_chart(
    bar_top_n(rej['reject_reason'].value_counts().to_dict(),
              title='Reject reasons (overall)'),
    use_container_width=True,
)

if 'symbol' in rej.columns:
    by_sym = rej.groupby(['symbol', 'reject_reason']).size().reset_index(name='n')
    c2.subheader('Reject reasons by symbol')
    c2.plotly_chart(reject_reason_stacked(by_sym, 'symbol'),
                    use_container_width=True)

if 'intended_side_mode' in rej.columns:
    by_side = rej.groupby(['intended_side_mode', 'reject_reason']).size().reset_index(name='n')
    st.subheader('Reject reasons by side mode')
    st.plotly_chart(reject_reason_stacked(by_side, 'intended_side_mode'),
                    use_container_width=True)
