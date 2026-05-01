# 04 — Information Architecture (V3)

**ORDER**: 0-9AF-MOBILE-TERMINAL-V3 — Phase 2

## Code Tree

```
zangetsu/dashboard_mobile/
├── __init__.py
├── app.py                       (FastAPI app + 8 routes; ~280 lines)
├── static/
│   └── style.css                (pure-black mobile-first CSS, ~100 rules)
└── templates/
    ├── _base.html               (viewport meta + theme-color + 30s refresh)
    ├── _topbar.html             (sticky top status bar with 6 health pills)
    ├── _bottomnav.html          (fixed bottom nav with 7 tabs)
    ├── overview.html            (KPI grid + reject depth + symbols table)
    ├── funnel.html              (Arena funnel + side split + reject depth)
    ├── candidates.html          (filter form + paginated table)
    ├── candidate_detail.html    (full metadata + monospace formula)
    ├── rejects.html             (depth bars + by-symbol + by-side tables)
    ├── survivors.html           (PASSED + near tables, strictly separated)
    ├── feedback.html            (weight bars + recommended actions)
    └── health.html              (freshness counts + per-source state table)
```

## Reuse from V1 / V2 (no duplication)

The mobile app IMPORTS V1 view-models verbatim — guaranteeing inherited truthfulness contracts:

- `zangetsu.dashboard.data_sources.batch_artifacts.load_latest_batch`
- `zangetsu.dashboard.view_models.{overview,arenas,candidates,survivors,feedback,health}`

## Tests Layout

```
zangetsu/tests/dashboard_mobile/
├── __init__.py
└── test_routes.py               (10 tests: health endpoint + all routes 200 +
                                   no fake zero + NOT_EVALUATED separate +
                                   survivor strictly separated + read-only HTTP
                                   verb enforcement + no forbidden imports +
                                   no write call patterns + 404 handling)
```

V1 dashboard tests (22) and V2 terminal tests (4) continue to pass — they validate the shared view-model layer the mobile UI depends on.

## Service Layout

- `ops/systemd/zangetsu-dashboard-mobile.service` — V3 unit, in-repo
- `scripts/zangetsu/run_dashboard_mobile.sh` — uvicorn launcher
- Drop-in: `~/.config/systemd/user/zangetsu-dashboard-mobile.service.d/tailscale-bind.conf` (host-specific Tailscale interface bind, kept untracked)
