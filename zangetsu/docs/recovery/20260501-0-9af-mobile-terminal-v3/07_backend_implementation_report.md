# 07 — Backend Implementation Report (V3)

**ORDER**: 0-9AF-MOBILE-TERMINAL-V3 — Phase 4 (backend)

## Backend Choice

**FastAPI + uvicorn**, serving server-rendered HTML via Jinja2 templates.

Rejected alternatives:
- Streamlit (V2): broken on phone — owner verdict
- React + Vite + TS: would require Node/npm/build pipeline; serves over HTTP a separate API anyway; mobile TTFB is worse for a dashboard checked via cellular Tailscale.

## Modules

| File | Role |
|---|---|
| `zangetsu/dashboard_mobile/app.py` | FastAPI app + 8 route handlers + 2 health endpoints |
| `zangetsu/dashboard_mobile/templates/_base.html` | layout shell + viewport meta + 30s refresh |
| `zangetsu/dashboard_mobile/templates/_topbar.html` | sticky status bar |
| `zangetsu/dashboard_mobile/templates/_bottomnav.html` | fixed nav |
| `zangetsu/dashboard_mobile/templates/{overview,funnel,candidates,candidate_detail,rejects,survivors,feedback,health}.html` | page bodies |
| `zangetsu/dashboard_mobile/static/style.css` | pure-black theme |

View-models reused unchanged from V1.

## Route Read-Only Enforcement

`test_app_is_read_only_no_write_paths` enumerates all `app.routes` and asserts none expose POST / PUT / PATCH / DELETE methods. The dashboard cannot accept a write request — even if a future regression added a form, the test would fail.

## Caching

Each request rebuilds view-models (cheap — file IO ~ ms). The client-side meta-refresh forces a full page reload every 30 s, which keeps state simple. A future V3.1 could add `@functools.lru_cache(maxsize=4)` on `load_batch_from_folder(folder)` to halve latency on repeat hits.

## Healthchecks

- `GET /_stcore/health` → `{"status": "ok"}` (compat with V1/V2 monitor patterns)
- `GET /healthz` → `{"ok": true}` (alt simpler form)

## Service

`zangetsu-dashboard-mobile.service` (systemd user unit, hardened: `ProtectHome=read-only`, `ProtectSystem=strict`, `PrivateTmp=yes`, `NoNewPrivileges=yes`).

Verified live:
```
$ systemctl --user is-active zangetsu-dashboard-mobile.service
active

$ curl -sS http://100.123.49.102:8785/_stcore/health
{"status":"ok"}
```
