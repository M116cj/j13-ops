import os
#!/usr/bin/env python3
"""V10 Factor Zoo Report - hourly health check.
Run: python3 scripts/v10_factor_zoo_report.py
Output: markdown to stdout + /tmp/v10_factor_zoo_latest.md
"""
import sys, os, asyncio, json
from pathlib import Path
sys.path.insert(0, '/home/j13/j13-ops')
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

DSN = os.environ.get('ZV5_DSN',
    os.environ['ZV5_DSN'])


def main():
    conn = psycopg2.connect(DSN)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    print(f"# V10 Factor Zoo Report - {ts}\n")

    # Overview
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE card_status = 'DISCOVERED') as active,
            COUNT(*) FILTER (WHERE card_status = 'SEED') as seeds,
            COUNT(*) FILTER (WHERE card_status = 'ARCHIVED') as archived,
            COUNT(DISTINCT regime) as n_regimes,
            COUNT(DISTINCT passport->'arena1'->>'symbol') as n_symbols,
            AVG(arena1_score) as avg_ic,
            MAX(arena1_score) as max_ic,
            MIN(arena1_score) FILTER (WHERE arena1_score > 0) as min_positive_ic
        FROM champion_pipeline
        WHERE engine_hash = 'zv5_v10_alpha'
    """)
    stats = cur.fetchone()

    print("## Overview")
    if stats['total'] == 0:
        print("No V10 alphas in factor zoo yet.")
    else:
        print(f"- **Total alphas**: {stats['total']}")
        print(f"- Active (DISCOVERED): {stats['active']}")
        print(f"- Seeds: {stats['seeds']}")
        print(f"- Archived: {stats['archived']}")
        print(f"- Regimes covered: {stats['n_regimes']}")
        print(f"- Symbols covered: {stats['n_symbols']}")
        print(f"- IC: avg={stats['avg_ic']:.4f}, max={stats['max_ic']:.4f}, min_pos={stats['min_positive_ic']:.4f}")

    # By regime
    print("\n## By Regime")
    cur.execute("""
        SELECT regime,
               COUNT(*) as cnt,
               AVG(arena1_score) as avg_ic,
               MAX(arena1_score) as max_ic
        FROM champion_pipeline
        WHERE engine_hash = 'zv5_v10_alpha' AND card_status IN ('DISCOVERED', 'SEED')
        GROUP BY regime
        ORDER BY cnt DESC
    """)
    rows = cur.fetchall()
    if rows:
        print("| Regime | Count | Avg IC | Max IC |")
        print("|--------|-------|--------|--------|")
        for r in rows:
            print(f"| {r['regime']} | {r['cnt']} | {r['avg_ic']:.4f} | {r['max_ic']:.4f} |")
    else:
        print("No data.")

    # Top 20 alphas
    print("\n## Top 20 Alphas by IC")
    cur.execute("""
        SELECT alpha_hash,
               regime,
               passport->'arena1'->>'symbol' as symbol,
               LEFT(passport->'arena1'->'alpha_expression'->>'formula', 60) as formula_preview,
               arena1_score as ic,
               card_status,
               evolution_operator,
               created_at
        FROM champion_pipeline
        WHERE engine_hash = 'zv5_v10_alpha'
        ORDER BY arena1_score DESC NULLS LAST
        LIMIT 20
    """)
    rows = cur.fetchall()
    if rows:
        print("| Hash | Regime | Symbol | Formula | IC | Status | Source |")
        print("|------|--------|--------|---------|----|----|--------|")
        for r in rows:
            print(f"| {r['alpha_hash'][:8]} | {r['regime']} | {r['symbol']} | `{r['formula_preview'] or 'N/A'}` | {r['ic']:.4f} | {r['card_status']} | {r['evolution_operator']} |")

    # Recent alphas (last 1 hour)
    print("\n## Recent Discoveries (last 1 hour)")
    cur.execute("""
        SELECT COUNT(*) as recent_count,
               AVG(arena1_score) as avg_recent_ic
        FROM champion_pipeline
        WHERE engine_hash = 'zv5_v10_alpha'
          AND card_status = 'DISCOVERED'
          AND created_at > NOW() - INTERVAL '1 hour'
    """)
    recent = cur.fetchone()
    print(f"- Recent count: {recent['recent_count']}")
    print(f"- Avg IC: {recent['avg_recent_ic']:.4f}" if recent['avg_recent_ic'] else "- Avg IC: N/A")

    conn.close()


if __name__ == "__main__":
    main()
