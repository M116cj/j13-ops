"""Freshness badge HTML / Streamlit helper."""
from __future__ import annotations

_BADGE_COLORS = {
    'FRESH': '#00b894',
    'STALE': '#fdcb6e',
    'OLD': '#d63031',
    'MISSING': '#636e72',
    'ERROR': '#d63031',
    'UNKNOWN': '#636e72',
}


def render_badge(state: str, age_seconds=None) -> str:
    color = _BADGE_COLORS.get(state, '#636e72')
    text = state
    if age_seconds is not None and state in {'FRESH', 'STALE', 'OLD'}:
        if age_seconds < 60:
            text += f' ({int(age_seconds)}s)'
        elif age_seconds < 3600:
            text += f' ({int(age_seconds / 60)}m)'
        elif age_seconds < 86400:
            text += f' ({int(age_seconds / 3600)}h)'
        else:
            text += f' ({int(age_seconds / 86400)}d)'
    return (f'<span style="display:inline-block;padding:2px 8px;border-radius:8px;'
            f'background:{color};color:white;font-size:12px;">{text}</span>')
