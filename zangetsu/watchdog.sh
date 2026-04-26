#!/bin/bash
# Load local runtime secrets for cron-launched workers.
# File is local-only, not committed, and must not be printed.
if [ -f "$HOME/.env.global" ]; then
  set -a
  . "$HOME/.env.global"
  set +a
fi

# Watchdog — checks each service independently, restarts only the dead one
# Install: crontab -e → */5 * * * * ~/j13-ops/zangetsu/watchdog.sh >> /tmp/zangetsu_watchdog.log 2>&1
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
STALE_THRESHOLD=1800  # 10 minutes — service considered unhealthy if log not updated



# Lockfile-to-log mapping (for health checks)
declare -A LOCK_TO_LOG=(
  [arena_pipeline_w0]=$LOG_DIR/zangetsu_a1_w0.log
  [arena_pipeline_w1]=$LOG_DIR/zangetsu_a1_w1.log
  [arena_pipeline_w2]=$LOG_DIR/zangetsu_a1_w2.log
  [arena_pipeline_w3]=$LOG_DIR/zangetsu_a1_w3.log
  [arena23_orchestrator]=$LOG_DIR/zangetsu_a23.log
  [arena45_orchestrator]=$LOG_DIR/zangetsu_a45.log
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
    echo "$(timestamp) WATCHDOG: rotated $logfile (was ${size} bytes)" >> /tmp/zangetsu_watchdog.log
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

# --- Reclaim lockfile: SIGTERM -> poll -> SIGKILL -> verify -> rm ---
# P1-I: services/pidlock.py uses fcntl.flock() on the opened fd.
# The advisory lock is bound to the inode, not the dentry. The old
# `rm -f $lock` + fire-and-forget kill pattern unlinked the dentry while
# the dead-but-not-reaped process still held the flock on the old inode.
# A new service process would then open() a brand-new inode, acquire a
# new flock, and two workers would run concurrently -> double DB writes.
#
# Correct protocol:
#   1. Empty pidfile or pid=1 -> stale, just rm.
#   2. pid not alive -> stale, just rm.
#   3. pid alive -> SIGTERM, poll kill-0 up to 10s (atexit is cheap),
#      then SIGKILL + 1s, then a final kill-0 verification. Only rm the
#      lockfile AFTER the kernel has reclaimed the old fd+inode+flock.
#   4. Still alive after SIGKILL -> return 1 (caller must abort restart
#      rather than spawn a second worker on a fresh inode).
reclaim_lock() {
  local lock=$1
  local name=$2
  [ -f "$lock" ] || return 0

  local old_pid
  old_pid=$(cat "$lock" 2>/dev/null)

  # Empty pidfile or PID 1 (init) -> stale, never signal init
  if [ -z "$old_pid" ] || [ "$old_pid" = "1" ]; then
    rm -f "$lock"
    return 0
  fi

  # PID not alive -> stale file, kernel already released the flock
  if ! kill -0 "$old_pid" 2>/dev/null; then
    rm -f "$lock"
    return 0
  fi

  # PID alive -> graceful terminate, then WAIT for exit (flock release)
  kill -TERM "$old_pid" 2>/dev/null || true

  local waited=0
  local max_wait=10
  while [ $waited -lt $max_wait ]; do
    if ! kill -0 "$old_pid" 2>/dev/null; then
      break
    fi
    sleep 1
    waited=$((waited + 1))
  done

  # Still alive after SIGTERM window -> force kill, wait one tick
  if kill -0 "$old_pid" 2>/dev/null; then
    echo "$(timestamp) WATCHDOG: $name pid=$old_pid ignored SIGTERM after ${max_wait}s, SIGKILL"
    kill -KILL "$old_pid" 2>/dev/null || true
    sleep 1
  fi

  # Final verification — refuse to rm lock + respawn if still alive
  # (zombie parent / ptrace hold / kernel bug).
  if kill -0 "$old_pid" 2>/dev/null; then
    echo "$(timestamp) WATCHDOG: $name pid=$old_pid UNKILLABLE, skipping restart to avoid double-worker race"
    return 1
  fi

  # Safe: old process gone, kernel has released flock on its inode.
  rm -f "$lock"
  return 0
}

# --- Restart a single service ---
restart_service() {
  local name=$1
  # Fallback: lockfile-based restart for A1 workers w1-w3 (not in systemd)
  local lock="$LOCK_DIR/${name}.lock"
  local log="${LOCK_TO_LOG[$name]:-$LOG_DIR/zangetsu_${name}.log}"

  # Reclaim lock with kill -> wait -> verify; abort restart if unkillable
  # so we never spawn a second worker racing on a fresh inode.
  if ! reclaim_lock "$lock" "$name"; then
    echo "$(timestamp) WATCHDOG: aborting $name restart (stuck old process)"
    return 1
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
for logfile in $LOG_DIR/zangetsu_*.log; do
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

  # Cron-managed services: lock file persists between runs, skip
  case "$name" in
    arena13_feedback|calcifer_supervisor|alpha_discovery) continue ;;
  esac

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
    # Orchestrators (A23/A45) idle when no candidates -> skip stale-log check, only PID-alive
    case "$name" in
      arena23_orchestrator|arena45_orchestrator)
        running_count=$((running_count + 1))
        continue
        ;;
    esac
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
