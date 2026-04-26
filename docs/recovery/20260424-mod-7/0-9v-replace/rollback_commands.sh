#!/usr/bin/env bash
# Rollback commands draft for 0-9V-REPLACE.
# This script is documentation only unless j13 explicitly authorizes
# rollback execution.

set -euo pipefail

cd /home/j13/j13-ops

OLD_SHA="f5f62b2b27a448dcf41c9ff6f6c847cb01c56c52"
OLD_BRANCH="phase-7/p7-pr4b-a2-a3-arena-batch-metrics"

echo "Rollback requires explicit j13 authorization."
echo
echo "Old SHA:    ${OLD_SHA}"
echo "Old branch: ${OLD_BRANCH}"
echo
echo "Manual rollback steps (do NOT execute without authorization):"
echo
echo "  1. Stop new runtime process (whatever launcher was used during forward switch)."
echo "     - If systemd:  sudo systemctl stop <new-service-name>"
echo "     - If cron:     no action needed (next watchdog cycle will pick up new SHA)"
echo "     - If manual:   kill <new PID>"
echo
echo "  2. git checkout main"
echo "     git reset --hard ${OLD_SHA}    # ONLY IF j13 explicitly authorizes"
echo
echo "  3. Re-checkout old branch (preserves the old branch reference for audit):"
echo "     git checkout ${OLD_BRANCH}"
echo "     # Re-apply dirty WIP from local backup if needed (user decision)"
echo
echo "  4. Restart old runtime via cron + watchdog (auto, every 5 min) or manual launcher."
echo
echo "  5. Verify:"
echo "     ps aux | grep -i zangetsu | grep -v grep"
echo "     tail -50 zangetsu/logs/engine.jsonl"
echo "     git rev-parse HEAD          # expected: ${OLD_SHA}"
echo
echo "  6. If rollback fails, escalate to j13 via Telegram."
