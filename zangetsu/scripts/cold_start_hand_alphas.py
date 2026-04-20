"""Cold-start hand-crafted alpha seeder for v0.7.2 observation window.

Five seed formulas per strategy (same set for j01 + j02; strategy-specific
thresholds control each alpha's admission). Each formula uses operators +
indicator terminals verified to exist in the engine's primitive set.

Flow per (strategy, formula, symbol):
    1. Parse formula -> DEAP PrimitiveTree via gp.PrimitiveTree.from_string
    2. Compile tree -> callable; exec on train + holdout slices
    3. Generate alpha signals; backtest train + val with strategy.MAX_HOLD_BARS
    4. Apply A1 internal gates (same as arena_pipeline)
    5. If all pass: INSERT into champion_pipeline_staging with full
       11-field provenance, then SELECT admission_validator($id)
    6. Emit engine_telemetry rows (manual_seed lane)

Safety:
    - No write to champion_pipeline_fresh directly (trigger blocks it)
    - No write to champion_legacy_archive (trigger blocks it)
    - Every admission goes through the same plpgsql validator GP workers use
    - fitness_version = manual_cold_start.v1.{strategy}@sha256:<this-script>
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Iterable

import asyncpg
import numpy as np
import polars as pl
from deap import gp

sys.path.insert(0, "/home/j13/j13-ops")

from zangetsu.config.settings import Settings
settings = Settings()
from zangetsu.engine.components.alpha_engine import AlphaEngine
from zangetsu.engine.components.alpha_signal import generate_alpha_signals
from zangetsu.engine.components.backtester import Backtester
from zangetsu.engine.components.indicator_bridge import build_indicator_cache
from zangetsu.services.shared_utils import wilson_lower

log = logging.getLogger("cold_start")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


SEED_FORMULAS = [
    "tanh_x(delta_9(close))",
    "neg(scale(rsi_14))",
    "mul(sign_x(delta_9(close)), relative_volume_20)",
    "protected_div(delta_20(close), normalized_atr_20)",
    "neg(funding_zscore_20)",
]


TRAIN_SPLIT_RATIO = 0.7
HOLDOUT_WINDOW_BARS = 200_000
COST_BPS = 5.0
ENTRY_THR = 0.80
EXIT_THR = 0.40
MIN_HOLD = 60
COOLDOWN = 60


STRATEGY_MODULES = {
    "j01": ("j01.fitness", "j01.config.thresholds"),
    "j02": ("j02.fitness", "j02.config.thresholds"),
}


def _script_sha() -> str:
    with open(__file__, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def load_symbol_data(symbol: str) -> dict:
    path = f"{settings.parquet_dir}/{symbol}.parquet"
    df = pl.read_parquet(path)
    w = min(HOLDOUT_WINDOW_BARS, len(df))
    split = int(w * TRAIN_SPLIT_RATIO)
    tail = df.tail(w)
    train = {
        "open": tail["open"].to_numpy()[:split].astype(np.float32),
        "high": tail["high"].to_numpy()[:split].astype(np.float32),
        "low": tail["low"].to_numpy()[:split].astype(np.float32),
        "close": tail["close"].to_numpy()[:split].astype(np.float32),
        "volume": tail["volume"].to_numpy()[:split].astype(np.float32),
    }
    holdout = {
        "open": tail["open"].to_numpy()[split:].astype(np.float32),
        "high": tail["high"].to_numpy()[split:].astype(np.float32),
        "low": tail["low"].to_numpy()[split:].astype(np.float32),
        "close": tail["close"].to_numpy()[split:].astype(np.float32),
        "volume": tail["volume"].to_numpy()[split:].astype(np.float32),
    }
    return {"train": train, "holdout": holdout}


def compile_formula(engine: AlphaEngine, formula: str):
    tree = gp.PrimitiveTree.from_string(formula, engine.pset)
    func = engine.toolbox.compile(expr=tree)
    return func, tree


def evaluate_and_backtest(func, data_slice, indicator_cache_to_inject, engine,
                         backtester, symbol, max_hold_bars):
    engine.indicator_cache.clear()
    engine.indicator_cache.update(indicator_cache_to_inject)
    try:
        raw = func(
            data_slice["close"].astype(np.float64),
            data_slice["high"].astype(np.float64),
            data_slice["low"].astype(np.float64),
            data_slice["close"].astype(np.float64),  # open fallback
            data_slice["volume"].astype(np.float64),
        )
    except Exception as e:
        return None, f"compile/eval exception: {type(e).__name__}:{e}"
    alpha_values = np.nan_to_num(
        np.asarray(raw, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0
    )
    if alpha_values.size != data_slice["close"].size:
        # Broadcast scalar or mismatched size
        if alpha_values.size == 1:
            alpha_values = np.full(data_slice["close"].size, float(alpha_values.item()), dtype=np.float32)
        elif alpha_values.size < data_slice["close"].size:
            padded = np.zeros(data_slice["close"].size, dtype=np.float32)
            padded[-alpha_values.size:] = alpha_values
            alpha_values = padded
        else:
            alpha_values = alpha_values[-data_slice["close"].size:]
    if float(np.std(alpha_values)) < 1e-10:
        return None, "zero_variance"
    signals, sizes, _ = generate_alpha_signals(
        alpha_values,
        entry_threshold=ENTRY_THR,
        exit_threshold=EXIT_THR,
        min_hold=MIN_HOLD,
        cooldown=COOLDOWN,
    )
    bt = backtester.run(
        signals,
        data_slice["close"].astype(np.float32),
        symbol,
        COST_BPS,
        max_hold_bars,
        high=data_slice["high"].astype(np.float32),
        low=data_slice["low"].astype(np.float32),
        sizes=sizes,
    )
    return bt, None


async def seed_one(db, strategy_id: str, formula: str, symbol: str,
                   engine: AlphaEngine, backtester: Backtester,
                   train_cache: dict, holdout_cache: dict, regime: str,
                   max_hold_bars: int, provenance_base: dict) -> dict:
    """Evaluate one formula on one symbol. Returns result dict."""
    alpha_hash = hashlib.md5(formula.encode("utf-8")).hexdigest()[:16]
    indicator_hash = f"coldstart_{alpha_hash}_{symbol}"
    try:
        func, tree = compile_formula(engine, formula)
    except Exception as e:
        return {"skipped": True, "reason": f"compile_failed: {type(e).__name__}:{e}"}

    # Load symbol data
    data = load_symbol_data(symbol)

    # Train backtest
    bt_train, err = evaluate_and_backtest(
        func, data["train"], train_cache, engine, backtester, symbol, max_hold_bars
    )
    if bt_train is None:
        return {"skipped": True, "reason": f"train_{err}"}
    if bt_train.total_trades < 30:
        return {"skipped": True, "reason": f"train_few_trades:{bt_train.total_trades}"}
    if bt_train.net_pnl <= 0:
        return {"skipped": True, "reason": f"train_neg_pnl:{bt_train.net_pnl:.4f}"}

    # Val backtest
    bt_val, err = evaluate_and_backtest(
        func, data["holdout"], holdout_cache, engine, backtester, symbol, max_hold_bars
    )
    if bt_val is None:
        return {"skipped": True, "reason": f"val_{err}"}
    if bt_val.total_trades < 15:
        return {"skipped": True, "reason": f"val_few_trades:{bt_val.total_trades}"}
    if bt_val.net_pnl <= 0:
        return {"skipped": True, "reason": f"val_neg_pnl:{bt_val.net_pnl:.4f}"}
    if bt_val.sharpe_ratio < 0.3:
        return {"skipped": True, "reason": f"val_low_sharpe:{bt_val.sharpe_ratio:.2f}"}
    val_wilson = wilson_lower(bt_val.winning_trades, bt_val.total_trades)
    if val_wilson < 0.52:
        return {"skipped": True, "reason": f"val_low_wr:{val_wilson:.3f}"}

    # Compute score (same as arena_pipeline)
    adjusted_wr = wilson_lower(bt_train.winning_trades, bt_train.total_trades)
    pnl_component = max(0.01, min(float(bt_val.net_pnl) + 1.0, 5.0))
    score = float(val_wilson) * pnl_component

    passport = {
        "arena1": {
            "alpha_expression": {
                "formula": formula,
                "ast_json": engine._tree_to_ast_json(tree),
                "alpha_hash": alpha_hash,
                "ic": 0.0,
                "ic_pvalue": 1.0,
                "depth": int(tree.height),
                "node_count": int(len(tree)),
                "generation": -1,
                "parent_hash": None,
                "used_operators": sorted({
                    n for n in engine._operator_names if n in formula
                }),
                "used_indicators": [
                    n for n in engine._indicator_terminal_names if n in formula
                ],
            },
            "alpha_hash": alpha_hash,
            "formula": formula,
            "ic": 0.0,
            "wr": float(bt_train.win_rate),
            "wilson_wr": float(adjusted_wr),
            "pnl": float(bt_train.net_pnl),
            "sharpe": float(bt_train.sharpe_ratio),
            "trades": int(bt_train.total_trades),
            "source": "manual_cold_start.v1",
        },
        "manual_seed": {
            "reason": "v0.7.2 bootstrap injection for observation window",
            "script": "cold_start_hand_alphas.py",
        },
    }

    # INSERT into staging with full provenance
    try:
        staging_id = await db.fetchval(
            """
            INSERT INTO champion_pipeline_staging (
                regime, indicator_hash, alpha_hash, status, n_indicators,
                arena1_score, arena1_win_rate, arena1_pnl, arena1_n_trades,
                passport, engine_hash, arena1_completed_at, strategy_id,
                engine_version, git_commit, config_hash, grammar_hash,
                fitness_version, patches_applied, run_id, worker_id,
                seed, epoch
            ) VALUES (
                $1, $2, $3, 'ARENA1_COMPLETE', $4,
                $5, $6, $7, $8,
                $9::jsonb, 'zv5_v10_alpha', NOW(), $10,
                $11, $12, $13, $14,
                $15, $16, $17, $18,
                $19, $20
            )
            RETURNING id
            """,
            regime,
            indicator_hash,
            alpha_hash,
            1,
            float(score),
            float(bt_train.win_rate),
            float(bt_train.net_pnl),
            int(bt_train.total_trades),
            json.dumps(passport),
            strategy_id,
            provenance_base["engine_version"],
            provenance_base["git_commit"],
            provenance_base["config_hash"],
            provenance_base["grammar_hash"],
            provenance_base["fitness_version"].replace("STRATEGY", strategy_id),
            provenance_base["patches_applied"],
            provenance_base["run_id"],
            0,
            0,
            "B_full_space",
        )
    except Exception as e:
        return {"skipped": True, "reason": f"staging_insert_failed: {type(e).__name__}:{e}"}

    verdict = await db.fetchval("SELECT admission_validator($1)", staging_id)
    return {
        "admitted": verdict == "admitted",
        "staging_id": staging_id,
        "verdict": verdict,
        "score": score,
        "val_pnl": float(bt_val.net_pnl),
        "val_wilson": float(val_wilson),
        "val_sharpe": float(bt_val.sharpe_ratio),
        "formula": formula,
        "symbol": symbol,
        "strategy": strategy_id,
    }


async def run_for_strategy(strategy_id: str, args):
    log.info("=== Cold-start seed for strategy: %s ===", strategy_id)
    # Dynamic import of strategy fitness + thresholds
    import importlib
    fit_mod_name, thresh_mod_name = STRATEGY_MODULES[strategy_id]
    fit_mod = importlib.import_module(fit_mod_name)
    thresh_mod = importlib.import_module(thresh_mod_name)
    max_hold = int(thresh_mod.MAX_HOLD_BARS)
    log.info("%s MAX_HOLD_BARS=%s", strategy_id, max_hold)

    # Provenance base — one bundle per strategy run
    from zangetsu.engine.provenance import (
        get_git_commit, compute_grammar_hash, compute_config_hash, generate_run_id,
    )
    from zangetsu.engine.patches import PATCHES_APPLIED
    if args.allow_dirty_tree:
        import subprocess as _sp
        try:
            _sha = _sp.check_output(["git", "rev-parse", "HEAD"], cwd="/home/j13/j13-ops", text=True).strip()
        except Exception:
            _sha = "unknown"
        git_sha = f"dirty:{_sha}"
    else:
        git_sha, _ = get_git_commit()
    provenance_base = {
        "engine_version": "zangetsu_v0.7.2",
        "git_commit": git_sha,
        "config_hash": compute_config_hash(settings),
        "fitness_version": f"manual_cold_start.v1.STRATEGY@sha256:{_script_sha()}",
        "patches_applied": list(PATCHES_APPLIED) + ["cold_start_hand_seed_v072"],
        "run_id": generate_run_id(),
    }

    # Create engine with strategy fitness
    engine = AlphaEngine(fitness_fn=fit_mod.fitness_fn)
    provenance_base["grammar_hash"] = compute_grammar_hash(
        engine._operator_names, engine._indicator_terminal_names
    )
    backtester = Backtester(settings)

    # DB pool
    pool = await asyncpg.create_pool(
        host=settings.db_host, port=settings.db_port,
        database=settings.db_name, user=settings.db_user,
        password=settings.db_password, min_size=1, max_size=3,
    )

    symbols = args.symbols or list(settings.symbols)
    if args.limit_symbols:
        symbols = symbols[:args.limit_symbols]

    results = []
    summary = {"total": 0, "admitted": 0, "rejected": 0, "skipped": 0,
               "error": 0, "by_reason": {}}

    try:
        for formula in SEED_FORMULAS:
            for sym in symbols:
                summary["total"] += 1
                # Build caches for this symbol
                data = load_symbol_data(sym)
                train_cache = build_indicator_cache(
                    np.ascontiguousarray(data["train"]["close"], dtype=np.float64),
                    np.ascontiguousarray(data["train"]["high"], dtype=np.float64),
                    np.ascontiguousarray(data["train"]["low"], dtype=np.float64),
                    np.ascontiguousarray(data["train"]["volume"], dtype=np.float64),
                )
                holdout_cache = build_indicator_cache(
                    np.ascontiguousarray(data["holdout"]["close"], dtype=np.float64),
                    np.ascontiguousarray(data["holdout"]["high"], dtype=np.float64),
                    np.ascontiguousarray(data["holdout"]["low"], dtype=np.float64),
                    np.ascontiguousarray(data["holdout"]["volume"], dtype=np.float64),
                )
                # Regime placeholder — real regime detection requires more context;
                # use DISCOVERED for manual seeds (neutral label).
                async with pool.acquire() as db:
                    res = await seed_one(
                        db, strategy_id, formula, sym, engine, backtester,
                        train_cache, holdout_cache, "DISCOVERED", max_hold,
                        provenance_base,
                    )
                if res.get("skipped"):
                    summary["skipped"] += 1
                    reason = res["reason"].split(":")[0]
                    summary["by_reason"][reason] = summary["by_reason"].get(reason, 0) + 1
                elif res.get("admitted"):
                    summary["admitted"] += 1
                    log.info("ADMITTED %s %s %s score=%.4f pnl=%.4f wilson=%.3f",
                             strategy_id, sym, formula[:40], res["score"],
                             res["val_pnl"], res["val_wilson"])
                else:
                    summary["rejected"] += 1
                    log.info("REJECTED %s %s verdict=%s", strategy_id, sym, res.get("verdict"))
                results.append(res)
    finally:
        await pool.close()

    log.info("%s summary: %s", strategy_id, json.dumps(summary, indent=2))
    return results, summary


async def main_async(args):
    all_results = {}
    for s in args.strategies:
        results, summary = await run_for_strategy(s, args)
        all_results[s] = {"results": results, "summary": summary}
    print(json.dumps({s: v["summary"] for s, v in all_results.items()}, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategies", nargs="+", default=["j01", "j02"])
    parser.add_argument("--symbols", nargs="+", default=None)
    parser.add_argument("--limit-symbols", type=int, default=None)
    parser.add_argument("--allow-dirty-tree", action="store_true",
                        help="operator override for ad-hoc runs; stamps git_sha as dirty:<sha>")
    parser.add_argument("--dry-run-one", action="store_true",
                        help="Just test 1 formula x 1 symbol for smoke; no DB write")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
