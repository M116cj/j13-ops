# 04 — Information Architecture

**ORDER**: 0-9AF-REDESIGN — Phase 2

## Single-Page IA (no sub-pages by design)

The terminal collapses V1's 10 separate pages into one dense single-page layout to match the operator's mental model of an exchange terminal. All views are reachable via:
- KPI cards (always visible)
- Center panels (funnel + depth always visible)
- Right drawer (details on demand)
- Bottom tabs (5 deep-dive views)

## File / Module Tree

```
zangetsu/dashboard_terminal/
├── __init__.py
├── app.py                     (single-page terminal entry; ~75 lines)
├── theme.py                   (dark CSS injection)
└── panels/
    ├── __init__.py
    ├── top_status_bar.py      (sticky bar — 12 status items)
    ├── kpi_strip.py           (10-card row)
    ├── arena_funnel.py        (Generated→A1→A2→Survivors funnel + A3 NOT_REACHED)
    ├── reject_depth.py        (order-book-style depth ladder)
    ├── sidebar_filter.py      (batch / symbol / side / arena selectors)
    ├── candidate_drawer.py    (right-side detail panel)
    └── bottom_tabs.py         (Candidates / Rejects / Survivors / Feedback / Health)
```

## Reuse from V1

The terminal IMPORTS V1 view-models verbatim:
- `zangetsu.dashboard.data_sources.batch_artifacts.load_batch_from_folder`
- `zangetsu.dashboard.view_models.{overview,arenas,candidates,survivors,feedback,health}`
- `zangetsu.dashboard.config.{REFRESH_INTERVAL_S, RECOVERY_ROOT}`

This guarantees the terminal inherits V1's tested truthfulness contract (no fake zero, NOT_EVALUATED separation, survivor separation).

## Tests Layout

```
zangetsu/tests/dashboard_terminal/
├── __init__.py
└── test_terminal_imports.py   (panels present + no forbidden imports + no write patterns)
```

V1 dashboard tests (22) continue to pass and are NOT removed — they validate the shared view-model layer the terminal depends on.

## Service Layout

- `ops/systemd/zangetsu-dashboard-terminal.service` — V2 service unit
- `scripts/zangetsu/run_dashboard_terminal.sh` — venv launcher
- Drop-in: `~/.config/systemd/user/zangetsu-dashboard-terminal.service.d/tailscale-bind.conf` (Tailscale interface bind, kept untracked since it's host-specific)
