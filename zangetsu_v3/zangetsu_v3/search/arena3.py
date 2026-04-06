"""Arena 3 CMA-MAE search engine — fully concurrent generation loop (V3.2 §9).

Performance target: <2s per generation with 36 candidates on i7-12700K.

Generation loop:
  Step 1: scheduler.ask() → N candidates
  Step 2: Hard clamp parameters (σ-relative entry/exit, absolute stop/pos/hold)
  Step 3: Batch signal computation — ONE matrix multiply
  Step 4: Vectorized Rung -1 prescreen (analytical predicted_sharpe)
  Step 5: Parallel Rung 0 — ThreadPoolExecutor(20), 1 random TRAIN segment each
  Step 6: Natural gap cutoff on Rung 0 fitness
  Step 7: Parallel Rung 1 — all promoted candidates, sequential over segments, early kill
  Step 8: Fitness = trimmed_min × min(SoS, 2.0) with 3-layer SoS
  Step 9: tell + persist to DB (search_candidates + search_progress)
"""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
import psycopg2
import psycopg2.extras

from .backtest import HFTBacktest, backtest_hft, hft_fitness, _active_time_sharpe
from .prescreen import vectorized_prescreen
from .scheduler import RegimeScheduler

__all__ = ["Arena3Runner", "SYMBOL_COST_BPS"]

logger = logging.getLogger(__name__)

# Per-symbol real trading cost in bps (V3.2 spec)
SYMBOL_COST_BPS: dict[str, float] = {
    "BTC": 4.0,
    "ETH": 4.0,
    "BNB": 5.0,
    "SOL": 6.0,
    "XRP": 7.0,
    "DOGE": 8.0,
}


def _hard_clamp_params(
    raw_params: np.ndarray,
    sigma: float,
    n_weights: int,
) -> dict:
    """Hard clamp parameters per V3.2 spec (Step 2).

    entry [0.3σ, 1.5σ], exit [0.05σ, 0.8σ] then min(exit, entry×0.8)
    stop [0.5, 5], pos [0.01, 0.25], hold [3, 480] int
    """
    raw = raw_params[n_weights:]
    s = max(sigma, 1e-8)

    entry = float(np.clip(raw[0], 0.3 * s, 1.5 * s))
    exit_ = float(np.clip(raw[1], 0.05 * s, 0.8 * s))
    exit_ = min(exit_, entry * 0.8)
    stop = float(np.clip(raw[2], 0.5, 5.0))
    pos = float(np.clip(raw[3], 0.01, 0.25))
    hold = int(np.clip(round(raw[4]), 3, 480))

    return {
        "entry_thr": entry,
        "exit_thr": exit_,
        "stop_mult": stop,
        "pos_frac": pos,
        "hold_max": hold,
    }


def _natural_gap_cutoff(scores: np.ndarray, min_promote: int = 3) -> np.ndarray:
    """Find largest gap in sorted Rung 0 fitness, promote top group (min 3).

    Returns indices into the original scores array for the promoted group.
    """
    if len(scores) <= min_promote:
        return np.arange(len(scores))

    order = np.argsort(scores)[::-1]  # descending
    sorted_s = scores[order]
    gaps = -np.diff(sorted_s)  # positive = drop in fitness

    # Largest gap position
    gap_idx = int(np.argmax(gaps))
    cutoff = max(gap_idx + 1, min_promote)

    return order[:cutoff]


def _compute_sos_3layer(seg_results: list[dict]) -> float:
    """3-layer Stability of Sharpe (Q10).

    Layer 1: fraction of segments with sharpe > 0
    Layer 2: coefficient of variation of positive sharpes (inverted)
    Layer 3: worst-to-median ratio of positive sharpes
    SoS = L1 * L2 * L3
    """
    if not seg_results:
        return 0.0

    sharpes = np.array([r["sharpe"] for r in seg_results])
    positive = sharpes[sharpes > 0]

    # Layer 1: fraction positive
    l1 = len(positive) / len(sharpes) if len(sharpes) > 0 else 0.0
    if l1 == 0 or len(positive) < 2:
        return 0.0

    # Layer 2: inverted CV = mean/std (higher = more stable)
    mean_p = float(np.mean(positive))
    std_p = float(np.std(positive))
    l2 = min(mean_p / (std_p + 1e-8), 5.0) / 5.0  # normalize to [0, 1]

    # Layer 3: worst-to-median ratio
    worst = float(np.min(positive))
    median = float(np.median(positive))
    l3 = worst / (median + 1e-8) if median > 0 else 0.0
    l3 = min(l3, 1.0)

    return float(l1 * l2 * l3)


def _backtest_single_segment(
    weights: np.ndarray,
    params: dict,
    signal: np.ndarray,
    close: np.ndarray,
    cost_bps: float,
    funding_rate: float,
) -> dict:
    """Run backtest on one segment. Thread-safe (no shared mutable state)."""
    pnl, pos, holds = backtest_hft(
        signal,
        close,
        float(params["entry_thr"]),
        float(params["exit_thr"]),
        float(params["stop_mult"]),
        float(params["pos_frac"]),
        int(params["hold_max"]),
        float(cost_bps),
        float(funding_rate),
    )

    total_bars = len(pnl)
    fitness = hft_fitness(pnl, total_bars)
    sharpe = _active_time_sharpe(pnl)

    active_pnl = pnl[pnl != 0]
    n_active = len(active_pnl)
    win_rate = float(np.mean(active_pnl > 0)) if n_active > 0 else 0.0

    # Trades per day
    active_mask = (pnl != 0).astype(np.int8)
    entries = int(np.sum(np.diff(active_mask) == 1))
    if len(pnl) > 0 and pnl[0] != 0:
        entries += 1
    n_days = max(total_bars / 1440.0, 1e-6)
    tpd = entries / n_days

    # Max drawdown
    cum = np.nancumsum(pnl)
    running_max = np.maximum.accumulate(cum)
    dd = running_max - cum
    max_dd = float(np.nanmax(dd)) if dd.size else 0.0

    # Average hold bars
    exits = np.where(np.diff(active_mask) == -1)[0]
    avg_hold = float(np.mean(holds[exits])) if len(exits) > 0 else 0.0

    return {
        "fitness": fitness,
        "sharpe": sharpe,
        "win_rate": win_rate,
        "tpd": tpd,
        "max_dd": max_dd,
        "hold_bars_avg": avg_hold,
    }


def _rung1_candidate(
    candidate_idx: int,
    weights: np.ndarray,
    params: dict,
    segments: list[dict],
    signal_batch_col: np.ndarray,
    seg_boundaries: list[int],
    seg_lengths: list[int],
    rung0_seg_idx: int,
    rung0_result: dict,
    rng_seed: int,
) -> tuple[int, dict]:
    """Rung 1: evaluate one candidate across ALL segments with early kill.

    Reuses Rung 0 result (Q09). Shuffles segment order (Q07).
    Early kill: every 5 segments, if fail_count >= 3, return -999.
    """
    n_segs = len(segments)
    rng = np.random.default_rng(rng_seed)
    seg_order = rng.permutation(n_segs)

    seg_results = [None] * n_segs
    fail_count = 0

    for eval_count, seg_i in enumerate(seg_order):
        if seg_i == rung0_seg_idx:
            # Reuse Rung 0 result (Q09)
            seg_results[seg_i] = rung0_result
            if rung0_result["fitness"] <= -999.0:
                fail_count += 1
        else:
            seg = segments[seg_i]
            start = seg_boundaries[seg_i]
            length = seg_lengths[seg_i]
            signal = signal_batch_col[start:start + length]

            result = _backtest_single_segment(
                weights, params, signal, seg["close"],
                seg["cost_bps"], seg.get("funding_rate", 0.0),
            )
            seg_results[seg_i] = result
            if result["fitness"] <= -999.0:
                fail_count += 1

        # Early kill check: every 5 segments
        if (eval_count + 1) % 5 == 0 and fail_count >= 3:
            # Fill remaining with -999
            for remaining_i in seg_order[eval_count + 1:]:
                seg_results[remaining_i] = {
                    "fitness": -999.0, "sharpe": 0.0, "win_rate": 0.0,
                    "tpd": 0.0, "max_dd": 0.0, "hold_bars_avg": 0.0,
                }
            break

    # Compute trimmed_min: drop worst 1
    fitnesses = np.array([r["fitness"] for r in seg_results])
    if len(fitnesses) <= 1:
        trimmed_min = float(fitnesses[0]) if len(fitnesses) > 0 else -999.0
    else:
        sorted_f = np.sort(fitnesses)
        trimmed_min = float(sorted_f[1])  # drop worst 1

    if trimmed_min <= 0:
        trimmed_min = -999.0

    # SoS (3-layer, Q10)
    sos = _compute_sos_3layer(seg_results)

    # Adjusted fitness = trimmed_min × min(SoS, 2.0)
    adjusted = trimmed_min * min(sos, 2.0) if trimmed_min > 0 else trimmed_min

    # Measures for GridArchive (Q08): [median_tpd, median_max_dd]
    tpds = [r["tpd"] for r in seg_results if r["fitness"] > -999.0]
    max_dds = [r["max_dd"] for r in seg_results if r["fitness"] > -999.0]
    sharpes = [r["sharpe"] for r in seg_results if r["fitness"] > -999.0]
    win_rates = [r["win_rate"] for r in seg_results if r["fitness"] > -999.0]
    hold_bars_list = [r["hold_bars_avg"] for r in seg_results if r["fitness"] > -999.0]

    median_tpd = float(np.median(tpds)) if tpds else 0.0
    median_max_dd = float(np.median(max_dds)) if max_dds else 0.0
    median_sharpe = float(np.median(sharpes)) if sharpes else 0.0
    median_win_rate = float(np.median(win_rates)) if win_rates else 0.0
    median_hold = float(np.median(hold_bars_list)) if hold_bars_list else 0.0

    return candidate_idx, {
        "trimmed_min": trimmed_min,
        "sos": sos,
        "adjusted_fitness": adjusted,
        "median_tpd": median_tpd,
        "median_max_dd": median_max_dd,
        "median_sharpe": median_sharpe,
        "median_win_rate": median_win_rate,
        "median_hold_bars": median_hold,
        "seg_results": seg_results,
    }


@dataclass
class Arena3Runner:
    """Fully concurrent Arena 3 CMA-MAE search engine.

    Parameters
    ----------
    regime : str
        Regime identifier (e.g. "bull_high_vol").
    factor_matrix : np.ndarray
        Shape (total_bars, n_factors). Concatenated factor values for all
        TRAIN segments, in segment order.
    segments : list[dict]
        Each dict has keys: close (np.ndarray), cost_bps (float),
        funding_rate (float), symbol (str), n_bars (int).
        factor_matrix rows correspond to concatenated segments.
    seg_boundaries : list[int]
        Start index of each segment in factor_matrix.
    factor_mu : np.ndarray
        Mean return per factor, shape (n_factors,).
    factor_cov : np.ndarray
        Covariance matrix, shape (n_factors, n_factors).
    median_signal_std : float
        From SignalScaleEstimator.
    db_dsn : str
        PostgreSQL connection string.
    pool_version : datetime
        Factor pool version timestamp.
    n_candidates : int
        Candidates per generation (default 36).
    max_workers : int
        ThreadPoolExecutor size (default 20).
    """

    regime: str
    factor_matrix: np.ndarray
    segments: list[dict]
    seg_boundaries: list[int]
    factor_mu: np.ndarray
    factor_cov: np.ndarray
    median_signal_std: float
    db_dsn: str
    pool_version: Optional[datetime] = None
    n_candidates: int = 36
    max_workers: int = 20
    measure_bounds: tuple = ((-5.0, 5.0), (0.0, 0.5))

    # Internal state
    _scheduler: Optional[RegimeScheduler] = field(default=None, init=False, repr=False)
    _n_weights: int = field(default=0, init=False)
    _n_factors: int = field(default=0, init=False)
    _seg_lengths: list[int] = field(default_factory=list, init=False)

    def __post_init__(self):
        self._n_factors = self.factor_matrix.shape[1]
        self._n_weights = self._n_factors
        # solution_dim = n_weights + 5 params (entry, exit, stop, pos, hold)
        solution_dim = self._n_weights + 5

        self._scheduler = RegimeScheduler(
            solution_dim=solution_dim,
            n_weights=self._n_weights,
            measure_bounds=self.measure_bounds,
            median_signal_std=self.median_signal_std,
        )

        # Precompute segment lengths from boundaries
        self._seg_lengths = []
        for i, start in enumerate(self.seg_boundaries):
            if i + 1 < len(self.seg_boundaries):
                length = self.seg_boundaries[i + 1] - start
            else:
                length = self.factor_matrix.shape[0] - start
            self._seg_lengths.append(length)

    def run(self, generations: int, seed: int = 42) -> dict:
        """Run the full Arena 3 search loop.

        Returns dict with final archive stats.
        """
        rng = np.random.default_rng(seed)
        n_segs = len(self.segments)
        total_elapsed = 0.0

        # Get DB connection (one per run, not per generation)
        conn = None
        try:
            conn = psycopg2.connect(self.db_dsn)
            conn.autocommit = False
        except Exception as e:
            logger.error("DB connection failed: %s — running without persistence", e)
            conn = None

        try:
            for gen in range(generations):
                t0 = time.monotonic()

                gen_result = self._run_generation(gen, rng, n_segs, conn)

                elapsed = time.monotonic() - t0
                total_elapsed += elapsed

                stats = self._scheduler.result_archive.stats
                logger.info(
                    "Arena3 [%s] gen=%d elapsed=%.3fs qd=%.2f elites=%d best=%.4f "
                    "r0_survive=%d r1_promote=%d",
                    self.regime, gen, elapsed,
                    stats.qd_score, stats.num_elites, stats.obj_max,
                    gen_result["rung0_survivors"],
                    gen_result["rung1_promoted"],
                )

        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

        stats = self._scheduler.result_archive.stats
        return {
            "regime": self.regime,
            "generations": generations,
            "total_elapsed": total_elapsed,
            "avg_gen_time": total_elapsed / max(generations, 1),
            "qd_score": float(stats.qd_score),
            "num_elites": int(stats.num_elites),
            "best_fitness": float(stats.obj_max),
            "coverage": float(stats.coverage),
        }

    def _run_generation(
        self,
        gen: int,
        rng: np.random.Generator,
        n_segs: int,
        conn: Optional[Any],
    ) -> dict:
        """Execute one generation — Steps 1-9."""

        # ── Step 1: ask() → N candidates ──
        solutions = self._scheduler.ask()
        n_actual = len(solutions)
        solutions_arr = np.array(solutions)  # (N, solution_dim)

        # ── Step 2: Hard clamp parameters ──
        sigma = self.median_signal_std
        all_params = []
        for sol in solutions:
            all_params.append(_hard_clamp_params(sol, sigma, self._n_weights))

        # ── Step 3: Batch signal computation — ONE matrix multiply ──
        weights_batch = solutions_arr[:, :self._n_weights]  # (N, n_factors)
        signal_batch = self.factor_matrix @ weights_batch.T  # (total_bars, N)

        # ── Step 4: Vectorized Rung -1 prescreen ──
        survivor_mask = vectorized_prescreen(
            weights_batch, self.factor_mu, self.factor_cov,
        )
        survivor_indices = np.where(survivor_mask)[0]

        if len(survivor_indices) == 0:
            # Nobody passes prescreen — tell all with -999
            objectives = [-999.0] * n_actual
            measures = [np.array([0.0, 0.0])] * n_actual
            self._scheduler.tell(objectives, measures)
            self._persist_generation(gen, solutions, all_params, objectives,
                                     measures, n_actual, conn,
                                     rung0_survivors=0, rung1_promoted=0,
                                     candidate_details=[None] * n_actual)
            return {"rung0_survivors": 0, "rung1_promoted": 0}

        # ── Step 5: Parallel Rung 0 — 1 random TRAIN segment each ──
        rung0_seg_indices = rng.integers(0, n_segs, size=len(survivor_indices))
        rung0_results: dict[int, dict] = {}
        rung0_seg_map: dict[int, int] = {}  # candidate_idx → seg_idx used

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {}
            for local_i, cand_idx in enumerate(survivor_indices):
                seg_i = int(rung0_seg_indices[local_i])
                seg = self.segments[seg_i]
                start = self.seg_boundaries[seg_i]
                length = self._seg_lengths[seg_i]
                signal = signal_batch[start:start + length, cand_idx]

                rung0_seg_map[cand_idx] = seg_i
                fut = pool.submit(
                    _backtest_single_segment,
                    weights_batch[cand_idx],
                    all_params[cand_idx],
                    signal,
                    seg["close"],
                    seg["cost_bps"],
                    seg.get("funding_rate", 0.0),
                )
                futures[fut] = cand_idx

            for fut in as_completed(futures):
                cand_idx = futures[fut]
                try:
                    rung0_results[cand_idx] = fut.result()
                except Exception as e:
                    logger.warning("Rung 0 backtest failed for candidate %d: %s", cand_idx, e)
                    rung0_results[cand_idx] = {
                        "fitness": -999.0, "sharpe": 0.0, "win_rate": 0.0,
                        "tpd": 0.0, "max_dd": 0.0, "hold_bars_avg": 0.0,
                    }

        # Rung 0 survival: fitness > -999
        rung0_scores = np.array([
            rung0_results[idx]["fitness"] for idx in survivor_indices
        ])
        rung0_survive_mask = rung0_scores > -999.0
        rung0_survivor_local = np.where(rung0_survive_mask)[0]
        rung0_survivor_global = survivor_indices[rung0_survivor_local]
        n_rung0_survive = len(rung0_survivor_global)

        if n_rung0_survive == 0:
            # Nobody survived Rung 0 — tell all with their scores
            objectives, measures, candidate_details = self._build_tell_data(
                n_actual, survivor_indices, rung0_results, {}, all_params,
            )
            self._scheduler.tell(objectives, measures)
            self._persist_generation(gen, solutions, all_params, objectives,
                                     measures, n_actual, conn,
                                     rung0_survivors=0, rung1_promoted=0,
                                     candidate_details=candidate_details)
            return {"rung0_survivors": 0, "rung1_promoted": 0}

        # ── Step 6: Natural gap cutoff ──
        survivor_r0_scores = np.array([
            rung0_results[idx]["fitness"] for idx in rung0_survivor_global
        ])
        promoted_local = _natural_gap_cutoff(survivor_r0_scores, min_promote=3)
        promoted_global = rung0_survivor_global[promoted_local]
        n_promoted = len(promoted_global)

        # ── Step 7: Parallel Rung 1 ──
        rung1_results: dict[int, dict] = {}

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {}
            for cand_idx in promoted_global:
                seed_val = int(rng.integers(0, 2**31))
                fut = pool.submit(
                    _rung1_candidate,
                    int(cand_idx),
                    weights_batch[cand_idx],
                    all_params[cand_idx],
                    self.segments,
                    signal_batch[:, cand_idx],
                    self.seg_boundaries,
                    self._seg_lengths,
                    rung0_seg_map[cand_idx],
                    rung0_results[cand_idx],
                    seed_val,
                )
                futures[fut] = cand_idx

            for fut in as_completed(futures):
                cand_idx = futures[fut]
                try:
                    _, result = fut.result()
                    rung1_results[cand_idx] = result
                except Exception as e:
                    logger.warning("Rung 1 failed for candidate %d: %s", cand_idx, e)
                    rung1_results[cand_idx] = {
                        "trimmed_min": -999.0, "sos": 0.0,
                        "adjusted_fitness": -999.0,
                        "median_tpd": 0.0, "median_max_dd": 0.0,
                        "median_sharpe": 0.0, "median_win_rate": 0.0,
                        "median_hold_bars": 0.0, "seg_results": [],
                    }

        # ── Step 8: Build objectives + measures for ALL candidates ──
        objectives, measures, candidate_details = self._build_tell_data(
            n_actual, survivor_indices, rung0_results, rung1_results, all_params,
        )

        # ── Step 9: tell + persist ──
        self._scheduler.tell(objectives, measures)
        self._persist_generation(
            gen, solutions, all_params, objectives, measures,
            n_actual, conn,
            rung0_survivors=n_rung0_survive,
            rung1_promoted=n_promoted,
            candidate_details=candidate_details,
        )

        return {
            "rung0_survivors": n_rung0_survive,
            "rung1_promoted": n_promoted,
        }

    def _build_tell_data(
        self,
        n_actual: int,
        prescreen_survivors: np.ndarray,
        rung0_results: dict[int, dict],
        rung1_results: dict[int, dict],
        all_params: list[dict],
    ) -> tuple[list[float], list[np.ndarray], list[Optional[dict]]]:
        """Build objectives and measures for tell().

        Returns (objectives, measures, candidate_details).
        All N candidates get a value — filtered ones get -999.
        """
        objectives = []
        measures = []
        candidate_details: list[Optional[dict]] = []

        prescreen_set = set(prescreen_survivors.tolist())

        for i in range(n_actual):
            if i in rung1_results:
                r1 = rung1_results[i]
                objectives.append(r1["adjusted_fitness"])
                measures.append(np.array([
                    r1["median_tpd"],
                    r1["median_max_dd"],
                ]))
                candidate_details.append({
                    "rung": 1,
                    "survived_rung0": True,
                    "trimmed_min": r1["trimmed_min"],
                    "sos": r1["sos"],
                    "adjusted_fitness": r1["adjusted_fitness"],
                    "median_sharpe": r1["median_sharpe"],
                    "median_win_rate": r1["median_win_rate"],
                    "median_tpd": r1["median_tpd"],
                    "median_max_dd": r1["median_max_dd"],
                    "median_hold_bars": r1["median_hold_bars"],
                    "seg_results": r1.get("seg_results"),
                })
            elif i in rung0_results:
                r0 = rung0_results[i]
                objectives.append(r0["fitness"])
                measures.append(np.array([
                    r0["tpd"],
                    r0["max_dd"],
                ]))
                candidate_details.append({
                    "rung": 0,
                    "survived_rung0": r0["fitness"] > -999.0,
                    "trimmed_min": None,
                    "sos": None,
                    "adjusted_fitness": None,
                    "median_sharpe": r0["sharpe"],
                    "median_win_rate": r0["win_rate"],
                    "median_tpd": r0["tpd"],
                    "median_max_dd": r0["max_dd"],
                    "median_hold_bars": r0["hold_bars_avg"],
                    "seg_results": None,
                })
            else:
                # Failed prescreen (Rung -1)
                objectives.append(-999.0)
                measures.append(np.array([0.0, 0.0]))
                candidate_details.append({
                    "rung": -1,
                    "survived_rung0": False,
                    "trimmed_min": None,
                    "sos": None,
                    "adjusted_fitness": None,
                    "median_sharpe": None,
                    "median_win_rate": None,
                    "median_tpd": None,
                    "median_max_dd": None,
                    "median_hold_bars": None,
                    "seg_results": None,
                })

        return objectives, measures, candidate_details

    def _persist_generation(
        self,
        gen: int,
        solutions: list[np.ndarray],
        all_params: list[dict],
        objectives: list[float],
        measures: list[np.ndarray],
        n_actual: int,
        conn: Optional[Any],
        rung0_survivors: int,
        rung1_promoted: int,
        candidate_details: list[Optional[dict]],
    ) -> None:
        """Persist to search_candidates + search_progress (Step 9)."""
        if conn is None:
            return

        try:
            with conn.cursor() as cur:
                # Build candidate rows
                rows = []
                for i in range(n_actual):
                    det = candidate_details[i] if candidate_details[i] else {}
                    weights_list = solutions[i][:self._n_weights].tolist()

                    # Serialize per_segment_results without full numpy arrays
                    seg_res_json = None
                    if det.get("seg_results"):
                        seg_res_json = json.dumps([
                            {k: v for k, v in r.items() if k != "pnl"}
                            for r in det["seg_results"]
                        ])

                    rows.append((
                        self.regime,
                        gen,
                        self.pool_version,
                        json.dumps(weights_list),
                        json.dumps(all_params[i]),
                        seg_res_json,
                        det.get("trimmed_min"),
                        det.get("sos"),
                        det.get("adjusted_fitness"),
                        det.get("median_sharpe"),
                        det.get("median_win_rate"),
                        det.get("median_tpd"),
                        det.get("median_max_dd"),
                        det.get("median_hold_bars"),
                        det.get("rung"),
                        det.get("survived_rung0", False),
                        False,  # is_elite — updated later
                    ))

                psycopg2.extras.execute_values(
                    cur,
                    """INSERT INTO search_candidates
                       (regime, generation, pool_version, weights_json, params_json,
                        per_segment_results_json, trimmed_min_fitness, sos,
                        adjusted_fitness, median_sharpe, median_win_rate,
                        median_tpd, median_max_dd, median_hold_bars,
                        rung, survived_rung0, is_elite)
                       VALUES %s""",
                    rows,
                    template="(%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,"
                             "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    page_size=100,
                )

                # search_progress
                stats = self._scheduler.result_archive.stats
                cur.execute(
                    """INSERT INTO search_progress
                       (regime, generation, pool_version, qd_score, coverage,
                        num_elites, best_fitness, rung0_survival_rate)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        self.regime,
                        gen,
                        self.pool_version,
                        float(stats.qd_score),
                        float(stats.coverage),
                        int(stats.num_elites),
                        float(stats.obj_max),
                        rung0_survivors / max(n_actual, 1),
                    ),
                )

            conn.commit()
        except Exception as e:
            logger.error("DB persist failed for gen %d: %s", gen, e)
            try:
                conn.rollback()
            except Exception:
                pass

    @property
    def result_archive(self):
        return self._scheduler.result_archive
