#!/bin/bash
# Watchdog — checks each service independently, restarts only the dead one
# Install: crontab -e → */5 * * * * ~/j13-ops/zangetsu/watchdog.sh >> /tmp/zv5_watchdog.log 2>&1
#
# NOTE: This replaces the old watchdog that killed ALL services when one was dead.
#       Also replaces scripts/watchdog_arena23.sh — remove that cron entry.

LOCK_DIR=/tmp/zangetsu
BASE=~/j13-ops/zangetsu
VENV=$BASE/.venv/bin/python3
LOG_DIR=/tmp
ENGINE_LOG=$BASE/logs/engine.jsonl
MAX_LOG_SIZE=$((50 * 1024 * 1024))  # 50MB
MAX_ROTATIONS=2
STALE_THRESHOLD=600  # 10 minutes — service considered unhealthy if log not updated

# Systemd-managed services (prefer systemctl restart for these)
SYSTEMD_SERVICES=(
  arena-pipeline
  arena23-orchestrator
  arena45-orchestrator
  console-api
  dashboard-api
)

# Lockfile-to-systemd mapping
declare -A LOCK_TO_SYSTEMD=(
  [arena_pipeline_w0]=arena-pipeline
  [arena23_orchestrator]=arena23-orchestrator
  [arena45_orchestrator]=arena45-orchestrator
)

# Lockfile-to-log mapping (for health checks)
declare -A LOCK_TO_LOG=(
  [arena_pipeline_w0]=$LOG_DIR/zv5_a1_w0.log
  [arena_pipeline_w1]=$LOG_DIR/zv5_a1_w1.log
  [arena_pipeline_w2]=$LOG_DIR/zv5_a1_w2.log
  [arena_pipeline_w3]=$LOG_DIR/zv5_a1_w3.log
  [arena23_orchestrator]=$LOG_DIR/zv5_a23.log
  [arena45_orchestrator]=$LOG_DIR/zv5_a45.log
)

timestamp() {
  date -u '+%Y-%m-%dT%H:%M:%S'
}

# --- Log Rotation ---
rotate_log() {
  local logfile=$1
  local max_size=$2
  local max_keep=$3

  [ -f "$logfile" ] || return 0
  local size
  size=$(stat -c%s "$logfile" 2>/dev/null || stat -f%z "$logfile" 2>/dev/null)
  [ -z "$size" ] && return 0

  if [ "$size" -gt "$max_size" ]; then
    # Rotate: .2 -> delete, .1 -> .2, current -> .1
    local i=$max_keep
    while [ $i -gt 1 ]; do
      prev=$((i - 1))
      [ -f "${logfile}.${prev}" ] && mv -f "${logfile}.${prev}" "${logfile}.${i}"
      i=$((i - 1))
    done
    mv -f "$logfile" "${logfile}.1"
    echo "$(timestamp) WATCHDOG: rotated $logfile (was ${size} bytes)" >> /tmp/zv5_watchdog.log
  fi
}

# --- Health Check: is log file recently updated? ---
check_log_activity() {
  local logfile=$1
  [ -f "$logfile" ] || return 1  # no log = unhealthy

  local now
  now=$(date +%s)
  local mtime
  mtime=$(stat -c%Y "$logfile" 2>/dev/null || stat -f%m "$logfile" 2>/dev/null)
  [ -z "$mtime" ] && return 1

  local age=$((now - mtime))
  if [ "$age" -gt "$STALE_THRESHOLD" ]; then
    return 1  # stale
  fi
  return 0
}

# --- Restart a single service ---
restart_service() {
  local name=$1
  local systemd_unit=${LOCK_TO_SYSTEMD[$name]:-}

  if [ -n "$systemd_unit" ]; then
    # Prefer systemd restart if this service has a unit
    echo "$(timestamp) WATCHDOG: restarting $name via systemd ($systemd_unit)"
    sudo systemctl restart "$systemd_unit" 2>/dev/null
    return $?
  fi

  # Fallback: lockfile-based restart for A1 workers w1-w3 (not in systemd)
  local lock="$LOCK_DIR/${name}.lock"
  local log="${LOCK_TO_LOG[$name]:-$LOG_DIR/zv5_${name}.log}"

  # Kill old process if still around
  if [ -f "$lock" ]; then
    local old_pid
    old_pid=$(cat "$lock" 2>/dev/null)
    if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
      kill "$old_pid" 2>/dev/null
      sleep 1
    fi
    rm -f "$lock"
  fi

  # Determine start command from name
  local cmd=""
  case "$name" in
    arena_pipeline_w*)
      local worker_id=${name##*_w}
      cmd="env A1_WORKER_ID=$worker_id A1_WORKER_COUNT=4 $VENV $BASE/services/arena_pipeline.py"
      ;;
    arena23_orchestrator)
      cmd="$VENV $BASE/services/arena23_orchestrator.py"
      ;;
    arena45_orchestrator)
      cmd="$VENV $BASE/services/arena45_orchestrator.py"
      ;;
    *)
      echo "$(timestamp) WATCHDOG: unknown service $name, cannot restart"
      return 1
      ;;
  esac

  cd "$BASE"
  eval "$cmd > $log 2>&1 &"
  local pid=$!
  disown $pid 2>/dev/null
  echo "$(timestamp) WATCHDOG: restarted $name (pid=$pid)"
}

# ========== MAIN ==========

# 1. Rotate engine.jsonl if too large
rotate_log "$ENGINE_LOG" "$MAX_LOG_SIZE" "$MAX_ROTATIONS"

# 2. Rotate service logs in /tmp if too large (same threshold)
for logfile in $LOG_DIR/zv5_*.log; do
  [ -f "$logfile" ] || continue
  rotate_log "$logfile" "$MAX_LOG_SIZE" "$MAX_ROTATIONS"
done

# 3. Check each lockfile-managed service independently
dead_count=0
running_count=0

for lock in $LOCK_DIR/*.lock; do
  [ -f "$lock" ] || continue
  pid=$(cat "$lock" 2>/dev/null)
  name=$(basename "$lock" .lock)

  alive=false
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    alive=true
  fi

  if ! $alive; then
    echo "$(timestamp) WATCHDOG: $name is DEAD (pid=$pid), restarting..."
    restart_service "$name"
    dead_count=$((dead_count + 1))
  else
    # Process exists, but check log activity for deeper health
    logfile="${LOCK_TO_LOG[$name]:-}"
    if [ -n "$logfile" ] && ! check_log_activity "$logfile"; then
      echo "$(timestamp) WATCHDOG: $name pid=$pid alive but log stale (>$(( STALE_THRESHOLD / 60 ))min), restarting..."
      restart_service "$name"
      dead_count=$((dead_count + 1))
    else
      running_count=$((running_count + 1))
    fi
  fi
done

# 4. Also check systemd-only services (console-api, dashboard-api)
for unit in console-api dashboard-api; do
  if ! systemctl is-active --quiet "$unit" 2>/dev/null; then
    echo "$(timestamp) WATCHDOG: systemd $unit is not active, restarting..."
    sudo systemctl restart "$unit" 2>/dev/null
    dead_count=$((dead_count + 1))
  else
    running_count=$((running_count + 1))
  fi
done

# 5. Periodic health log (every 30 min)
if [ "$dead_count" -eq 0 ]; then
  minute=$(date +%M)
  if [ $((minute % 30)) -lt 5 ]; then
    echo "$(timestamp) WATCHDOG: all $running_count services healthy"
  fi
fi
