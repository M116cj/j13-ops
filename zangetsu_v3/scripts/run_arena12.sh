#!/bin/bash
set -e
cd ~/j13-ops/zangetsu_v3
source .venv/bin/activate

echo "=== Arena 1: PySR Signal Pool (11 regimes × 5 targets) ==="
echo "Started: $(date)"
python3 scripts/arena1_full.py

echo ""
echo "=== Arena 2: Auto-Compress ==="
echo "Started: $(date)"
python3 scripts/arena2_compress.py

echo ""
echo "=== COMPLETE: $(date) ==="
echo "Factor pool: arena2_results/factor_pool.json"
