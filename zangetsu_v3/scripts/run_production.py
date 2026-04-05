#!/usr/bin/env python3
"""Production pipeline: real OHLCV → search → gate → card → live replay.

Usage (on Alaya):
    cd ~/j13-ops/zangetsu_v3
    python3 -m scripts.run_production
"""
from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import polars as pl
import psycopg2

# ── project imports ──────────────────────────────────────────────
from zangetsu_v3.core.feature_engine import FeatureEngine
from zangetsu_v3.core.data_split import DataSplit
from zangetsu_v3.factors.bootstrap import compute_factor_matrix
from zangetsu_v3.factors.normalizer import RobustNormalizer
from zangetsu_v3.regime.labeler import RegimeLabeler
from zangetsu_v3.regime.predictor import OnlineRegimePredictor
from zangetsu_v3.search.backtest import NumbaContinuousBacktest
from zangetsu_v3.search.hyperband import HyperbandPipeline, make_evaluator, estimate_signal_scale, make_signal_adaptive_bounds
from zangetsu_v3.search.scheduler import RegimeScheduler
from zangetsu_v3.gates.gate1 import Gate1
from zangetsu_v3.gates.gate2 import DeflatedSharpeGate
from zangetsu_v3.gates.gate3 import HoldoutGate
from zangetsu_v3.cards.exporter import CardExporter
from zangetsu_v3.live.journal import LiveJournal
from zangetsu_v3.live.monitor import LiveMonitor
from zangetsu_v3.live.main_loop import build_live_state, on_new_bar

# ── config ───────────────────────────────────────────────────────
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
DB_DSN = "dbname=zangetsu user=zangetsu password=9c424966bebb05a42966186bb22d7480 host=127.0.0.1 port=5432"
TRAINING_MONTHS = 18
EMBARGO_DAYS = 90
HOLDOUT_MONTHS = 10
CMA_MAE_GENERATIONS = 1000
N_WEIGHTS = 15
N_PARAMS = 5
SOLUTION_DIM = N_WEIGHTS + N_PARAMS
SEARCH_THREADS = 20
COST_BPS = 3.0
FUNDING_RATE = 0.0001
LIVE_REPLAY_BARS = 500         # bars to replay from holdout
OUTPUT_BASE = Path("strategies")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("prod")


# ── data loading ─────────────────────────────────────────────────
def load_ohlcv(symbol: str, months: int) -> pl.DataFrame:
    """Load raw 1-minute OHLCV from PostgreSQL."""
    end_ms = int(datetime(2026, 3, 29, tzinfo=timezone.utc).timestamp() * 1000)
    start_ms = int((datetime(2026, 3, 29, tzinfo=timezone.utc) - timedelta(days=30 * months)).timestamp() * 1000)

    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT timestamp, open, high, low, close, volume "
                "FROM ohlcv_1m WHERE symbol = %s AND timestamp >= %s AND timestamp <= %s "
                "ORDER BY timestamp",
                (symbol, start_ms, end_ms),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        raise RuntimeError(f"No data for {symbol}")

    df = pl.DataFrame(
        rows,
        schema=["timestamp_ms", "open", "high", "low", "close", "volume"],
        orient="row",
    )
    df = df.with_columns(
        pl.from_epoch(pl.col("timestamp_ms"), time_unit="ms").alias("timestamp"),
        pl.col("open").cast(pl.Float64),
        pl.col("high").cast(pl.Float64),
        pl.col("low").cast(pl.Float64),
        pl.col("close").cast(pl.Float64),
        pl.col("volume").cast(pl.Float64),
    ).drop("timestamp_ms").sort("timestamp")

    log.info(f"  {symbol}: {len(df)} 1m bars "
             f"({df['timestamp'].min()} to {df['timestamp'].max()})")
    return df


# ── per-symbol pipeline ─────────────────────────────────────────
def run_symbol(symbol: str) -> dict:
    """Full pipeline for one symbol. Returns summary dict."""
    log.info(f"{'='*60}")
    log.info(f"SYMBOL: {symbol}")
    log.info(f"{'='*60}")

    card_id = f"v3-{symbol.lower()}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
    out_dir = OUTPUT_BASE / card_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── S01: Load & Feature ──────────────────────────────────────
    t0 = time.monotonic()
    raw = load_ohlcv(symbol, TRAINING_MONTHS)
    fe = FeatureEngine()
    featured = fe.compute(raw)
    log.info(f"  S01 features: {featured.shape} cols={featured.columns}")

    # ── S02: Data split ──────────────────────────────────────────
    ds = DataSplit(embargo_days=EMBARGO_DAYS, holdout_months=HOLDOUT_MONTHS)
    train, embargo, holdout = ds.split(featured)
    log.info(f"  S02 split: train={len(train)} embargo={len(embargo)} holdout={len(holdout)}")
    if len(train) < 200:
        log.warning(f"  SKIP {symbol}: train set too small ({len(train)})")
        return {"symbol": symbol, "status": "SKIPPED", "reason": "train_too_small"}

    # ── S03: Normalizer ──────────────────────────────────────────
    feature_cols = ["rolling_return", "realized_vol", "volume_zscore", "range_zscore"]
    normalizer = RobustNormalizer()
    normalizer.fit(train.select(feature_cols))
    log.info(f"  S03 normalizer fit on {len(train)} rows")

    # ── S04: Regime labeler (BIC model selection) ────────────────
    labeler = RegimeLabeler(min_states=2, max_states=5)
    train_labels = labeler.fit(train)
    n_regimes = len(np.unique(train_labels))
    log.info(f"  S04 regime: {n_regimes} states (BIC selected)")

    # ── S05: Online predictor smoke check ────────────────────────
    predictor = OnlineRegimePredictor(debounce=5)
    for lbl in train_labels[:30]:
        predictor.step(int(lbl))
    log.info(f"  S05 predictor: active_regime={predictor.active_regime} conf={predictor.switch_confidence:.3f}")

    # ── S06: Factor matrix ───────────────────────────────────────
    factor_df = compute_factor_matrix(train)
    factor_names = list(factor_df.columns)
    factor_matrix = factor_df.to_numpy()

    # Pad or trim to N_WEIGHTS
    if factor_matrix.shape[1] < N_WEIGHTS:
        factor_matrix = np.hstack([factor_matrix,
                                   np.zeros((len(train), N_WEIGHTS - factor_matrix.shape[1]))])
    elif factor_matrix.shape[1] > N_WEIGHTS:
        factor_matrix = factor_matrix[:, :N_WEIGHTS]
        factor_names = factor_names[:N_WEIGHTS]

    # Drop warmup NaN rows
    valid_mask = ~np.any(np.isnan(factor_matrix), axis=1)
    factor_matrix = factor_matrix[valid_mask]
    train = train.filter(pl.Series(valid_mask))
    train_labels = train_labels[valid_mask]

    # Normalize factor_matrix: per-column robust z-score (median + MAD)
    factor_normalizer = RobustNormalizer()
    factor_df_clean = pl.DataFrame(
        {name: factor_matrix[:, i] for i, name in enumerate(factor_names)}
    )
    factor_normalizer.fit(factor_df_clean)
    factor_df_normed = factor_normalizer.transform(factor_df_clean)
    factor_matrix = factor_df_normed.to_numpy()

    factor_stds = np.std(factor_matrix, axis=0)
    log.info(f"  S06 factors: {factor_matrix.shape} (after NaN drop + normalize)")
    log.info(f"  Factor stds (post-norm): min={factor_stds.min():.3f} max={factor_stds.max():.3f} mean={factor_stds.mean():.3f}")

    # ── S07: CMA-MAE search (per-regime) ─────────────────────────
    # Find regimes with enough bars (>5% of train) for meaningful search
    unique_regimes, regime_counts = np.unique(train_labels, return_counts=True)
    min_regime_bars = int(len(train_labels) * 0.05)
    viable_mask = regime_counts >= min_regime_bars
    viable_regimes = unique_regimes[viable_mask]
    viable_counts = regime_counts[viable_mask]
    regime_ranked = viable_regimes[np.argsort(-viable_counts)]
    log.info(f"  Regime distribution: {dict(zip(unique_regimes.tolist(), regime_counts.tolist()))}")
    log.info(f"  Viable regimes (>{min_regime_bars} bars): {regime_ranked.tolist()}")
    if len(regime_ranked) == 0:
        log.warning(f"  SKIP {symbol}: no viable regimes")
        return {"symbol": symbol, "status": "SKIPPED", "reason": "no_viable_regimes"}

    close_arr = train["close"].to_numpy()
    engine = NumbaContinuousBacktest()
    best_results = {}

    # Fix2: estimate signal scale from factor_matrix
    median_std = estimate_signal_scale(factor_matrix)
    adaptive_bounds = make_signal_adaptive_bounds(median_std)
    log.info(f"  Fix2: median_signal_std={median_std:.6f}, "
             f"entry_range=[{adaptive_bounds[0,0]:.6f}, {adaptive_bounds[0,1]:.6f}], "
             f"exit_range=[{adaptive_bounds[1,0]:.6f}, {adaptive_bounds[1,1]:.6f}]")

    # Fix2 verification: midpoint backtest should have reasonable tpd
    mid_entry = (adaptive_bounds[0, 0] + adaptive_bounds[0, 1]) / 2
    mid_exit = (adaptive_bounds[1, 0] + adaptive_bounds[1, 1]) / 2
    mid_params = {"entry_thr": mid_entry, "exit_thr": mid_exit, "stop_mult": 3.0, "pos_frac": 0.08, "hold_max": 60}
    mid_signal = factor_matrix @ np.random.default_rng(42).standard_normal(N_WEIGHTS) * 0.5
    mid_result = engine.evaluate(mid_signal, close_arr, mid_params, train_labels, int(regime_ranked[0]), COST_BPS, FUNDING_RATE)
    log.info(f"  Fix2 verify: midpoint tpd={mid_result.trades_per_day:.2f}, "
             f"active_bars={mid_result.n_active_bars}, sharpe={mid_result.sharpe:.2f}")

    for target_regime in regime_ranked[:min(4, len(regime_ranked))]:
        target_regime = int(target_regime)
        regime_pct = float(regime_counts[unique_regimes == target_regime][0]) / len(train_labels) * 100
        log.info(f"  S07 search: regime {target_regime} ({regime_pct:.1f}% of train), {CMA_MAE_GENERATIONS} gen...")

        # Fix4: pass signal scale to scheduler
        scheduler = RegimeScheduler(
            solution_dim=SOLUTION_DIM,
            n_weights=N_WEIGHTS,
            param_bounds=adaptive_bounds,
            median_signal_std=median_std,
        )
        hyper = HyperbandPipeline(scheduler=scheduler, n_jobs=SEARCH_THREADS)

        # min_active = regime_bars * 0.001
        regime_bars = int(regime_counts[unique_regimes == target_regime][0])
        min_active = max(int(regime_bars * 0.001), 30)
        log.info(f"    min_active_bars={min_active} (regime_bars={regime_bars})")

        evaluator = make_evaluator(
            factor_matrix=factor_matrix,
            close=close_arr,
            regime_labels=train_labels,
            target_regime_id=target_regime,
            cost_bps=COST_BPS,
            funding_rate=FUNDING_RATE,
            engine=engine,
            n_weights=N_WEIGHTS,
            param_bounds=adaptive_bounds,
            min_active_bars=min_active,
        )

        t_search = time.monotonic()
        hyper.run(generations=CMA_MAE_GENERATIONS, evaluator=evaluator)
        search_secs = time.monotonic() - t_search

        n_elites = scheduler.archive.stats.num_elites
        best_elite = scheduler.archive.best_elite
        best_fitness = float(best_elite["objective"])
        log.info(f"    regime {target_regime}: {n_elites} elites, best_fitness={best_fitness:.4f}, "
                 f"time={search_secs:.1f}s, qd_final={hyper.qd_history[-1]:.2f}")

        best_results[target_regime] = {
            "elite": best_elite,
            "n_elites": n_elites,
            "qd_history": hyper.qd_history,
            "search_seconds": search_secs,
        }

    # Pick regime with best elite fitness
    best_regime = max(best_results, key=lambda r: float(best_results[r]["elite"]["objective"]))
    best_elite = best_results[best_regime]["elite"]
    best_sol = best_elite["solution"]
    weights = best_sol[:N_WEIGHTS]
    # Use the scheduler from the best regime to denormalize (has adaptive bounds)
    best_scheduler = RegimeScheduler(
        solution_dim=SOLUTION_DIM, n_weights=N_WEIGHTS,
        param_bounds=adaptive_bounds, median_signal_std=median_std,
    )
    best_params = best_scheduler.denormalize_params(best_sol)
    log.info(f"  Best regime: {best_regime}, fitness={float(best_elite['objective']):.4f}")
    log.info(f"  Params: {best_params}")

    # ── S08: Gates ───────────────────────────────────────────────
    signal = factor_matrix @ weights
    train_result = engine.evaluate(
        signal=signal, close=close_arr, params=best_params,
        regime_labels=train_labels, target_regime_id=best_regime,
        cost_bps=COST_BPS, funding_rate=FUNDING_RATE,
    )

    # Gate 1: PnL robustness
    g1 = Gate1()
    g1_pass = g1.evaluate(train_result)
    log.info(f"  S08 Gate1: {'PASS' if g1_pass else 'FAIL'} "
             f"(trimmed_min={g1.last_trimmed_min:.4f}, sos={g1.last_sos:.4f})")

    # Gate 2: Deflated Sharpe (Fix5: n_trials = num_elites, not cumulative ask count)
    g2 = DeflatedSharpeGate(threshold=0.05)
    n_trials_elites = sum(r["n_elites"] for r in best_results.values())
    g2.increment_trials(n_trials_elites)
    g2_pass = g2.gate(
        observed_sharpe=train_result.sharpe,
        n_observations=train_result.n_active_bars,  # Fix3: use active bars
        n_trials=n_trials_elites,
    )
    log.info(f"  S08 Gate2 (DSR): {'PASS' if g2_pass else 'FAIL'} "
             f"(sharpe={train_result.sharpe:.4f}, dsr={g2.last_dsr:.4f}, "
             f"trials={n_trials_elites}, active_bars={train_result.n_active_bars})")

    # Gate 3: Holdout (use factor_normalizer from train — no lookahead)
    holdout_fm_raw = compute_factor_matrix(holdout).to_numpy()
    if holdout_fm_raw.shape[1] < N_WEIGHTS:
        holdout_fm_raw = np.hstack([holdout_fm_raw,
                                np.zeros((holdout_fm_raw.shape[0], N_WEIGHTS - holdout_fm_raw.shape[1]))])
    elif holdout_fm_raw.shape[1] > N_WEIGHTS:
        holdout_fm_raw = holdout_fm_raw[:, :N_WEIGHTS]

    ho_valid = ~np.any(np.isnan(holdout_fm_raw), axis=1)
    holdout_fm_raw = holdout_fm_raw[ho_valid]
    holdout_filtered = holdout.filter(pl.Series(ho_valid))

    # Normalize holdout factors using train's normalizer (no data leakage)
    ho_df = pl.DataFrame({name: holdout_fm_raw[:, i] for i, name in enumerate(factor_names)})
    holdout_fm = factor_normalizer.transform(ho_df).to_numpy()
    holdout_labels = labeler.label(holdout_filtered)
    holdout_sig = holdout_fm @ weights
    holdout_result = engine.evaluate(
        signal=holdout_sig, close=holdout_filtered["close"].to_numpy(),
        params=best_params, regime_labels=holdout_labels,
        target_regime_id=best_regime, cost_bps=COST_BPS, funding_rate=FUNDING_RATE,
    )
    g3 = HoldoutGate()
    g3_pass, g3_reason = g3.gate(
        holdout_result=holdout_result,
        train_max_dd=train_result.max_drawdown,
        train_trades_per_day=train_result.trades_per_day,
    )
    log.info(f"  S08 Gate3 (holdout): {'PASS' if g3_pass else 'FAIL'} "
             f"(sharpe={holdout_result.sharpe:.4f}, dd={holdout_result.max_drawdown:.4f}) "
             f"reason={g3_reason}")

    all_gates_pass = g1_pass and g2_pass and g3_pass
    status = "PASSED_HOLDOUT" if all_gates_pass else "FAILED_HOLDOUT"
    log.info(f"  GATES: {status}")

    # ── S09: Export card ─────────────────────────────────────────
    labeler.save(out_dir / "regime.pkl")

    card_payload = {
        "version": "3.0",
        "id": card_id,
        "symbol": symbol,
        "regime": {
            "n_states": n_regimes,
            "target_regime": best_regime,
            "distribution": dict(zip(unique_regimes.tolist(), regime_counts.tolist())),
        },
        "warmup_bars": 60,
        "normalization": {
            "method": "robust",
            "feature_cols": feature_cols,
            "factor_medians": factor_normalizer.medians,
            "factor_scales": factor_normalizer.scales,
        },
        "factors": {
            "names": factor_names,
            "weights": weights.tolist(),
        },
        "params": best_params,
        "cost_model": {
            "cost_bps": COST_BPS,
            "funding_rate": FUNDING_RATE,
        },
        "backtest": {
            "windows": [{
                "max_drawdown": train_result.max_drawdown,
                "sharpe": train_result.sharpe,
                "total_return": train_result.total_return,
                "trades_per_day": train_result.trades_per_day,
                "win_rate": train_result.win_rate,
            }],
        },
        "validation": {
            "gate1_pass": g1_pass,
            "gate2_pass": g2_pass,
            "gate2_dsr": g2.last_dsr,
            "gate3_pass": g3_pass,
            "gate3_reason": g3_reason,
            "holdout_sharpe": holdout_result.sharpe,
            "holdout_max_dd": holdout_result.max_drawdown,
        },
        "regime_labeler": "hmm_bic",
        "deployment_hints": {
            "timeframe": "1m",
            "lookback": 60,
            "max_stale_seconds": 120,
        },
        "status": status,
        "search_meta": {
            "generations": CMA_MAE_GENERATIONS,
            "regimes_searched": list(best_results.keys()),
            "total_elites": sum(r["n_elites"] for r in best_results.values()),
        },
    }

    exporter = CardExporter()
    paths = exporter.export(
        output_dir=out_dir,
        card_payload=card_payload,
        regime_model=labeler,
    )
    log.info(f"  S09 card exported: {out_dir}")

    # ── S10: Live replay ─────────────────────────────────────────
    if not all_gates_pass:
        log.info(f"  S10 SKIP live replay: gates did not pass")
        total_secs = time.monotonic() - t0
        return {
            "symbol": symbol, "card_id": card_id, "status": status,
            "train_sharpe": train_result.sharpe, "holdout_sharpe": holdout_result.sharpe,
            "n_regimes": n_regimes, "best_regime": best_regime,
            "elapsed_s": total_secs, "live_replay": "skipped",
        }

    log.info(f"  S10 live replay: {min(LIVE_REPLAY_BARS, len(holdout_filtered))} bars...")
    card_json = json.loads((out_dir / "card.json").read_text())
    journal = LiveJournal(out_dir / "live_journal.parquet")
    monitor = LiveMonitor(log_path=out_dir / "monitor.jsonl")

    from zangetsu_v3.live.risk_manager import RiskLimits
    state = build_live_state(
        card=card_json,
        weights=weights,
        normalizer=normalizer,
        labeler=labeler,
        predictor=OnlineRegimePredictor(debounce=5),
        risk_limits=RiskLimits(),
        max_stale_seconds=120,
        lookback=60,
    )

    replay_n = min(LIVE_REPLAY_BARS, len(holdout_filtered))
    replay_fm = holdout_fm[:replay_n]
    actions = {}
    open_positions: dict = {}

    for i in range(replay_n):
        bar_row = holdout_filtered.slice(i, 1)
        factor_row = replay_fm[i]
        if np.any(np.isnan(factor_row)):
            continue
        open_positions, result = on_new_bar(
            symbol=symbol,
            bar_df=bar_row,
            factor_row=factor_row,
            state=state,
            open_positions=open_positions,
            journal=journal,
            monitor=monitor,
        )
        action = result.get("action", "unknown")
        actions[action] = actions.get(action, 0) + 1

    journal_df = journal.read()
    log.info(f"  S10 replay done: {replay_n} bars, actions={actions}, "
             f"journal_trades={len(journal_df)}")

    total_secs = time.monotonic() - t0
    log.info(f"  Total time: {total_secs:.1f}s")

    return {
        "symbol": symbol, "card_id": card_id, "status": status,
        "train_sharpe": train_result.sharpe, "holdout_sharpe": holdout_result.sharpe,
        "n_regimes": n_regimes, "best_regime": best_regime,
        "elapsed_s": total_secs,
        "live_replay": {"bars": replay_n, "actions": actions, "trades": len(journal_df)},
    }


# ── main ─────────────────────────────────────────────────────────
def main():
    log.info("Zangetsu V3 — Production Pipeline")
    log.info(f"Symbols: {SYMBOLS}")
    log.info(f"Training: {TRAINING_MONTHS}mo, Embargo: {EMBARGO_DAYS}d, Holdout: {HOLDOUT_MONTHS}mo")
    log.info(f"Search: {CMA_MAE_GENERATIONS} gen, {SEARCH_THREADS} threads")
    log.info(f"Timeframe: 1m (raw)")
    log.info("")

    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)

    results = []
    for sym in SYMBOLS:
        try:
            r = run_symbol(sym)
            results.append(r)
        except Exception as e:
            log.error(f"FAILED {sym}: {e}", exc_info=True)
            results.append({"symbol": sym, "status": "ERROR", "error": str(e)})

    # ── Summary ──────────────────────────────────────────────────
    log.info("")
    log.info("=" * 70)
    log.info("PRODUCTION PIPELINE SUMMARY")
    log.info("=" * 70)
    for r in results:
        sym = r["symbol"]
        st = r["status"]
        if st in ("PASSED_HOLDOUT", "FAILED_HOLDOUT"):
            log.info(f"  {sym:12s} {st:18s} train_sharpe={r['train_sharpe']:.4f} "
                     f"holdout_sharpe={r['holdout_sharpe']:.4f} "
                     f"regimes={r['n_regimes']} best={r['best_regime']} "
                     f"time={r['elapsed_s']:.0f}s")
        else:
            log.info(f"  {sym:12s} {st:18s} {r.get('reason', r.get('error', ''))}")

    # Save summary
    summary_path = OUTPUT_BASE / f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M')}.json"
    with summary_path.open("w") as f:
        json.dump(results, f, indent=2, default=str)
    log.info(f"\nSummary saved: {summary_path}")

    passed = [r for r in results if r["status"] == "PASSED_HOLDOUT"]
    log.info(f"\n{len(passed)}/{len(SYMBOLS)} strategies passed all gates")


if __name__ == "__main__":
    main()
