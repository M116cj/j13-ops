"""ZANGETSU Terminal — exchange-style internal observability (0-9AF V2).

Single-page terminal layout:
  ┌─────────────────────────────────────────────────────────────────┐
  │ TOP STATUS BAR (sticky)                                          │
  ├─────────────┬───────────────────────────────┬─────────────────┤
  │ LEFT PANEL  │ CENTER (KPI + funnel + depth) │ RIGHT (drawer)  │
  ├─────────────┴───────────────────────────────┴─────────────────┤
  │ BOTTOM TABS: Candidates | Rejects | Survivors | Feedback | Health │
  └─────────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations
import json
import pathlib
import streamlit as st

from zangetsu.dashboard.config import REFRESH_INTERVAL_S
from zangetsu.dashboard.data_sources.batch_artifacts import (
    BatchView, load_batch_from_folder,
)
from zangetsu.dashboard.view_models.overview import build_overview
from zangetsu.dashboard.view_models.arenas import build_a1, build_a2

from zangetsu.dashboard_terminal.theme import TERMINAL_CSS
from zangetsu.dashboard_terminal.panels import (
    top_status_bar, kpi_strip, arena_funnel, reject_depth,
    sidebar_filter, candidate_drawer, bottom_tabs,
)


st.set_page_config(
    page_title='ZANGETSU Terminal v2',
    page_icon='⚡', layout='wide', initial_sidebar_state='expanded',
)
st.markdown(TERMINAL_CSS, unsafe_allow_html=True)


def _head_sha() -> str | None:
    try:
        head_path = pathlib.Path('/home/j13/j13-ops/.git/HEAD')
        if not head_path.exists():
            return None
        ref = head_path.read_text().strip()
        if ref.startswith('ref: '):
            ref_path = pathlib.Path('/home/j13/j13-ops/.git') / ref[5:]
            if ref_path.exists():
                return ref_path.read_text().strip()
        return ref
    except Exception:
        return None


@st.cache_data(ttl=REFRESH_INTERVAL_S)
def _cached_batch_for(folder_str: str | None) -> BatchView:
    folder = pathlib.Path(folder_str) if folder_str else None
    return load_batch_from_folder(folder)


# Sidebar reads available batches & filters; first call uses no batch view to discover folders
sel = sidebar_filter.render(BatchView(folder=None, folder_name=None,
                                      artifacts={}, freshness={},
                                      run_summary_raw=None))
bv = _cached_batch_for(str(sel.folder) if sel.folder else None)

# Search box on sidebar (post-batch-load)
search_text = st.sidebar.text_input('SEARCH candidate_id / alpha_hash',
                                    label_visibility='collapsed', placeholder='search…')

# Top status bar
ov = build_overview(bv)
top_status_bar.render(bv, ov, head_sha=_head_sha())

if bv.folder is None:
    st.error('No recovery batch found.')
    st.stop()

# KPI strip
a1 = build_a1(bv); a2 = build_a2(bv)
sv_art = bv.artifacts.get('survivor_report')
near_art = bv.artifacts.get('near_survivor_report')
n_surv = len(sv_art.rows) if (sv_art and sv_art.state == 'OK' and sv_art.rows is not None) else None
n_near = len(near_art.rows) if (near_art and near_art.state == 'OK' and near_art.rows is not None) else None
kpi_strip.render(ov, n_surv, n_near, a2.dominant_reject_reason)

# 3-column body (left selector lives in sidebar; center funnel + depth, right drawer)
left, right = st.columns([7, 3], gap='small')
with left:
    arena_funnel.render(bv, ov, a1, a2)
    reject_depth.render(bv.run_summary_raw or {})

# Bottom tabs (selection feeds the right drawer)
df_results = bv.artifacts.get('shadow_batch_results')
df_results_rows = df_results.rows if (df_results and df_results.state == 'OK') else None
df_manifest = bv.artifacts.get('candidate_manifest')
df_manifest_rows = df_manifest.rows if (df_manifest and df_manifest.state == 'OK') else None

selected_id = bottom_tabs.render(
    bv, ov, df_results_rows, df_manifest_rows,
    sel.symbol_filter, sel.side_filter, sel.arena_filter, search_text,
)

with right:
    candidate_drawer.render(df_results_rows, selected_id, df_manifest_rows)
