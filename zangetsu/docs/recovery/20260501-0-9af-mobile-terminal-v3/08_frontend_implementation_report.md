# 08 — Frontend Implementation Report (V3)

**ORDER**: 0-9AF-MOBILE-TERMINAL-V3 — Phase 4 (frontend)

## Frontend Stack

Vanilla HTML + CSS, Jinja2 server-side rendered. ~30 lines of inline JavaScript only for the live UTC clock (no external JS deps, no bundler).

## Why Not React + Vite

| Criterion | HTML/CSS (V3) | React + Vite |
|---|---|---|
| Time to ship | hours | days |
| Mobile TTFB on cellular Tailscale | < 200 ms (HTML over TLS) | client-side render after JS bundle download |
| External deps | Jinja2 (already used by FastAPI) | Node + npm + Vite + React + TypeScript + ECharts |
| Build pipeline | none | required |
| Maintenance surface | 1 venv | venv + Node + JS deps + lockfiles |
| Visual ceiling | dark CSS + responsive grid → matches OKX-app feel | unbounded (but not needed) |

For a single-operator internal observability dashboard checked from a phone, server-rendered HTML wins on every mobile metric.

## Page Templates

8 pages + 3 partials:

| Template | Lines | Renders |
|---|---:|---|
| _base.html | 25 | viewport / theme-color / 30s refresh / topbar+nav slots |
| _topbar.html | 18 | sticky brand + 6 health pills + UTC clock |
| _bottomnav.html | 10 | 7-tab fixed nav with active highlight |
| overview.html | 50 | KPI grid + reject depth + symbol table |
| funnel.html | 40 | Arena funnel + side split + reject depth |
| candidates.html | 55 | filter form + paginated row table with click-to-detail links |
| candidate_detail.html | 40 | full metadata card + monospace formula |
| rejects.html | 50 | depth bars + by-symbol table + by-side table |
| survivors.html | 45 | two strictly-separated tables (PASSED / near) |
| feedback.html | 45 | weight bars + recommended actions table |
| health.html | 40 | freshness count KPIs + per-source state table |

## CSS Strategy

- ~100 selectors, ~6 KB compressed
- Single `/static/style.css` served by FastAPI `StaticFiles`
- CSS custom properties (`:root`) for theming
- Media queries for responsive grid breakpoints (480 px / 760 px)
- iOS safe-area inset handling: `env(safe-area-inset-top)` / `env(safe-area-inset-bottom)`

## Interactivity

| Action | Mechanism |
|---|---|
| Filter candidates | `<form method="get" action="/candidates">` (no JS) |
| Search candidates | `<input name="q">` in same form |
| Open candidate detail | `<a href="/candidate/{cid}">` (full page navigation) |
| Switch tab | `<a href="/path">` (full page navigation) |
| Auto-refresh | `<meta http-equiv="refresh" content="30">` |
| Live UTC clock | 1-line setInterval, no framework |

This is the simplest interaction model that still feels like a mobile app — every action is one HTTP GET → server renders → done.

## What's Explicitly Absent (per order §4.1)

- No `<form method="POST">` anywhere
- No JS fetch / XHR / WebSocket
- No service-worker
- No external CDN
- No write API
- Verified by `test_app_is_read_only_no_write_paths` and `test_no_write_call_patterns`
