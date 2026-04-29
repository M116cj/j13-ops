"""HE3 Horizon Economic Telemetry — pure helper for per-horizon batch metrics.

TEAM ORDER: 0-9Y-HE3-HORIZON-ECONOMIC-TELEMETRY
Status:     telemetry-only, additive. No behavior change to validation,
            cost, A2_MIN_TRADES, champion promotion, or deployable semantics.

Builds {selected_horizon: {trade_count_median, gross_pnl_median, net_pnl_median,
                            ..., cost_over_gross_ratio}} dict from per-alpha
data lists already populated by the round in arena_pipeline.py.

Forbidden:
  - no validator / cost / A2_MIN_TRADES / alpha_zoo / CANARY / production refs
  - no DB writes / no file writes / no env mutation
  - no shared mutable state
"""
from __future__ import annotations

import statistics
import math
from typing import Any, Dict, Iterable, List, Optional


def _median(xs: Iterable[float]) -> Optional[float]:
    ys = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    if not ys:
        return None
    return float(statistics.median(ys))


def _mean(xs: Iterable[float]) -> Optional[float]:
    ys = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    if not ys:
        return None
    return float(sum(ys) / len(ys))


def _safe_sum(xs: Iterable[float]) -> Optional[float]:
    ys = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    if not ys:
        return None
    return float(sum(ys))


def build_horizon_metrics(
    selected_horizon: int,
    *,
    train_gross_pnl: List[float],
    train_net_pnl: List[float],
    train_total_trades: List[int],
    train_win_rate: List[float],
    round_total_cost_bps: Optional[float] = None,
    signal_density_per_bar: Optional[float] = None,
    skipped_count_total: int = 0,
    kept_count_total: int = 0,
    entered_count_total: int = 0,
) -> Dict[int, Dict[str, Any]]:
    """Pure aggregator: returns {selected_horizon: <metrics dict>}.

    Never raises; on internal error returns {} so the calling emitter can
    proceed without breaking the existing batch-metrics emission.

    The dict matches master-order spec:
      trade_count, skipped_count, gross_pnl_sum, net_pnl_sum, total_cost,
      win_rate, signal_density_per_bar, gross_per_trade, net_per_trade,
      cost_per_trade, cost_over_gross_ratio (+ alpha_count, mean/median variants).
    """
    try:
        h = int(selected_horizon)
    except Exception:
        return {}

    try:
        # Ensure aligned lengths: lists are populated in lockstep per alpha
        # in arena_pipeline.py, but defensively use min length to avoid mis-zip.
        n_aligned = min(len(train_gross_pnl), len(train_net_pnl), len(train_total_trades))

        gross_list = list(train_gross_pnl[:n_aligned])
        net_list = list(train_net_pnl[:n_aligned])
        trades_list = list(train_total_trades[:n_aligned])
        wr_list = list(train_win_rate)  # win_rate may have its own length

        # Per-trade derived series
        gpt_per_alpha = [
            float(g) / float(t)
            for g, t in zip(gross_list, trades_list)
            if t and float(t) > 0
        ]
        npt_per_alpha = [
            float(n) / float(t)
            for n, t in zip(net_list, trades_list)
            if t and float(t) > 0
        ]
        cost_over_gross = [
            (float(g) - float(n)) / float(g)
            for g, n in zip(gross_list, net_list)
            if g and float(g) > 0
        ]

        trade_count_median = _median(trades_list)
        total_trades_sum = _safe_sum(trades_list)

        cost_per_trade: Optional[float] = None
        if (
            round_total_cost_bps is not None
            and trade_count_median is not None
            and trade_count_median > 0
        ):
            cost_per_trade = float(round_total_cost_bps) / float(trade_count_median)

        # total_cost approximation: round_total_cost_bps × n_alphas
        total_cost: Optional[float] = None
        if round_total_cost_bps is not None and n_aligned > 0:
            total_cost = float(round_total_cost_bps) * n_aligned

        metrics: Dict[str, Any] = {
            "alpha_count": int(n_aligned),
            "trade_count_median": trade_count_median,
            "trade_count_mean": _mean(trades_list),
            "trade_count_total": int(total_trades_sum) if total_trades_sum is not None else None,
            "skipped_count_total": int(skipped_count_total),
            "kept_count_total": int(kept_count_total),
            "entered_count_total": int(entered_count_total),
            "gross_pnl_median": _median(gross_list),
            "gross_pnl_mean": _mean(gross_list),
            "gross_pnl_sum": _safe_sum(gross_list),
            "net_pnl_median": _median(net_list),
            "net_pnl_mean": _mean(net_list),
            "net_pnl_sum": _safe_sum(net_list),
            "total_cost": total_cost,
            "win_rate_median": _median(wr_list),
            "signal_density_per_bar": (
                float(signal_density_per_bar) if signal_density_per_bar is not None else None
            ),
            "gross_per_trade_median": _median(gpt_per_alpha),
            "net_per_trade_median": _median(npt_per_alpha),
            "cost_per_trade": cost_per_trade,
            "cost_over_gross_ratio": _median(cost_over_gross),
        }
        return {h: metrics}
    except Exception:
        # Never raise from a pure helper — empty dict on any internal error.
        return {}


def aggregate_horizon_metrics_across_batches(
    batches: Iterable[Dict[str, Any]],
) -> Dict[int, Dict[str, Any]]:
    """Cross-batch aggregator (used by Phase 5 analysis).

    Each batch in `batches` is an `aggregate_metrics` dict containing
    `horizon_metrics` (per HE3 schema). This function groups by horizon and
    computes median-of-medians across batches.

    Args:
        batches: iterable of `aggregate_metrics` dicts.

    Returns:
        {horizon: {field: median across batches}}
    """
    grouped: Dict[int, Dict[str, List[float]]] = {}
    for am in batches:
        hm = am.get("horizon_metrics") if isinstance(am, dict) else None
        if not isinstance(hm, dict):
            continue
        for h, m in hm.items():
            if not isinstance(m, dict):
                continue
            try:
                h_int = int(h)
            except Exception:
                continue
            bucket = grouped.setdefault(h_int, {})
            for k, v in m.items():
                if isinstance(v, (int, float)) and not (
                    isinstance(v, float) and math.isnan(v)
                ):
                    bucket.setdefault(k, []).append(float(v))
    out: Dict[int, Dict[str, Any]] = {}
    for h, fields in grouped.items():
        out[h] = {k: _median(vs) for k, vs in fields.items()}
        out[h]["batch_count"] = max((len(vs) for vs in fields.values()), default=0)
    return out
