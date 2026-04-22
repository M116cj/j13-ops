"""Combinatorial injection — uses Codex #2's compiled combinatorial alphas.

Same schema fix as zangetsu_zoo_run.py: bypasses Codex #2's hallucinated
alpha_staging injector, uses proven cold_start_hand_alphas.py pipeline.

Sampling strategy:
- T1 unary wraps (992): ALL — cheapest, most predictable
- T3 mutations (479): ALL — targeted variations of best known formulas
- T2 pairwise binary (2000): sample 500 — bread, random quality
- T4 triple composition (500): SKIP — most fragile
Total: ~1971 formulas
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
import sys

sys.path.insert(0, "/home/j13/j13-ops")
sys.path.insert(0, "/home/j13/j13-ops/zangetsu/scripts")

from zangetsu.config.settings import Settings
settings = Settings()
import cold_start_hand_alphas as css

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("combo")


def load_combinatorial(path: str, t2_sample: int = 500, seed: int = 20260421):
    rng = random.Random(seed)
    with open(path) as f:
        rows = json.load(f)
    buckets = {"T1": [], "T2": [], "T3": [], "T4": []}
    for r in rows:
        t = r.get("tier", "?")
        if t in buckets and r.get("compile_ok", False):
            buckets[t].append(r.get("formula_zangetsu"))
    t1, t2, t3 = buckets["T1"], buckets["T2"], buckets["T3"]
    rng.shuffle(t2)
    selected = t1 + t3 + t2[:t2_sample]
    log.info("selected: T1=%d T3=%d T2-sample=%d (total=%d); T4 skipped",
             len(t1), len(t3), len(t2[:t2_sample]), len(selected))
    return selected


async def run(args):
    formulas = load_combinatorial(args.input, t2_sample=args.t2_sample)
    if args.limit:
        formulas = formulas[:args.limit]
        log.info("Limited to %d", len(formulas))
    css.SEED_FORMULAS = formulas

    summaries = {}
    for strategy in args.strategies:
        _, summary = await css.run_for_strategy(strategy, args)
        summaries[strategy] = summary

    print(json.dumps(summaries, indent=2))
    admitted = sum(s.get("admitted", 0) for s in summaries.values())
    log.info("COMBO ADMITTED: %d across strategies", admitted)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="/tmp/combinatorial_compiled.json")
    p.add_argument("--strategies", nargs="+", default=["j01", "j02"])
    p.add_argument("--symbols", nargs="+", default=None)
    p.add_argument("--limit-symbols", type=int, default=None)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--t2-sample", type=int, default=500)
    p.add_argument("--allow-dirty-tree", action="store_true", default=True)
    p.add_argument("--dry-run-one", action="store_true")
    args = p.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
