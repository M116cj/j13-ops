"""Overnight alpha zoo injection — uses Codex #1's translated formulas,
runs them through the proven cold_start_hand_alphas.py pipeline.

Reason for this wrapper (not using Codex #1's alpha_zoo_batch_injection.py):
Codex #1 hallucinated table name `alpha_staging` — actual Zangetsu schema
is `champion_pipeline_staging`. Our cold_start_hand_alphas.py uses the
correct schema and is already proven end-to-end (2 admissions during
the earlier 30-formula run).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

sys.path.insert(0, "/home/j13/j13-ops")
sys.path.insert(0, "/home/j13/j13-ops/zangetsu/scripts")

from zangetsu.config.settings import Settings
settings = Settings()
import cold_start_hand_alphas as css

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("zoo_overnight")


def load_translated(path: str = "/tmp/zangetsu-translated-alphas.json"):
    with open(path) as f:
        rows = json.load(f)
    formulas = []
    sources = {}
    for r in rows:
        if not r.get("translatable"):
            continue
        f = r.get("translated")
        if not f or not isinstance(f, str):
            continue
        formulas.append(f)
        sources[f] = (r.get("source", "unknown"), r.get("source_id", "?"))
    return formulas, sources


async def run(args):
    formulas, src_map = load_translated(args.input)
    log.info("Loaded %d translatable formulas from %s", len(formulas), args.input)

    if args.limit:
        formulas = formulas[:args.limit]
        log.info("Limited to first %d", len(formulas))

    css.SEED_FORMULAS = formulas

    summaries = {}
    for strategy in args.strategies:
        _, summary = await css.run_for_strategy(strategy, args)
        summaries[strategy] = summary

    print(json.dumps(summaries, indent=2))

    admitted_count = sum(s.get("admitted", 0) for s in summaries.values())
    log.info("OVERALL ADMITTED: %d across %d strategies", admitted_count, len(summaries))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="/tmp/zangetsu-translated-alphas.json")
    p.add_argument("--strategies", nargs="+", default=["j01", "j02"])
    p.add_argument("--symbols", nargs="+", default=None)
    p.add_argument("--limit-symbols", type=int, default=None)
    p.add_argument("--limit", type=int, default=None, help="limit formulas for smoke test")
    p.add_argument("--allow-dirty-tree", action="store_true", default=True)
    p.add_argument("--dry-run-one", action="store_true")
    args = p.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
