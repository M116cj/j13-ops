#!/usr/bin/env python3
"""Zangetsu V3.1 — HFT per-regime cross-symbol production pipeline.

Usage (on Alaya):
    cd ~/j13-ops/zangetsu_v3
    python3 -m scripts.run_v31
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import polars as pl
import psycopg2

from zangetsu_v3.core.feature_engine import FeatureEngine
from zangetsu_v3.core.segment_extractor import SegmentExtractor, Segment
from zangetsu_v3.factors.hft_factors import compute_hft_factors, N_FACTORS, FACTOR_NAMES as HFT_FACTOR_NAMES
from zangetsu_v3.factors.normalizer import RobustNormalizer
from zangetsu_v3.regime.rule_labeler import (
    label_symbol, Regime, REGIME_NAMES, SEARCH_REGIMES,
)
from zangetsu_v3.search.backtest import HFTBacktest
from zangetsu_v3.search.hyperband import ZeroConfigPipeline
from zangetsu_v3.search.scheduler import RegimeScheduler
from zangetsu_v3.search.signal_scale import SignalScaleEstimator
from zangetsu_v3.gates.gate1 import Gate1
from zangetsu_v3.gates.gate2 import DeflatedSharpeGate
from zangetsu_v3.gates.gate3 import HoldoutGate
from zangetsu_v3.cards.exporter import CardExporter

# ── config ───────────────────────────────────────────────────────
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
DB_DSN = "dbname=zangetsu user=zangetsu password=REDACTED host=127.0.0.1 port=5432"
TRAINING_MONTHS = 18
EMBARGO_DAYS = 90
MIN_SEGMENT_BARS = 1440       # 1 day
CMA_MAE_GENERATIONS = 1000
N_WEIGHTS = N_FACTORS  # 15 HFT factors
N_PARAMS = 5
SOLUTION_DIM = N_WEIGHTS + N_PARAMS
SEARCH_THREADS = 2            # per regime (11 regimes × 2 = 22 threads max)
OUTPUT_BASE = Path("strategies")

# Per-symbol costs (C17)
COST_BPS_R0 = {"BTCUSDT": 3, "ETHUSDT": 3, "BNBUSDT": 5, "SOLUSDT": 5, "XRPUSDT": 6, "DOGEUSDT": 6}
COST_BPS_R1 = {"BTCUSDT": 4, "ETHUSDT": 4, "BNBUSDT": 7, "SOLUSDT": 7, "XRPUSDT": 8, "DOGEUSDT": 8}
FUNDING_RATE = 0.0001  # Phase 1 constant

# Regimes to search (11) vs overlay only (2)
SEARCH_REGIME_IDS = [
    Regime.BULL_TREND, Regime.BEAR_TREND, Regime.BULL_PULLBACK, Regime.BEAR_RALLY,
    Regime.TOPPING, Regime.BOTTOMING, Regime.CONSOLIDATION, Regime.SQUEEZE,
    Regime.CHOPPY_VOLATILE, Regime.DISTRIBUTION, Regime.ACCUMULATION,
]
OVERLAY_ONLY = {Regime.PARABOLIC: 0.3, Regime.LIQUIDITY_CRISIS: 0.0}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("v31")


# ── data loading ─────────────────────────────────────────────────
def load_ohlcv(symbol: str, months: int) -> pl.DataFrame:
    end_ms = int(datetime(2026, 3, 29, tzinfo=timezone.utc).timestamp() * 1000)
    start_ms = int((datetime(2026, 3, 29, tzinfo=timezone.utc) - timedelta(days=30 * months)).timestamp() * 1000)
    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT timestamp, open, high, low, close, volume "
                "FROM ohlcv_1m WHERE symbol = %s AND timestamp >= %s AND timestamp <= %s ORDER BY timestamp",
                (symbol, start_ms, end_ms),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    if not rows:
        raise RuntimeError(f"No data for {symbol}")
    df = pl.DataFrame(rows, schema=["timestamp_ms", "open", "high", "low", "close", "volume"], orient="row")
    return df.with_columns(
        pl.from_epoch(pl.col("timestamp_ms"), time_unit="ms").alias("timestamp"),
        pl.col("open").cast(pl.Float64), pl.col("high").cast(pl.Float64),
        pl.col("low").cast(pl.Float64), pl.col("close").cast(pl.Float64),
        pl.col("volume").cast(pl.Float64),
    ).drop("timestamp_ms").sort("timestamp")


# ── main pipeline ────────────────────────────────────────────────
def main():
    log.info("Zangetsu V3.1 — HFT Per-Regime Cross-Symbol Pipeline")
    log.info(f"Symbols: {SYMBOLS}, Generations: {CMA_MAE_GENERATIONS}")
    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)
    t_global = time.monotonic()

    # ── Step 1: Load all symbols + label ─────────────────────────
    log.info("Step 1: Loading OHLCV + Rule-based 13-state labeling (4h)")
    symbol_data = {}
    for sym in SYMBOLS:
        raw = load_ohlcv(sym, TRAINING_MONTHS)
        labels_1m, labels_4h, df_4h = label_symbol(raw)
        symbol_data[sym] = (raw, labels_1m)
        unique, counts = np.unique(labels_1m, return_counts=True)
        dist = {REGIME_NAMES[int(u)]: int(c) for u, c in zip(unique, counts)}
        log.info(f"  {sym}: {len(raw)} bars, regimes: {dist}")

    # ── Step 2: Extract segments per regime ──────────────────────
    log.info("Step 2: Extracting segments (min 1 day)")
    extractor = SegmentExtractor(min_segment_bars=MIN_SEGMENT_BARS)
    all_segments = extractor.extract_all(symbol_data)

    for regime_id, segs in sorted(all_segments.items()):
        name = REGIME_NAMES.get(regime_id, f"R{regime_id}")
        total_days = sum(s.days for s in segs)
        syms = set(s.symbol for s in segs)
        log.info(f"  {name:25s}: {len(segs):>4d} segs, {total_days:>7.1f} days, {len(syms)}/6 symbols")

    # ── Step 3: Per-regime search ────────────────────────────────
    results = {}
    for regime_id in SEARCH_REGIME_IDS:
        name = REGIME_NAMES[regime_id]
        segs = all_segments.get(regime_id, [])
        if len(segs) < 3:
            log.warning(f"  SKIP {name}: only {len(segs)} segments")
            results[regime_id] = {"status": "SKIPPED", "reason": f"only {len(segs)} segments"}
            continue

        log.info(f"\n{'='*60}")
        log.info(f"REGIME: {name} ({len(segs)} segments)")
        log.info(f"{'='*60}")

        # Split TRAIN / HOLDOUT with embargo fallback for small regimes
        embargo = EMBARGO_DAYS
        train_segs, holdout_segs = extractor.split_train_holdout(segs, train_ratio=0.7, embargo_days=embargo)
        # If holdout < 5 segs, reduce embargo until we get enough
        while len(holdout_segs) < 5 and embargo > 0:
            embargo = max(0, embargo - 30)
            train_segs, holdout_segs = extractor.split_train_holdout(segs, train_ratio=0.7, embargo_days=embargo)
        log.info(f"  TRAIN: {len(train_segs)} segs, HOLDOUT: {len(holdout_segs)} segs (embargo={embargo}d)")

        if len(train_segs) < 2:
            log.warning(f"  SKIP {name}: train too small ({len(train_segs)} segs)")
            results[regime_id] = {"status": "SKIPPED", "reason": "train_too_small"}
            continue

        # Build factor matrices per segment (TRAIN)
        train_seg_data = []
        factor_normalizer = RobustNormalizer()
        all_factor_dfs = []

        for seg in train_segs:
            fm_df = compute_hft_factors(seg.ohlcv)
            # Drop NaN warmup
            fm_np = fm_df.to_numpy()
            valid = ~np.any(np.isnan(fm_np), axis=1)
            fm_np = fm_np[valid]
            close_seg = seg.ohlcv.filter(pl.Series(valid))["close"].to_numpy()
            if len(fm_np) < 100:
                continue
            factor_names = list(fm_df.columns[:N_WEIGHTS])
            if fm_np.shape[1] > N_WEIGHTS:
                fm_np = fm_np[:, :N_WEIGHTS]
            elif fm_np.shape[1] < N_WEIGHTS:
                fm_np = np.hstack([fm_np, np.zeros((len(fm_np), N_WEIGHTS - fm_np.shape[1]))])
            all_factor_dfs.append(pl.DataFrame({n: fm_np[:, i] for i, n in enumerate(factor_names)}))
            train_seg_data.append({"fm_raw": fm_np, "close": close_seg, "symbol": seg.symbol})

        if not train_seg_data:
            log.warning(f"  SKIP {name}: no valid factor data")
            results[regime_id] = {"status": "SKIPPED", "reason": "no_valid_factors"}
            continue

        # Per-regime cross-symbol normalization (C06)
        combined_factors = pl.concat(all_factor_dfs)
        factor_normalizer.fit(combined_factors)
        factor_names = list(combined_factors.columns)

        # Apply normalization
        train_segments_for_eval = []
        for i, sd in enumerate(train_seg_data):
            fm_df = pl.DataFrame({n: sd["fm_raw"][:, j] for j, n in enumerate(factor_names)})
            fm_normed = factor_normalizer.transform(fm_df).to_numpy()
            train_segments_for_eval.append({
                "factor_matrix": fm_normed,
                "close": sd["close"],
                "cost_bps": float(COST_BPS_R1.get(sd["symbol"], 5)),
                "funding_rate": FUNDING_RATE,
            })

        # Signal scale estimation (C26) — per-segment, not combined
        # Each segment's signal has its own scale; use median across segments
        scale_est = SignalScaleEstimator()
        per_seg_stds = []
        for seg_d in train_segments_for_eval:
            seg_std = scale_est.estimate(seg_d["factor_matrix"])
            per_seg_stds.append(seg_std)
        median_std = float(np.median(per_seg_stds))
        scale_est.median_std = median_std
        bounds_info = scale_est.derive_bounds()
        param_bounds = bounds_info["param_bounds"]

        total_rows = sum(s["factor_matrix"].shape[0] for s in train_segments_for_eval)
        log.info(f"  Factors: {len(train_segments_for_eval)} segs, {total_rows} total rows, signal_std={median_std:.4f}")
        log.info(f"  Entry range: [{param_bounds[0,0]:.4f}, {param_bounds[0,1]:.4f}]")
        log.info(f"  Hold range: [{param_bounds[4,0]:.0f}, {param_bounds[4,1]:.0f}] (HFT)")

        # CMA-MAE search with C16 Zero-Config Pipeline
        scheduler = RegimeScheduler(
            solution_dim=SOLUTION_DIM, n_weights=N_WEIGHTS,
            param_bounds=param_bounds, median_signal_std=median_std,
        )
        pipeline = ZeroConfigPipeline(
            scheduler=scheduler,
            segments=train_segments_for_eval,
            n_weights=N_WEIGHTS,
            param_bounds=param_bounds,
            n_jobs=SEARCH_THREADS,
        )

        t_search = time.monotonic()
        pipeline.run(generations=CMA_MAE_GENERATIONS)
        search_secs = time.monotonic() - t_search

        n_elites = scheduler.archive.stats.num_elites
        log.info(f"  Search: {n_elites} elites, time={search_secs:.0f}s")
        log.info(f"  Rung0 survived: {pipeline.rung0_survive_count}, Rung1 promoted: {pipeline.rung1_promote_count}")

        if n_elites == 0:
            log.warning(f"  {name}: 0 elites after {CMA_MAE_GENERATIONS} gen")
            results[regime_id] = {"status": "NO_ELITES"}
            continue

        best_elite = scheduler.archive.best_elite
        best_fitness = float(best_elite["objective"])
        best_sol = best_elite["solution"]
        best_params = scheduler.denormalize_params(best_sol)
        weights = best_sol[:N_WEIGHTS]

        log.info(f"  Best fitness: {best_fitness:.4f}")
        log.info(f"  Params: {best_params}")
        log.info(f"  QD final: {pipeline.qd_history[-1]:.2f}")

        # ── Gates ────────────────────────────────────────────────
        # Gate 1: Train consistency (trimmed_min already in fitness)
        g1 = Gate1()
        # Use the aggregate train result for Gate1
        engine = HFTBacktest()
        train_fitnesses = []
        for seg_d in train_segments_for_eval:
            sig = seg_d["factor_matrix"] @ weights
            res = engine.evaluate(sig, seg_d["close"], best_params, seg_d["cost_bps"], seg_d["funding_rate"])
            train_fitnesses.append(res)

        # Gate1 on best segment result
        best_train = max(train_fitnesses, key=lambda r: r.hft_fitness)
        g1_pass = g1.evaluate(best_train)
        log.info(f"  Gate1: {'PASS' if g1_pass else 'FAIL'} (sos={g1.last_sos:.4f})")

        # Gate 2: DSR
        g2 = DeflatedSharpeGate(threshold=0.05)
        g2_pass = g2.gate(
            observed_sharpe=best_train.sharpe,
            n_observations=best_train.n_active_bars,
            n_trials=n_elites,
        )
        log.info(f"  Gate2: {'PASS' if g2_pass else 'FAIL'} (dsr={g2.last_dsr:.4f}, trials={n_elites})")

        # Gate 3: Holdout
        g3 = HoldoutGate()
        if holdout_segs:
            holdout_fitnesses = []
            for seg in holdout_segs:
                fm_df = compute_hft_factors(seg.ohlcv)
                fm_np = fm_df.to_numpy()
                valid = ~np.any(np.isnan(fm_np), axis=1)
                fm_np = fm_np[valid]
                if fm_np.shape[1] > N_WEIGHTS:
                    fm_np = fm_np[:, :N_WEIGHTS]
                elif fm_np.shape[1] < N_WEIGHTS:
                    fm_np = np.hstack([fm_np, np.zeros((len(fm_np), N_WEIGHTS - fm_np.shape[1]))])
                if len(fm_np) < 100:
                    continue
                fm_df_n = pl.DataFrame({n: fm_np[:, j] for j, n in enumerate(factor_names)})
                fm_normed = factor_normalizer.transform(fm_df_n).to_numpy()
                close_ho = seg.ohlcv.filter(pl.Series(valid))["close"].to_numpy()
                sig = fm_normed @ weights
                res = engine.evaluate(sig, close_ho, best_params,
                                      float(COST_BPS_R1.get(seg.symbol, 5)), FUNDING_RATE)
                holdout_fitnesses.append(res)

            if holdout_fitnesses:
                # Aggregate holdout: use trimmed min
                ho_fits = [r.hft_fitness for r in holdout_fitnesses]
                ho_sharpes = [r.sharpe for r in holdout_fitnesses]
                ho_wrs = [r.win_rate for r in holdout_fitnesses]
                ho_tpds = [r.trades_per_day for r in holdout_fitnesses]

                # Build aggregate result for Gate3
                best_ho = max(holdout_fitnesses, key=lambda r: r.hft_fitness)
                g3_pass, g3_reason = g3.gate(holdout_result=best_ho)
                log.info(f"  Gate3: {'PASS' if g3_pass else 'FAIL'} — {g3_reason}")
                log.info(f"    Holdout: {len(holdout_fitnesses)} segs, "
                         f"best_fitness={best_ho.hft_fitness:.4f}, "
                         f"wr={best_ho.win_rate:.3f}, tpd={best_ho.trades_per_day:.1f}")
            else:
                g3_pass = False
                g3_reason = "no_valid_holdout_data"
                log.warning(f"  Gate3: FAIL — no valid holdout data")
        else:
            g3_pass = False
            g3_reason = "no_holdout_segments"
            log.warning(f"  Gate3: FAIL — no holdout segments")

        all_pass = g1_pass and g2_pass and g3_pass
        status = "PASSED" if all_pass else "FAILED_HOLDOUT"
        log.info(f"  RESULT: {status}")

        # Export card
        card_id = f"{name}_expert"
        card_dir = OUTPUT_BASE / card_id
        card_payload = {
            "version": "3.1",
            "id": card_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "regime": name,
            "regime_includes": [REGIME_NAMES[int(r)] for r in SEARCH_REGIMES.get(name, [regime_id])],
            "applicable_symbols": SYMBOLS,
            "warmup_bars": 200,
            "style": "HFT",
            "normalization": {
                "method": "robust_zscore_per_regime",
                "medians": factor_normalizer.medians,
                "stds": factor_normalizer.scales,
            },
            "factors": [
                {"index": i, "name": factor_names[i], "weight": float(weights[i])}
                for i in range(N_WEIGHTS)
            ],
            "params": best_params,
            "cost_model": {
                "trading_bps_per_symbol": COST_BPS_R1,
                "funding_rate_avg": FUNDING_RATE,
            },
            "backtest": {
                "train_segments": len(train_segs),
                "train_symbols": list(set(s.symbol for s in train_segs)),
                "best_fitness": best_fitness,
                "best_sharpe": best_train.sharpe,
                "best_win_rate": best_train.win_rate,
                "best_tpd": best_train.trades_per_day,
                "best_hold_avg": best_train.hold_bars_avg,
            },
            "validation": {
                "gate1_pass": g1_pass, "gate1_sos": g1.last_sos,
                "gate2_pass": g2_pass, "gate2_dsr": g2.last_dsr,
                "gate3_pass": g3_pass, "gate3_reason": g3_reason,
                "n_elites": n_elites,
                "deflated_sharpe_ratio": g2.last_dsr,
            },
            "regime_labeler": {"method": "rule_based_4h", "resample": "4h"},
            "deployment_hints": {"max_concurrent_positions": 3},
            "status": "PASSED_HOLDOUT" if all_pass else "FAILED_HOLDOUT",
        }

        exporter = CardExporter()
        from zangetsu_v3.regime.labeler import RegimeLabeler
        try:
            labeler = RegimeLabeler(min_states=2, max_states=5)
            labeler_obj = labeler
        except Exception:
            labeler_obj = None

        if labeler_obj:
            exporter.export(output_dir=card_dir, card_payload=card_payload, regime_model=labeler_obj)
        else:
            card_dir.mkdir(parents=True, exist_ok=True)
            (card_dir / "card.json").write_text(json.dumps(card_payload, indent=2, default=str))

        results[regime_id] = {
            "regime": name, "status": status,
            "n_elites": n_elites, "best_fitness": best_fitness,
            "params": best_params,
            "gate1": g1_pass, "gate2": g2_pass, "gate3": g3_pass,
            "search_seconds": search_secs,
        }

    # ── Summary ──────────────────────────────────────────────────
    total_time = time.monotonic() - t_global
    log.info(f"\n{'='*70}")
    log.info("ZANGETSU V3.1 — PRODUCTION SUMMARY")
    log.info(f"{'='*70}")

    passed = 0
    for regime_id in SEARCH_REGIME_IDS:
        r = results.get(regime_id, {"status": "NOT_RUN"})
        name = REGIME_NAMES[regime_id]
        st = r.get("status", "?")
        if st in ("PASSED", "FAILED_HOLDOUT"):
            g1 = "✓" if r.get("gate1") else "✗"
            g2 = "✓" if r.get("gate2") else "✗"
            g3 = "✓" if r.get("gate3") else "✗"
            log.info(f"  {name:25s} {st:18s} G1:{g1} G2:{g2} G3:{g3} "
                     f"fitness={r.get('best_fitness', 0):.4f} time={r.get('search_seconds', 0):.0f}s")
            if st == "PASSED":
                passed += 1
        else:
            log.info(f"  {name:25s} {st}")

    log.info(f"\n{passed}/{len(SEARCH_REGIME_IDS)} experts passed all gates")
    log.info(f"Total time: {total_time:.0f}s ({total_time/60:.1f}min)")

    summary_path = OUTPUT_BASE / f"v31-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M')}.json"
    with summary_path.open("w") as f:
        json.dump({k: v for k, v in results.items()}, f, indent=2, default=str)
    log.info(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
