#!/usr/bin/env bash
# 0-9AF V3 — mobile observability terminal runner.
set -euo pipefail
VENV=${VENV:-/home/j13/zangetsu-dashboard-venv}
REPO=${REPO:-/home/j13/j13-ops}
HOST=${ZANGETSU_DASHBOARD_HOST:-127.0.0.1}
PORT=${ZANGETSU_DASHBOARD_PORT:-8785}
cd "$REPO"
exec "$VENV/bin/uvicorn" zangetsu.dashboard_mobile.app:app \
  --host "$HOST" --port "$PORT" --no-access-log --workers 1
