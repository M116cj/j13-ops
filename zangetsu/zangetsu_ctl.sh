#!/bin/bash
# zangetsu_ctl.sh — start/stop/status/logs/health/reap for all Zangetsu V9 services
# Usage: ./zangetsu_ctl.sh {start|stop|status|restart|logs|health|reap}
set -e

BASE=~/j13-ops/zangetsu
VENV=$BASE/.venv/bin/python3
LOCK_DIR=/tmp/zangetsu
LOG_DIR=/tmp
A1_WORKERS=4  # Total A1 discovery workers

PSQL_CMD="docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu -t -c"

cd "$BASE"
mkdir -p "$LOCK_DIR"

# Load project secrets (DB password etc.) before spawning services.
# Services require os.environ[ZV5_DB_PASSWORD] with no fallback.
if [ -f "$BASE/secret/.env" ]; then
  set -a
  . "$BASE/secret/.env"
  set +a
else
  echo "FATAL: $BASE/secret/.env missing — services will crash on import"; exit 1
fi

start_if_not_running() {
  local name=$1 lock=$2 cmd=$3 log=$4
  if [ -f "$lock" ] && kill -0 "$(cat "$lock" 2>/dev/null)" 2>/dev/null; then
    echo "  $name: already running (pid=$(cat "$lock"))"
  else
    rm -f "$lock"
    eval "$cmd > $log 2>&1 &"
    local pid=$!
    disown $pid 2>/dev/null
    sleep 0.3
    echo "  $name: started (pid=$pid)"
  fi
}

case "${1:-status}" in
  start)
    # Clear stale Numba cache to prevent ModuleNotFoundError on cold restart
    find . -name '*.nbi' -not -path './.venv/*' -delete 2>/dev/null
    find . -name '*.nbc' -not -path './.venv/*' -delete 2>/dev/null
    echo "Starting Zangetsu V9 services ($A1_WORKERS A1 workers)..."

    # A1 workers split across strategy tracks (v0.7.0 engine split):
    #   w0, w1 -> J01 (harmonic K=2)
    #   w2, w3 -> J02 (ICIR K=5)
    # Each worker exports STRATEGY_ID; arena_pipeline.py reads it to
    # import the right strategy project's fitness_fn.
    for i in $(seq 0 $((A1_WORKERS - 1))); do
      if [ $i -lt 2 ]; then
        STRATEGY=j01
        LANE=baseline
      else
        STRATEGY=j02
        LANE=exploration
      fi
      start_if_not_running \
        "A1-W$i-${STRATEGY}" \
        "$LOCK_DIR/arena_pipeline_w${i}.lock" \
        "env STRATEGY_ID=${STRATEGY} A1_WORKER_ID=$i A1_WORKER_COUNT=$A1_WORKERS A1_LANE=$LANE $VENV services/arena_pipeline.py" \
        "$LOG_DIR/zangetsu_a1_w${i}.log"
    done

    # A23 Orchestrator
    start_if_not_running \
      "A23" \
      "$LOCK_DIR/arena23_orchestrator.lock" \
      "$VENV services/arena23_orchestrator.py" \
      "$LOG_DIR/zangetsu_a23.log"

    # A45 Orchestrator
    start_if_not_running \
      "A45" \
      "$LOCK_DIR/arena45_orchestrator.lock" \
      "$VENV services/arena45_orchestrator.py" \
      "$LOG_DIR/zangetsu_a45.log"


    sleep 5
    echo ""
    bash "$(dirname "$0")/zangetsu_ctl.sh" status
    ;;

  stop)
    echo "Stopping Zangetsu V9 services..."
    # Graceful: SIGTERM via lockfile PIDs
    for lock in $LOCK_DIR/*.lock; do
      [ -f "$lock" ] || continue
      pid=$(cat "$lock" 2>/dev/null)
      name=$(basename "$lock" .lock)
      if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null
        echo "  $name: SIGTERM -> $pid"
      fi
    done
    sleep 3
    # Force: kill anything remaining
    for p in $(pgrep -f 'services/arena' 2>/dev/null); do
      kill -9 "$p" 2>/dev/null && echo "  force killed $p"
    done
    rm -f $LOCK_DIR/*.lock
    echo "  All stopped."
    ;;

  restart)
    bash "$(dirname "$0")/zangetsu_ctl.sh" stop
    sleep 2
    bash "$(dirname "$0")/zangetsu_ctl.sh" start
    ;;

  status)
    echo "=== Zangetsu V5 Service Status ==="
    running=0
    for lock in $LOCK_DIR/*.lock; do
      [ -f "$lock" ] || continue
      pid=$(cat "$lock" 2>/dev/null)
      name=$(basename "$lock" .lock)
      if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        cpu=$(ps -p "$pid" -o pcpu= 2>/dev/null | tr -d ' ')
        mem=$(ps -p "$pid" -o pmem= 2>/dev/null | tr -d ' ')
        elapsed=$(ps -p "$pid" -o etime= 2>/dev/null | tr -d ' ')
        echo "  $name: RUNNING pid=$pid cpu=${cpu}% mem=${mem}% uptime=$elapsed"
        running=$((running + 1))
      else
        echo "  $name: DEAD (stale lock, pid=$pid)"
      fi
    done

    # Systemd services
    echo ""
    echo "=== Systemd Services ==="
    for unit in arena-pipeline arena23-orchestrator arena45-orchestrator console-api dashboard-api; do
      state=$(systemctl is-active "$unit" 2>/dev/null || echo "unknown")
      if [ "$state" = "active" ]; then
        pid=$(systemctl show "$unit" --property=MainPID --value 2>/dev/null)
        echo "  $unit: $state (pid=$pid)"
      else
        echo "  $unit: $state"
      fi
    done

    # Orphan check
    echo ""
    orphan_count=0
    for p in $(pgrep -f 'services/arena' 2>/dev/null); do
      found=0
      for lock in $LOCK_DIR/*.lock; do
        [ -f "$lock" ] && [ "$(cat "$lock" 2>/dev/null)" = "$p" ] && found=1
      done
      if [ "$found" = "0" ]; then
        echo "  ORPHAN: pid=$p ($(ps -p $p -o args= 2>/dev/null | head -c 60))"
        orphan_count=$((orphan_count + 1))
      fi
    done

    echo ""
    echo "  Total: $running locked services, $orphan_count orphans"
    echo ""
    echo "=== Pipeline Stats ==="
    $PSQL_CMD "
      SELECT 'v6_total:    ' || count(*) FROM champion_pipeline WHERE engine_hash LIKE 'zv5_%'
      UNION ALL SELECT 'candidates:  ' || count(*) FROM champion_pipeline WHERE status='CANDIDATE'
      UNION ALL SELECT 'deployable:  ' || count(*) FROM champion_pipeline WHERE status='DEPLOYABLE'
      UNION ALL SELECT 'a1_queue:    ' || count(*) FROM champion_pipeline WHERE status='ARENA1_COMPLETE'
      UNION ALL SELECT 'a3_queue:    ' || count(*) FROM champion_pipeline WHERE status='ARENA3_COMPLETE'
    " 2>/dev/null
    ;;

  logs)
    # Tail logs for all services via journalctl + log files
    # Usage: zangetsu_ctl.sh logs [service_name] [lines]
    local_service="${2:-}"
    lines="${3:-100}"

    if [ -n "$local_service" ]; then
      case "$local_service" in
        a1|a1-w*|pipeline)
          # Tail all A1 worker logs
          echo "=== A1 Worker Logs (last $lines lines each) ==="
          for i in $(seq 0 $((A1_WORKERS - 1))); do
            logfile="$LOG_DIR/zangetsu_a1_w${i}.log"
            if [ -f "$logfile" ]; then
              echo "--- A1-W$i ---"
              tail -n "$lines" "$logfile"
            fi
          done
          ;;
        a23|arena23)
          echo "=== Arena23 Logs ==="
          journalctl -u arena23-orchestrator -n "$lines" --no-pager 2>/dev/null || tail -n "$lines" "$LOG_DIR/zangetsu_a23.log" 2>/dev/null
          ;;
        a45|arena45)
          echo "=== Arena45 Logs ==="
          journalctl -u arena45-orchestrator -n "$lines" --no-pager 2>/dev/null || tail -n "$lines" "$LOG_DIR/zangetsu_a45.log" 2>/dev/null
          ;;
        console)
          echo "=== Console API Logs ==="
          journalctl -u console-api -n "$lines" --no-pager 2>/dev/null
          ;;
        dashboard)
          echo "=== Dashboard API Logs ==="
          journalctl -u dashboard-api -n "$lines" --no-pager 2>/dev/null
          ;;
        *)
          echo "Unknown service: $local_service"
          echo "Available: a1, a23, a45, console, dashboard"
          exit 1
          ;;
      esac
    else
      # Follow all services (live tail)
      echo "=== Live tail of all Zangetsu V9 services (Ctrl+C to stop) ==="
      journalctl -u arena-pipeline -u arena23-orchestrator -u arena45-orchestrator \
                 -u console-api -u dashboard-api \
                 -f --no-pager 2>/dev/null &
      JOURNAL_PID=$!

      # Also tail lockfile-managed worker logs
      tail -f $LOG_DIR/zangetsu_a1_w*.log $LOG_DIR/zangetsu_a23.log $LOG_DIR/zangetsu_a45.log 2>/dev/null &
      TAIL_PID=$!

      trap "kill $JOURNAL_PID $TAIL_PID 2>/dev/null; exit 0" INT TERM
      wait
    fi
    ;;

  health)
    echo "=== Zangetsu V5 Health Check ==="
    echo ""

    # 1. Disk usage
    echo "--- Disk ---"
    df -h / /home 2>/dev/null | grep -v tmpfs
    echo ""

    # 2. Memory
    echo "--- Memory ---"
    free -h 2>/dev/null || vm_stat 2>/dev/null
    echo ""

    # 3. GPU (if nvidia-smi available)
    if command -v nvidia-smi &>/dev/null; then
      echo "--- GPU ---"
      nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader 2>/dev/null
      echo ""
    fi

    # 4. Database health
    echo "--- Database ---"
    db_ok=true
    if ! docker exec deploy-postgres-1 pg_isready -U zangetsu -d zangetsu -q 2>/dev/null; then
      echo "  PostgreSQL: NOT READY"
      db_ok=false
    else
      echo "  PostgreSQL: OK"
      # Connection count
      $PSQL_CMD "SELECT 'connections: ' || count(*) FROM pg_stat_activity WHERE datname='zangetsu'" 2>/dev/null
      # Dead tuples (top 3 tables)
      echo "  Top dead-tuple tables:"
      $PSQL_CMD "
        SELECT '    ' || schemaname || '.' || relname || ': ' || n_dead_tup || ' dead'
        FROM pg_stat_user_tables
        ORDER BY n_dead_tup DESC LIMIT 3
      " 2>/dev/null
      # DB size
      $PSQL_CMD "SELECT 'db_size: ' || pg_size_pretty(pg_database_size('zangetsu'))" 2>/dev/null
    fi
    echo ""

    # 5. Active services
    echo "--- Services ---"
    total_ok=0
    total_bad=0
    for unit in arena-pipeline arena23-orchestrator arena45-orchestrator console-api dashboard-api; do
      state=$(systemctl is-active "$unit" 2>/dev/null || echo "unknown")
      if [ "$state" = "active" ]; then
        total_ok=$((total_ok + 1))
        echo "  $unit: OK"
      else
        total_bad=$((total_bad + 1))
        echo "  $unit: $state !!!"
      fi
    done
    echo ""

    # 6. Stuck entries in DB
    echo "--- Stuck PROCESSING entries ---"
    if $db_ok; then
      $PSQL_CMD "
        SELECT status || ': ' || count(*)
        FROM champion_pipeline
        WHERE status LIKE '%PROCESSING%'
          AND updated_at < NOW() - INTERVAL '30 minutes'
        GROUP BY status
      " 2>/dev/null
      stuck=$($PSQL_CMD "
        SELECT count(*)
        FROM champion_pipeline
        WHERE status LIKE '%PROCESSING%'
          AND updated_at < NOW() - INTERVAL '30 minutes'
      " 2>/dev/null | tr -d ' ')
      if [ "${stuck:-0}" -gt 0 ]; then
        echo "  WARNING: $stuck entries stuck in PROCESSING >30min (use 'reap' to fix)"
      else
        echo "  None stuck."
      fi
    fi
    echo ""

    # 7. Log file sizes
    echo "--- Log Sizes ---"
    for f in $LOG_DIR/zangetsu_*.log $BASE/logs/engine.jsonl; do
      [ -f "$f" ] || continue
      size=$(du -h "$f" 2>/dev/null | cut -f1)
      echo "  $(basename "$f"): $size"
    done
    echo ""

    # Summary
    echo "--- Summary ---"
    echo "  Services: $total_ok OK, $total_bad down"
    if [ "$total_bad" -gt 0 ] || [ "${stuck:-0}" -gt 0 ]; then
      echo "  STATUS: DEGRADED"
    else
      echo "  STATUS: HEALTHY"
    fi
    ;;

  reap)
    # Reset stuck PROCESSING entries back to their previous queue status
    # Usage: zangetsu_ctl.sh reap [--dry-run] [--age MINUTES]
    dry_run=false
    age_minutes=30

    shift || true
    while [ $# -gt 0 ]; do
      case "$1" in
        --dry-run) dry_run=true; shift ;;
        --age) age_minutes="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
      esac
    done

    echo "=== Reaping stuck PROCESSING entries (older than ${age_minutes}min) ==="
    echo ""

    # Show what will be reaped
    echo "--- Stuck entries ---"
    $PSQL_CMD "
      SELECT id, status, worker_id,
             ROUND(EXTRACT(EPOCH FROM (NOW() - updated_at))/60) || 'min ago' AS age
      FROM champion_pipeline
      WHERE status LIKE '%PROCESSING%'
        AND updated_at < NOW() - INTERVAL '${age_minutes} minutes'
      ORDER BY updated_at
    " 2>/dev/null

    count=$($PSQL_CMD "
      SELECT count(*)
      FROM champion_pipeline
      WHERE status LIKE '%PROCESSING%'
        AND updated_at < NOW() - INTERVAL '${age_minutes} minutes'
    " 2>/dev/null | tr -d ' ')

    if [ "${count:-0}" -eq 0 ]; then
      echo "  No stuck entries found."
      exit 0
    fi

    echo ""
    echo "  Found $count stuck entries."

    if $dry_run; then
      echo "  DRY RUN — no changes made."
      exit 0
    fi

    # Reset each PROCESSING status back to its pre-processing state
    # ARENA2_PROCESSING -> ARENA1_COMPLETE
    # ARENA3_PROCESSING -> ARENA2_COMPLETE
    # ARENA4_PROCESSING -> ARENA3_COMPLETE
    # ARENA5_PROCESSING -> ARENA4_COMPLETE (if exists)
    echo ""
    echo "--- Resetting ---"

    for mapping in \
      "ARENA2_PROCESSING:ARENA1_COMPLETE" \
      "ARENA3_PROCESSING:ARENA2_COMPLETE" \
      "ARENA4_PROCESSING:ARENA3_COMPLETE" \
      "ARENA5_PROCESSING:ARENA4_COMPLETE"; do

      from="${mapping%%:*}"
      to="${mapping##*:}"

      affected=$($PSQL_CMD "
        UPDATE champion_pipeline
        SET status = '$to', worker_id = NULL, updated_at = NOW()
        WHERE status = '$from'
          AND updated_at < NOW() - INTERVAL '${age_minutes} minutes'
        RETURNING id
      " 2>/dev/null | grep -c '[0-9]' || echo 0)

      if [ "$affected" -gt 0 ]; then
        echo "  $from -> $to: $affected entries reset"
      fi
    done

    # Log the reap event
    echo ""
    total_reaped=$($PSQL_CMD "SELECT 'total_reaped'" 2>/dev/null | wc -l || echo 0)
    echo "  Reap complete. Run 'bash "$(dirname "$0")/zangetsu_ctl.sh" status' to verify pipeline."
    ;;

  *)
    echo "Usage: $0 {start|stop|status|restart|logs|health|reap}"
    echo ""
    echo "Commands:"
    echo "  start    Start all arena workers + orchestrators"
    echo "  stop     Graceful stop all services"
    echo "  restart  Stop then start"
    echo "  status   Show running services + pipeline stats"
    echo "  logs     Tail logs (usage: logs [a1|a23|a45|console|dashboard] [lines])"
    echo "  health   Full health check (DB, disk, memory, services, stuck entries)"
    echo "  reap     Reset stuck PROCESSING entries (usage: reap [--dry-run] [--age MINUTES])"
    exit 1
    ;;
esac
