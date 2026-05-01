# 08 — Frontend Implementation Report

**ORDER**: 0-9AF-REDESIGN — Phase 4 (frontend layer)

## Frontend Choice

Streamlit + custom CSS injection + Plotly charts.

Reasoning vs the order's preferred React + Vite + TS:

| Criterion | Streamlit + CSS | React + Vite |
|---|---|---|
| Time to ship V2 | hours | days–weeks |
| Coexistence with V1 | reuses V1 view_models verbatim | requires duplicating data API as FastAPI |
| Operator-reachable today | yes (already deployed) | requires Node + npm + build pipeline + serve |
| Visual ceiling | dark theme + custom CSS gives terminal feel | unbounded |
| Maintenance surface | 1 venv + Streamlit | venv + Node + JS deps + build artifacts |

Decision: ship Streamlit V2 now. Order §8.2 explicitly allows: "Streamlit acceptable only if it achieves true terminal-style UX." Gemini PASS confirms the goal is met.

## Frontend Modules (panels)

| Module | What it renders | Key visual cue |
|---|---|---|
| top_status_bar | sticky 30 px bar with 12 status items | colored badges + UTC clock |
| kpi_strip | 10-card row | 22 px monospace value, color-coded by kind |
| arena_funnel | Plotly funnel + A3/A4/A5 NOT_REACHED row | dark plotly_dark template + cyan/green gradient |
| reject_depth | order-book-style horizontal bars | red "pressure" bars + percent + count |
| sidebar_filter | batch / symbol / side / arena selectors + search | left dock |
| candidate_drawer | full detail card | green/red net coloring + monospace formula block |
| bottom_tabs | 5 tabs with row-click → drawer | flat dark tabs, cyan underline on active |

## Theme

`zangetsu/dashboard_terminal/theme.py` injects `TERMINAL_CSS`:
- 80+ rules covering background, panels, KPIs, badges, depth-row, tabs, dataframes, monospace numbers
- Streamlit theme CLI flags align (dark base + cyan primary + monospace font)

## Interactivity

| Action | Where |
|---|---|
| Pick batch | sidebar selectbox |
| Filter symbol / side / arena | sidebar selectboxes |
| Search candidate_id / alpha_hash | sidebar text input |
| Click candidate row → load drawer | Streamlit dataframe `on_select='rerun'` |
| Switch deep-dive view | bottom tabs |
| Auto-refresh data | st.cache_data TTL = 20 s |

## What's Explicitly Absent (per order §4.1)

- No buttons that mutate state
- No form_submit_button
- No subprocess / system-call surface
- No write API
- No file-write actions (verified by `test_terminal_no_write_actions`)
