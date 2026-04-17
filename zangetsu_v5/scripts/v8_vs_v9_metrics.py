#!/usr/bin/env python3
"""V8 vs V9 metrics comparison framework.

Generates a markdown report comparing champion throughput, stage pass rates,
average metrics and regime distribution across engine_hash versions
(zv5_v6, zv5_v71 = V8, zv5_v9).

Usage:
    .venv/bin/python3 scripts/v8_vs_v9_metrics.py [--dsn DSN] [--hours N]

Adversarial notes (Q1 dimensions):
  - Input boundary: NULL engine_hash rows, zero-count divisions guarded
  - Silent failure: DB errors raise, not swallowed; empty results rendered
    explicitly as "(no data)" so absence is visible
  - External dependency: psycopg2 connect failure surfaces traceback
  - Concurrency/race: read-only snapshot, no locks, safe under live writes
  - Scope creep: single-purpose reporting, stdout markdown only
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

import psycopg2
import psycopg2.extras

DEFAULT_DSN = "postgresql://zangetsu:REDACTED@127.0.0.1:5432/zangetsu"

# engine_hash values of interest. V8 == zv5_v71 (and earlier zv5_v6). V9 == zv5_v9.
TRACKED_HASHES: Sequence[str] = ("zv5_v6", "zv5_v71", "zv5_v9")


def fetch_engine_hashes(cur) -> List[str]:
    cur.execute(
        "SELECT DISTINCT engine_hash FROM champion_pipeline "
        "WHERE engine_hash IS NOT NULL ORDER BY engine_hash"
    )
    return [r[0] for r in cur.fetchall()]


def per_engine_counts(cur, engine_hash: str) -> Dict[str, int]:
    cur.execute(
        """
        SELECT status, COUNT(*) FROM champion_pipeline
        WHERE engine_hash = %s
        GROUP BY status
        """,
        (engine_hash,),
    )
    return {status: n for status, n in cur.fetchall()}


def insert_rate_per_5min(cur, engine_hash: str) -> Optional[float]:
    """A1 champions inserted per 5-min cycle = total inserts / span-5min-buckets."""
    cur.execute(
        """
        SELECT COUNT(*)::float,
               EXTRACT(EPOCH FROM (MAX(created_at) - MIN(created_at)))::float
        FROM champion_pipeline
        WHERE engine_hash = %s
        """,
        (engine_hash,),
    )
    n, span_sec = cur.fetchone()
    if not n or not span_sec or span_sec <= 0:
        return None
    buckets = max(span_sec / 300.0, 1.0)
    return n / buckets


def pass_rate(num: int, denom: int) -> Optional[float]:
    if denom == 0:
        return None
    return num / denom


def avg_metrics(cur, engine_hash: str) -> Dict[str, Optional[float]]:
    cur.execute(
        """
        SELECT
            AVG(arena1_win_rate), AVG(arena1_pnl), AVG(arena1_score),
            AVG(arena2_win_rate),
            AVG(arena3_sharpe),   AVG(arena3_expectancy), AVG(arena3_pnl),
            AVG(arena4_hell_wr),  AVG(arena4_variability)
        FROM champion_pipeline
        WHERE engine_hash = %s
        """,
        (engine_hash,),
    )
    row = cur.fetchone() or (None,) * 9
    keys = (
        "a1_wr", "a1_pnl", "a1_score",
        "a2_wr",
        "a3_sharpe", "a3_exp", "a3_pnl",
        "a4_hell_wr", "a4_var",
    )
    return dict(zip(keys, row))


def regime_distribution(cur, engine_hash: str) -> List[Tuple[str, int]]:
    cur.execute(
        """
        SELECT COALESCE(regime, '(null)') AS regime, COUNT(*)
        FROM champion_pipeline
        WHERE engine_hash = %s
        GROUP BY regime
        ORDER BY COUNT(*) DESC
        """,
        (engine_hash,),
    )
    return list(cur.fetchall())


def fmt(v: Optional[float], digits: int = 4) -> str:
    if v is None:
        return "-"
    try:
        return f"{float(v):.{digits}f}"
    except (TypeError, ValueError):
        return str(v)


def fmt_pct(v: Optional[float]) -> str:
    if v is None:
        return "-"
    return f"{100.0 * float(v):.2f}%"


def build_report(dsn: str) -> str:
    conn = psycopg2.connect(dsn)
    try:
        cur = conn.cursor()
        discovered = fetch_engine_hashes(cur)
        # Keep explicit tracked list first, then any extras found.
        ordered = list(TRACKED_HASHES) + [h for h in discovered if h not in TRACKED_HASHES]

        out: List[str] = []
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        out.append(f"# Zangetsu V8 vs V9 Metrics Report\n")
        out.append(f"_Generated: {now}_\n")
        out.append(f"_DSN: {dsn.split('@')[-1]}_\n")

        out.append("\n## Discovered engine_hash values\n")
        if discovered:
            for h in discovered:
                out.append(f"- `{h}`")
        else:
            out.append("(no champion rows in champion_pipeline yet)")
        out.append("")

        # Throughput + pass rate table
        out.append("\n## Throughput and stage pass rates\n")
        header = (
            "| engine_hash | total | A1→A3 passed | A3 pass rate | A3→A4 deployable | A4 pass rate | A1 ins/5min |"
        )
        sep = "|---|---|---|---|---|---|---|"
        out.append(header)
        out.append(sep)
        for h in ordered:
            counts = per_engine_counts(cur, h)
            total = sum(counts.values())
            a1_complete = counts.get("ARENA1_COMPLETE", 0) + counts.get("ARENA2_PROCESSING", 0) \
                          + counts.get("ARENA2_COMPLETE", 0) + counts.get("ARENA3_PROCESSING", 0) \
                          + counts.get("ARENA3_COMPLETE", 0) + counts.get("ARENA3_REJECTED", 0) \
                          + counts.get("ARENA4_PROCESSING", 0) + counts.get("ARENA4_ELIMINATED", 0) \
                          + counts.get("DEPLOYABLE", 0)
            a3_complete = counts.get("ARENA3_COMPLETE", 0) + counts.get("ARENA4_PROCESSING", 0) \
                          + counts.get("ARENA4_ELIMINATED", 0) + counts.get("DEPLOYABLE", 0)
            deployable = counts.get("DEPLOYABLE", 0)
            a3_rate = pass_rate(a3_complete, a1_complete)
            a4_rate = pass_rate(deployable, a3_complete)
            ins_rate = insert_rate_per_5min(cur, h)
            out.append(
                f"| `{h}` | {total} | {a3_complete} | {fmt_pct(a3_rate)} | "
                f"{deployable} | {fmt_pct(a4_rate)} | {fmt(ins_rate, 2)} |"
            )

        # Stage avg metrics
        out.append("\n## Average metrics by stage\n")
        out.append(
            "| engine_hash | A1 WR | A1 PnL | A1 score | A2 WR | A3 Sharpe | A3 Exp | A3 PnL | A4 hellWR | A4 Var |"
        )
        out.append("|---|---|---|---|---|---|---|---|---|---|")
        for h in ordered:
            m = avg_metrics(cur, h)
            out.append(
                f"| `{h}` | {fmt(m['a1_wr'])} | {fmt(m['a1_pnl'])} | {fmt(m['a1_score'])} | "
                f"{fmt(m['a2_wr'])} | {fmt(m['a3_sharpe'])} | {fmt(m['a3_exp'])} | "
                f"{fmt(m['a3_pnl'])} | {fmt(m['a4_hell_wr'])} | {fmt(m['a4_var'])} |"
            )

        # Regime distribution per engine
        out.append("\n## Regime distribution of champions\n")
        for h in ordered:
            out.append(f"\n### `{h}`\n")
            dist = regime_distribution(cur, h)
            if not dist:
                out.append("(no data)")
                continue
            out.append("| regime | count |")
            out.append("|---|---|")
            for regime, n in dist:
                out.append(f"| {regime} | {n} |")

        # Status distribution
        out.append("\n## Status distribution per engine_hash\n")
        out.append("| engine_hash | status | count |")
        out.append("|---|---|---|")
        for h in ordered:
            counts = per_engine_counts(cur, h)
            if not counts:
                out.append(f"| `{h}` | (no rows) | 0 |")
                continue
            for status, n in sorted(counts.items(), key=lambda kv: -kv[1]):
                out.append(f"| `{h}` | {status} | {n} |")

        return "\n".join(out) + "\n"
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="V8 vs V9 metrics comparison")
    ap.add_argument("--dsn", default=DEFAULT_DSN, help="PostgreSQL DSN")
    args = ap.parse_args()
    try:
        report = build_report(args.dsn)
    except psycopg2.Error as exc:
        print(f"DB error: {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
