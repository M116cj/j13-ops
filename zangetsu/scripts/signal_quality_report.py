#!/usr/bin/env python3
"""Signal quality analysis framework.

For a given engine_hash, extracts per-champion indicator_names from
passport.arena1.indicator_names and computes per-indicator:

  - usage frequency
  - avg arena1_win_rate when indicator is present
  - avg arena3_sharpe when indicator is present
  - good/bad ratio (arena3_sharpe > threshold vs <= threshold)

Outputs a ranked markdown list — indicators most correlated with success
first, noise indicators (high usage / weak A3) flagged last.

Usage:
    .venv/bin/python3 scripts/signal_quality_report.py \
        --engine-hash zv5_v71 [--dsn DSN] [--good-sharpe 0.5]

Adversarial notes (Q1 dimensions):
  - Input boundary: missing / malformed passport, missing indicator_names,
    zero-count indicators all handled without crashes
  - Silent failure: empty dataset produces explicit "(no data)" report,
    not silent zero output
  - External dependency: DB connection errors raise; jsonb parsing defensive
  - Concurrency/race: read-only snapshot query, safe under writes
  - Scope creep: reporting only, no mutation of champion_pipeline
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional

import psycopg2
import psycopg2.extras

DEFAULT_DSN = "postgresql://zangetsu:9c424966bebb05a42966186bb22d7480@127.0.0.1:5432/zangetsu"


def extract_indicator_names(passport: Any) -> List[str]:
    """Defensively read passport.arena1.indicator_names. Returns [] on malformed."""
    if not isinstance(passport, dict):
        return []
    arena1 = passport.get("arena1")
    if not isinstance(arena1, dict):
        return []
    names = arena1.get("indicator_names")
    if not isinstance(names, list):
        return []
    return [str(n) for n in names if n]


def fetch_champions(cur, engine_hash: str) -> List[Dict[str, Any]]:
    cur.execute(
        """
        SELECT id, passport, arena1_win_rate, arena3_sharpe, status
        FROM champion_pipeline
        WHERE engine_hash = %s
        """,
        (engine_hash,),
    )
    rows = []
    for row in cur.fetchall():
        rows.append({
            "id": row[0],
            "passport": row[1],
            "a1_wr": row[2],
            "a3_sharpe": row[3],
            "status": row[4],
        })
    return rows


def aggregate(
    champions: Iterable[Dict[str, Any]],
    good_sharpe_threshold: float,
) -> Dict[str, Dict[str, Any]]:
    per_ind: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "uses": 0,
        "a1_wr_samples": [],
        "a3_sharpe_samples": [],
        "good": 0,
        "bad": 0,
        "a3_evaluated": 0,
    })
    total = 0
    for champ in champions:
        total += 1
        names = extract_indicator_names(champ["passport"])
        if not names:
            continue
        a1_wr = champ["a1_wr"]
        a3 = champ["a3_sharpe"]
        for name in set(names):  # dedupe within champion
            entry = per_ind[name]
            entry["uses"] += 1
            if a1_wr is not None:
                entry["a1_wr_samples"].append(float(a1_wr))
            if a3 is not None:
                entry["a3_sharpe_samples"].append(float(a3))
                entry["a3_evaluated"] += 1
                if float(a3) > good_sharpe_threshold:
                    entry["good"] += 1
                else:
                    entry["bad"] += 1
    per_ind["_total_champions"] = {"total": total}  # type: ignore[assignment]
    return per_ind


def safe_mean(xs: List[float]) -> Optional[float]:
    if not xs:
        return None
    return mean(xs)


def build_report(
    dsn: str,
    engine_hash: str,
    good_sharpe: float,
) -> str:
    conn = psycopg2.connect(dsn)
    try:
        cur = conn.cursor()
        champions = fetch_champions(cur, engine_hash)
    finally:
        conn.close()

    agg = aggregate(champions, good_sharpe)
    total = agg.pop("_total_champions", {"total": 0})["total"]  # type: ignore[arg-type]

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    out: List[str] = []
    out.append(f"# Signal Quality Report — `{engine_hash}`\n")
    out.append(f"_Generated: {now}_")
    out.append(f"_Total champions sampled: {total}_")
    out.append(f"_Good Sharpe threshold: > {good_sharpe}_")
    out.append("")

    if total == 0 or not agg:
        out.append("## (no data)\n")
        out.append(
            f"No champions found for engine_hash `{engine_hash}`. "
            "This is expected baseline state if V9 has not produced data yet "
            "or archived engine_hash is absent."
        )
        return "\n".join(out) + "\n"

    # Build rows with derived stats
    rows: List[Dict[str, Any]] = []
    for name, stats in agg.items():
        uses = stats["uses"]
        if uses == 0:
            continue
        a1_wr = safe_mean(stats["a1_wr_samples"])
        a3_sh = safe_mean(stats["a3_sharpe_samples"])
        good = stats["good"]
        bad = stats["bad"]
        evaluated = stats["a3_evaluated"]
        good_ratio = (good / evaluated) if evaluated else None
        rows.append({
            "name": name,
            "uses": uses,
            "usage_freq": uses / total if total else 0.0,
            "a1_wr": a1_wr,
            "a3_sharpe": a3_sh,
            "good": good,
            "bad": bad,
            "good_ratio": good_ratio,
        })

    # Rank by composite: avg a3_sharpe (primary), then usage. None sharpes sink.
    def sort_key(r: Dict[str, Any]):
        sh = r["a3_sharpe"] if r["a3_sharpe"] is not None else float("-inf")
        return (-sh, -r["uses"])

    rows.sort(key=sort_key)

    out.append("## Ranked indicators (by avg A3 Sharpe, then usage)\n")
    out.append("| rank | indicator | uses | usage_freq | avg A1 WR | avg A3 Sharpe | good | bad | good_ratio |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(rows, start=1):
        a1_wr_s = "-" if r["a1_wr"] is None else f"{r['a1_wr']:.4f}"
        a3_sh_s = "-" if r["a3_sharpe"] is None else f"{r['a3_sharpe']:.4f}"
        gr_s = "-" if r["good_ratio"] is None else f"{r['good_ratio']:.3f}"
        out.append(
            f"| {i} | `{r['name']}` | {r['uses']} | {r['usage_freq']:.3f} | "
            f"{a1_wr_s} | {a3_sh_s} | {r['good']} | {r['bad']} | {gr_s} |"
        )

    # Noise section: high usage, low a3_sharpe or low good_ratio
    noise = [
        r for r in rows
        if r["a3_sharpe"] is not None
        and r["a3_sharpe"] <= good_sharpe
        and r["usage_freq"] >= 0.05
    ]
    noise.sort(key=lambda r: (-r["usage_freq"], r["a3_sharpe"]))

    out.append("\n## Noise indicators (usage ≥ 5% but avg A3 Sharpe ≤ threshold)\n")
    if not noise:
        out.append("(none detected)")
    else:
        out.append("| indicator | usage_freq | avg A3 Sharpe | good_ratio |")
        out.append("|---|---|---|---|")
        for r in noise:
            gr_s = "-" if r["good_ratio"] is None else f"{r['good_ratio']:.3f}"
            out.append(
                f"| `{r['name']}` | {r['usage_freq']:.3f} | "
                f"{r['a3_sharpe']:.4f} | {gr_s} |"
            )

    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Signal quality indicator ranking")
    ap.add_argument("--dsn", default=DEFAULT_DSN, help="PostgreSQL DSN")
    ap.add_argument("--engine-hash", required=True, help="engine_hash to analyze (e.g. zv5_v71, zv5_v9)")
    ap.add_argument("--good-sharpe", type=float, default=0.5,
                    help="arena3_sharpe threshold above which a champion is 'good'")
    args = ap.parse_args()
    try:
        report = build_report(args.dsn, args.engine_hash, args.good_sharpe)
    except psycopg2.Error as exc:
        print(f"DB error: {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
