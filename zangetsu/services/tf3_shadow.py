"""TF3 Shadow Activation — runs TF2 aggregation profiles alongside baseline.

TEAM ORDER: 0-9Y-TF3-SIGNAL-AGGREGATION-SHADOW-ACTIVATION
Status:     SHADOW-only, env-gated (ARENA_TF3_SHADOW=1).

Wraps TF2's pure helper `apply_signal_aggregation` with a shadow-execution
harness used by `arena_pipeline.py`. Each shadow call:
  1. applies one of three profiles to (signals, sizes) — never mutates inputs
  2. runs a separate `backtester.run` on the filtered signal series
  3. accumulates per-profile per-alpha metrics

Forbidden actions (mirror master order TF3):
  - NO change to validation logic
  - NO change to cost model
  - NO change to A2_MIN_TRADES (25)
  - NO mutation of baseline data
  - NO promotion / champion / deployable semantics change
  - NO CANARY / production / capital / risk modification

Default invariant: when ARENA_TF3_SHADOW != "1", `is_shadow_enabled()` returns
False and the caller skips this entire module. No side effects.
"""
from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

import numpy as np

from zangetsu.services.signal_aggregation import (
    apply_signal_aggregation,
    PROFILE_STRENGTH_FILTER,
    PROFILE_TOP_K_PER_BAR,
    PROFILE_HYBRID,
)

log = logging.getLogger(__name__)


# --- Activation gate --------------------------------------------------------
def _read_shadow_flag() -> bool:
    return os.environ.get("ARENA_TF3_SHADOW", "0").strip().lower() in ("1", "true", "yes", "on")


# Cached at module-import for performance + test predictability.
# Tests patch this via monkeypatch / direct override.
_TF3_SHADOW_ENABLED = _read_shadow_flag()


def is_shadow_enabled() -> bool:
    """Returns True iff ARENA_TF3_SHADOW=1 was set at module import time."""
    return _TF3_SHADOW_ENABLED


def refresh_shadow_flag() -> bool:
    """For tests / debug only — re-reads env and returns current value."""
    global _TF3_SHADOW_ENABLED
    _TF3_SHADOW_ENABLED = _read_shadow_flag()
    return _TF3_SHADOW_ENABLED


# --- Profile parameter set --------------------------------------------------
# Selected from TF2 fixture sweeps; tunable via ARENA_TF3_PROFILE_PARAMS env
# if needed for future experiments. Defaults are conservative.

PROFILE_KEYS = ("strength", "top_k", "hybrid")

PROFILE_PARAMS: Dict[str, Dict[str, Any]] = {
    "strength": {
        "profile": PROFILE_STRENGTH_FILTER,
        "kwargs": {"strength_quantile": 0.95},
        "label": "STRENGTH_q0.95",
    },
    "top_k": {
        "profile": PROFILE_TOP_K_PER_BAR,
        "kwargs": {"top_k": 50},
        "label": "TOPK_K=50",
    },
    "hybrid": {
        "profile": PROFILE_HYBRID,
        "kwargs": {"strength_quantile": 0.90, "top_k": 50},
        "label": "HYBRID_q0.90_K=50",
    },
}


@dataclass
class ShadowAccumulator:
    """Per-profile, per-symbol-regime accumulator. Lists of per-alpha samples."""
    train_gross_pnl: List[float] = field(default_factory=list)
    train_net_pnl: List[float] = field(default_factory=list)
    train_total_trades: List[int] = field(default_factory=list)
    train_win_rate: List[float] = field(default_factory=list)
    skipped_count_total: int = 0
    kept_count_total: int = 0
    entered_count_total: int = 0
    error_count: int = 0


def make_accumulators() -> Dict[str, ShadowAccumulator]:
    """Fresh accumulator dict, one per profile."""
    return {k: ShadowAccumulator() for k in PROFILE_KEYS}


def run_shadow_for_alpha(
    *,
    signals: np.ndarray,
    sizes: np.ndarray,
    backtester,
    close_f32: np.ndarray,
    high_f32: Optional[np.ndarray],
    low_f32: Optional[np.ndarray],
    sym: str,
    cost_bps: float,
    max_hold: int,
    accumulators: Dict[str, ShadowAccumulator],
) -> None:
    """Run all 3 profiles for one alpha. Updates `accumulators` in place.

    Defensive: any exception per-profile is caught + logged at DEBUG; the
    profile's `error_count` is incremented; baseline path is never affected.
    """
    for key in PROFILE_KEYS:
        params = PROFILE_PARAMS[key]
        acc = accumulators[key]
        try:
            agg = apply_signal_aggregation(
                signals, sizes,
                profile=params["profile"],
                strength=sizes,  # signals_aggregation contract: sizes IS strength
                **params["kwargs"],
            )
        except Exception as _ae:
            log.debug(f"[tf3] profile={key} aggregation failed: {_ae}")
            acc.error_count += 1
            continue

        acc.entered_count_total += agg.entered_count
        acc.kept_count_total += agg.kept_count
        acc.skipped_count_total += agg.skipped_count

        # If aggregation suppressed all entries, skip backtester (no trades)
        if agg.kept_count == 0:
            acc.train_gross_pnl.append(0.0)
            acc.train_net_pnl.append(0.0)
            acc.train_total_trades.append(0)
            acc.train_win_rate.append(0.0)
            continue

        try:
            bt = backtester.run(
                agg.signals,
                close_f32,
                sym,
                cost_bps,
                max_hold,
                high=high_f32,
                low=low_f32,
                sizes=agg.sizes,
            )
        except Exception as _be:
            log.debug(f"[tf3] profile={key} shadow backtest failed: {_be}")
            acc.error_count += 1
            continue

        # Defensive per-field reads (matches baseline pattern)
        try:
            acc.train_gross_pnl.append(float(bt.gross_pnl))
        except Exception:
            pass
        try:
            acc.train_net_pnl.append(float(bt.net_pnl))
        except Exception:
            pass
        try:
            acc.train_total_trades.append(int(bt.total_trades))
        except Exception:
            pass
        try:
            acc.train_win_rate.append(float(bt.win_rate))
        except Exception:
            pass


def _median(xs):
    if not xs:
        return None
    ys = sorted(xs)
    n = len(ys)
    mid = n // 2
    return float(ys[mid] if n % 2 == 1 else 0.5 * (ys[mid - 1] + ys[mid]))


def _mean(xs):
    return float(sum(xs) / len(xs)) if xs else None


def build_shadow_profiles_payload(
    accumulators: Dict[str, ShadowAccumulator],
    *,
    baseline_train_gross_pnl: List[float],
    baseline_train_net_pnl: List[float],
    baseline_train_total_trades: List[int],
    baseline_train_win_rate: List[float],
) -> Dict[str, Dict[str, Any]]:
    """Build the per-batch shadow_profiles dict to attach to arena_batch_metrics.

    Mirrors aggregate_metrics shape: medians + means + counts. NEVER overwrites
    baseline fields; this is a NEW key on the emitted batch event.
    """
    payload: Dict[str, Dict[str, Any]] = {
        "baseline": {
            "trade_count_median": _median(baseline_train_total_trades),
            "gross_pnl_median": _median(baseline_train_gross_pnl),
            "net_pnl_median": _median(baseline_train_net_pnl),
            "win_rate_median": _median(baseline_train_win_rate),
            "skipped_count_total": 0,
            "alpha_count": len(baseline_train_net_pnl),
        }
    }
    for key in PROFILE_KEYS:
        acc = accumulators[key]
        params = PROFILE_PARAMS[key]
        gpt = None
        npt = None
        # gross_per_trade / net_per_trade aggregated across alphas: median of (gross/trades) where trades>0
        gpt_per_alpha = [
            g / t for g, t in zip(acc.train_gross_pnl, acc.train_total_trades) if t > 0
        ]
        npt_per_alpha = [
            n / t for n, t in zip(acc.train_net_pnl, acc.train_total_trades) if t > 0
        ]
        if gpt_per_alpha:
            gpt = _median(gpt_per_alpha)
        if npt_per_alpha:
            npt = _median(npt_per_alpha)
        payload[key] = {
            "label": params["label"],
            "trade_count_median": _median(acc.train_total_trades),
            "gross_pnl_median": _median(acc.train_gross_pnl),
            "net_pnl_median": _median(acc.train_net_pnl),
            "win_rate_median": _median(acc.train_win_rate),
            "gross_per_trade_median": gpt,
            "net_per_trade_median": npt,
            "skipped_count_total": int(acc.skipped_count_total),
            "kept_count_total": int(acc.kept_count_total),
            "entered_count_total": int(acc.entered_count_total),
            "error_count": int(acc.error_count),
            "params": params["kwargs"],
            "alpha_count": len(acc.train_net_pnl),
        }
    return payload
