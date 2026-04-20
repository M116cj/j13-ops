#!/usr/bin/env bash
# ============================================================
# verify_no_archive_reads.sh
# ------------------------------------------------------------
# Governance rule #5: downstream SQL-touching code paths must
# query champion_pipeline_fresh. Comments and docstrings with
# the word "champion_pipeline" are allowed (history / prose).
#
# Matches only actual SQL statements: FROM|INTO|UPDATE|JOIN
# immediately preceding the bare name.
#
# Exit 0 if clean; exit 1 with a list of offending files otherwise.
# ============================================================
set -u

REPO="${1:-/home/j13/j13-ops}"

matches=$(grep -rnE '(FROM|INTO|UPDATE|JOIN)[[:space:]]+champion_pipeline\b[^_]' \
    --include='*.py' \
    --include='*.sh' \
    --include='*.sql' \
    --exclude-dir=.venv \
    --exclude-dir=site-packages \
    --exclude-dir=__pycache__ \
    --exclude-dir=archive \
    --exclude-dir=.backup_20260418_122707_claude_deploy \
    --exclude-dir=migrations \
    --exclude-dir=docs \
    --exclude-dir=refactor-history \
    --exclude='rescan_legacy_with_new_gates.py' \
    --exclude='seed_101_alphas.py' \
    --exclude='seed_101_alphas_batch2.py' \
    --exclude='alpha_discovery.py' \
    --exclude='factor_zoo.py' \
    --exclude='verify_no_archive_reads.sh' \
    --exclude='*.pre_*' \
    --exclude='*.orig' \
    --exclude='*.bak*' \
    "$REPO" 2>/dev/null \
    | grep -v 'champion_pipeline_fresh' \
    | grep -v 'champion_pipeline_staging' \
    | grep -v 'champion_pipeline_rejected' \
    | grep -v 'champion_legacy_archive' || true)

if [ -n "$matches" ]; then
    echo "REFUSED: bare 'champion_pipeline' SQL references found (governance rule #5):"
    echo "$matches"
    echo ""
    echo "Fix: replace with champion_pipeline_fresh (live ranking/selection)"
    echo "     or champion_legacy_archive (explicit data-science queries only)."
    echo ""
    echo "Deprecated scripts (seed_*, alpha_discovery, factor_zoo, rescan)"
    echo "are excluded from this scan — their DEPRECATED guard prevents"
    echo "accidental execution."
    exit 1
fi

echo "verify_no_archive_reads: clean"
exit 0
