#!/bin/bash
# Watchdog: auto-restart arena23 if not running
PROC="arena23_orchestrator.py"
LOG="/tmp/zangetsu_arena23.log"

if ! pgrep -f "$PROC" > /dev/null; then
    echo "$(date): arena23 not running, restarting..." >> /tmp/watchdog_arena23.log
    cd /home/j13/j13-ops
    nohup /home/j13/j13-ops/zangetsu/.venv/bin/python3 /home/j13/j13-ops/zangetsu/services/arena23_orchestrator.py > "$LOG" 2>&1 &
    echo "$(date): restarted PID=$!" >> /tmp/watchdog_arena23.log
fi
