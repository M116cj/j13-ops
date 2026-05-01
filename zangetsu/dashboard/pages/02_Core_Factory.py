import streamlit as st
from zangetsu.dashboard.data_sources.batch_artifacts import load_latest_batch
from zangetsu.dashboard.components.charts import bar_top_n, funnel_chart
from zangetsu.dashboard.components.freshness_badge import render_badge

st.set_page_config(page_title='Core Factory', page_icon='🏭', layout='wide')
st.title('Core Factory Funnel')

bv = load_latest_batch()
if bv.folder is None:
    st.error('No recovery batch found.')
    st.stop()

manifest = bv.artifacts.get('candidate_manifest')
results = bv.artifacts.get('shadow_batch_results')
collisions = bv.artifacts.get('formula_collision_report')
fr_m = bv.freshness.get('candidate_manifest')
fr_r = bv.freshness.get('shadow_batch_results')

st.markdown(
    f'**Manifest**: {fr_m.path}  · {render_badge(fr_m.state if fr_m else "UNKNOWN", fr_m.age_seconds if fr_m else None)}  \n'
    f'**Results**: {fr_r.path}  · {render_badge(fr_r.state if fr_r else "UNKNOWN", fr_r.age_seconds if fr_r else None)}',
    unsafe_allow_html=True,
)

if manifest is None or manifest.state != 'OK' or manifest.rows is None:
    st.warning('Manifest NO DATA')
    st.stop()
mdf = manifest.rows
n_total = len(mdf)
n_unique_formulas = mdf['alpha_hash'].nunique() if 'alpha_hash' in mdf.columns else 0

cols = st.columns(4)
cols[0].metric('Candidates', n_total)
cols[1].metric('Unique formulas', n_unique_formulas)
if collisions and collisions.state == 'OK' and collisions.rows is not None:
    cdf = collisions.rows
    coll = int(cdf.get('collisions_dropped').sum()) if 'collisions_dropped' in cdf.columns else 0
    unsupp = int(cdf.get('unsupported_operator_count').sum()) if 'unsupported_operator_count' in cdf.columns else 0
    cols[2].metric('Formula collisions', coll)
    cols[3].metric('Unsupported ops', unsupp)
else:
    cols[2].metric('Formula collisions', 'NO DATA')
    cols[3].metric('Unsupported ops', 'NO DATA')

st.divider()
st.subheader('Stage funnel')
n_eval = 0
n_pass = 0
if results and results.state == 'OK' and results.rows is not None:
    rdf = results.rows
    n_eval = int((rdf['status'].isin(['PASSED', 'REJECTED'])).sum())
    n_pass = int((rdf['status'] == 'PASSED').sum())
st.plotly_chart(funnel_chart([
    ('Generated', n_total),
    ('Evaluated', n_eval),
    ('Passed shadow A2', n_pass),
]), use_container_width=True)

c1, c2 = st.columns(2)
if 'grammar_family' in mdf.columns:
    c1.subheader('Grammar families')
    c1.plotly_chart(bar_top_n(mdf['grammar_family'].value_counts().to_dict(),
                              title='By grammar_family'), use_container_width=True)
if 'primitive_family' in mdf.columns:
    c2.subheader('Primitive families')
    c2.plotly_chart(bar_top_n(mdf['primitive_family'].value_counts().to_dict(),
                              title='By primitive_family'), use_container_width=True)

c3, c4 = st.columns(2)
if 'intended_side_mode' in mdf.columns:
    c3.subheader('Side mode mix')
    c3.plotly_chart(bar_top_n(mdf['intended_side_mode'].value_counts().to_dict(),
                              title='By intended_side_mode'), use_container_width=True)
if 'symbol' in mdf.columns:
    c4.subheader('Symbol coverage')
    c4.plotly_chart(bar_top_n(mdf['symbol'].value_counts().to_dict(),
                              title='Candidates per symbol', n=20), use_container_width=True)
