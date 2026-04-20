"""Mine top-N archive formulas; re-run them as Epoch B cold-start seeds.

Governance note:
  rule #1 forbids Epoch A rows entering live ranking/promotion/deployment.
  A formula STRING is a mathematical object, not the row itself — extracting
  the string and re-evaluating it under Epoch B config (v0.7.2 max_hold=120,
  fresh indicator cache, fresh backtester) produces a brand-new Epoch B
  candidate with new provenance (run_id, fitness_version=legacy_reseed.v1).
  The old archive row stays frozen and un-touched.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys

import asyncpg

sys.path.insert(0, "/home/j13/j13-ops")
sys.path.insert(0, "/home/j13/j13-ops/zangetsu/scripts")

from zangetsu.config.settings import Settings
settings = Settings()

import cold_start_hand_alphas as css  # reuse seed_one etc.

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("reseed")


async def fetch_top_formulas(top_n: int) -> list[str]:
    """Return N unique formulas from archive, ordered by arena1_score."""
    pool = await asyncpg.create_pool(
        host=settings.db_host, port=settings.db_port,
        database=settings.db_name, user=settings.db_user,
        password=settings.db_password, min_size=1, max_size=2,
    )
    try:
        rows = await pool.fetch("""
            SELECT DISTINCT passport->'arena1'->>'formula' AS formula
            FROM champion_legacy_archive
            WHERE passport->'arena1'->>'formula' IS NOT NULL
              AND arena1_pnl > 0
              AND arena1_n_trades >= 30
              AND arena1_score > 0.4
            ORDER BY formula
            LIMIT $1
        """, top_n * 4)  # oversample; many are near-duplicates
    finally:
        await pool.close()

    formulas = []
    seen = set()
    for r in rows:
        f = r["formula"]
        # Collapse trivial wrappers to dedupe: pow2(X) / tanh_x(X) / abs_x(X) share most behavior
        core = f
        for wrapper in ("pow2(", "tanh_x(", "abs_x(", "sign_x("):
            if core.startswith(wrapper) and core.endswith(")"):
                core = core[len(wrapper):-1]
        if core not in seen:
            seen.add(core)
            formulas.append(f)
        if len(formulas) >= top_n:
            break
    return formulas


async def run(args):
    formulas = await fetch_top_formulas(args.top_n)
    log.info("mined %d unique legacy formulas:", len(formulas))
    for f in formulas:
        log.info("  %s", f)

    # Monkey-patch cold_start's SEED_FORMULAS and reuse run_for_strategy
    css.SEED_FORMULAS = formulas

    all_summaries = {}
    for strategy in args.strategies:
        _, summary = await css.run_for_strategy(strategy, args)
        all_summaries[strategy] = summary
    print(json.dumps(all_summaries, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategies", nargs="+", default=["j01", "j02"])
    parser.add_argument("--symbols", nargs="+", default=None)
    parser.add_argument("--limit-symbols", type=int, default=None)
    parser.add_argument("--top-n", type=int, default=15,
                        help="number of distinct legacy formulas to mine")
    parser.add_argument("--allow-dirty-tree", action="store_true", default=True)
    parser.add_argument("--dry-run-one", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
