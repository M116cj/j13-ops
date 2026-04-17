"""13-state causal-only regime labeler for 4H bars.

Classifies market regime using ATR, ADX, EMA slopes, and rolling
volatility. CAUSAL ONLY: label[i] uses exclusively data[..=i].
No lookahead, no future data leakage.

Regime states:
    0  = quiet_range          (low vol, low ADX)
    1  = trending_up_weak     (EMA slope +, ADX 15-25)
    2  = trending_up_strong   (EMA slope +, ADX > 25)
    3  = trending_down_weak   (EMA slope -, ADX 15-25)
    4  = trending_down_strong (EMA slope -, ADX > 25)
    5  = high_vol_up          (high ATR, positive drift)
    6  = high_vol_down        (high ATR, negative drift)
    7  = mean_revert          (price near EMA, low ADX, moderate vol)
    8  = breakout_up          (price breaks upper band)
    9  = breakout_down        (price breaks lower band)
    10 = compression          (ATR contracting, Bollinger squeeze)
    11 = expansion            (ATR expanding from compression)
    12 = choppy               (ADX < 15, moderate-high vol)
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


# -- Resampling -------------------------------------------------------

def resample_to_4h(df_1m: pd.DataFrame) -> pd.DataFrame:
    """Resample 1-minute OHLCV to 4-hour bars.

    Expects columns: open, high, low, close, volume.
    Index must be a DatetimeIndex or a 'timestamp' column.
    """
    if not isinstance(df_1m.index, pd.DatetimeIndex):
        if "timestamp" in df_1m.columns:
            df_1m = df_1m.set_index("timestamp")
        else:
            raise ValueError("Need DatetimeIndex or 'timestamp' column")

    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    df_4h = df_1m.resample("4h").agg(agg).dropna(subset=["close"])
    return df_4h


# -- Causal indicator helpers -----------------------------------------

def _ema(series: np.ndarray, span: int) -> np.ndarray:
    """Causal EMA via recursive formula. No future data."""
    out = np.empty_like(series)
    alpha = 2.0 / (span + 1)
    out[0] = series[0]
    for i in range(1, len(series)):
        out[i] = alpha * series[i] + (1 - alpha) * out[i - 1]
    return out


def _true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    """True range, causal. First bar uses high-low."""
    tr = np.empty(len(high))
    tr[0] = high[0] - low[0]
    for i in range(1, len(high)):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )
    return tr


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray,
         period: int = 14) -> np.ndarray:
    """Average True Range, causal EMA smoothing."""
    tr = _true_range(high, low, close)
    return _ema(tr, period)


def _adx(high: np.ndarray, low: np.ndarray, close: np.ndarray,
         period: int = 14) -> np.ndarray:
    """ADX (Average Directional Index), fully causal.

    Returns array of same length; first `period` values are approximate.
    """
    n = len(high)
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)

    for i in range(1, n):
        up = high[i] - high[i - 1]
        down = low[i - 1] - low[i]
        if up > down and up > 0:
            plus_dm[i] = up
        if down > up and down > 0:
            minus_dm[i] = down

    atr_arr = _atr(high, low, close, period)
    smooth_plus = _ema(plus_dm, period)
    smooth_minus = _ema(minus_dm, period)

    plus_di = np.zeros(n)
    minus_di = np.zeros(n)
    dx = np.zeros(n)

    for i in range(n):
        if atr_arr[i] > 0:
            plus_di[i] = 100.0 * smooth_plus[i] / atr_arr[i]
            minus_di[i] = 100.0 * smooth_minus[i] / atr_arr[i]
        di_sum = plus_di[i] + minus_di[i]
        if di_sum > 0:
            dx[i] = 100.0 * abs(plus_di[i] - minus_di[i]) / di_sum

    adx_out = _ema(dx, period)
    return adx_out


def _rolling_std(arr: np.ndarray, window: int) -> np.ndarray:
    """Causal rolling standard deviation."""
    out = np.zeros(len(arr))
    for i in range(len(arr)):
        start = max(0, i - window + 1)
        out[i] = np.std(arr[start:i + 1])
    return out


def _ema_slope(ema_arr: np.ndarray, lookback: int = 3) -> np.ndarray:
    """Causal slope of EMA over lookback bars."""
    slope = np.zeros(len(ema_arr))
    for i in range(lookback, len(ema_arr)):
        slope[i] = ema_arr[i] - ema_arr[i - lookback]
    return slope


# -- Core labeler ------------------------------------------------------

def label_4h_causal(
    df_4h: pd.DataFrame,
    atr_period: int = 14,
    adx_period: int = 14,
    ema_period: int = 21,
    vol_window: int = 20,
    bb_window: int = 20,
    bb_mult: float = 2.0,
) -> np.ndarray:
    """Label every 4H bar with one of 13 regime states.

    CAUSAL: label[i] depends only on data[..=i]. Safe for live use.

    Args:
        df_4h: DataFrame with columns [open, high, low, close, volume].

    Returns:
        np.ndarray of int regime labels, same length as df_4h.
    """
    high = df_4h["high"].values.astype(np.float64)
    low = df_4h["low"].values.astype(np.float64)
    close = df_4h["close"].values.astype(np.float64)
    n = len(close)

    # Compute causal indicators
    atr = _atr(high, low, close, atr_period)
    adx = _adx(high, low, close, adx_period)
    ema = _ema(close, ema_period)
    slope = _ema_slope(ema, lookback=3)
    vol = _rolling_std(close, vol_window)

    # Bollinger bands (causal)
    bb_ma = np.zeros(n)
    bb_std = np.zeros(n)
    for i in range(n):
        start = max(0, i - bb_window + 1)
        bb_ma[i] = np.mean(close[start:i + 1])
        bb_std[i] = np.std(close[start:i + 1])
    bb_upper = bb_ma + bb_mult * bb_std
    bb_lower = bb_ma - bb_mult * bb_std

    # ATR percentile (causal rolling)
    atr_pct = np.zeros(n)
    for i in range(1, n):
        window = atr[max(0, i - 100):i + 1]
        rank = np.sum(window <= atr[i])
        atr_pct[i] = rank / len(window)

    # ATR rate of change (causal, 5-bar)
    atr_roc = np.zeros(n)
    for i in range(5, n):
        if atr[i - 5] > 0:
            atr_roc[i] = (atr[i] - atr[i - 5]) / atr[i - 5]

    # Bandwidth squeeze detection
    bw = np.zeros(n)
    for i in range(n):
        if bb_ma[i] > 0:
            bw[i] = (bb_upper[i] - bb_lower[i]) / bb_ma[i]

    bw_pct = np.zeros(n)
    for i in range(1, n):
        window = bw[max(0, i - 100):i + 1]
        rank = np.sum(window <= bw[i])
        bw_pct[i] = rank / len(window)

    # Classify each bar
    labels = np.zeros(n, dtype=np.int32)
    for i in range(n):
        labels[i] = _classify_bar(
            adx_val=adx[i],
            slope_val=slope[i],
            atr_pct_val=atr_pct[i],
            atr_roc_val=atr_roc[i],
            close_val=close[i],
            ema_val=ema[i],
            bb_upper_val=bb_upper[i],
            bb_lower_val=bb_lower[i],
            bw_pct_val=bw_pct[i],
            vol_val=vol[i],
            vol_median=np.median(vol[max(0, i - 100):i + 1]),
        )
    return labels


def _classify_bar(
    adx_val: float,
    slope_val: float,
    atr_pct_val: float,
    atr_roc_val: float,
    close_val: float,
    ema_val: float,
    bb_upper_val: float,
    bb_lower_val: float,
    bw_pct_val: float,
    vol_val: float,
    vol_median: float,
) -> int:
    """Classify a single bar into one of 13 regime states."""
    high_vol = atr_pct_val > 0.8
    low_vol = atr_pct_val < 0.3
    squeeze = bw_pct_val < 0.1
    expanding = atr_roc_val > 0.15

    # 10: Compression (squeeze)
    if squeeze and adx_val < 20:
        return 10

    # 11: Expansion (coming out of squeeze)
    if expanding and atr_roc_val > 0.2:
        return 11

    # 8: Breakout up
    if close_val > bb_upper_val and slope_val > 0 and adx_val > 20:
        return 8

    # 9: Breakout down
    if close_val < bb_lower_val and slope_val < 0 and adx_val > 20:
        return 9

    # 5: High vol up
    if high_vol and slope_val > 0:
        return 5

    # 6: High vol down
    if high_vol and slope_val < 0:
        return 6

    # 2: Strong trend up
    if adx_val > 25 and slope_val > 0:
        return 2

    # 4: Strong trend down
    if adx_val > 25 and slope_val < 0:
        return 4

    # 1: Weak trend up
    if 15 <= adx_val <= 25 and slope_val > 0:
        return 1

    # 3: Weak trend down
    if 15 <= adx_val <= 25 and slope_val < 0:
        return 3

    # 7: Mean reversion
    if adx_val < 15 and vol_val <= vol_median * 1.2:
        dist = abs(close_val - ema_val) / ema_val if ema_val > 0 else 1.0
        if dist < 0.01:
            return 7

    # 12: Choppy
    if adx_val < 15 and vol_val > vol_median * 0.8:
        return 12

    # 0: Quiet range (default)
    return 0


def label_latest(buffer_4h: pd.DataFrame) -> int:
    """Label only the latest bar from a rolling 4H buffer.

    Expects a DataFrame with at least ~100 bars for proper indicator warmup.
    Returns the regime label (int) for the final bar.
    """
    if len(buffer_4h) < 2:
        return 0  # insufficient data -> quiet range
    labels = label_4h_causal(buffer_4h)
    return int(labels[-1])
