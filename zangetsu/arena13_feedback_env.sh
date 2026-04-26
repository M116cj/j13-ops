#!/usr/bin/env bash
set -euo pipefail
# Load local runtime secrets for cron-launched arena13 feedback loop.
# This file must not print secrets.
if [ -f "$HOME/.env.global" ]; then
  set -a
  . "$HOME/.env.global"
  set +a
fi
cd /home/j13/j13-ops/zangetsu
exec /home/j13/j13-ops/zangetsu/.venv/bin/python /home/j13/j13-ops/zangetsu/services/arena13_feedback.py
