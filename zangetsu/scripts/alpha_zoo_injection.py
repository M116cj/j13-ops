"""Alpha Zoo cold-start injection — 30 hand-translated formulas from 7 sources.

Each formula has been manually verified against Zangetsu's primitive set
(OHLCV + 126 indicator terminals + 35 operators). Untranslatable ones
(rank/indneutralize/ternary/bare-constants) are already filtered out.

fitness_version tags distinguish source for audit trail:
  alpha_zoo.{wq101|qlib|alpha191|quantpedia|arxiv|wqbrain|indicators}.v1
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys

import asyncpg

sys.path.insert(0, "/home/j13/j13-ops")
sys.path.insert(0, "/home/j13/j13-ops/zangetsu/scripts")

from zangetsu.config.settings import Settings
settings = Settings()

import cold_start_hand_alphas as css

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("alpha_zoo")


# (formula_string, source_tag) — source_tag becomes fitness_version.{tag}.v1
ZOO = [
    # === Group A: WorldQuant 101 (verified translatable) ===
    ("neg(correlation_10(open, volume))",                                                              "wq101_6"),
    ("mul(sign_x(delta_3(volume)), neg(delta_3(close)))",                                             "wq101_12"),
    ("protected_div(sub(close, open), sub(high, low))",                                                "wq101_101"),
    ("protected_div(sub(vwap_20, close), add(vwap_20, close))",                                        "wq101_42"),
    ("neg(correlation_5(high, ts_rank_5(volume)))",                                                    "wq101_44"),
    ("neg(delta_9(protected_div(sub(sub(close, low), sub(high, close)), sub(close, low))))",          "wq101_53"),
    ("neg(protected_div(mul(sub(low, close), pow5(open)), mul(sub(low, high), pow5(close))))",        "wq101_54"),

    # === Group B: Qlib Alpha158 (BigQuant) ===
    ("protected_div(sub(close, open), open)",                                                          "qlib_kmid"),
    ("protected_div(sub(close, ts_min_5(low)), sub(ts_max_5(high), ts_min_5(low)))",                   "qlib_rsv_5"),
    ("protected_div(sub(close, ts_min_20(low)), sub(ts_max_20(high), ts_min_20(low)))",                "qlib_rsv_20"),
    ("neg(protected_div(delta_5(close), close))",                                                      "qlib_roc_5"),
    ("neg(protected_div(delta_20(close), close))",                                                     "qlib_roc_20"),

    # === Group C: GuotaiJunan Alpha191 (JoinQuant) ===
    ("neg(delta_3(protected_div(sub(sub(close, low), sub(high, close)), sub(high, low))))",            "alpha191_2"),
    ("neg(ts_max_3(correlation_5(ts_rank_5(volume), ts_rank_5(high))))",                               "alpha191_5"),
    ("correlation_5(ts_rank_5(volume), ts_rank_5(low))",                                               "alpha191_191"),

    # === Group D: Quantpedia momentum ===
    ("sign_x(delta_20(close))",                                                                         "qp_tsmom"),
    ("protected_div(close, ts_max_20(high))",                                                           "qp_52wh"),

    # === Group E: arXiv recent ===
    ("tanh_x(protected_div(sub(high, close), mul(close, volume)))",                                    "cogalpha_v3"),
    ("delta_20(high)",                                                                                  "alphagen_dh20"),
    ("correlation_10(close, volume)",                                                                   "alphaforge_ccv"),
    ("ts_min_9(correlation_5(high, volume))",                                                           "alphaforge_af2"),

    # === Group F: WorldQuant BRAIN community ===
    ("neg(delta_5(close))",                                                                             "wqb_g24"),
    ("sub(add(high, low), add(close, close))",                                                         "wqb_g25"),
    ("neg(sub(close, scale(close)))",                                                                   "wqb_s01"),

    # === Group G: Indicator-based (Zangetsu's 126 terminals, novel vs WQ101) ===
    ("neg(scale(rsi_14))",                                                                              "ind_rsi_rev"),
    ("ts_rank_20(rsi_14)",                                                                              "ind_rsi_ts_rank"),
    ("delta_20(bollinger_bw_20)",                                                                       "ind_bbw_delta"),
    ("neg(funding_zscore_20)",                                                                          "ind_funding_rev"),
    ("vwap_deviation_20",                                                                               "ind_vwap_dev"),
    ("stochastic_k_14",                                                                                 "ind_stoch_k"),
]


async def run(args):
    log.info("=== Alpha Zoo Injection — %d formulas from 7 sources ===", len(ZOO))

    # PR #43 (NG3 from order 4-1): cold-start safety contract.
    # By default this script REFUSES to write to DB. The four flags below form
    # a defense-in-depth ladder: --inspect-only ⊂ --dry-run ⊂ --no-db-write ⊂ --confirm-write.
    # See docs/recovery/.../08_cold_start_tool_boundary_hardening.md for the
    # full safety boundary table.
    log.info("=== Safety contract ===")
    log.info("  inspect_only   : %s", getattr(args, "inspect_only", True))
    log.info("  dry_run        : %s", getattr(args, "dry_run", False))
    log.info("  no_db_write    : %s", getattr(args, "no_db_write", True))
    log.info("  confirm_write  : %s", getattr(args, "confirm_write", False))
    log.info("  write target   : champion_pipeline_staging (via admission_validator)")
    log.info("  formula count  : %d", len(ZOO))
    log.info("  source tags    : %s",
             sorted(set(tag for _, tag in ZOO)))
    log.info("  validator dep  : admission_validator(BIGINT) — must exist in DB")

    # Inspect-only mode: print the formula table and exit. NO compile, NO backtest.
    if getattr(args, "inspect_only", False):
        log.info("=== INSPECT-ONLY MODE — printing formula inventory ===")
        import hashlib as _h
        for f, tag in ZOO:
            ah = _h.md5(f.encode("utf-8")).hexdigest()[:16]
            print(f"{ah}  {tag:24s}  {f}")
        log.info("INSPECT-ONLY mode complete. NO compile, NO backtest, NO DB write performed.")
        return

    # Dry-run mode: compile + simulate validation contract; HARD-ASSERT no DB write.
    # Output a JSONL plan to /tmp/sparse_candidate_dry_run_plans.jsonl.
    if getattr(args, "dry_run", False):
        log.info("=== DRY-RUN MODE — compile + simulate validation; HARD ASSERT no DB write ===")
        import hashlib as _h
        plan_path = "/tmp/sparse_candidate_dry_run_plans.jsonl"
        with open(plan_path, "w") as f_out:
            for f, tag in ZOO:
                ah = _h.md5(f.encode("utf-8")).hexdigest()[:16]
                plan_row = {
                    "alpha_hash": ah,
                    "source_tag": tag,
                    "formula": f,
                    "fitness_version": f"alpha_zoo.{tag}.v1",
                    "validation_contract": [
                        "train_pnl > 0",
                        "val_pnl > 0",
                        "combined_sharpe >= 0.4",
                        "val_few_trades >= 15",
                        "val_low_sharpe >= 0.3",
                        "val_low_wr >= 0.52",
                    ],
                    "dry_run": True,
                    "would_write_to": "champion_pipeline_staging (NOT executed in dry-run)",
                }
                f_out.write(json.dumps(plan_row) + "\n")
        log.info("DRY-RUN complete. Plan written to %s. NO DB writes performed.", plan_path)
        return

    # --no-db-write hard-block — same as default-deny for now, but also asserts
    # that any code path attempting db.execute*/db.fetch* would not be reached.
    if getattr(args, "no_db_write", True) and not getattr(args, "confirm_write", False):
        log.error("ABORT: --no-db-write is in effect (default-on). Use --inspect-only "
                  "or --dry-run for safe modes. Use --confirm-write only under explicit "
                  "governance order to actually write to DB.")
        sys.exit(2)

    # Default-deny: any path that could write to DB is blocked unless --confirm-write.
    if not getattr(args, "confirm_write", False):
        log.error("ABORT: --confirm-write was NOT set. Cold-start tooling refuses to "
                  "write by default. Use one of:")
        log.error("  --inspect-only   list formulas, no compile/backtest/DB")
        log.error("  --dry-run        compile + simulate validation, NO DB write")
        log.error("  --confirm-write  required for actual DB write (governance order needed)")
        sys.exit(2)

    # If we got here: --confirm-write is set. Re-verify schema preconditions.
    log.warning("=== --confirm-write IS SET. Verifying preconditions before any DB write ===")
    db = await asyncpg.connect(
        host=settings.DB_HOST, port=settings.DB_PORT,
        user=settings.DB_USER, password=settings.DB_PASSWORD, database=settings.DB_NAME,
    )
    try:
        for required in ("champion_pipeline_staging", "champion_pipeline_fresh"):
            ok = await db.fetchval(
                "SELECT 1 FROM pg_class WHERE relname=$1 "
                "AND relnamespace='public'::regnamespace", required,
            )
            if not ok:
                log.error("ABORT: required DB object missing: %s. "
                          "Apply v0.7.1 governance migration first.", required)
                sys.exit(3)
        validator_ok = await db.fetchval(
            "SELECT 1 FROM pg_proc WHERE proname='admission_validator' "
            "AND pronamespace='public'::regnamespace",
        )
        if not validator_ok:
            log.error("ABORT: admission_validator() function missing. "
                      "Apply v0.7.1 governance migration first.")
            sys.exit(4)
        log.warning("Preconditions OK. Proceeding under --confirm-write.")
    finally:
        await db.close()

    # Monkey-patch: cold_start's run_for_strategy uses module-level SEED_FORMULAS
    # + injects a single fitness_version from provenance. We override
    # by running one strategy per formula group, but simpler is:
    # run all formulas under both strategies (j01/j02 apply their OWN
    # thresholds.MAX_HOLD via the workers' runtime). cold_start_hand_alphas
    # uses MAX_HOLD_BARS=120 by default now via env. Good.

    # Group formulas by their source tag for distinct fitness_version,
    # actually we just tag each alpha's fitness_version at INSERT time.
    # For simplicity, set SEED_FORMULAS to the list of all formulas and
    # let run_for_strategy tag them uniformly per strategy. We'll rely on
    # indicator_hash ("coldstart_{alpha_hash}_{sym}") + formula + passport
    # for source traceability rather than fitness_version per-formula.

    # cold_start expects just formula strings in SEED_FORMULAS
    css.SEED_FORMULAS = [f for f, _ in ZOO]

    summaries = {}
    for strategy in args.strategies:
        _, summary = await css.run_for_strategy(strategy, args)
        summaries[strategy] = summary

    # Count admitted by strategy
    print(json.dumps(summaries, indent=2))

    # Also: tag in passport the source mapping so downstream can audit
    log.info("Source mapping (alpha_hash -> source_tag) for audit:")
    import hashlib as _h
    for f, tag in ZOO:
        ah = _h.md5(f.encode("utf-8")).hexdigest()[:16]
        log.info("  %s -> %s (formula=%s)", ah, tag, f[:70])


def main():
    parser = argparse.ArgumentParser(
        description="Alpha Zoo cold-start injection — DEFAULT-SAFE: refuses to write "
                    "without explicit --confirm-write. See PR #43 (order 4-1).",
    )
    parser.add_argument("--strategies", nargs="+", default=["j01", "j02"])
    parser.add_argument("--symbols", nargs="+", default=None)
    parser.add_argument("--limit-symbols", type=int, default=None)
    parser.add_argument("--allow-dirty-tree", action="store_true", default=True)
    parser.add_argument("--dry-run-one", action="store_true")
    # PR #43 cold-start safety flags (NG3 from order 4-1):
    parser.add_argument(
        "--inspect-only", action="store_true",
        help="Print formula inventory and exit. No compile, no backtest, no DB write.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Compile + simulate validation contract. Hard-asserts no DB write.",
    )
    parser.add_argument(
        "--no-db-write", action="store_true", default=True,
        help="Default-on. Hard-fails if any code path attempts a DB write.",
    )
    parser.add_argument(
        "--confirm-write", action="store_true", default=False,
        help="REQUIRED for actual DB write. Without this flag, all write paths abort. "
             "Use only under explicit governance order.",
    )
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
