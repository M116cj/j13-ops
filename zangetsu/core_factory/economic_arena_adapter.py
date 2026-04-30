"""Shadow-only Economic Arena adapter (0-9AB + 0-9AC).

0-9AC additions:
- p99 absolute-magnitude signal clipping (axis H by default).
- Band-crossing trigger (axis D by default).
- LRU cache on per-(symbol, timeframe, axis) data dict to avoid reloading.
- Extended EvaluationResult with clip_metadata and trigger_metadata.

No DB write. No exchange API. No production runtime touched.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
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
from .signal_processing import (
    ClipMetadata,
    apply_p99_abs_clip,
    signal_to_trades_band_crossing,
    signal_to_trades_sign_flip,
)


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / 'zangetsu' / 'data'

TIMEFRAME_MINUTES = {
    '1m': 1, '5m': 5, '15m': 15, '30m': 30, '1h': 60, '4h': 240, '1d': 1440,
}


@dataclass
class EvaluationParams:
    value_clip: Optional[str] = None  # 'p99_abs' or None
    trigger: str = 'sign_flip'  # 'sign_flip' or 'band_crossing'
    band_k: float = 1.0
    rolling_sigma_window: int = 20


@dataclass
class EvaluationResult:
    candidate_id: str
    status: str
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
    clip_metadata: Optional[dict] = None
    trigger_metadata: Optional[dict] = None


def _load_ohlcv(symbol: str, timeframe: str) -> pd.DataFrame | None:
    p = DATA_ROOT / 'ohlcv' / f'{symbol}.parquet'
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    df = df.dropna()
    if timeframe == '1m':
        return df
    minutes = TIMEFRAME_MINUTES.get(timeframe)
    if minutes is None:
        return None
    df = df.copy()
    df['bucket'] = (df['timestamp'] // (minutes * 60_000)) * (minutes * 60_000)
    g = df.groupby('bucket', sort=True).agg(
        open=('open', 'first'), high=('high', 'max'),
        low=('low', 'min'), close=('close', 'last'),
        volume=('volume', 'sum'),
    ).reset_index().rename(columns={'bucket': 'timestamp'})
    return g


def _load_funding(symbol: str) -> pd.DataFrame | None:
    p = DATA_ROOT / 'funding' / f'{symbol}.parquet'
    return None if not p.exists() else pd.read_parquet(p)


def _load_oi(symbol: str) -> pd.DataFrame | None:
    p = DATA_ROOT / 'oi' / f'{symbol}.parquet'
    return None if not p.exists() else pd.read_parquet(p)


def _align_to_grid(grid_ts: np.ndarray, src_ts: np.ndarray, src_val: np.ndarray) -> np.ndarray:
    idx = np.searchsorted(src_ts, grid_ts, side='right') - 1
    idx = np.clip(idx, 0, len(src_val) - 1)
    return src_val[idx].astype(np.float32)


# Cache built data dicts. Keyed by (symbol, timeframe, axis_id) — same axis_id
# uses same data layout. Caches are LRU-bounded to avoid memory growth across
# many symbols.
@lru_cache(maxsize=64)
def _build_data_dict_cached(symbol: str, timeframe: str, axis_id: str) -> tuple | None:
    ohlc = _load_ohlcv(symbol, timeframe)
    if ohlc is None or len(ohlc) < 100:
        return None
    out = {
        'open': ohlc['open'].to_numpy(dtype=np.float32),
        'high': ohlc['high'].to_numpy(dtype=np.float32),
        'low': ohlc['low'].to_numpy(dtype=np.float32),
        'close': ohlc['close'].to_numpy(dtype=np.float32),
        'volume': ohlc['volume'].to_numpy(dtype=np.float32),
    }
    if axis_id == 'H':
        ts = ohlc['timestamp'].to_numpy()
        f = _load_funding(symbol)
        o = _load_oi(symbol)
        if f is None or o is None or len(f) == 0 or len(o) == 0:
            out['funding'] = np.zeros(len(ohlc), dtype=np.float32)
            out['oi'] = np.zeros(len(ohlc), dtype=np.float32)
            out['__h_lite__'] = np.array([1.0], dtype=np.float32)
        else:
            out['funding'] = _align_to_grid(ts, f['timestamp'].to_numpy(),
                                            f['fundingRate'].to_numpy(dtype=np.float32))
            out['oi'] = _align_to_grid(ts, o['timestamp'].to_numpy(),
                                       o['sumOpenInterest'].to_numpy(dtype=np.float32))
    # tuple-ify to make cache hashable.
    return tuple(sorted(out.items()))


def _build_data_dict(symbol: str, timeframe: str, axis_id: str) -> dict[str, np.ndarray] | None:
    cached = _build_data_dict_cached(symbol, timeframe, axis_id)
    if cached is None:
        return None
    return dict(cached)


def _evaluate_ast(ast, data: dict[str, np.ndarray]) -> np.ndarray:
    if ast[0] == 'field':
        return evaluate_field(ast[1], data)
    if ast[0] == 'op':
        spec = get_primitive(ast[1])
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
    raise UnsupportedOperatorError(f'bad_node:{ast[0]}')


def evaluate_candidate(
    *,
    candidate_id: str,
    formula_ast,
    symbol: str,
    timeframe: str,
    axis_id: str,
    intended_side_mode: str,
    cost_bps_round_trip: float = ROUND_TRIP_COST_BPS,
    params: Optional[EvaluationParams] = None,
) -> EvaluationResult:
    params = params or EvaluationParams()
    data = _build_data_dict(symbol, timeframe, axis_id)
    if data is None:
        return EvaluationResult(
            candidate_id=candidate_id, status='NOT_EVALUATED',
            reject_reason=None, blocker_reason='AXIS_COMPONENT_UNAVAILABLE',
            gross_bps=0.0, cost_bps=0.0, net_bps=0.0,
            trade_count=0, long_trade_count=0, short_trade_count=0,
            a1_pass=None, a2_pass=None,
        )
    try:
        signal = _evaluate_ast(formula_ast, data)
    except UnsupportedOperatorError:
        return EvaluationResult(
            candidate_id=candidate_id, status='NOT_EVALUATED',
            reject_reason=None, blocker_reason='UNSUPPORTED_OPERATOR',
            gross_bps=0.0, cost_bps=0.0, net_bps=0.0,
            trade_count=0, long_trade_count=0, short_trade_count=0,
            a1_pass=None, a2_pass=None,
        )
    except Exception:
        return EvaluationResult(
            candidate_id=candidate_id, status='ERROR',
            reject_reason='evaluation_runtime_error', blocker_reason=None,
            gross_bps=0.0, cost_bps=0.0, net_bps=0.0,
            trade_count=0, long_trade_count=0, short_trade_count=0,
            a1_pass=None, a2_pass=None,
        )

    clip_meta_dict: Optional[dict] = None
    if params.value_clip == 'p99_abs':
        signal, cmeta = apply_p99_abs_clip(signal)
        clip_meta_dict = cmeta.to_dict()

    close = data['close']
    if params.trigger == 'band_crossing':
        returns, n_long, n_short = signal_to_trades_band_crossing(
            signal, close, intended_side_mode,
            band_k=params.band_k, rolling_sigma_window=params.rolling_sigma_window,
        )
        trigger_meta = {
            'trigger_type': 'band_crossing',
            'band_k': params.band_k,
            'rolling_sigma_window': params.rolling_sigma_window,
            'side_mode': intended_side_mode,
        }
    else:
        returns, n_long, n_short = signal_to_trades_sign_flip(
            signal, close, intended_side_mode,
        )
        trigger_meta = {
            'trigger_type': 'sign_flip',
            'side_mode': intended_side_mode,
        }

    trade_count = len(returns)
    if trade_count == 0:
        return EvaluationResult(
            candidate_id=candidate_id, status='REJECTED',
            reject_reason='no_trades_generated', blocker_reason=None,
            gross_bps=0.0, cost_bps=0.0, net_bps=0.0,
            trade_count=0, long_trade_count=0, short_trade_count=0,
            a1_pass=False, a2_pass=False,
            clip_metadata=clip_meta_dict, trigger_metadata=trigger_meta,
        )
    gross_bps = float(np.mean(returns))
    cost_bps = float(cost_bps_round_trip)
    net_bps = gross_bps - cost_bps
    a1_pass = trade_count >= 5
    a2_pass = (trade_count >= A2_MIN_TRADES) and (sum(returns) - trade_count * cost_bps) > 0
    if a2_pass:
        status = 'PASSED'
        reject_reason = None
    else:
        status = 'REJECTED'
        if trade_count < A2_MIN_TRADES:
            reject_reason = 'too_few_trades'
        elif net_bps <= 0:
            reject_reason = 'non_positive_net'
        else:
            reject_reason = 'UNKNOWN_REJECT'
    return EvaluationResult(
        candidate_id=candidate_id, status=status,
        reject_reason=reject_reason, blocker_reason=None,
        gross_bps=gross_bps, cost_bps=cost_bps, net_bps=net_bps,
        trade_count=trade_count, long_trade_count=n_long, short_trade_count=n_short,
        a1_pass=bool(a1_pass), a2_pass=bool(a2_pass),
        clip_metadata=clip_meta_dict, trigger_metadata=trigger_meta,
    )
