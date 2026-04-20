#!/usr/bin/env bash
# ============================================================
# calcifer_v071_watch.sh
# ------------------------------------------------------------
# Runs every 15 min via cron. Polls v0.7.1 dual-evidence VIEWs
# and writes a single JSON verdict to /tmp/calcifer_process_<color>.json.
#
# Color semantics (post 1-h grace from WORKER boot, not system boot):
#   GREEN  : activity + no excessive process exceptions
#   YELLOW : activity but drift in process metrics
#   RED    : zero activity OR process-exception flood
#
# Grace reference is the oldest zangetsu worker lock mtime; if no
# lock exists, workers are not running and the watch refuses to judge.
# ============================================================
set -u

PSQL() {
    docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu -t -A -F"|" -c "$1" 2>/dev/null
}

TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
COLOR="GREEN"
NOTES=""

# Worker uptime reference — mtime of the newest arena_pipeline lock
LOCK_DIR=/tmp/zangetsu
newest_mtime=0
for lock in "$LOCK_DIR"/arena_pipeline_w*.lock; do
    [ -e "$lock" ] || continue
    m=$(stat -c %Y "$lock" 2>/dev/null || echo 0)
    [ "$m" -gt "$newest_mtime" ] && newest_mtime=$m
done
NOW=$(date +%s)
if [ "$newest_mtime" -eq 0 ]; then
    WORKER_UP=-1
else
    WORKER_UP=$((NOW - newest_mtime))
fi

# If workers not running, don't judge recovery
if [ "$WORKER_UP" -eq -1 ]; then
    COLOR="NOT_RUNNING"
    NOTES="no_worker_locks_found"
else
    # Per-strategy queries
    j01_outcome=$(PSQL "SELECT COALESCE(total_fresh,0), COALESCE(indicator_alpha_ratio_pct,0) FROM fresh_pool_outcome_health WHERE strategy_id='j01'")
    j02_outcome=$(PSQL "SELECT COALESCE(total_fresh,0), COALESCE(indicator_alpha_ratio_pct,0) FROM fresh_pool_outcome_health WHERE strategy_id='j02'")
    j01_process=$(PSQL "SELECT COALESCE(compile_exception_count,0), COALESCE(evaluate_exception_count,0), COALESCE(indicator_terminal_exception_count,0), COALESCE(cache_hit_rate,0), COALESCE(admitted_rate,0) FROM fresh_pool_process_health WHERE strategy_id='j01'")
    j02_process=$(PSQL "SELECT COALESCE(compile_exception_count,0), COALESCE(evaluate_exception_count,0), COALESCE(indicator_terminal_exception_count,0), COALESCE(cache_hit_rate,0), COALESCE(admitted_rate,0) FROM fresh_pool_process_health WHERE strategy_id='j02'")

    IFS="|" read -r J01_TOTAL J01_RATIO <<< "${j01_outcome:-0|0}"
    IFS="|" read -r J02_TOTAL J02_RATIO <<< "${j02_outcome:-0|0}"
    IFS="|" read -r J01_PE J01_EE J01_IE J01_CH J01_AR <<< "${j01_process:-0|0|0|0|0}"
    IFS="|" read -r J02_PE J02_EE J02_IE J02_CH J02_AR <<< "${j02_process:-0|0|0|0|0}"

    # Grace: 1h from worker boot
    if [ "$WORKER_UP" -gt 3600 ]; then
        total=$(( ${J01_TOTAL:-0} + ${J02_TOTAL:-0} ))
        if [ "${total}" -lt 1 ]; then
            COLOR="RED"
            NOTES="zero_activity_after_1h_worker_grace"
        fi
        j01_ex=$(( ${J01_PE:-0} + ${J01_EE:-0} + ${J01_IE:-0} ))
        j02_ex=$(( ${J02_PE:-0} + ${J02_EE:-0} + ${J02_IE:-0} ))
        if [ "${j01_ex}" -gt 1000 ] || [ "${j02_ex}" -gt 1000 ]; then
            COLOR="RED"
            NOTES="${NOTES} process_exception_over_1000"
        elif { [ "${j01_ex}" -gt 100 ] || [ "${j02_ex}" -gt 100 ]; } && [ "$COLOR" = "GREEN" ]; then
            COLOR="YELLOW"
            NOTES="${NOTES} process_exception_over_100"
        fi
    else
        # Inside grace window — always GREEN unless process has errors already
        j01_ex=$(( ${J01_PE:-0} + ${J01_EE:-0} + ${J01_IE:-0} ))
        j02_ex=$(( ${J02_PE:-0} + ${J02_EE:-0} + ${J02_IE:-0} ))
        if [ "${j01_ex}" -gt 500 ] || [ "${j02_ex}" -gt 500 ]; then
            COLOR="YELLOW"
            NOTES="in_grace_but_early_exceptions"
        fi
    fi
fi

out="/tmp/calcifer_process_$(echo $COLOR | tr '[:upper:]' '[:lower:]').json"
rm -f /tmp/calcifer_process_green.json /tmp/calcifer_process_yellow.json /tmp/calcifer_process_red.json /tmp/calcifer_process_not_running.json 2>/dev/null

cat > "$out" <<EOF
{
  "ts": "$TS",
  "color": "$COLOR",
  "notes": "$(echo $NOTES | xargs)",
  "worker_uptime_sec": $WORKER_UP,
  "j01": {
    "outcome": {"total_fresh": ${J01_TOTAL:-0}, "indicator_alpha_ratio_pct": ${J01_RATIO:-0}},
    "process": {"compile_exception": ${J01_PE:-0}, "evaluate_exception": ${J01_EE:-0}, "indicator_terminal_exception": ${J01_IE:-0}, "cache_hit_rate": ${J01_CH:-0}, "admitted_rate": ${J01_AR:-0}}
  },
  "j02": {
    "outcome": {"total_fresh": ${J02_TOTAL:-0}, "indicator_alpha_ratio_pct": ${J02_RATIO:-0}},
    "process": {"compile_exception": ${J02_PE:-0}, "evaluate_exception": ${J02_EE:-0}, "indicator_terminal_exception": ${J02_IE:-0}, "cache_hit_rate": ${J02_CH:-0}, "admitted_rate": ${J02_AR:-0}}
  }
}
EOF
