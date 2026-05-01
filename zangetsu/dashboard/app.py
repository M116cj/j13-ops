"""Streamlit entrypoint for ZANGETSU internal dashboard (0-9AF).

Pages live under zangetsu/dashboard/pages/ and are auto-discovered by
Streamlit's multi-page convention. Run via:

  /home/j13/zangetsu-dashboard-venv/bin/streamlit run \
    /home/j13/j13-ops/zangetsu/dashboard/app.py \
    --server.address 127.0.0.1 --server.port 8785 --server.headless true
"""
from __future__ import annotations
import streamlit as st

from zangetsu.dashboard.config import REFRESH_INTERVAL_S
from zangetsu.dashboard.data_sources.batch_artifacts import load_latest_batch
from zangetsu.dashboard.view_models.overview import build_overview
from zangetsu.dashboard.view_models.health import now_iso

st.set_page_config(
    page_title='ZANGETSU — Internal Dashboard',
    page_icon='📊', layout='wide', initial_sidebar_state='expanded',
)


@st.cache_data(ttl=REFRESH_INTERVAL_S)
def _cached_batch():
    bv = load_latest_batch()
    return bv


def landing():
    st.title('ZANGETSU — Internal Observability Dashboard')
    st.caption(
        'Read-only · internal only · no write controls. '
        f'Generated at {now_iso()}.'
    )
    st.markdown(
        '''
Use the sidebar to navigate to:

- **Overview** — system state & KPI cards
- **Core Factory** — primitive → grammar → generator → arena funnel
- **Arena A1 / A2 / A3** — per-arena pass/reject detail
- **Candidates** — searchable explorer
- **Survivors** — survivors and near-survivors (strictly separated)
- **Rejects** — reject-reason explorer
- **Feedback** — feedback weights and next-batch weights
- **System Health** — source freshness and parser state

Boundaries (per ORDER 0-9AF):
- No live trading. No control plane. No writes.
- No fake zeros — "NO DATA", "STALE", "MISSING" are distinct from 0.
- NOT_EVALUATED ≠ REJECTED. Survivor ≠ Near-survivor. Survivor ≠ Deployable.
        '''
    )
    bv = _cached_batch()
    ov = build_overview(bv)
    if ov.state == 'NO_DATA':
        st.warning('No batch artifacts found — run  first.')
        return
    st.subheader('Latest batch')
    cols = st.columns(4)
    cols[0].metric('Batch folder', ov.folder_name or 'n/a')
    cols[1].metric('Generation ID', ov.generation_id or 'n/a')
    cols[2].metric('Candidates', ov.candidates_total or 0)
    cols[3].metric('A2_MIN_TRADES', ov.a2_min_trades or 'n/a')


if __name__ == '__main__':
    landing()
else:
    landing()
