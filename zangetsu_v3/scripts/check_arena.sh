#!/bin/bash
# Check if Arena 1+2 completed, notify via Calcifer Telegram bot
LOG=~/j13-ops/zangetsu_v3/logs/arena12_v2.log
TOKEN=$(grep CALCIFER_TG_TOKEN ~/alaya/calcifer/.env | cut -d= -f2)
CHAT_ID=5252897787

if grep -q 'ARENA 1 COMPLETE' "$LOG" 2>/dev/null; then
    # Get key stats
    UNIQUE=$(grep 'Unique expressions' "$LOG" | tail -1 | grep -oP '\d+')
    TIME=$(grep 'Time:' "$LOG" | tail -1)
    
    # Check if Arena 2 also done
    if grep -q 'factor_pool.json' "$LOG" 2>/dev/null; then
        NFACTORS=$(grep 'Final factor pool' "$LOG" | grep -oP '\d+')
        MSG="🏁 Arena 1+2 完成
━━━━━━━━━━━━━━━━━━
Arena 1: ${UNIQUE} 獨立表達式
Arena 2: ${NFACTORS} 個 factors 壓縮完成
${TIME}

factor_pool.json 已就緒，可以進 Arena 3。"
    else
        MSG="🏁 Arena 1 完成（Arena 2 可能進行中）
━━━━━━━━━━━━━━━━━━
${UNIQUE} 獨立表達式
${TIME}"
    fi
    
    curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage"         -d chat_id="${CHAT_ID}"         -d text="${MSG}" > /dev/null
    
    # Remove cron job after notification
    crontab -l 2>/dev/null | grep -v check_arena | crontab -
    exit 0
fi
