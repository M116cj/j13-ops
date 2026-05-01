# 07 — Backend Implementation Report

**ORDER**: 0-9AF-REDESIGN — Phase 4 (backend layer)

## Backend Choice

Streamlit's Python runtime serves as the backend layer. No separate FastAPI service was added because:

1. The dashboard is single-user / single-tenant (one operator at a time).
2. All data sources are file-based artifacts under `docs/recovery/` — direct file IO is faster than serializing through HTTP.
3. Adding FastAPI would duplicate the existing legacy `zangetsu/dashboard/api.py` surface and increase deploy complexity.
4. Streamlit's @st.cache_data (TTL = 20 s) gives the same caching benefit a FastAPI route would.

## Backend Modules

| Module | Role |
|---|---|
| `zangetsu.dashboard.config` | Paths, port, refresh interval, freshness thresholds |
| `zangetsu.dashboard.data_sources.parsers` | parse_jsonl / parse_csv / parse_json with state |
| `zangetsu.dashboard.data_sources.runtime_health` | freshness_for(path) → FreshnessReport |
| `zangetsu.dashboard.data_sources.batch_artifacts` | load_batch_from_folder + load_latest_batch + REQUIRED_FILES |
| `zangetsu.dashboard.view_models.{overview,arenas,candidates,survivors,feedback,health}` | Pure-function transforms BatchView → typed dataclasses |

## Truthfulness Guarantees in the Backend Layer

- `build_overview` returns `state='NO_DATA'` (not zero) when run_summary missing.
- `build_a3` returns `state='NOT_AVAILABLE'` (not zero) since shadow orders never run A3.
- `survivor_bank.is_survivor` requires `status == 'PASSED'`; `is_near_survivor` requires `status == 'REJECTED'` AND -5 ≤ net ≤ 0.
- `feedback_weights_from_summary` returns `status='EMPTY_WITH_REASON'` when no rejections; never fakes weights.

These guarantees are inherited unchanged from V1 — verified by the existing 22 V1 dashboard tests + 4 new terminal contract tests.

## Service Restart Cost

Backend changes do NOT require service restart for view-model logic edits — Streamlit auto-reloads on file change. Only `theme.py` / `app.py` structural changes need a hard restart, handled by `systemctl --user restart zangetsu-dashboard-terminal.service`.

## API Contract for Future Frontend Migration

If V3 ever migrates to React + FastAPI, the view-model layer (`view_models/*`) is already framework-agnostic — every function takes BatchView and returns a dataclass. Wrapping each in a `/api/` route is a mechanical step.
