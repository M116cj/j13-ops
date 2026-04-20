"""Re-score the existing champion_pipeline pool with the new A2/A3/A4 gates.

Produces tier=historical DEPLOYABLE labels for alphas that survive the
three disjoint OOS slices of the holdout. Does NOT promote to live
trading (card_status stays INACTIVE) — live promotion requires a
tier=live_proven record from the 14-day A5 shadow service.

Usage:
    python scripts/rescan_legacy_with_new_gates.py [--limit N] [--symbol BTCUSDT]
"""




from __future__ import annotations


# ============================================================
# DEPRECATED — DO NOT USE
# ------------------------------------------------------------
# v0.7.1 governance ruling (2026-04-20):
#   Epoch A (legacy archive) rows MUST NOT participate in ranking,
#   promotion, deployment, or any downstream selection. This script's
#   original intent — rescoring legacy alphas under new gates — is
#   explicitly forbidden because the legacy pool is a biased sample
#   produced under indicator-disabled GP, not a valid search-space
#   snapshot.
#
#   The script is retained here for archaeology only. Any attempt to
#   run it requires the explicit flag --i-know-archive-is-frozen and
#   will refuse to write back to the DB regardless.
# ============================================================
import sys as _sys
if "--i-know-archive-is-frozen" not in _sys.argv:
    print("REFUSED: rescan_legacy_with_new_gates.py is DEPRECATED (v0.7.1).")
    print("Legacy pool MUST NOT be re-ranked per governance rule #1.")
    print("If you truly know what you are doing, pass --i-know-archive-is-frozen.")
    _sys.exit(2)
else:
    _sys.argv.remove("--i-know-archive-is-frozen")
    print("WARNING: rescan running with deprecation flag bypassed.")
    print("This script will NOT write to DB in v0.7.1 mode; observe only.")

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import asyncpg
import numpy as np
import polars as pl

sys.path.insert(0, "/home/j13/j13-ops")

from zangetsu.config.settings import Settings
settings = Settings()
from zangetsu.engine.components.backtester import Backtester, _vectorized_backtest
from zangetsu.services.arena_gates import (
    Trade,
    arena2_pass,
    arena3_pass,
    arena4_pass,
    build_a3_segments,
)
from zangetsu.services.holdout_splits import split_holdout_three_ways
from zangetsu.services.regime_tagger import Regime
from zangetsu.services.signal_reconstructor import reconstruct_signal_from_passport


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("rescan")


TRAIN_SPLIT_RATIO = 0.7
HOLDOUT_WINDOW_BARS = 200_000
COST_BPS = 5.0
MAX_HOLD_BARS = 60  # aligned with ALPHA_FORWARD_HORIZON
A4_MIN_BARS = 500


# Map existing champion_pipeline.regime labels to the 3-bucket regime
# tagger used by A4. Unknown labels fall back to CHOP.
_REGIME_MAP = {
    "BULL_TREND": Regime.BULL.value,
    "BULL_PULLBACK": Regime.BULL.value,
    "PARABOLIC": Regime.BULL.value,
    "ACCUMULATION": Regime.BULL.value,
    "BOTTOMING": Regime.BULL.value,
    "BEAR_TREND": Regime.BEAR.value,
    "BEAR_RALLY": Regime.BEAR.value,
    "LIQUIDITY_CRISIS": Regime.BEAR.value,
    "DISTRIBUTION": Regime.BEAR.value,
    "CONSOLIDATION": Regime.CHOP.value,
    "CHOPPY_VOLATILE": Regime.CHOP.value,
    "MULTI": Regime.CHOP.value,
    "DISCOVERED": Regime.CHOP.value,
}


def load_holdout(symbol: str) -> dict[str, np.ndarray]:
    path = f"{settings.parquet_dir}/{symbol}.parquet"
    df = pl.read_parquet(path)
    w = min(HOLDOUT_WINDOW_BARS, len(df))
    split = int(w * TRAIN_SPLIT_RATIO)
    holdout_len = w - split
    tail = df.tail(w)
    start = split
    return {
        "open": tail["open"].to_numpy()[start:].astype(np.float32),
        "high": tail["high"].to_numpy()[start:].astype(np.float32),
        "low": tail["low"].to_numpy()[start:].astype(np.float32),
        "close": tail["close"].to_numpy()[start:].astype(np.float32),
        "volume": tail["volume"].to_numpy()[start:].astype(np.float32),
        "_len": holdout_len,
    }


def extract_trades(
    signals: np.ndarray,
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
) -> list[Trade]:
    """Run the core vectorized backtest and return per-trade records."""
    if signals.size < 50:
        return []
    cost_frac = COST_BPS / 10_000.0
    pnl_arr, entries, exits, _reasons = _vectorized_backtest(
        signals.astype(np.int8),
        close.astype(np.float64),
        high.astype(np.float64),
        low.astype(np.float64),
        cost_frac,
        MAX_HOLD_BARS,
        0.0,  # atr_stop_mult disabled for historical rescan
        np.zeros_like(close, dtype=np.float64),
        np.ones_like(close, dtype=np.float64),
    )
    trades: list[Trade] = []
    for i in range(len(entries)):
        exit_idx = int(exits[i])
        trades.append(
            Trade(
                pnl=float(pnl_arr[exit_idx]),
                entry_idx=int(entries[i]),
                exit_idx=exit_idx,
            )
        )
    return trades


def run_gates_on_holdout(
    passport: dict,
    regime_label: str,
    holdout: dict[str, np.ndarray],
) -> dict:
    """Split holdout, reconstruct signal per slice, run A2/A3/A4."""
    split = split_holdout_three_ways(holdout["close"])
    arrays = ("open", "high", "low", "close", "volume")

    def slice_for(start: int, end: int) -> dict[str, np.ndarray]:
        return {k: holdout[k][start:end] for k in arrays}

    third = holdout["_len"] // 3
    bounds = {
        "a2": (0, third),
        "a3": (third, 2 * third),
        "a4": (2 * third, holdout["_len"]),
    }

    report: dict = {"gates": {}}

    # A2 ------------------------------------------------------------------
    s = bounds["a2"]
    seg = slice_for(*s)
    signals, _sizes, _agree = reconstruct_signal_from_passport(
        passport=passport,
        close=seg["close"], high=seg["high"], low=seg["low"],
        open_arr=seg["open"], volume=seg["volume"],
        min_hold=MAX_HOLD_BARS, cooldown=MAX_HOLD_BARS,
    )
    a2_trades = extract_trades(signals, seg["close"], seg["high"], seg["low"])
    r2 = arena2_pass(a2_trades)
    report["gates"]["a2"] = {"passed": r2.passed, "reason": r2.reason, **r2.metrics}
    if not r2.passed:
        report["final"] = "arena2_rejected"
        return report

    # A3 ------------------------------------------------------------------
    s = bounds["a3"]
    seg = slice_for(*s)
    signals, _sizes, _agree = reconstruct_signal_from_passport(
        passport=passport,
        close=seg["close"], high=seg["high"], low=seg["low"],
        open_arr=seg["open"], volume=seg["volume"],
        min_hold=MAX_HOLD_BARS, cooldown=MAX_HOLD_BARS,
    )
    a3_trades = extract_trades(signals, seg["close"], seg["high"], seg["low"])
    buckets = build_a3_segments(seg["close"], a3_trades)
    r3 = arena3_pass(buckets)
    report["gates"]["a3"] = {"passed": r3.passed, "reason": r3.reason, **r3.metrics}
    if not r3.passed:
        report["final"] = "arena3_rejected"
        return report

    # A4 ------------------------------------------------------------------
    s = bounds["a4"]
    seg = slice_for(*s)
    if seg["close"].size < A4_MIN_BARS:
        report["final"] = "a4_slice_too_small"
        return report
    signals, _sizes, _agree = reconstruct_signal_from_passport(
        passport=passport,
        close=seg["close"], high=seg["high"], low=seg["low"],
        open_arr=seg["open"], volume=seg["volume"],
        min_hold=MAX_HOLD_BARS, cooldown=MAX_HOLD_BARS,
    )
    a4_trades = extract_trades(signals, seg["close"], seg["high"], seg["low"])
    training_regime = _REGIME_MAP.get(regime_label, Regime.CHOP.value)
    r4 = arena4_pass(seg["close"], a4_trades, training_regime)
    report["gates"]["a4"] = {"passed": r4.passed, "reason": r4.reason, **r4.metrics}
    if not r4.passed:
        report["final"] = "arena4_rejected"
        return report

    report["final"] = "deployable_historical"
    return report


async def rescan(limit: Optional[int], symbol: str) -> None:
    log.info("loading holdout for %s", symbol)
    holdout = load_holdout(symbol)
    log.info("holdout bars=%d (a2=%d a3=%d a4=%d)",
             holdout["_len"],
             holdout["_len"] // 3,
             holdout["_len"] // 3,
             holdout["_len"] - 2 * (holdout["_len"] // 3))

    pool = await asyncpg.create_pool(
        host=settings.db_host, port=settings.db_port,
        database=settings.db_name, user=settings.db_user,
        password=settings.db_password, min_size=1, max_size=3,
    )
    try:
        limit_clause = f"LIMIT {int(limit)}" if limit else ""
        rows = await pool.fetch(f"""
            SELECT id, regime, passport, engine_hash, status
            FROM champion_pipeline
            WHERE status IN ('LEGACY', 'ARENA2_REJECTED', 'ARENA4_ELIMINATED')
              AND passport IS NOT NULL
              AND (deployable_tier IS NULL)
            ORDER BY id DESC
            {limit_clause}
        """)
        log.info("candidates to rescan: %d", len(rows))

        counts = {
            "checked": 0, "passed": 0,
            "rejected_a2": 0, "rejected_a3": 0, "rejected_a4": 0,
            "error": 0,
        }
        for row in rows:
            counts["checked"] += 1
            try:
                passport = row["passport"]
                if isinstance(passport, str):
                    passport = json.loads(passport)
                if not isinstance(passport, dict):
                    counts["error"] += 1
                    continue
                result = run_gates_on_holdout(passport, row["regime"], holdout)
                final = result["final"]
                if final == "deployable_historical":
                    counts["passed"] += 1
                    # v0.7.1 governance: write-back blocked. Observe only.
                    log.info("[DEPRECATED rescan, would-write-blocked] id=%s verdict=%s", row["id"], result["final"])
                    log.info("PASS id=%s regime=%s", row["id"], row["regime"])
                elif final == "arena2_rejected":
                    counts["rejected_a2"] += 1
                elif final == "arena3_rejected":
                    counts["rejected_a3"] += 1
                elif final == "arena4_rejected":
                    counts["rejected_a4"] += 1
            except Exception as e:
                log.warning("id=%s failed: %s", row.get("id"), e)
                counts["error"] += 1

            if counts["checked"] % 50 == 0:
                log.info("progress: %s", counts)

        log.info("DONE: %s", counts)
    finally:
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--symbol", default="BTCUSDT")
    args = parser.parse_args()
    asyncio.run(rescan(args.limit, args.symbol))


if __name__ == "__main__":
    main()
