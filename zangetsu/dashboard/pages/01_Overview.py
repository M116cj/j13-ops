import streamlit as st
from zangetsu.dashboard.data_sources.batch_artifacts import load_latest_batch
from zangetsu.dashboard.view_models.overview import build_overview
from zangetsu.dashboard.components.charts import (
    bar_top_n, funnel_chart, status_donut,
)
from zangetsu.dashboard.components.freshness_badge import render_badge

st.set_page_config(page_title='Overview', page_icon='📊', layout='wide')
st.title('Overview')

bv = load_latest_batch()
if bv.folder is None:
    st.error('No recovery batch found.')
    st.stop()
ov = build_overview(bv)
fr = bv.freshness.get('run_summary')
if fr is not None:
    st.markdown(f'**Source**: {fr.path}  '
                f'  Freshness: {render_badge(fr.state, fr.age_seconds)}',
                unsafe_allow_html=True)

if ov.state != 'OK':
    st.warning('Run summary missing — showing partial state.')

cols = st.columns(4)
cols[0].metric('Candidates total', ov.candidates_total if ov.candidates_total is not None else 'NO DATA')
cols[1].metric('PASSED', ov.passed if ov.passed is not None else 'NO DATA')
cols[2].metric('REJECTED', ov.rejected if ov.rejected is not None else 'NO DATA')
cols[3].metric('UNKNOWN_REJECT', ov.unknown_reject if ov.unknown_reject is not None else 'NO DATA')

cols2 = st.columns(4)
cols2[0].metric('NOT_EVALUATED', ov.not_evaluated if ov.not_evaluated is not None else 'NO DATA')
cols2[1].metric('ERROR', ov.error if ov.error is not None else 'NO DATA')
cols2[2].metric('Duration (s)', ov.duration_seconds if ov.duration_seconds is not None else 'NO DATA')
cols2[3].metric('Feedback', ov.overall_feedback_status or 'NO DATA')

st.divider()
st.subheader('Funnel')
if ov.candidates_total:
    stages = [
        ('Generated', ov.candidates_total),
        ('Evaluated', (ov.passed or 0) + (ov.rejected or 0)),
        ('Passed', ov.passed or 0),
    ]
    st.plotly_chart(funnel_chart(stages), use_container_width=True)
else:
    st.info('NO DATA')

st.divider()
left, right = st.columns(2)
rs = bv.run_summary_raw or {}
reasons = ((rs.get('overall_reject_summary') or {}).get('rejected_by_reason') or {})
left.subheader('Top reject reasons')
left.plotly_chart(bar_top_n(reasons, title='Top reject reasons'), use_container_width=True)

results_art = bv.artifacts.get('shadow_batch_results')
if results_art and results_art.state == 'OK' and results_art.rows is not None:
    df = results_art.rows
    counts = {'PASSED': int((df['status'] == 'PASSED').sum()),
              'REJECTED': int((df['status'] == 'REJECTED').sum()),
              'NOT_EVALUATED': int((df['status'] == 'NOT_EVALUATED').sum()),
              'ERROR': int((df['status'] == 'ERROR').sum())}
    right.subheader('Status mix')
    right.plotly_chart(status_donut(counts), use_container_width=True)
    sym_counts = df.groupby('symbol').size().to_dict() if 'symbol' in df.columns else {}
    st.plotly_chart(bar_top_n(sym_counts, title='Top symbols by candidate count', n=14), use_container_width=True)
else:
    right.info('Status mix: NO DATA')
