# 05 — Visual Design Spec

**ORDER**: 0-9AF-REDESIGN — Phase 2

## Color Tokens (CSS `:root`)

| Token | Value | Use |
|---|---|---|
| --bg | #0b0f17 | App background |
| --panel | #11161f | Panels / cards |
| --panel-2 | #161c27 | Top status bar |
| --border | #1f2735 | All borders |
| --fg | #e2e8f0 | Foreground text |
| --muted | #64748b | Captions / labels |
| --accent | #38bdf8 | Active / highlight |
| --green | #22c55e | Pass / healthy |
| --red | #ef4444 | Reject / unhealthy |
| --yellow | #f59e0b | Near-survivor / stale / warn |
| --gray | #475569 | NA / NO DATA |
| --mono | ui-monospace, JetBrains Mono | All numeric values |

## Component Patterns

- `.zt-status-bar` — sticky 30 px bar, monospace 12 px, gap 14 px
- `.zt-kpi` — 60 px card, 22 px monospace value, 10 px uppercase label
- `.zt-card` — 6 px radius, 1 px border, 8/10 px padding
- `.zt-tag-pass / .zt-tag-rej / .zt-tag-near / .zt-tag-na` — colored badges
- `.zt-depth-row` — 3-column grid: 220 px label / flex bar / 60 px percent
- `stTabs` — flat dark tabs with cyan underline on active

## Streamlit Theme

CLI flags in `run_dashboard_terminal.sh`:
```
--theme.base dark
--theme.primaryColor #38bdf8
--theme.backgroundColor #0b0f17
--theme.secondaryBackgroundColor #11161f
--theme.textColor #e2e8f0
--theme.font monospace
```

Combined with `TERMINAL_CSS` injection in `app.py`, this gives a fully dark, dense, monospace-numbers terminal feel.

## Information Density

- Top status bar: 12 status items, single-line
- KPI strip: 10 cards across full width
- Center panels: funnel (320 px) + depth (~220 px) stacked
- Right drawer: ~360 px tall card with formula in monospace
- Bottom tabs: tables at 320 px height with sticky headers
- Total above-fold (1080 p): all KPI + funnel + depth + first 6 candidate rows visible without scrolling
