"""Migrate PySR arena1 results from JSON files to zangetsu DB.

Reads all {REGIME}_h{HORIZON}.json files from arena1_results/ and inserts into
factor_candidates and arena1_runs tables.
"""
import json
import os
import re
import sys
from pathlib import Path

import psycopg2

RESULTS_DIR = Path(__file__).parent / "arena1_results"
DSN = os.environ.get(
    "ZV3_DB_DSN",
    "dbname=zangetsu user=zangetsu password=9c424966bebb05a42966186bb22d7480 host=127.0.0.1 port=5432",
)

FILE_PATTERN = re.compile(r"^(.+)_(h\d+)\.json$")


def main():
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()

    # Check for existing pysr data to avoid duplicates
    cur.execute("SELECT count(*) FROM factor_candidates WHERE source='pysr'")
    existing = cur.fetchone()[0]
    if existing > 0:
        print(f"WARNING: {existing} pysr rows already exist in factor_candidates. Skipping insert.")
        conn.close()
        sys.exit(0)

    files = sorted(RESULTS_DIR.glob("*.json"))
    total_candidates = 0
    runs = []

    for fpath in files:
        m = FILE_PATTERN.match(fpath.name)
        if not m:
            print(f"SKIP: {fpath.name} does not match pattern")
            continue

        regime = m.group(1)
        horizon = m.group(2)

        with open(fpath) as f:
            candidates = json.load(f)

        count = len(candidates)
        total_candidates += count

        for c in candidates:
            cur.execute(
                """INSERT INTO factor_candidates
                   (source, regime, horizon, raw_expression, loss, score, ast_json, created_at)
                   VALUES ('pysr', %s, %s, %s, %s, %s, %s, NOW())""",
                (
                    regime,
                    horizon,
                    c["raw_expression"],
                    c["loss"],
                    c["score"],
                    json.dumps(c["expression"]),
                ),
            )

        runs.append((regime, horizon, count))
        print(f"  {fpath.name}: {count} candidates inserted")

    # Insert arena1_runs
    for regime, horizon, count in runs:
        cur.execute(
            """INSERT INTO arena1_runs
               (regime, horizon, status, candidates_found, completed_at)
               VALUES (%s, %s, 'completed', %s, NOW())""",
            (regime, horizon, count),
        )

    conn.commit()
    print(f"\nDone: {total_candidates} candidates from {len(runs)} files.")

    # Verify
    cur.execute("SELECT count(*), regime FROM factor_candidates WHERE source='pysr' GROUP BY regime ORDER BY regime")
    print("\nVerification (factor_candidates):")
    for row in cur.fetchall():
        print(f"  {row[1]}: {row[0]} candidates")

    cur.execute("SELECT count(*) FROM arena1_runs")
    print(f"\narena1_runs: {cur.fetchone()[0]} rows")

    conn.close()


if __name__ == "__main__":
    main()
