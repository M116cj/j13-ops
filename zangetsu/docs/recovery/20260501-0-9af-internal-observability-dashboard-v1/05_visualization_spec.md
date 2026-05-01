# 05 — Visualization Spec

**ORDER**: 0-9AF — Phase 2

## Chart Library

Plotly (via plotly.graph_objects + plotly.express). Static export via kaleido + headless Chrome (used only for screenshot generation, not the live app).

## Reusable Components (`components/charts.py`)

| Function | Purpose |
|---|---|
| `funnel_chart(stages)` | Stage-by-stage candidate count (Generated → Evaluated → Passed) |
| `bar_top_n(items, title, n, orient)` | Top-N horizontal bar (default) for reject reasons / symbols / weights |
| `status_donut(counts)` | PASSED / REJECTED / NOT_EVAL / ERROR donut |
| `reject_reason_stacked(df, group_col)` | Stacked bar of reject reasons by symbol or side |

## Per-Page Charts

| Page | Visual elements |
|---|---|
| Overview | KPI cards (8) + funnel + reject-reasons bar + status donut + top symbols bar |
| Core Factory | KPI cards + funnel + grammar-family bar + primitive-family bar + side-mode bar + per-symbol bar |
| Arena A1 | KPI cards + side-split bar + per-symbol table |
| Arena A2 | KPI cards (8) + side-split bar + per-symbol table |
| Arena A3 | NOT_AVAILABLE banner + brief note |
| Candidates | 5 filter widgets + search box + sortable table (up to 2000 rows) |
| Survivors | Two strictly-separated tables (PASSED above, near-survivors below) |
| Rejects | KPI cards + 3 charts (overall, by symbol stacked, by side stacked) |
| Feedback | 4 KPI + bar of weights + recommended-actions bar + raw JSON expanders |
| System Health | KPI summary + per-source state table + summary banner |

## Visual Defaults

- Color: muted blues / greens for OK; warm yellow for STALE; red for OLD/MISSING/ERROR
- Layout: `wide` mode; chart height 300–380 px; KPI band 80 px
- Refresh: `@st.cache_data(ttl=20s)` on landing page; per-page sources reload on each render

Truthfulness rules enforced via view-model contracts:
- numeric values fall back to `'NO DATA'` string when source is None
- A3 page early-returns NOT_AVAILABLE without rendering a 0/0 chart
