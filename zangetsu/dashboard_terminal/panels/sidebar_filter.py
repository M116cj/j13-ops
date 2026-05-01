"""Left sidebar — batch / symbol / arena selectors."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import pathlib
import streamlit as st

from zangetsu.dashboard.config import RECOVERY_ROOT


@dataclass
class SidebarSelection:
    folder: Optional[pathlib.Path]
    symbol_filter: str  # '(any)' or symbol
    side_filter: str    # '(any)', 'LONG', 'SHORT', 'BOTH'
    arena_filter: str   # '(any)', 'A1', 'A2', 'A3'


def render(bv) -> SidebarSelection:
    st.sidebar.markdown('<div class="zt-card-title">BATCH</div>', unsafe_allow_html=True)
    folders = sorted([d for d in pathlib.Path(RECOVERY_ROOT).iterdir() if d.is_dir()],
                     key=lambda d: d.name, reverse=True)
    if not folders:
        st.sidebar.markdown('<span class="zt-muted">NO BATCH</span>', unsafe_allow_html=True)
        return SidebarSelection(None, '(any)', '(any)', '(any)')
    names = [f.name for f in folders]
    default_idx = next((i for i, n in enumerate(names) if 'shadow' in n), 0)
    chosen = st.sidebar.selectbox('Batch folder', names, index=default_idx, label_visibility='collapsed')
    folder = next(f for f in folders if f.name == chosen)

    st.sidebar.markdown('<div class="zt-card-title" style="margin-top:10px;">FILTERS</div>',
                        unsafe_allow_html=True)
    df = None
    art = bv.artifacts.get('shadow_batch_results')
    if art and art.state == 'OK' and art.rows is not None:
        df = art.rows
    sym_choices = ['(any)']
    side_choices = ['(any)']
    if df is not None:
        sym_choices += sorted(df['symbol'].dropna().unique().tolist())
        side_choices += sorted(df['intended_side_mode'].dropna().unique().tolist())
    sym = st.sidebar.selectbox('Symbol', sym_choices, label_visibility='collapsed')
    side = st.sidebar.selectbox('Side', side_choices, label_visibility='collapsed')
    arena = st.sidebar.selectbox('Arena', ['(any)', 'A1', 'A2', 'A3'], label_visibility='collapsed')

    return SidebarSelection(folder, sym, side, arena)
