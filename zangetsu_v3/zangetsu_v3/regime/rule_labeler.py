"""Rule-based 13-state regime labeler on 4h resampled bars (C02, C03, C05).

Offline labeler with full lookback/lookahead. Output broadcasts back to 1m bars.
Two-pass approach:
  Pass 1: Assign base regimes (trend, consolidation, squeeze, choppy, special)
  Pass 2: Use lookahead to carve pullback/rally/topping/bottoming from trends
"""
from __future__ import annotations

from enum import IntEnum

import numpy as np
import polars as pl


class Regime(IntEnum):
    BULL_TREND = 0
    BEAR_TREND = 1
    BULL_PULLBACK = 2
    BEAR_RALLY = 3
    DISTRIBUTION = 4
    ACCUMULATION = 5
    CONSOLIDATION = 6
    CHOPPY_VOLATILE = 7
    SQUEEZE = 8
    TOPPING = 9
    BOTTOMING = 10
    LIQUIDITY_CRISIS = 11
    PARABOLIC = 12


REGIME_NAMES = {r.value: r.name for r in Regime}

SEARCH_REGIMES = {
    "BULL_TREND": [Regime.BULL_TREND, Regime.BULL_PULLBACK, Regime.BOTTOMING],
    "BEAR_TREND": [Regime.BEAR_TREND, Regime.BEAR_RALLY, Regime.TOPPING],
    "CONSOLIDATION": [Regime.CONSOLIDATION, Regime.ACCUMULATION, Regime.DISTRIBUTION],
    "SQUEEZE": [Regime.SQUEEZE],
}


def resample_to_4h(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df.sort("timestamp")
        .group_by_dynamic("timestamp", every="4h")
        .agg([
            pl.col("open").first(),
            pl.col("high").max(),
            pl.col("low").min(),
            pl.col("close").last(),
            pl.col("volume").sum(),
        ])
    )


def _compute_features(df_4h: pl.DataFrame) -> dict:
    """Compute structural features. Returns dict of numpy arrays."""
    close = df_4h["close"].to_numpy().astype(np.float64)
    high = df_4h["high"].to_numpy().astype(np.float64)
    low = df_4h["low"].to_numpy().astype(np.float64)
    volume = df_4h["volume"].to_numpy().astype(np.float64)
    n = len(close)

    ma20 = _rolling_mean(close, 20)
    ma50 = _rolling_mean(close, 50)
    ma_slope_20 = np.full(n, np.nan)
    ma_slope_20[5:] = (ma20[5:] - ma20[:-5]) / (ma20[:-5] + 1e-12)

    adx = _adx(high, low, close, 14)
    atr = _atr(high, low, close, 14)
    atr_pct = _rolling_percentile(atr, 100)

    bb_std = _rolling_std(close, 20)
    bb_width = 2 * bb_std / (ma20 + 1e-12)
    bb_width_pct = _rolling_percentile(bb_width, 100)

    # Swing detection (5-bar)
    swing_high = _rolling_max(high, 5)
    swing_low = _rolling_min(low, 5)
    hh = np.zeros(n)
    ll = np.zeros(n)
    for i in range(10, n):
        hh[i] = 1.0 if swing_high[i] > swing_high[i - 5] else (-1.0 if swing_high[i] < swing_high[i - 5] else 0.0)
        ll[i] = 1.0 if swing_low[i] > swing_low[i - 5] else (-1.0 if swing_low[i] < swing_low[i - 5] else 0.0)

    vol_ma20 = _rolling_mean(volume, 20)
    vol_ratio = volume / (vol_ma20 + 1e-12)

    daily_ret = np.full(n, np.nan)
    daily_ret[6:] = (close[6:] - close[:-6]) / (close[:-6] + 1e-12)

    ret_3d = np.full(n, np.nan)
    ret_3d[18:] = (close[18:] - close[:-18]) / (close[:-18] + 1e-12)

    range_high = _rolling_max(high, 50)
    range_low = _rolling_min(low, 50)
    rel_pos = (close - range_low) / (range_high - range_low + 1e-12)

    # Per-bar return (for pullback/rally detection)
    bar_ret = np.zeros(n)
    bar_ret[1:] = (close[1:] - close[:-1]) / (close[:-1] + 1e-12)

    return {
        "close": close, "high": high, "low": low, "volume": volume,
        "ma20": ma20, "ma50": ma50, "ma_slope_20": ma_slope_20,
        "adx": adx, "atr_pct": atr_pct, "bb_width_pct": bb_width_pct,
        "hh": hh, "ll": ll, "vol_ratio": vol_ratio,
        "daily_ret": daily_ret, "ret_3d": ret_3d, "rel_pos": rel_pos,
        "bar_ret": bar_ret,
    }


def _classify_13_regimes(feat: dict, n: int) -> np.ndarray:
    """Two-pass classification."""
    labels = np.full(n, Regime.CONSOLIDATION, dtype=np.int8)

    ms = feat["ma_slope_20"]
    adx_arr = feat["adx"]
    atr_pct = feat["atr_pct"]
    bb_pct = feat["bb_width_pct"]
    hh = feat["hh"]
    ll = feat["ll"]
    daily_ret = feat["daily_ret"]
    ret_3d = feat["ret_3d"]
    rel_pos = feat["rel_pos"]
    close = feat["close"]
    ma20 = feat["ma20"]
    bar_ret = feat["bar_ret"]

    # ── Pass 1: Base regimes ─────────────────────────────────────
    for i in range(50, n):
        if np.isnan(ms[i]):
            continue
        adx_i = adx_arr[i] if np.isfinite(adx_arr[i]) else 15.0

        # Special (highest priority)
        if not np.isnan(daily_ret[i]) and daily_ret[i] < -0.15:
            labels[i] = Regime.LIQUIDITY_CRISIS
            continue
        if not np.isnan(ret_3d[i]) and ret_3d[i] > 0.30:
            labels[i] = Regime.PARABOLIC
            continue

        # Volatility
        if atr_pct[i] < 15 and bb_pct[i] < 15:
            labels[i] = Regime.SQUEEZE
            continue
        # Choppy: high ATR + no trend (relaxed: ATR>60 or ADX<25)
        if atr_pct[i] > 60 and adx_i < 25:
            labels[i] = Regime.CHOPPY_VOLATILE
            continue

        # Trend
        bull_trend = ms[i] > 0.003 and (hh[i] > 0 or ll[i] > 0) and close[i] > ma20[i]
        bear_trend = ms[i] < -0.003 and (hh[i] < 0 or ll[i] < 0) and close[i] < ma20[i]

        if bull_trend:
            labels[i] = Regime.BULL_TREND
            continue
        if bear_trend:
            labels[i] = Regime.BEAR_TREND
            continue

        # Consolidation subtypes
        if adx_i < 25:
            if rel_pos[i] > 0.7:
                labels[i] = Regime.DISTRIBUTION
            elif rel_pos[i] < 0.3:
                labels[i] = Regime.ACCUMULATION
            else:
                labels[i] = Regime.CONSOLIDATION
            continue

        # Mild trend fallback
        if ms[i] > 0.001:
            labels[i] = Regime.BULL_TREND
        elif ms[i] < -0.001:
            labels[i] = Regime.BEAR_TREND

    # ── Pass 2: Carve pullback/rally from trends ─────────────────
    # Within BULL_TREND, consecutive >=2 bars of close[i] < close[i-1] → BULL_PULLBACK
    for i in range(51, n):
        if labels[i] == Regime.BULL_TREND:
            if bar_ret[i] < -0.001 and bar_ret[i - 1] < -0.001:
                labels[i] = Regime.BULL_PULLBACK
                if labels[i - 1] == Regime.BULL_TREND:
                    labels[i - 1] = Regime.BULL_PULLBACK
        elif labels[i] == Regime.BEAR_TREND:
            if bar_ret[i] > 0.001 and bar_ret[i - 1] > 0.001:
                labels[i] = Regime.BEAR_RALLY
                if labels[i - 1] == Regime.BEAR_TREND:
                    labels[i - 1] = Regime.BEAR_RALLY

    # ── Pass 3: Topping/Bottoming with lookahead ─────────────────
    # Find transitions: BULL→BEAR = topping zone, BEAR→BULL = bottoming zone
    # Mark the last N bars before transition
    TRANSITION_BARS = 5  # last 5 bars (20h) before regime flip

    for i in range(50, n - 1):
        # Find where BULL_TREND (or pullback) switches to BEAR_TREND (or rally/consol)
        cur_bull = labels[i] in (Regime.BULL_TREND, Regime.BULL_PULLBACK)
        cur_bear = labels[i] in (Regime.BEAR_TREND, Regime.BEAR_RALLY)

        if cur_bull:
            # Look ahead: does it become bear within TRANSITION_BARS?
            for j in range(i + 1, min(i + TRANSITION_BARS + 1, n)):
                if labels[j] in (Regime.BEAR_TREND, Regime.BEAR_RALLY, Regime.DISTRIBUTION):
                    # Mark i..j-1 as TOPPING
                    for k in range(max(i - TRANSITION_BARS + 1, 50), j):
                        if labels[k] in (Regime.BULL_TREND, Regime.BULL_PULLBACK):
                            labels[k] = Regime.TOPPING
                    break

        elif cur_bear:
            for j in range(i + 1, min(i + TRANSITION_BARS + 1, n)):
                if labels[j] in (Regime.BULL_TREND, Regime.BULL_PULLBACK, Regime.ACCUMULATION):
                    for k in range(max(i - TRANSITION_BARS + 1, 50), j):
                        if labels[k] in (Regime.BEAR_TREND, Regime.BEAR_RALLY):
                            labels[k] = Regime.BOTTOMING
                    break

    return labels


def _smooth_labels(labels: np.ndarray, min_segment_bars: int = 2) -> np.ndarray:
    """Remove regime flickers shorter than min_segment_bars."""
    smoothed = labels.copy()
    n = len(labels)
    i = 0
    while i < n:
        j = i + 1
        while j < n and labels[j] == labels[i]:
            j += 1
        seg_len = j - i
        if seg_len < min_segment_bars and i > 0:
            smoothed[i:j] = smoothed[i - 1]
        i = j
    return smoothed


def label_4h(df_4h: pl.DataFrame, smooth_bars: int = 2) -> np.ndarray:
    feat = _compute_features(df_4h)
    raw_labels = _classify_13_regimes(feat, len(df_4h))
    return _smooth_labels(raw_labels, smooth_bars)


def broadcast_to_1m(labels_4h: np.ndarray, n_1m: int, timestamps_4h: np.ndarray, timestamps_1m: np.ndarray) -> np.ndarray:
    labels_1m = np.full(n_1m, Regime.CONSOLIDATION, dtype=np.int8)
    j = 0
    for i in range(n_1m):
        while j < len(timestamps_4h) - 1 and timestamps_1m[i] >= timestamps_4h[j + 1]:
            j += 1
        labels_1m[i] = labels_4h[j]
    return labels_1m


def label_symbol(df_1m: pl.DataFrame, smooth_bars: int = 2) -> tuple[np.ndarray, np.ndarray, pl.DataFrame]:
    df_4h = resample_to_4h(df_1m)
    labels_4h = label_4h(df_4h, smooth_bars)
    ts_4h = df_4h["timestamp"].to_numpy()
    ts_1m = df_1m["timestamp"].to_numpy()
    labels_1m = broadcast_to_1m(labels_4h, len(df_1m), ts_4h, ts_1m)
    return labels_1m, labels_4h, df_4h


def regime_report(labels: np.ndarray, timeframe_minutes: int = 240) -> dict:
    n = len(labels)
    unique, counts = np.unique(labels, return_counts=True)
    transitions = int(np.sum(np.diff(labels) != 0))
    total_segments = transitions + 1

    per_regime = {}
    for u, c in zip(unique, counts):
        name = REGIME_NAMES.get(int(u), f"UNKNOWN_{u}")
        pct = float(c) / n * 100
        mask = labels == u
        diffs = np.diff(mask.astype(int))
        starts = int(np.sum(diffs == 1)) + (1 if mask[0] else 0)
        avg_bars = c / max(starts, 1)
        avg_hours = avg_bars * timeframe_minutes / 60
        per_regime[name] = {
            "bars": int(c), "pct": round(pct, 1),
            "segments": starts, "avg_hours": round(avg_hours, 1),
        }

    return {
        "n_bars": n, "total_segments": total_segments,
        "n_regimes_present": len(unique), "regimes": per_regime,
    }


def to_search_regime(labels_13: np.ndarray) -> np.ndarray:
    mapping = {}
    for search_name, fine_list in SEARCH_REGIMES.items():
        for r in fine_list:
            mapping[int(r)] = search_name
    mapping.setdefault(int(Regime.CHOPPY_VOLATILE), "CONSOLIDATION")
    mapping.setdefault(int(Regime.LIQUIDITY_CRISIS), "BEAR_TREND")
    mapping.setdefault(int(Regime.PARABOLIC), "BULL_TREND")

    result = np.empty(len(labels_13), dtype="U20")
    for i, lbl in enumerate(labels_13):
        result[i] = mapping.get(int(lbl), "CONSOLIDATION")
    return result


# ── numpy helpers ────────────────────────────────────────────────

def _rolling_mean(x, w):
    out = np.full_like(x, np.nan)
    cs = np.nancumsum(x)
    out[w - 1:] = (cs[w - 1:] - np.concatenate([[0], cs[:-w]])) / w
    return out

def _rolling_std(x, w):
    out = np.full_like(x, np.nan)
    for i in range(w - 1, len(x)):
        out[i] = np.std(x[i - w + 1:i + 1])
    return out

def _rolling_max(x, w):
    out = np.full_like(x, np.nan)
    for i in range(w - 1, len(x)):
        out[i] = np.max(x[i - w + 1:i + 1])
    return out

def _rolling_min(x, w):
    out = np.full_like(x, np.nan)
    for i in range(w - 1, len(x)):
        out[i] = np.min(x[i - w + 1:i + 1])
    return out

def _rolling_percentile(x, w):
    out = np.full_like(x, np.nan)
    for i in range(w - 1, len(x)):
        window = x[i - w + 1:i + 1]
        valid = window[np.isfinite(window)]
        if len(valid) > 0:
            out[i] = np.searchsorted(np.sort(valid), x[i]) / len(valid) * 100
    return out

def _atr(high, low, close, period):
    n = len(close)
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
    return _ema(tr, period)

def _ema(x, period):
    out = np.full_like(x, np.nan)
    alpha = 2.0 / (period + 1)
    start = 0
    while start < len(x) - period and not np.all(np.isfinite(x[start:start + period])):
        start += 1
    if start >= len(x) - period:
        return out
    out[start + period - 1] = np.mean(x[start:start + period])
    for i in range(start + period, len(x)):
        if np.isfinite(x[i]) and np.isfinite(out[i - 1]):
            out[i] = alpha * x[i] + (1 - alpha) * out[i - 1]
        elif np.isfinite(out[i - 1]):
            out[i] = out[i - 1]
    return out

def _adx(high, low, close, period=14):
    n = len(close)
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)
    for i in range(1, n):
        up = high[i] - high[i - 1]
        down = low[i - 1] - low[i]
        plus_dm[i] = up if (up > down and up > 0) else 0.0
        minus_dm[i] = down if (down > up and down > 0) else 0.0
    atr_vals = _atr(high, low, close, period)
    plus_di = _ema(plus_dm, period) / (atr_vals + 1e-12) * 100
    minus_di = _ema(minus_dm, period) / (atr_vals + 1e-12) * 100
    dx = np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-12) * 100
    return _ema(dx, period)


__all__ = [
    "Regime", "REGIME_NAMES", "SEARCH_REGIMES",
    "resample_to_4h", "label_4h", "label_symbol", "broadcast_to_1m",
    "regime_report", "to_search_regime",
]
