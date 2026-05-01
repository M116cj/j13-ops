"""Dashboard module.

Two coexisting interfaces inside this package:

1. Legacy FastAPI dashboard (api.py, models.py, run.py, static/) — predates 0-9AF.
2. 0-9AF observability dashboard — Streamlit-based; entrypoint
   `zangetsu/dashboard/app.py` plus modules under
   `data_sources/`, `view_models/`, `components/`, `pages/`.

The `create_dashboard_app` re-export is lazy so importing the observability
modules does not require FastAPI to be installed.
"""

__all__ = ['create_dashboard_app']


def __getattr__(name):
    if name == 'create_dashboard_app':
        from .api import create_dashboard_app as _factory  # lazy
        return _factory
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
