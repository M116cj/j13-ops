#!/usr/bin/env bash
# 0-9AF V2 — internal observability terminal runner.
set -euo pipefail
VENV=${VENV:-/home/j13/zangetsu-dashboard-venv}
REPO=${REPO:-/home/j13/j13-ops}
HOST=${ZANGETSU_DASHBOARD_HOST:-127.0.0.1}
PORT=${ZANGETSU_DASHBOARD_PORT:-8785}
cd "$REPO"
exec "$VENV/bin/streamlit" run zangetsu/dashboard_terminal/app.py \
  --server.address "$HOST" \
  --server.port "$PORT" \
  --server.headless true \
  --browser.gatherUsageStats false \
  --theme.base dark \
  --theme.primaryColor '#38bdf8' \
  --theme.backgroundColor '#0b0f17' \
  --theme.secondaryBackgroundColor '#11161f' \
  --theme.textColor '#e2e8f0' \
  --theme.font 'monospace'
