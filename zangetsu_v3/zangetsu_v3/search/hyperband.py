"""V3.1 Zero-Config Pipeline (C16): Rung-1 prescreen → Rung0 single-segment → natural gap → Rung1 all-segments → tell-all."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Tuple

import numpy as np
from joblib import Parallel, delayed

from .backtest import HFTBacktest


def _decode_params(solution: np.ndarray, n_weights: int, pb: np.ndarray) -> dict:
    """Denormalize [0,1] params with hard clamp (C09, C50)."""
    raw = solution[n_weights:]
    entry = float(np.clip(pb[0, 0] + np.clip(raw[0], 0, 1) * (pb[0, 1] - pb[0, 0]), pb[0, 0], pb[0, 1]))
    exit_ = float(np.clip(pb[1, 0] + np.clip(raw[1], 0, 1) * (pb[1, 1] - pb[1, 0]), pb[1, 0], pb[1, 1]))
    exit_ = float(np.clip(exit_, pb[1, 0], min(entry * 0.8, pb[1, 1])))
    stop = float(np.clip(pb[2, 0] + np.clip(raw[2], 0, 1) * (pb[2, 1] - pb[2, 0]), 0.5, 5.0))
    pf = float(np.clip(pb[3, 0] + np.clip(raw[3], 0, 1) * (pb[3, 1] - pb[3, 0]), 0.01, 0.25))
    hm = int(np.clip(pb[4, 0] + np.clip(raw[4], 0, 1) * (pb[4, 1] - pb[4, 0]), 3, 30))
    return {"entry_thr": entry, "exit_thr": exit_, "stop_mult": stop, "pos_frac": pf, "hold_max": hm}


def _eval_single_segment(solution: np.ndarray, seg: dict, n_weights: int, pb: np.ndarray) -> dict:
    """Rung 0: evaluate one candidate on one segment. Returns result dict."""
    engine = HFTBacktest()
    weights = solution[:n_weights]
    params = _decode_params(solution, n_weights, pb)
    signal = seg["factor_matrix"] @ weights
    result = engine.evaluate(signal, seg["close"], params, seg["cost_bps"], seg["funding_rate"])
    return {
        "hft_fitness": result.hft_fitness,
        "sharpe": result.sharpe,
        "win_rate": result.win_rate,
        "tpd": result.trades_per_day,
    }


def _eval_all_segments(solution: np.ndarray, segments: list[dict], n_weights: int, pb: np.ndarray) -> dict:
    """Rung 1: evaluate one candidate on ALL segments. Returns trimmed-min result."""
    engine = HFTBacktest()
    weights = solution[:n_weights]
    params = _decode_params(solution, n_weights, pb)

    seg_fitnesses = []
    seg_sharpes = []
    for seg in segments:
        signal = seg["factor_matrix"] @ weights
        result = engine.evaluate(signal, seg["close"], params, seg["cost_bps"], seg["funding_rate"])
        seg_fitnesses.append(result.hft_fitness)
        seg_sharpes.append(result.sharpe)

    arr = np.array(seg_fitnesses)
    if len(arr) <= 1:
        trimmed_min = float(arr[0]) if len(arr) > 0 else -999.0
    else:
        sorted_f = np.sort(arr)
        trimmed_min = float(sorted_f[1])  # drop worst 1

    if trimmed_min <= 0:
        trimmed_min = -999.0

    return {
        "trimmed_min": trimmed_min,
        "avg_sharpe": float(np.mean(seg_sharpes)),
        "seg_fitnesses": seg_fitnesses,
    }


def _natural_gap_cutoff(scores: np.ndarray, min_cutoff: int = 3) -> np.ndarray:
    """C14: promote top candidates above natural gap in sorted fitness."""
    if len(scores) <= min_cutoff:
        return np.ones(len(scores), dtype=bool)
    order = np.argsort(scores)[::-1]
    sorted_s = scores[order]
    gaps = np.diff(sorted_s)
    gap_idx = int(np.argmin(gaps))
    cutoff = max(gap_idx + 1, min_cutoff)
    mask = np.zeros(len(scores), dtype=bool)
    mask[order[:cutoff]] = True
    return mask


@dataclass
class ZeroConfigPipeline:
    """C16: Rung-1 → Rung0 (1 segment) → natural gap → Rung1 (all segments) → tell-all."""
    scheduler: object
    segments: list[dict]        # all TRAIN segments for this regime
    n_weights: int
    param_bounds: np.ndarray
    n_jobs: int = 2
    qd_history: List[float] = field(default_factory=list)
    rung0_survive_count: int = 0
    rung1_promote_count: int = 0

    def run(self, generations: int) -> None:
        rng = np.random.default_rng(42)
        n_segs = len(self.segments)
        pb = self.param_bounds
        nw = self.n_weights

        for gen in range(generations):
            sols = self.scheduler.ask()
            n_candidates = len(sols)

            # ── Rung 0: random 1 segment per candidate ──────────
            seg_indices = rng.integers(0, n_segs, size=n_candidates)
            r0_results = Parallel(n_jobs=self.n_jobs, backend="loky")(
                delayed(_eval_single_segment)(sols[i], self.segments[seg_indices[i]], nw, pb)
                for i in range(n_candidates)
            )

            # Rung 0 survival: hft_fitness > -999 (i.e. tpd>=20 + wr>=0.52 + sharpe>0 on 1 segment)
            r0_scores = np.array([r["hft_fitness"] for r in r0_results])
            survive_mask = r0_scores > -999.0
            n_survive = int(survive_mask.sum())
            self.rung0_survive_count += n_survive

            if n_survive == 0:
                # Nobody survived Rung 0 — tell all with their Rung 0 scores
                objs = r0_scores.tolist()
                meas = [np.array([r["sharpe"], r["hft_fitness"]]) for r in r0_results]
                self.scheduler.tell(objs, meas)
                stats = self.scheduler.result_archive.stats
                self.qd_history.append(float(stats.qd_score))
                continue

            # ── Natural gap cutoff on Rung 0 survivors ──────────
            survivor_indices = np.where(survive_mask)[0]
            survivor_scores = r0_scores[survivor_indices]
            promote_mask = _natural_gap_cutoff(survivor_scores, min_cutoff=3)
            promoted_indices = survivor_indices[promote_mask]
            self.rung1_promote_count += len(promoted_indices)

            # ── Rung 1: promoted candidates on ALL segments ─────
            r1_results = {}
            if len(promoted_indices) > 0:
                r1_list = Parallel(n_jobs=self.n_jobs, backend="loky")(
                    delayed(_eval_all_segments)(sols[i], self.segments, nw, pb)
                    for i in promoted_indices
                )
                for idx, r1 in zip(promoted_indices, r1_list):
                    r1_results[idx] = r1

            # ── Tell ALL candidates (C14) ───────────────────────
            objs = []
            meas_list = []
            for i in range(n_candidates):
                if i in r1_results:
                    # Use Rung 1 trimmed-min as fitness
                    r1 = r1_results[i]
                    objs.append(r1["trimmed_min"])
                    meas_list.append(np.array([r1["avg_sharpe"], r1["trimmed_min"]]))
                else:
                    # Didn't make it to Rung 1 — use Rung 0 score
                    objs.append(float(r0_scores[i]))
                    meas_list.append(np.array([r0_results[i]["sharpe"], float(r0_scores[i])]))

            self.scheduler.tell(objs, meas_list)
            stats = self.scheduler.result_archive.stats
            self.qd_history.append(float(stats.qd_score))


__all__ = ["ZeroConfigPipeline", "_natural_gap_cutoff", "_decode_params"]
