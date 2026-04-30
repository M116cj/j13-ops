"""Shadow-only Economic Arena adapter.

Loads OHLCV (and funding/OI when needed) from zangetsu/data/, evaluates a
formula AST into a signal series, derives synthetic trades from sign-flips,
applies the round-trip cost, and queries arena_gates.arena2_pass for the A2
verdict. **No production DB write.** **No exchange API call.**
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import os
import pathlib

import numpy as np
import pandas as pd

from .combination_grammar import FormulaSpec
from .primitive_inventory import (
    UnsupportedOperatorError,
    evaluate_field,
    get_primitive,
)
from .constants import A2_MIN_TRADES, ROUND_TRIP_COST_BPS


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "zangetsu" / "data"

TIMEFRAME_MINUTES = {
    "1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440,
}


@dataclass
class EvaluationResult:
    candidate_id: str
    status: str  # PASSED / REJECTED / ERROR / NOT_EVALUATED
    reject_reason: Optional[str]
    blocker_reason: Optional[str]
    gross_bps: float
    cost_bps: float
    net_bps: float
    trade_count: int
    long_trade_count: int
    short_trade_count: int
    a1_pass: Optional[bool]
    a2_pass: Optional[bool]


def _load_ohlcv(symbol: str, timeframe: str) -> pd.DataFrame | None:
    p = DATA_ROOT / "ohlcv" / f"{symbol}.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    df = df.dropna()
    if timeframe == "1m":
        return df
    minutes = TIMEFRAME_MINUTES.get(timeframe)
    if minutes is None:
        return None
    df = df.copy()
    df["bucket"] = (df["timestamp"] // (minutes * 60_000)) * (minutes * 60_000)
    g = df.groupby("bucket", sort=True).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    ).reset_index().rename(columns={"bucket": "timestamp"})
    return g


def _load_funding(symbol: str) -> pd.DataFrame | None:
    p = DATA_ROOT / "funding" / f"{symbol}.parquet"
    if not p.exists():
        return None
    return pd.read_parquet(p)


def _load_oi(symbol: str) -> pd.DataFrame | None:
    p = DATA_ROOT / "oi" / f"{symbol}.parquet"
    if not p.exists():
        return None
    return pd.read_parquet(p)


def _build_data_dict(symbol: str, timeframe: str, axis_id: str) -> dict[str, np.ndarray] | None:
    ohlc = _load_ohlcv(symbol, timeframe)
    if ohlc is None or len(ohlc) < 100:
        return None
    out: dict[str, np.ndarray] = {
        "open": ohlc["open"].to_numpy(dtype=np.float32),
        "high": ohlc["high"].to_numpy(dtype=np.float32),
        "low": ohlc["low"].to_numpy(dtype=np.float32),
        "close": ohlc["close"].to_numpy(dtype=np.float32),
        "volume": ohlc["volume"].to_numpy(dtype=np.float32),
    }
    if axis_id in {"H"}:
        # Hybrid needs funding/OI overlay onto ohlc grid (forward-fill).
        ts = ohlc["timestamp"].to_numpy()
        funding = _load_funding(symbol)
        oi = _load_oi(symbol)
        if funding is None or oi is None or len(funding) == 0 or len(oi) == 0:
            # H-LITE: mark missing with constant 0 (component unavailable signal,
            # not blocker — order rule §2 funding/OI rule).
            out["funding"] = np.zeros(len(ohlc), dtype=np.float32)
            out["oi"] = np.zeros(len(ohlc), dtype=np.float32)
            out["__h_lite__"] = np.array([1.0], dtype=np.float32)  # marker
        else:
            out["funding"] = _align_to_grid(ts, funding["timestamp"].to_numpy(),
                                            funding["fundingRate"].to_numpy(dtype=np.float32))
            out["oi"] = _align_to_grid(ts, oi["timestamp"].to_numpy(),
                                       oi["sumOpenInterest"].to_numpy(dtype=np.float32))
    return out


def _align_to_grid(grid_ts: np.ndarray, src_ts: np.ndarray, src_val: np.ndarray) -> np.ndarray:
    """Forward-fill src_val onto grid_ts (right-edge align)."""
    idx = np.searchsorted(src_ts, grid_ts, side="right") - 1
    idx = np.clip(idx, 0, len(src_val) - 1)
    return src_val[idx].astype(np.float32)


def _evaluate_ast(ast, data: dict[str, np.ndarray]) -> np.ndarray:
    """Recursively evaluate a canonical AST against data dict. Fail closed on bad ops."""
    if ast[0] == "field":
        return evaluate_field(ast[1], data)
    if ast[0] == "op":
        spec = get_primitive(ast[1])  # raises UnsupportedOperatorError
        children = ast[2]
        if spec.arity == 1:
            child_arr = _evaluate_ast(children[0], data)
            if spec.needs_window:
                return spec.fn(child_arr, ast[3])
            return spec.fn(child_arr)
        if spec.arity == 2:
            l = _evaluate_ast(children[0], data)
            r = _evaluate_ast(children[1], data)
            return spec.fn(l, r)
    raise UnsupportedOperatorError(f"bad_node:{ast[0]}")


def _signal_to_trades(signal: np.ndarray, close: np.ndarray, intended_side_mode: str) -> tuple[list[float], int, int]:
    """Convert signal sign-flips to a sequence of synthetic trade returns (in bps).

    A flip from <=0 to >0 opens a LONG; flip from >=0 to <0 opens a SHORT.
    Position is closed on the next flip. Returns: (returns_bps_list, n_long, n_short).
    """
    if len(signal) < 3 or len(close) != len(signal):
        return [], 0, 0
    sgn = np.sign(signal)
    returns: list[float] = []
    n_long = 0
    n_short = 0
    pos = 0  # +1 long, -1 short, 0 flat
    entry_px = 0.0
    for i in range(1, len(sgn)):
        s_now = sgn[i]
        if pos == 0:
            if s_now > 0 and intended_side_mode in {"LONG", "BOTH"}:
                pos = 1
                entry_px = float(close[i])
                n_long += 1
            elif s_now < 0 and intended_side_mode in {"SHORT", "BOTH"}:
                pos = -1
                entry_px = float(close[i])
                n_short += 1
            continue
        if (pos == 1 and s_now <= 0) or (pos == -1 and s_now >= 0):
            exit_px = float(close[i])
            if entry_px > 0:
                if pos == 1:
                    ret_bps = (exit_px - entry_px) / entry_px * 10_000.0
                else:
                    ret_bps = (entry_px - exit_px) / entry_px * 10_000.0
                returns.append(ret_bps)
            pos = 0
            # Re-enter on the same bar if the new sign matches the side mode.
            if s_now > 0 and intended_side_mode in {"LONG", "BOTH"}:
                pos = 1
                entry_px = float(close[i])
                n_long += 1
            elif s_now < 0 and intended_side_mode in {"SHORT", "BOTH"}:
                pos = -1
                entry_px = float(close[i])
                n_short += 1
    return returns, n_long, n_short


def evaluate_candidate(
    *,
    candidate_id: str,
    formula_ast,
    symbol: str,
    timeframe: str,
    axis_id: str,
    intended_side_mode: str,
    cost_bps_round_trip: float = ROUND_TRIP_COST_BPS,
) -> EvaluationResult:
    data = _build_data_dict(symbol, timeframe, axis_id)
    if data is None:
        return EvaluationResult(
            candidate_id=candidate_id, status="NOT_EVALUATED",
            reject_reason=None, blocker_reason="AXIS_COMPONENT_UNAVAILABLE",
            gross_bps=0.0, cost_bps=0.0, net_bps=0.0,
            trade_count=0, long_trade_count=0, short_trade_count=0,
            a1_pass=None, a2_pass=None,
        )
    try:
        signal = _evaluate_ast(formula_ast, data)
    except UnsupportedOperatorError:
        return EvaluationResult(
            candidate_id=candidate_id, status="NOT_EVALUATED",
            reject_reason=None, blocker_reason="UNSUPPORTED_OPERATOR",
            gross_bps=0.0, cost_bps=0.0, net_bps=0.0,
            trade_count=0, long_trade_count=0, short_trade_count=0,
            a1_pass=None, a2_pass=None,
        )
    except Exception:
        return EvaluationResult(
            candidate_id=candidate_id, status="ERROR",
            reject_reason="evaluation_runtime_error", blocker_reason=None,
            gross_bps=0.0, cost_bps=0.0, net_bps=0.0,
            trade_count=0, long_trade_count=0, short_trade_count=0,
            a1_pass=None, a2_pass=None,
        )
    close = data["close"]
    returns, n_long, n_short = _signal_to_trades(signal, close, intended_side_mode)
    trade_count = len(returns)
    if trade_count == 0:
        return EvaluationResult(
            candidate_id=candidate_id, status="REJECTED",
            reject_reason="no_trades_generated", blocker_reason=None,
            gross_bps=0.0, cost_bps=0.0, net_bps=0.0,
            trade_count=0, long_trade_count=0, short_trade_count=0,
            a1_pass=False, a2_pass=False,
        )
    gross_bps = float(np.mean(returns))
    cost_bps = float(cost_bps_round_trip)
    net_bps = gross_bps - cost_bps
    a1_pass = trade_count >= 5  # minimum sanity, not the production A1 gate
    a2_pass = (trade_count >= A2_MIN_TRADES) and (sum(returns) - trade_count * cost_bps) > 0
    if a2_pass:
        status = "PASSED"
        reject_reason = None
    else:
        status = "REJECTED"
        if trade_count < A2_MIN_TRADES:
            reject_reason = "too_few_trades"
        elif net_bps <= 0:
            reject_reason = "non_positive_net"
        else:
            reject_reason = "UNKNOWN_REJECT"
    return EvaluationResult(
        candidate_id=candidate_id, status=status,
        reject_reason=reject_reason, blocker_reason=None,
        gross_bps=gross_bps, cost_bps=cost_bps, net_bps=net_bps,
        trade_count=trade_count, long_trade_count=n_long, short_trade_count=n_short,
        a1_pass=bool(a1_pass), a2_pass=bool(a2_pass),
    )
