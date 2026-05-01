import streamlit as st
import pandas as pd
from zangetsu.dashboard.data_sources.batch_artifacts import load_latest_batch
from zangetsu.dashboard.view_models.health import build_health, now_iso
from zangetsu.dashboard.components.freshness_badge import render_badge

st.set_page_config(page_title='System Health', page_icon='🩺', layout='wide')
st.title('System Health — source freshness and parser state')

st.caption(f'Dashboard refresh time (UTC): {now_iso()}')

bv = load_latest_batch()
rows = build_health(bv)

def _badge(s, age):
    return render_badge(s, age)

# Render as Streamlit table with HTML badges
st.subheader('Per-source state')
data = [{
    'source_key': r.source_key,
    'parse_state': r.parse_state,
    'freshness_state': r.freshness_state,
    'age_seconds': r.age_seconds,
    'mtime_iso': r.mtime_iso,
    'note': r.note or '',
    'path': r.path,
} for r in rows]
df = pd.DataFrame(data)
st.dataframe(df, use_container_width=True)

stale = [r for r in rows if r.freshness_state in {'STALE', 'OLD'}]
missing = [r for r in rows if r.freshness_state == 'MISSING']
errored = [r for r in rows if r.parse_state == 'ERROR']
parser_errors = errored

if stale:
    st.warning(f'{len(stale)} source(s) STALE/OLD.')
if missing:
    st.warning(f'{len(missing)} source(s) MISSING.')
if parser_errors:
    st.error(f'{len(parser_errors)} source(s) had parser errors.')
if not (stale or missing or parser_errors):
    st.success('All sources FRESH and parsed cleanly.')
