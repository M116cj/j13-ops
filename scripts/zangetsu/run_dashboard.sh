#!/usr/bin/env bash
# 0-9AF — internal observability dashboard runner.
# Read-only: binds 127.0.0.1 only; no public exposure.
set -euo pipefail
VENV=${VENV:-/home/j13/zangetsu-dashboard-venv}
REPO=${REPO:-/home/j13/j13-ops}
HOST=${ZANGETSU_DASHBOARD_HOST:-127.0.0.1}
PORT=${ZANGETSU_DASHBOARD_PORT:-8785}
cd "$REPO"
exec "$VENV/bin/streamlit" run zangetsu/dashboard/app.py \
  --server.address "$HOST" \
  --server.port "$PORT" \
  --server.headless true \
  --browser.gatherUsageStats false
