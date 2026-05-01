import streamlit as st
from zangetsu.dashboard.data_sources.batch_artifacts import load_latest_batch
from zangetsu.dashboard.view_models.survivors import build_survivors

st.set_page_config(page_title='Survivors', page_icon='🟢', layout='wide')
st.title('Survivors / Near-Survivors')

st.caption('Strict separation. Survivor ≠ Deployable. NOT_EVALUATED is excluded from both.')

bv = load_latest_batch()
view = build_survivors(bv)
if view.state == 'NO_DATA':
    st.warning(f'NO DATA — {view.note}')
    st.stop()

st.subheader('Survivors (status = PASSED)')
if view.survivors is None or view.survivors.empty:
    st.info('No survivors in this batch.')
else:
    st.dataframe(view.survivors, use_container_width=True)

st.divider()
st.subheader('Near-survivors (status = REJECTED with net_bps in [-5, 0])')
if view.near_survivors is None or view.near_survivors.empty:
    st.info('No near-survivors in this batch.')
else:
    st.dataframe(view.near_survivors.head(2000), use_container_width=True)

st.caption('Deployable count semantics unchanged — this page does not affect zangetsu_status.')
