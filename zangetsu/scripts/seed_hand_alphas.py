"""Seed hand-crafted V10 alphas into champion_pipeline as ARENA1_COMPLETE.

Purpose: bootstrap V10 alpha path out of cold-start (GP has evolved 50k+ rounds
without producing a single A4-passing alpha because fitness=|IC| overfits train).
This script injects human-designed, orthogonal alpha formulas directly, bypassing
GP for the first generation so A2/A3/A4/A5 have real candidates to evaluate and
the A13 feedback loop can begin learning survivor patterns.

Respects j13 hard rules:
- Do NOT change any arena gate threshold (uses the EXACT same gates as arena_pipeline).
- Do NOT skip any arena output (seeds enter at ARENA1_COMPLETE, traverse A2→A3→A4→A5).
- Orthogonality enforced: pairwise Spearman |corr| < 0.3 between accepted seeds.
- A1 training state correctness preserved: uses TRAIN cache for train backtest and
  HOLDOUT cache for val backtest via explicit cache swap.

Usage:
  cd ~/j13-ops/zangetsu
  .venv/bin/python scripts/seed_hand_alphas.py --yaml scripts/seed_hand_alphas.yaml \
      --symbol BTCUSDT --regime BULL_TREND [--dry-run]
"""
import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np
import polars as pl
import yaml
from deap import gp
from scipy.stats import spearmanr

sys.path.insert(0, "/home/j13/j13-ops")

from zangetsu.config.cost_model import CostModel
from zangetsu.config.settings import Settings
from zangetsu.engine.components.alpha_engine import AlphaEngine, AlphaResult
from zangetsu.engine.components.alpha_signal import generate_alpha_signals
from zangetsu.engine.components.backtester import Backtester
from zangetsu.engine.components.indicator_bridge import build_indicator_cache
from zangetsu.services.data_collector import merge_funding_to_1m, merge_oi_to_1m
from zangetsu.services.shared_utils import wilson_lower

# Gate values — EXACT same as arena_pipeline.py (v0.5.9 val gates). Do not alter.
A1_MIN_TRADES = 30
A1_VAL_MIN_TRADES = 15
A1_VAL_MIN_SHARPE = 0.3
A1_VAL_MIN_WILSON = 0.52
ENTRY_THR = 0.80
EXIT_THR = 0.50
MIN_HOLD = 60
COOLDOWN = 60
MAX_HOLD = 480
TRAIN_SPLIT_RATIO = 0.70

# Orthogonality threshold
MAX_PAIR_CORR = 0.3


def _load_symbol(sym: str, data_dir: Path):
    df = pl.read_parquet(data_dir / "ohlcv" / f"{sym}.parquet")
    w = min(200000, len(df))
    arrs = {k: df[k].to_numpy()[-w:].astype(np.float32) for k in ("open", "close", "high", "low", "volume")}
    split = int(w * TRAIN_SPLIT_RATIO)
    out = {"train": {k: v[:split] for k, v in arrs.items()},
           "holdout": {k: v[split:] for k, v in arrs.items()},
           "total_bars": w, "train_bars": split, "holdout_bars": w - split}
    try:
        funding = merge_funding_to_1m(data_dir / "ohlcv" / f"{sym}.parquet",
                                       data_dir / "funding" / f"{sym}.parquet").astype(np.float32)
        out["train"]["funding_rate"] = funding[-w:][:split]
        out["holdout"]["funding_rate"] = funding[-w:][split:]
    except Exception as e:
        print(f"[warn] funding merge failed {sym}: {e}")
    try:
        oi = merge_oi_to_1m(data_dir / "ohlcv" / f"{sym}.parquet",
                            data_dir / "oi" / f"{sym}.parquet").astype(np.float32)
        out["train"]["oi"] = oi[-w:][:split]
        out["holdout"]["oi"] = oi[-w:][split:]
    except Exception as e:
        print(f"[warn] oi merge failed {sym}: {e}")
    return out


def _evaluate_seed(name: str, formula: str, engine: AlphaEngine,
                    train_cache, holdout_cache, d_train, d_hold,
                    cost_bps: float, backtester: Backtester, verbose: bool = True):
    """Return dict with compile/train/val metrics + decision, or None if bad."""
    # Compile
    try:
        tree = gp.PrimitiveTree.from_string(formula, engine.pset)
        func = engine.toolbox.compile(expr=tree)
    except Exception as e:
        return {"name": name, "formula": formula, "reject": f"compile_fail:{e}"}

    # Evaluate on train
    engine.indicator_cache.clear()
    engine.indicator_cache.update(train_cache)
    close_t = d_train["close"].astype(np.float64)
    high_t = d_train["high"].astype(np.float64)
    low_t = d_train["low"].astype(np.float64)
    vol_t = d_train["volume"].astype(np.float64)
    try:
        av_t = func(close_t, high_t, low_t, close_t, vol_t)
        av_t = np.nan_to_num(np.asarray(av_t, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    except Exception as e:
        return {"name": name, "formula": formula, "reject": f"train_eval_fail:{e}"}
    if av_t.ndim == 0 or av_t.size == 1:
        av_t = np.full(len(close_t), float(av_t), dtype=np.float32)
    if av_t.shape[0] != len(close_t):
        return {"name": name, "formula": formula, "reject": f"shape_mismatch:{av_t.shape}"}
    if np.std(av_t) < 1e-10:
        return {"name": name, "formula": formula, "reject": "train_zero_std"}

    # Train IC
    fr_t = np.zeros_like(close_t)
    fr_t[:-1] = (close_t[1:] - close_t[:-1]) / np.maximum(close_t[:-1], 1e-10)
    try:
        ic_t, _ = spearmanr(av_t, fr_t)
        ic_t = 0.0 if np.isnan(ic_t) else float(ic_t)
    except Exception:
        ic_t = 0.0

    # Train backtest
    try:
        sigs_t, szs_t, _ = generate_alpha_signals(av_t, entry_threshold=ENTRY_THR,
                                                    exit_threshold=EXIT_THR,
                                                    min_hold=MIN_HOLD, cooldown=COOLDOWN)
        bt_t = backtester.run(sigs_t, d_train["close"].astype(np.float32), "BTC", cost_bps, MAX_HOLD,
                              high=d_train["high"].astype(np.float32),
                              low=d_train["low"].astype(np.float32), sizes=szs_t)
    except Exception as e:
        return {"name": name, "formula": formula, "reject": f"train_bt_fail:{e}"}
    if bt_t.total_trades < A1_MIN_TRADES:
        return {"name": name, "formula": formula, "ic_train": ic_t, "train_trades": int(bt_t.total_trades),
                "reject": f"train_few_trades:{bt_t.total_trades}<{A1_MIN_TRADES}"}

    # Evaluate on holdout (swap cache)
    engine.indicator_cache.clear()
    engine.indicator_cache.update(holdout_cache)
    try:
        close_h = d_hold["close"].astype(np.float64)
        av_h = func(close_h, d_hold["high"].astype(np.float64), d_hold["low"].astype(np.float64),
                    close_h, d_hold["volume"].astype(np.float64))
        av_h = np.nan_to_num(np.asarray(av_h, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
        if av_h.ndim == 0 or av_h.size == 1:
            av_h = np.full(len(close_h), float(av_h), dtype=np.float32)
    finally:
        engine.indicator_cache.clear()
        engine.indicator_cache.update(train_cache)

    if np.std(av_h) < 1e-10:
        return {"name": name, "formula": formula, "ic_train": ic_t, "reject": "val_zero_std"}

    # Val backtest
    try:
        sigs_v, szs_v, _ = generate_alpha_signals(av_h, entry_threshold=ENTRY_THR,
                                                    exit_threshold=EXIT_THR,
                                                    min_hold=MIN_HOLD, cooldown=COOLDOWN)
        bt_v = backtester.run(sigs_v, d_hold["close"].astype(np.float32), "BTC", cost_bps, MAX_HOLD,
                              high=d_hold["high"].astype(np.float32),
                              low=d_hold["low"].astype(np.float32), sizes=szs_v)
    except Exception as e:
        return {"name": name, "formula": formula, "ic_train": ic_t, "reject": f"val_bt_fail:{e}"}

    val_wilson = wilson_lower(bt_v.winning_trades, bt_v.total_trades) if bt_v.total_trades > 0 else 0.0
    metrics = {
        "name": name, "formula": formula,
        "ic_train": ic_t, "train_trades": int(bt_t.total_trades),
        "train_wr": float(bt_t.win_rate), "train_pnl": float(bt_t.net_pnl),
        "val_trades": int(bt_v.total_trades), "val_pnl": float(bt_v.net_pnl),
        "val_sharpe": float(bt_v.sharpe_ratio), "val_wilson": float(val_wilson),
        "val_wr": float(bt_v.win_rate),
        "alpha_values_train": av_t,  # for pairwise corr
    }

    # Gate chain (same as arena_pipeline)
    if bt_v.total_trades < A1_VAL_MIN_TRADES:
        metrics["reject"] = f"val_few_trades:{bt_v.total_trades}<{A1_VAL_MIN_TRADES}"
    elif float(bt_v.net_pnl) <= 0:
        metrics["reject"] = f"val_neg_pnl:{bt_v.net_pnl:.4f}"
    elif float(bt_v.sharpe_ratio) < A1_VAL_MIN_SHARPE:
        metrics["reject"] = f"val_low_sharpe:{bt_v.sharpe_ratio:.3f}<{A1_VAL_MIN_SHARPE}"
    elif float(val_wilson) < A1_VAL_MIN_WILSON:
        metrics["reject"] = f"val_low_wilson:{val_wilson:.3f}<{A1_VAL_MIN_WILSON}"
    else:
        metrics["reject"] = None

    return metrics


def _pairwise_corr_filter(candidates):
    """Keep candidates in yaml order, reject any whose max |Spearman corr|
    against an already-accepted candidate exceeds MAX_PAIR_CORR."""
    accepted = []
    for c in candidates:
        if c.get("reject"):
            continue
        ok = True
        worst_pair = None
        worst_abs = 0.0
        for a in accepted:
            corr, _ = spearmanr(c["alpha_values_train"], a["alpha_values_train"])
            corr = 0.0 if np.isnan(corr) else float(corr)
            if abs(corr) > MAX_PAIR_CORR:
                ok = False
            if abs(corr) > worst_abs:
                worst_abs = abs(corr)
                worst_pair = a["name"]
        c["worst_corr_abs"] = worst_abs
        c["worst_corr_pair"] = worst_pair
        if ok:
            accepted.append(c)
        else:
            c["reject"] = f"corr_with_{worst_pair}:{worst_abs:.3f}>{MAX_PAIR_CORR}"
    return accepted


async def _insert_seed(db, metrics, sym, regime, engine):
    """Build V10 passport and INSERT as ARENA1_COMPLETE."""
    formula = metrics["formula"]
    tree = gp.PrimitiveTree.from_string(formula, engine.pset)
    alpha_hash = "seed_" + hashlib.md5(formula.encode()).hexdigest()[:12]

    # Build AlphaResult for passport (consistent with _individual_to_result output shape).
    try:
        ast_json = engine._tree_to_ast_json(tree)
    except Exception as e:
        return False, f"ast_json_fail:{e}"

    used_indicators = [n for n in engine._indicator_terminal_names if n in formula]
    used_operators = sorted({n for n in engine._operator_names if n in formula})

    alpha_result = AlphaResult(
        formula=formula, ast_json=ast_json, alpha_hash=alpha_hash,
        depth=int(tree.height), node_count=int(len(tree)),
        used_indicators=used_indicators, used_operators=list(used_operators),
        ic=float(metrics["ic_train"]), ic_pvalue=0.0, generation=0,
    )

    score = float(metrics["val_wilson"]) * max(0.01, min(float(metrics["val_pnl"]) + 1.0, 5.0))
    passport = {
        "arena1": {
            "alpha_expression": alpha_result.to_dict(),
            "alpha_hash": alpha_hash,
            "formula": formula,
            "ic": float(metrics["ic_train"]),
            "wr": float(metrics["train_wr"]),
            "pnl": float(metrics["train_pnl"]),
            "trades": int(metrics["train_trades"]),
            "hash": f"zv10_{alpha_hash}_{sym}",
            "symbol": sym,
            "regime": regime,
            "lane": "seed_hand_crafted",
            "entry_threshold": ENTRY_THR,
            "exit_threshold": EXIT_THR,
            "min_hold": MIN_HOLD,
            "cooldown": COOLDOWN,
        },
        "val_metrics": {
            "trades": int(metrics["val_trades"]),
            "net_pnl": float(metrics["val_pnl"]),
            "sharpe": float(metrics["val_sharpe"]),
            "wilson_wr": float(metrics["val_wilson"]),
            "win_rate": float(metrics["val_wr"]),
        },
        "seed_provenance": {"name": metrics["name"], "orthogonal_corr_max": metrics.get("worst_corr_abs", 0.0)},
    }
    indicator_hash = f"zv10_{alpha_hash}_{sym}"

    try:
        await db.execute(
            """
            INSERT INTO champion_pipeline (
                regime, indicator_hash, alpha_hash, status, n_indicators,
                arena1_score, arena1_win_rate, arena1_pnl, arena1_n_trades,
                passport, engine_hash, arena1_completed_at
            ) VALUES (
                $1, $2, $3, 'ARENA1_COMPLETE', $4,
                $5, $6, $7, $8,
                $9::jsonb, 'zv5_v10_alpha_seed_v1', NOW()
            )
            ON CONFLICT (alpha_hash) DO NOTHING
            """,
            regime, indicator_hash, alpha_hash, len(used_indicators),
            score, float(metrics["train_wr"]), float(metrics["train_pnl"]), int(metrics["train_trades"]),
            json.dumps(passport),
        )
        return True, None
    except Exception as e:
        return False, f"db_insert_fail:{e}"


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--yaml", required=True, help="path to seed yaml")
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--regime", default="BULL_TREND")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    settings = Settings()
    data_dir = Path("/home/j13/j13-ops/zangetsu/data")

    # Load OHLCV + caches
    print(f"[load] {args.symbol}")
    data = _load_symbol(args.symbol, data_dir)
    train_cache = build_indicator_cache(
        close=data["train"]["close"], high=data["train"]["high"],
        low=data["train"]["low"], volume=data["train"]["volume"],
        funding=data["train"].get("funding_rate"), oi=data["train"].get("oi"),
    )
    hold_cache = build_indicator_cache(
        close=data["holdout"]["close"], high=data["holdout"]["high"],
        low=data["holdout"]["low"], volume=data["holdout"]["volume"],
        funding=data["holdout"].get("funding_rate"), oi=data["holdout"].get("oi"),
    )
    print(f"[cache] train={len(train_cache)} holdout={len(hold_cache)}")

    # Engine + backtester
    engine = AlphaEngine(indicator_cache=train_cache)
    cost_model = CostModel()
    cost_bps = cost_model.get(args.symbol).total_round_trip_bps

    class _Cfg:
        backtest_chunk_size = 10000
        backtest_gpu_enabled = False
        backtest_gpu_batch_size = 64
    bt = Backtester(_Cfg())

    # Load formulas
    with open(args.yaml) as f:
        seeds = yaml.safe_load(f)
    print(f"[seeds] {len(seeds)} formulas loaded from {args.yaml}")

    # Evaluate each
    results = []
    for s in seeds:
        r = _evaluate_seed(s["name"], s["formula"], engine, train_cache, hold_cache,
                            data["train"], data["holdout"], cost_bps, bt)
        results.append(r)
        rej = r.get("reject")
        msg = f"REJECT {rej}" if rej else f"PASS ic={r.get('ic_train',0):.3f} val_pnl={r.get('val_pnl',0):.4f} val_sharpe={r.get('val_sharpe',0):.3f} val_wilson={r.get('val_wilson',0):.3f}"
        print(f"  {s['name']:32s} {msg}")

    # Pairwise corr filter
    accepted = _pairwise_corr_filter(results)
    print(f"\n[corr-filter] {len(accepted)}/{sum(1 for r in results if not r.get('reject'))} passed orthogonality")
    for c in accepted:
        print(f"  {c['name']:32s} worst_pair={c.get('worst_corr_pair')} corr={c.get('worst_corr_abs',0):.3f}")

    if args.dry_run:
        print("\n[dry-run] no DB writes")
        return 0

    if not accepted:
        print("[done] 0 accepted — nothing to insert")
        return 0

    # Insert
    import asyncpg
    db = await asyncpg.create_pool(
        host=settings.db_host, port=settings.db_port,
        database="zangetsu", user=settings.db_user, password=settings.db_password,
        min_size=1, max_size=2,
    )
    try:
        inserted = 0
        for c in accepted:
            ok, err = await _insert_seed(db, c, args.symbol, args.regime, engine)
            if ok:
                inserted += 1
                print(f"[insert] {c['name']} alpha_hash=seed_{hashlib.md5(c['formula'].encode()).hexdigest()[:12]}")
            else:
                print(f"[insert-fail] {c['name']} {err}")
        print(f"\n[done] inserted {inserted}/{len(accepted)} ARENA1_COMPLETE rows")
    finally:
        await db.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
