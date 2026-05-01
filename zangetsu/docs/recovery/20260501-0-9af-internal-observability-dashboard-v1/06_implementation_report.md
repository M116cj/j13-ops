# 06 — Implementation Report

**ORDER**: 0-9AF — Phase 4

## Code Added (count + paths)

13 dashboard modules:
```
zangetsu/dashboard/config.py
zangetsu/dashboard/app.py
zangetsu/dashboard/data_sources/__init__.py
zangetsu/dashboard/data_sources/parsers.py
zangetsu/dashboard/data_sources/runtime_health.py
zangetsu/dashboard/data_sources/batch_artifacts.py
zangetsu/dashboard/view_models/__init__.py
zangetsu/dashboard/view_models/overview.py
zangetsu/dashboard/view_models/arenas.py
zangetsu/dashboard/view_models/candidates.py
zangetsu/dashboard/view_models/survivors.py
zangetsu/dashboard/view_models/feedback.py
zangetsu/dashboard/view_models/health.py
zangetsu/dashboard/components/__init__.py
zangetsu/dashboard/components/freshness_badge.py
zangetsu/dashboard/components/charts.py
zangetsu/dashboard/components/metric_cards.py
zangetsu/dashboard/components/tables.py
zangetsu/dashboard/components/filters.py
zangetsu/dashboard/pages/01_Overview.py
zangetsu/dashboard/pages/02_Core_Factory.py
zangetsu/dashboard/pages/03_Arena_A1.py
zangetsu/dashboard/pages/04_Arena_A2.py
zangetsu/dashboard/pages/05_Arena_A3.py
zangetsu/dashboard/pages/06_Candidates.py
zangetsu/dashboard/pages/07_Survivors.py
zangetsu/dashboard/pages/08_Rejects.py
zangetsu/dashboard/pages/09_Feedback.py
zangetsu/dashboard/pages/10_System_Health.py
```

5 dashboard tests:
```
zangetsu/tests/dashboard/test_parsers.py
zangetsu/tests/dashboard/test_freshness_logic.py
zangetsu/tests/dashboard/test_view_models.py
zangetsu/tests/dashboard/test_no_fake_zero.py
zangetsu/tests/dashboard/test_dashboard_contracts.py
```

3 ops/scripts:
```
ops/systemd/zangetsu-dashboard.service
scripts/zangetsu/run_dashboard.sh
scripts/zangetsu/make_dashboard_screenshots.py
```

1 modified (lazy):
```
zangetsu/dashboard/__init__.py    (lazy create_dashboard_app re-export → coexist with legacy FastAPI without requiring fastapi at observability-import time)
```

## Dependencies

Installed in `/home/j13/zangetsu-dashboard-venv` (separate from system python):
- streamlit 1.57.0
- plotly 6.7.0
- pandas 3.0.2
- pyarrow 24.0.0
- kaleido + chromium (for screenshot export only)
- pillow 12.2.0

System python is unaffected (numba/numpy core_factory tests still pass with system python).

## Coexistence with Legacy FastAPI Dashboard

Existing `zangetsu/dashboard/api.py` (FastAPI) predates this order. To avoid breaking it:
1. `__init__.py` retains `create_dashboard_app` export, but lazily (via `__getattr__`) so importing the new observability modules in an environment without fastapi does not crash.
2. New code is in submodules; no name collision.
3. `tests/dashboard/test_dashboard_contracts.py` scopes contract checks to ONLY the 0-9AF modules (excludes legacy api.py / models.py / run.py).
