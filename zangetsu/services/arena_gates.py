"""Arena gate functions (A2 / A3 / A4).

Pure, side-effect-free functions. Each takes a trade list for the
relevant holdout segment(s) and returns a `GateResult` with the pass
verdict plus the numbers that produced it. The orchestrators and the
legacy rescan script both call these — there is exactly one definition
of every gate in the codebase.

Design anchor: j13 explicit requirement (2026-04-20)
    "我要訓練的冠軍是要確保在真實的狀況之下可以有穩定的
     pnl/勝率/交易次數"

A2 — coarse OOS PnL gate (holdout first 1/3).
A3 — time-segment stability gate (holdout middle 1/3, 5 segments).
A4 — market-regime stability gate (holdout last 1/3, regime-tagged).
A1 fitness lives in engine/components/alpha_engine.py._evaluate.
A5 (14-day live paper-trade shadow) runs in its own shadow service,
not here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

import numpy as np

from zangetsu.services.holdout_splits import split_into_segments
from zangetsu.services.regime_tagger import Regime, tag_regime


@dataclass(frozen=True)
class Trade:
    pnl: float
    entry_idx: int
    exit_idx: int


@dataclass(frozen=True)
class GateResult:
    passed: bool
    reason: str
    metrics: dict = field(default_factory=dict)


# --------------------------------------------------------------------- A2

A2_MIN_TRADES: int = 25


def arena2_pass(trades: Sequence[Trade]) -> GateResult:
    """A2: require enough trades AND positive total PnL on holdout 1/3."""
    n = len(trades)
    if n < A2_MIN_TRADES:
        return GateResult(False, "too_few_trades", {"trades": n, "min": A2_MIN_TRADES})
    total_pnl = float(sum(t.pnl for t in trades))
    if total_pnl <= 0:
        return GateResult(False, "non_positive_pnl", {"trades": n, "total_pnl": total_pnl})
    return GateResult(True, "ok", {"trades": n, "total_pnl": total_pnl})


# --------------------------------------------------------------------- A3

A3_SEGMENTS: int = 5
A3_MIN_TRADES_PER_SEGMENT: int = 15
A3_MIN_WR_PASSES: int = 4
A3_MIN_PNL_PASSES: int = 4
A3_WR_FLOOR: float = 0.45


def arena3_pass(trades_per_segment: Sequence[Sequence[Trade]]) -> GateResult:
    """A3: 5 segments of the middle third; ≥4 pass WR>0.45 AND ≥4 pass PnL>0."""
    if len(trades_per_segment) != A3_SEGMENTS:
        return GateResult(False, "wrong_segment_count",
                          {"got": len(trades_per_segment), "expected": A3_SEGMENTS})

    valid = 0
    wr_passes = 0
    pnl_passes = 0
    per_segment: list[dict] = []

    for idx, seg_trades in enumerate(trades_per_segment):
        n = len(seg_trades)
        if n < A3_MIN_TRADES_PER_SEGMENT:
            per_segment.append({"segment": idx, "trades": n, "reason": "too_few"})
            continue
        valid += 1
        wins = sum(1 for t in seg_trades if t.pnl > 0)
        wr = wins / n
        pnl = float(sum(t.pnl for t in seg_trades))
        seg_info = {"segment": idx, "trades": n, "wr": wr, "pnl": pnl}
        if wr > A3_WR_FLOOR:
            wr_passes += 1
            seg_info["wr_pass"] = True
        if pnl > 0:
            pnl_passes += 1
            seg_info["pnl_pass"] = True
        per_segment.append(seg_info)

    if valid < A3_SEGMENTS:
        return GateResult(False, "not_enough_valid_segments",
                          {"valid": valid, "required": A3_SEGMENTS,
                           "segments": per_segment})
    if wr_passes < A3_MIN_WR_PASSES:
        return GateResult(False, "wr_stability_fail",
                          {"wr_passes": wr_passes, "required": A3_MIN_WR_PASSES,
                           "segments": per_segment})
    if pnl_passes < A3_MIN_PNL_PASSES:
        return GateResult(False, "pnl_stability_fail",
                          {"pnl_passes": pnl_passes, "required": A3_MIN_PNL_PASSES,
                           "segments": per_segment})
    return GateResult(True, "ok",
                      {"wr_passes": wr_passes, "pnl_passes": pnl_passes,
                       "segments": per_segment})


def build_a3_segments(close: np.ndarray, trades: Iterable[Trade]) -> list[list[Trade]]:
    """Partition trades into A3_SEGMENTS buckets by entry bar index.

    Segment boundaries are equal-width over the close array passed in
    (which must be the A3 slice of the holdout). Use this to convert a
    flat trade list into the 5-segment structure arena3_pass expects.
    """
    n = close.size
    if n < A3_SEGMENTS:
        raise ValueError(f"A3 segment source too small: n={n}")
    segment_edges = np.linspace(0, n, A3_SEGMENTS + 1, dtype=np.int64)
    buckets: list[list[Trade]] = [[] for _ in range(A3_SEGMENTS)]
    for trade in trades:
        for i in range(A3_SEGMENTS):
            if segment_edges[i] <= trade.entry_idx < segment_edges[i + 1]:
                buckets[i].append(trade)
                break
    return buckets


# --------------------------------------------------------------------- A4

A4_REGIME_WR_FLOOR: float = 0.40
A4_MIN_TRADES_PER_REGIME: int = 10
A4_MIN_OTHER_REGIMES_PASS: int = 1


def arena4_pass(
    close: np.ndarray,
    trades: Sequence[Trade],
    training_regime: str,
) -> GateResult:
    """A4: WR>0.40 in training regime AND in ≥1 other regime.

    `close` is the A4 slice of the holdout. Regime labels are derived
    on-the-fly (the regime tagger is deterministic for the same close).
    """
    labels = tag_regime(close)
    regime_trades: dict[str, list[Trade]] = {r.value: [] for r in Regime}
    for t in trades:
        if 0 <= t.entry_idx < labels.size:
            regime_trades[labels[t.entry_idx]].append(t)

    metrics: dict[str, dict] = {}
    passes: dict[str, bool] = {}
    for r, ts in regime_trades.items():
        if len(ts) < A4_MIN_TRADES_PER_REGIME:
            metrics[r] = {"trades": len(ts), "reason": "insufficient"}
            continue
        wins = sum(1 for t in ts if t.pnl > 0)
        wr = wins / len(ts)
        metrics[r] = {"trades": len(ts), "wr": wr}
        passes[r] = wr > A4_REGIME_WR_FLOOR

    if training_regime not in metrics or "wr" not in metrics[training_regime]:
        return GateResult(False, "no_data_in_training_regime",
                          {"training_regime": training_regime, "regimes": metrics})
    if not passes.get(training_regime, False):
        return GateResult(False, "training_regime_wr_fail",
                          {"training_regime": training_regime, "regimes": metrics})

    other_passes = sum(
        1 for r, ok in passes.items() if r != training_regime and ok
    )
    if other_passes < A4_MIN_OTHER_REGIMES_PASS:
        return GateResult(False, "no_other_regime_passed",
                          {"training_regime": training_regime,
                           "other_passes": other_passes,
                           "regimes": metrics})
    return GateResult(True, "ok",
                      {"training_regime": training_regime,
                       "other_passes": other_passes,
                       "regimes": metrics})
