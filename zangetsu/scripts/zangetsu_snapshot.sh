#!/bin/bash
# zangetsu_snapshot.sh — produce /tmp/zangetsu_live.json, 1-shot atomic write
# deploy: copy to Alaya /home/j13/j13-ops/zangetsu/scripts/zangetsu_snapshot.sh
# schedule: * * * * * bash /home/j13/j13-ops/zangetsu/scripts/zangetsu_snapshot.sh
# read:    ssh j13@100.123.49.102 "cat /tmp/zangetsu_live.json"

set -u
OUT=/tmp/zangetsu_live.json
TMP=/tmp/zangetsu_live.json.tmp
LOG=/home/j13/j13-ops/zangetsu/logs/engine.jsonl

TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# workers (tolerate grep-no-match)
A1=$(ps -eo args | grep -c "services/arena_pipeline.py" || echo 0)
A2=$(ps -eo args | grep -c "services/arena23_orchestrator.py" || echo 0)
A45=$(ps -eo args | grep -c "services/arena45_orchestrator.py" || echo 0)
# subtract the grep process itself if it shows up
A1=$((A1 > 0 ? A1 - 1 : 0)); A2=$((A2 > 0 ? A2 - 1 : 0)); A45=$((A45 > 0 ? A45 - 1 : 0))

# db: v10 breakdown all-time + last 1h
V10_DB=$(docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu -t -A -F'|' -c "SELECT status, count(*) FROM champion_pipeline WHERE engine_hash='zv5_v10_alpha' GROUP BY status ORDER BY status" 2>/dev/null | tr '\n' ';')
V10_1H=$(docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu -t -A -F'|' -c "SELECT status, count(*) FROM champion_pipeline WHERE engine_hash='zv5_v10_alpha' AND updated_at > NOW() - INTERVAL '1 hour' GROUP BY status" 2>/dev/null | tr '\n' ';')
# orphan processing
ORPHAN=$(docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu -t -A -c "SELECT count(*) FROM champion_pipeline WHERE worker_id IS NOT NULL AND status IN ('ARENA2_PROCESSING','ARENA3_PROCESSING','ARENA4_PROCESSING')" 2>/dev/null || echo -1)

# recent bad errors in last 500 lines (exclude benign duplicate-key noise)
# grep -c always outputs a number; exit status 1 means 0 matches — don't use || echo 0 (would duplicate)
BAD_ERR=$(tail -500 "$LOG" 2>/dev/null | grep -E "ERROR|Traceback|NameError|signal_gen failed|too many values|no_valid_combos" | grep -vc "uniq_alpha_hash_v10" 2>/dev/null)
[ -z "$BAD_ERR" ] && BAD_ERR=0

# disk
DISK_PCT=$(df -h /home/j13 2>/dev/null | awk 'NR==2 {print $5}' | tr -d '%')
LOG_MB=$(du -m "$LOG" 2>/dev/null | awk '{print $1}')

# A2 cumulative stats (from latest stats line)
A2_STATS=$(tail -2000 "$LOG" 2>/dev/null | grep "A2 stats" | tail -1 | sed 's/.*msg": "//; s/".*//' || echo "")

# version (top of VERSION_LOG)
VERSION=$(grep -E "^## v" /home/j13/j13-ops/zangetsu/VERSION_LOG.md 2>/dev/null | head -1 | sed 's/## //; s/ — .*//' || echo "unknown")

# build JSON atomically
cat > "$TMP" <<EOF
{
  "ts": "$TS",
  "version_log_top": "$VERSION",
  "workers": {"a1": $A1, "a23": $A2, "a45": $A45, "expected_core": 6, "healthy": $( [ $((A1+A2+A45)) -ge 6 ] && echo true || echo false )},
  "v10_db": "$V10_DB",
  "v10_last_1h": "$V10_1H",
  "orphan_processing": $ORPHAN,
  "recent_bad_errors": ${BAD_ERR:-0},
  "disk_pct": ${DISK_PCT:-0},
  "log_mb": ${LOG_MB:-0},
  "a2_stats_latest": "$A2_STATS"
}
EOF

mv "$TMP" "$OUT"
chmod 644 "$OUT"
