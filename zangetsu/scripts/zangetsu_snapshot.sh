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

# db: fresh pool breakdown (Epoch B only) + archive reference count
V10_DB=$(docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu -t -A -F'|' -c "SELECT status, count(*) FROM champion_pipeline_fresh GROUP BY status ORDER BY status" 2>/dev/null | tr '\n' ';')
V10_1H=$(docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu -t -A -F'|' -c "SELECT status, count(*) FROM champion_pipeline_fresh WHERE updated_at > NOW() - INTERVAL '1 hour' GROUP BY status" 2>/dev/null | tr '\n' ';')
ARCHIVE_COUNT=$(docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu -t -A -c "SELECT count(*) FROM champion_legacy_archive" 2>/dev/null || echo 0)
# orphan processing
ORPHAN=$(docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu -t -A -c "SELECT count(*) FROM champion_pipeline_fresh WHERE worker_id_str IS NOT NULL AND status IN ('ARENA2_PROCESSING','ARENA3_PROCESSING','ARENA4_PROCESSING')" 2>/dev/null || echo -1)

# recent bad errors in last 500 lines (exclude benign duplicate-key noise)
# grep -c always outputs a number; exit status 1 means 0 matches — don't use || echo 0 (would duplicate)
BAD_ERR=$(tail -500 "$LOG" 2>/dev/null | grep -E "ERROR|Traceback|NameError|signal_gen failed|too many values|no_valid_combos" | grep -vc "uniq_alpha_hash_v10" 2>/dev/null)
[ -z "$BAD_ERR" ] && BAD_ERR=0

# disk
DISK_PCT=$(df -h /home/j13 2>/dev/null | awk 'NR==2 {print $5}' | tr -d '%')
LOG_MB=$(du -m "$LOG" 2>/dev/null | awk '{print $1}')

# A2 cumulative stats (from latest stats line)
A2_STATS=$(tail -2000 "$LOG" 2>/dev/null | grep "A2 stats" | tail -1 | sed 's/.*msg": "//; s/".*//' || echo "")

# §17.1 per-strategy VIEW tier breakdown — single source of truth per strategy
read_tiers() {
  local view="$1"
  docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu -t -A -F"|" -c \
    "SELECT deployable_count,deployable_historical,deployable_fresh,deployable_live_proven,candidate_count,active_count,COALESCE(ROUND(last_live_at_age_h::numeric,2),-1),champions_last_1h FROM $view" 2>/dev/null
}

# Engine-wide rollup (for backward-compat zangetsu_status)
TIERS=$(read_tiers zangetsu_status)
IFS="|" read -r T_TOTAL T_HIST T_FRESH T_LIVE T_CAND T_ACT T_AGE T_LAST1H <<< "$TIERS"
: ${T_TOTAL:=0}; : ${T_HIST:=0}; : ${T_FRESH:=0}; : ${T_LIVE:=0}; : ${T_CAND:=0}; : ${T_ACT:=0}; : ${T_AGE:=-1}; : ${T_LAST1H:=0}

# J01 strategy
J01=$(read_tiers j01_status)
IFS="|" read -r J01_TOTAL J01_HIST J01_FRESH J01_LIVE J01_CAND J01_ACT J01_AGE J01_LAST1H <<< "$J01"
: ${J01_TOTAL:=0}; : ${J01_HIST:=0}; : ${J01_FRESH:=0}; : ${J01_LIVE:=0}; : ${J01_CAND:=0}; : ${J01_ACT:=0}; : ${J01_AGE:=-1}; : ${J01_LAST1H:=0}

# J02 strategy
J02=$(read_tiers j02_status)
IFS="|" read -r J02_TOTAL J02_HIST J02_FRESH J02_LIVE J02_CAND J02_ACT J02_AGE J02_LAST1H <<< "$J02"
: ${J02_TOTAL:=0}; : ${J02_HIST:=0}; : ${J02_FRESH:=0}; : ${J02_LIVE:=0}; : ${J02_CAND:=0}; : ${J02_ACT:=0}; : ${J02_AGE:=-1}; : ${J02_LAST1H:=0}

# version (top of VERSION_LOG)
VERSION=$(grep -E "^## v" /home/j13/j13-ops/zangetsu/VERSION_LOG.md 2>/dev/null | head -1 | sed 's/## //; s/ — .*//' || echo "unknown")


# v0.7.1: dual-evidence health VIEWs — outcome + process
read_outcome() {
  docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu -t -A -F"|" -c \
    "SELECT total_fresh, alphas_with_indicators, indicator_alpha_ratio_pct, distinct_indicators, avg_depth, avg_nodes, deployable_count FROM fresh_pool_outcome_health WHERE strategy_id='$1'" 2>/dev/null
}
read_process() {
  docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu -t -A -F"|" -c \
    "SELECT compile_exception_count, evaluate_exception_count, indicator_terminal_exception_count, COALESCE(cache_hit_rate,0), nan_inf_count, zero_variance_count, COALESCE(admitted_rate,0), COALESCE(rejected_rate,0) FROM fresh_pool_process_health WHERE strategy_id='$1'" 2>/dev/null
}

for S in j01 j02; do
  _out_line=$(read_outcome $S)
  IFS="|" read -r O_TOTAL O_WITH O_RATIO O_DISTINCT O_DEPTH O_NODES O_DEP <<< "$_out_line"
  : ${O_TOTAL:=0}; : ${O_WITH:=0}; : ${O_RATIO:=0}; : ${O_DISTINCT:=0}; : ${O_DEPTH:=0}; : ${O_NODES:=0}; : ${O_DEP:=0}
  eval "${S^^}_O_TOTAL=$O_TOTAL; ${S^^}_O_WITH=$O_WITH; ${S^^}_O_RATIO=$O_RATIO; ${S^^}_O_DISTINCT=$O_DISTINCT; ${S^^}_O_DEPTH=$O_DEPTH; ${S^^}_O_NODES=$O_NODES; ${S^^}_O_DEP=$O_DEP"
  PROC=$(read_process $S)
  IFS="|" read -r P_COMP P_EVAL P_IND P_HIT P_NAN P_ZERO P_ADM P_REJ <<< "$PROC"
  : ${P_COMP:=0}; : ${P_EVAL:=0}; : ${P_IND:=0}; : ${P_HIT:=0}; : ${P_NAN:=0}; : ${P_ZERO:=0}; : ${P_ADM:=0}; : ${P_REJ:=0}
  eval "${S^^}_P_COMP=$P_COMP; ${S^^}_P_EVAL=$P_EVAL; ${S^^}_P_IND=$P_IND; ${S^^}_P_HIT=$P_HIT; ${S^^}_P_NAN=$P_NAN; ${S^^}_P_ZERO=$P_ZERO; ${S^^}_P_ADM=$P_ADM; ${S^^}_P_REJ=$P_REJ"
done

# build JSON atomically
cat > "$TMP" <<EOF
{
  "ts": "$TS",
  "version_log_top": "$VERSION",
  "epoch": "B_full_space_active",
  "archive_count": ${ARCHIVE_COUNT},
  "workers": {"a1": $A1, "a23": $A2, "a45": $A45, "expected_core": 6, "healthy": $( [ $((A1+A2+A45)) -ge 6 ] && echo true || echo false )},
  "tiers": {
    "deployable_total": ${T_TOTAL},
    "historical": ${T_HIST},
    "fresh": ${T_FRESH},
    "live_proven": ${T_LIVE},
    "candidate": ${T_CAND},
    "active": ${T_ACT},
    "last_live_age_h": ${T_AGE},
    "champions_last_1h": ${T_LAST1H}
  },
  "strategies": {
    "j01": {
      "name": "J01",
      "fitness": "harmonic K=2",
      "deployable_total": ${J01_TOTAL},
      "historical": ${J01_HIST},
      "fresh": ${J01_FRESH},
      "live_proven": ${J01_LIVE},
      "candidate": ${J01_CAND},
      "active": ${J01_ACT},
      "last_live_age_h": ${J01_AGE},
      "champions_last_1h": ${J01_LAST1H}
    },
    "j01_health": {
      "outcome": {
        "total_fresh": ${J01_O_TOTAL},
        "alphas_with_indicators": ${J01_O_WITH},
        "indicator_alpha_ratio_pct": ${J01_O_RATIO},
        "distinct_indicators": ${J01_O_DISTINCT},
        "avg_depth": ${J01_O_DEPTH},
        "avg_nodes": ${J01_O_NODES},
        "deployable_count": ${J01_O_DEP}
      },
      "process": {
        "compile_exception_count": ${J01_P_COMP},
        "evaluate_exception_count": ${J01_P_EVAL},
        "indicator_terminal_exception_count": ${J01_P_IND},
        "cache_hit_rate": ${J01_P_HIT},
        "nan_inf_count": ${J01_P_NAN},
        "zero_variance_count": ${J01_P_ZERO},
        "admitted_rate": ${J01_P_ADM},
        "rejected_rate": ${J01_P_REJ}
      }
    },
    "j02_health": {
      "outcome": {
        "total_fresh": ${J02_O_TOTAL},
        "alphas_with_indicators": ${J02_O_WITH},
        "indicator_alpha_ratio_pct": ${J02_O_RATIO},
        "distinct_indicators": ${J02_O_DISTINCT},
        "avg_depth": ${J02_O_DEPTH},
        "avg_nodes": ${J02_O_NODES},
        "deployable_count": ${J02_O_DEP}
      },
      "process": {
        "compile_exception_count": ${J02_P_COMP},
        "evaluate_exception_count": ${J02_P_EVAL},
        "indicator_terminal_exception_count": ${J02_P_IND},
        "cache_hit_rate": ${J02_P_HIT},
        "nan_inf_count": ${J02_P_NAN},
        "zero_variance_count": ${J02_P_ZERO},
        "admitted_rate": ${J02_P_ADM},
        "rejected_rate": ${J02_P_REJ}
      }
    },
    "j02": {
      "name": "J02",
      "fitness": "ICIR K=5",
      "deployable_total": ${J02_TOTAL},
      "historical": ${J02_HIST},
      "fresh": ${J02_FRESH},
      "live_proven": ${J02_LIVE},
      "candidate": ${J02_CAND},
      "active": ${J02_ACT},
      "last_live_age_h": ${J02_AGE},
      "champions_last_1h": ${J02_LAST1H}
    }
  },
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
