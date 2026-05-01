"""Dashboard configuration (read-only)."""
from __future__ import annotations
import os
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
RECOVERY_ROOT = REPO_ROOT / 'zangetsu' / 'docs' / 'recovery'

DEFAULT_HOST = os.environ.get('ZANGETSU_DASHBOARD_HOST', '127.0.0.1')
DEFAULT_PORT = int(os.environ.get('ZANGETSU_DASHBOARD_PORT', '8785'))
REFRESH_INTERVAL_S = int(os.environ.get('ZANGETSU_DASHBOARD_REFRESH', '20'))

# Freshness thresholds (seconds since artifact mtime)
FRESH_AGE_S = 60 * 60 * 6           # 6h → FRESH
STALE_AGE_S = 60 * 60 * 24 * 3      # 3d → STALE; older = OLD
