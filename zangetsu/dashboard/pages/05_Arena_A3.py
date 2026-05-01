import streamlit as st
from zangetsu.dashboard.data_sources.batch_artifacts import load_latest_batch
from zangetsu.dashboard.view_models.arenas import build_a3

st.set_page_config(page_title='Arena A3', page_icon='🥉', layout='wide')
st.title('Arena A3 — segmented holdout')

bv = load_latest_batch()
a3 = build_a3(bv)
if a3.state == 'NOT_AVAILABLE':
    st.info(f'NOT AVAILABLE — {a3.note}')
    st.markdown("A3 requires segmented holdout evaluation. Current SHADOW orders "
                "(0-9AB / 0-9AC / 0-9AD) do not run A3. The page is reserved for future "
                "scale-up orders that exercise services.arena_gates.arena3_pass.")
    st.stop()
