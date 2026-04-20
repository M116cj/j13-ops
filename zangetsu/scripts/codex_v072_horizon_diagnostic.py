#!/usr/bin/env python3
"""Portable v0.7.2 horizon diagnostic for a single formula/symbol.

This script is designed to run inside the real Zangetsu repo on Alaya.
It does not require DB access; it evaluates one formula directly from
parquet OHLCV and the engine/backtester components.

Example:
  cd /home/j13/j13-ops
  set -a && . zangetsu/secret/.env && set +a
  export PYTHONPATH=/home/j13/j13-ops
  zangetsu/.venv/bin/python /path/to/codex_v072_horizon_diagnostic.py \
    --repo-root /home/j13/j13-ops \
    --strategy-id j01 \
    --symbol BTCUSDT \
    --formula 'pow2(ts_rank_3(ts_rank_3(ts_rank_3(ts_rank_3(close)))))'
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Iterable

import numpy as np
import polars as pl
from deap import gp


def _quantiles(arr: np.ndarray, probs: Iterable[float]) -> dict[str, float]:
    vals = np.quantile(arr.astype(np.float64), list(probs))
    out: dict[str, float] = {}
    for prob, val in zip(probs, vals):
        out[f"p{int(prob * 100):02d}"] = float(val)
    return out


def _series_stats(arr: np.ndarray) -> dict[str, float]:
    arr64 = np.asarray(arr, dtype=np.float64)
    return {
        "min": float(np.min(arr64)),
        "max": float(np.max(arr64)),
        "mean": float(np.mean(arr64)),
        "std": float(np.std(arr64)),
        **_quantiles(arr64, [0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99]),
    }


def _signal_counts(signals: np.ndarray) -> dict[str, int]:
    return {
        "long": int(np.sum(signals == 1)),
        "short": int(np.sum(signals == -1)),
        "flat": int(np.sum(signals == 0)),
    }


def _wilson_lower(wins: int, total: int, z: float = 1.96) -> float:
    if total <= 0:
        return 0.0
    p = wins / total
    denom = 1.0 + (z * z / total)
    centre = p + (z * z / (2.0 * total))
    adjust = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * total)) / total)
    return (centre - adjust) / denom


def _load_tail_split(parquet_path: Path, window_bars: int, train_ratio: float) -> dict[str, dict[str, np.ndarray]]:
    df = pl.read_parquet(parquet_path)
    w = min(window_bars, len(df))
    if w < 2000:
        raise RuntimeError(f"not enough bars in {parquet_path}: {w}")
    tail = df.tail(w)
    split = int(w * train_ratio)
    cols = ("open", "high", "low", "close", "volume")
    train = {c: tail[c].to_numpy()[:split].astype(np.float32) for c in cols}
    holdout = {c: tail[c].to_numpy()[split:].astype(np.float32) for c in cols}
    return {"train": train, "holdout": holdout}


def _compile_formula(engine, formula: str):
    tree = gp.PrimitiveTree.from_string(formula, engine.pset)
    func = engine.toolbox.compile(expr=tree)
    return tree, func


def _evaluate_formula(func, engine, data_slice: dict[str, np.ndarray], indicator_cache: dict) -> np.ndarray:
    engine.indicator_cache.clear()
    engine.indicator_cache.update(indicator_cache)
    raw = func(
        data_slice["close"].astype(np.float64),
        data_slice["high"].astype(np.float64),
        data_slice["low"].astype(np.float64),
        data_slice["open"].astype(np.float64),
        data_slice["volume"].astype(np.float64),
    )
    alpha = np.nan_to_num(np.asarray(raw, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    if alpha.ndim == 0 or alpha.size == 1:
        alpha = np.full(data_slice["close"].shape[0], float(alpha.item()), dtype=np.float32)
    if alpha.shape[0] != data_slice["close"].shape[0]:
        if alpha.shape[0] > data_slice["close"].shape[0]:
            alpha = alpha[-data_slice["close"].shape[0] :]
        else:
            padded = np.zeros(data_slice["close"].shape[0], dtype=np.float32)
            padded[-alpha.shape[0] :] = alpha
            alpha = padded
    return alpha


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, help="real j13-ops repo root on Alaya")
    parser.add_argument("--strategy-id", choices=["j01", "j02"], default="j01")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument(
        "--formula",
        default="pow2(ts_rank_3(ts_rank_3(ts_rank_3(ts_rank_3(close)))))",
    )
    parser.add_argument("--window-bars", type=int, default=200000)
    parser.add_argument("--train-ratio", type=float, default=0.70)
    parser.add_argument("--entry-threshold", type=float, default=0.80)
    parser.add_argument("--exit-threshold", type=float, default=0.40)
    parser.add_argument("--min-hold", type=int, default=60)
    parser.add_argument("--cooldown", type=int, default=60)
    parser.add_argument("--cost-bps", type=float, default=5.0)
    parser.add_argument("--horizons", default="60,120,240,480")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    if not repo_root.exists():
        raise RuntimeError(f"repo root does not exist: {repo_root}")

    sys.path.insert(0, str(repo_root))

    from zangetsu.config.settings import Settings
    from zangetsu.engine.components.alpha_engine import AlphaEngine
    from zangetsu.engine.components.alpha_signal import generate_alpha_signals
    from zangetsu.engine.components.backtester import Backtester
    from zangetsu.engine.components.indicator_bridge import build_indicator_cache

    fit_mod = __import__(f"{args.strategy_id}.fitness", fromlist=["fitness_fn"])
    settings = Settings()
    backtester = Backtester(settings)
    engine = AlphaEngine(fitness_fn=fit_mod.fitness_fn)

    parquet_path = repo_root / "zangetsu" / "data" / "ohlcv" / f"{args.symbol}.parquet"
    data = _load_tail_split(parquet_path, args.window_bars, args.train_ratio)

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

    tree, func = _compile_formula(engine, args.formula)
    alpha_train = _evaluate_formula(func, engine, data["train"], train_cache)
    alpha_holdout = _evaluate_formula(func, engine, data["holdout"], holdout_cache)

    sig_train, size_train, _ = generate_alpha_signals(
        alpha_train,
        entry_threshold=args.entry_threshold,
        exit_threshold=args.exit_threshold,
        min_hold=args.min_hold,
        cooldown=args.cooldown,
    )
    sig_holdout, size_holdout, _ = generate_alpha_signals(
        alpha_holdout,
        entry_threshold=args.entry_threshold,
        exit_threshold=args.exit_threshold,
        min_hold=args.min_hold,
        cooldown=args.cooldown,
    )

    horizon_results: list[dict[str, object]] = []
    horizons = [int(x.strip()) for x in args.horizons.split(",") if x.strip()]
    for horizon in horizons:
        bt_train = backtester.run(
            sig_train,
            data["train"]["close"],
            args.symbol,
            args.cost_bps,
            horizon,
            high=data["train"]["high"],
            low=data["train"]["low"],
            sizes=size_train,
        )
        bt_holdout = backtester.run(
            sig_holdout,
            data["holdout"]["close"],
            args.symbol,
            args.cost_bps,
            horizon,
            high=data["holdout"]["high"],
            low=data["holdout"]["low"],
            sizes=size_holdout,
        )
        horizon_results.append(
            {
                "max_hold": horizon,
                "train": {
                    "trades": int(bt_train.total_trades),
                    "net_pnl": float(bt_train.net_pnl),
                    "sharpe": float(bt_train.sharpe_ratio),
                    "wilson_wr": float(_wilson_lower(bt_train.winning_trades, bt_train.total_trades)),
                    "win_rate": float(bt_train.win_rate),
                    "avg_hold_bars": float(bt_train.avg_hold_bars),
                },
                "holdout": {
                    "trades": int(bt_holdout.total_trades),
                    "net_pnl": float(bt_holdout.net_pnl),
                    "sharpe": float(bt_holdout.sharpe_ratio),
                    "wilson_wr": float(_wilson_lower(bt_holdout.winning_trades, bt_holdout.total_trades)),
                    "win_rate": float(bt_holdout.win_rate),
                    "avg_hold_bars": float(bt_holdout.avg_hold_bars),
                },
            }
        )

    positive_horizons = [
        row["max_hold"]
        for row in horizon_results
        if row["train"]["net_pnl"] > 0 or row["holdout"]["net_pnl"] > 0
    ]

    output = {
        "meta": {
            "repo_root": str(repo_root),
            "strategy_id": args.strategy_id,
            "symbol": args.symbol,
            "formula": args.formula,
            "tree_height": int(tree.height),
            "tree_nodes": int(len(tree)),
            "entry_threshold": args.entry_threshold,
            "exit_threshold": args.exit_threshold,
            "min_hold": args.min_hold,
            "cooldown": args.cooldown,
            "cost_bps": args.cost_bps,
            "window_bars": args.window_bars,
            "train_ratio": args.train_ratio,
        },
        "alpha_distribution": {
            "train": _series_stats(alpha_train),
            "holdout": _series_stats(alpha_holdout),
        },
        "signal_distribution": {
            "train": _signal_counts(sig_train),
            "holdout": _signal_counts(sig_holdout),
        },
        "trade_counts_from_signals": {
            "train_position_changes": int(np.sum(np.diff(sig_train.astype(np.int16)) != 0)),
            "holdout_position_changes": int(np.sum(np.diff(sig_holdout.astype(np.int16)) != 0)),
        },
        "backtests_by_horizon": horizon_results,
        "positive_horizons": positive_horizons,
    }

    print(json.dumps(output, indent=2, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
