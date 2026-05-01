import json
import streamlit as st
from zangetsu.dashboard.data_sources.batch_artifacts import load_latest_batch
from zangetsu.dashboard.view_models.feedback import build_feedback

st.set_page_config(page_title='Feedback', page_icon='♻️', layout='wide')
st.title('Feedback Loop — feedback_weights and next_batch_weights')

bv = load_latest_batch()
view = build_feedback(bv)
if view.state == 'NO_DATA':
    st.warning(f'NO DATA — {view.note}')
    st.stop()

st.subheader('feedback_weights.json')
fw = view.feedback_weights or {}
overall = fw.get('overall') or {}
status = overall.get('status', 'NO DATA')
st.metric('Overall feedback status', status)
if status == 'OK':
    weights = overall.get('weights') or {}
    if weights:
        st.bar_chart(weights, use_container_width=True)
    else:
        st.info('weights present but empty')
else:
    st.info(f"Reason: {overall.get('reason', 'n/a')}")

st.divider()
st.subheader('next_batch_weights.json')
nb = view.next_batch_weights or {}
nb_overall = nb.get('overall') or {}
status_nb = nb_overall.get('status', 'NO DATA')
st.metric('Next-batch status', status_nb)
actions = nb_overall.get('recommended_actions') or []
if actions:
    import pandas as pd
    df = pd.DataFrame(actions)
    st.dataframe(df, use_container_width=True)
else:
    st.info('No recommended actions (status not OK or below share threshold).')

with st.expander('Raw feedback_weights.json'):
    st.code(json.dumps(fw, indent=2), language='json')
with st.expander('Raw next_batch_weights.json'):
    st.code(json.dumps(nb, indent=2), language='json')
