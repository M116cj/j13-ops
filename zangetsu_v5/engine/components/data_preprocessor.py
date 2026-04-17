"""Data Preprocessor — Nondimensionalization module for Zangetsu V5.

Transforms raw OHLCV + funding + OI into scale-free features (5 factor categories).
All outputs are unitless (no USD dependency).

Factor Categories:
  F1: Momentum  — returns, log_returns (+ indicator-level: RSI, PPO, ROC, etc.)
  F2: Volatility — normalized_atr, realized_vol, bollinger_bw, garman_klass, normalized_range
  F3: Volume     — relative_volume, volume_ratio, vwap_deviation, volume_price_corr (+ MFI)
  F4: Funding    — funding_rate, funding_zscore, cumulative_funding
  F5: OI         — oi_change, oi_relative, oi_price_divergence

Usage:
    from zangetsu_v5.engine.components.data_preprocessor import enrich_data_cache
    enrich_data_cache(data_cache)  # mutates in-place
"""
from __future__ import annotations

import numpy as np
from typing import Dict

try:
    from numba import njit
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False
    def njit(*args, **kwargs):
        def wrapper(fn):
            return fn
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return wrapper


# ═══════════════════════════════════════════════════════════════════
# F1: Momentum
# ═══════════════════════════════════════════════════════════════════

@njit(cache=True)
def compute_returns(close: np.ndarray) -> np.ndarray:
    """Simple returns: r(t) = (C(t) - C(t-1)) / C(t-1)."""
    n = len(close)
    r = np.zeros(n, dtype=np.float64)
    for i in range(1, n):
        if close[i - 1] != 0.0:
            r[i] = (close[i] - close[i - 1]) / close[i - 1]
    return r


@njit(cache=True)
def compute_log_returns(close: np.ndarray) -> np.ndarray:
    """Log returns: ln(C(t) / C(t-1))."""
    n = len(close)
    lr = np.zeros(n, dtype=np.float64)
    for i in range(1, n):
        if close[i - 1] > 0.0:
            ratio = close[i] / close[i - 1]
            if ratio > 1e-15:
                lr[i] = np.log(ratio)
    return lr


# ═══════════════════════════════════════════════════════════════════
# F2: Volatility
# ═══════════════════════════════════════════════════════════════════

@njit(cache=True)
def compute_normalized_range(high: np.ndarray, low: np.ndarray,
                              close: np.ndarray) -> np.ndarray:
    """Normalized range: (H - L) / C. Scale-free volatility proxy."""
    n = len(close)
    nr = np.zeros(n, dtype=np.float64)
    for i in range(n):
        if close[i] > 0.0:
            nr[i] = (high[i] - low[i]) / close[i]
    return nr


@njit(cache=True)
def compute_normalized_atr(high: np.ndarray, low: np.ndarray,
                            close: np.ndarray, period: int = 14) -> np.ndarray:
    """Normalized ATR: ATR(period) / close. Scale-free."""
    n = len(close)
    natr = np.zeros(n, dtype=np.float64)
    if n < 2:
        return natr

    # True Range
    tr = np.zeros(n, dtype=np.float64)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i - 1])
        lc = abs(low[i] - close[i - 1])
        tr[i] = max(hl, hc, lc)

    # EMA-style ATR
    atr = np.zeros(n, dtype=np.float64)
    # Seed with SMA
    if n >= period:
        s = 0.0
        for i in range(period):
            s += tr[i]
        atr[period - 1] = s / period
        for i in range(period, n):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
        for i in range(period - 1, n):
            if close[i] > 0.0:
                natr[i] = atr[i] / close[i]
    return natr


@njit(cache=True)
def compute_realized_volatility(log_returns: np.ndarray, window: int = 20) -> np.ndarray:
    """Realized volatility: rolling std of log returns."""
    n = len(log_returns)
    rv = np.zeros(n, dtype=np.float64)
    if n < window:
        return rv

    # Rolling variance via running sums
    sum1 = 0.0
    sum2 = 0.0
    for i in range(window):
        sum1 += log_returns[i]
        sum2 += log_returns[i] * log_returns[i]
    var = sum2 / window - (sum1 / window) ** 2
    rv[window - 1] = np.sqrt(max(var, 0.0))

    for i in range(window, n):
        old = log_returns[i - window]
        new = log_returns[i]
        sum1 += new - old
        sum2 += new * new - old * old
        var = sum2 / window - (sum1 / window) ** 2
        rv[i] = np.sqrt(max(var, 0.0))
    return rv


@njit(cache=True)
def compute_bollinger_bw(close: np.ndarray, window: int = 20) -> np.ndarray:
    """Bollinger Bandwidth: (upper - lower) / middle = 2*2*std / SMA = 4*std/SMA."""
    n = len(close)
    bw = np.zeros(n, dtype=np.float64)
    if n < window:
        return bw

    sum1 = 0.0
    sum2 = 0.0
    for i in range(window):
        sum1 += close[i]
        sum2 += close[i] * close[i]

    mean = sum1 / window
    var = sum2 / window - mean * mean
    if mean > 0.0:
        bw[window - 1] = 4.0 * np.sqrt(max(var, 0.0)) / mean

    for i in range(window, n):
        old = close[i - window]
        new = close[i]
        sum1 += new - old
        sum2 += new * new - old * old
        mean = sum1 / window
        var = sum2 / window - mean * mean
        if mean > 0.0:
            bw[i] = 4.0 * np.sqrt(max(var, 0.0)) / mean
    return bw


@njit(cache=True)
def compute_garman_klass(open_: np.ndarray, high: np.ndarray,
                          low: np.ndarray, close: np.ndarray,
                          window: int = 20) -> np.ndarray:
    """Garman-Klass volatility estimator (nondimensional).
    GK = 0.5 * ln(H/L)^2 - (2ln2 - 1) * ln(C/O)^2, then rolling mean."""
    n = len(close)
    gk = np.zeros(n, dtype=np.float64)
    if n < 2:
        return gk

    LN2 = np.log(2.0)
    bar_gk = np.zeros(n, dtype=np.float64)
    for i in range(n):
        l_val = low[i] if low[i] > 0.0 else 1e-15
        o_val = open_[i] if open_[i] > 0.0 else 1e-15
        hl = np.log(high[i] / l_val)
        co = np.log(close[i] / o_val)
        bar_gk[i] = 0.5 * hl * hl - (2.0 * LN2 - 1.0) * co * co

    # Rolling mean
    if n >= window:
        s = 0.0
        for i in range(window):
            s += bar_gk[i]
        gk[window - 1] = s / window
        for i in range(window, n):
            s += bar_gk[i] - bar_gk[i - window]
            gk[i] = s / window
    return gk


# ═══════════════════════════════════════════════════════════════════
# F3: Volume
# ═══════════════════════════════════════════════════════════════════

@njit(cache=True)
def compute_relative_volume(volume: np.ndarray, window: int = 20) -> np.ndarray:
    """Relative volume: V / SMA(V, window)."""
    n = len(volume)
    rv = np.zeros(n, dtype=np.float64)
    if n == 0:
        return rv

    # Expanding mean for warmup
    cumsum = 0.0
    for i in range(min(window, n)):
        cumsum += volume[i]
        mean_val = cumsum / (i + 1)
        if mean_val > 0.0:
            rv[i] = volume[i] / mean_val

    # Rolling mean after warmup
    if n > window:
        roll_sum = cumsum
        for i in range(window, n):
            roll_sum += volume[i] - volume[i - window]
            mean_val = roll_sum / window
            if mean_val > 0.0:
                rv[i] = volume[i] / mean_val
    return rv


@njit(cache=True)
def compute_volume_ratio(volume: np.ndarray) -> np.ndarray:
    """Volume ratio: V(t) / V(t-1)."""
    n = len(volume)
    vr = np.zeros(n, dtype=np.float64)
    for i in range(1, n):
        if volume[i - 1] > 0.0:
            vr[i] = volume[i] / volume[i - 1]
    return vr


@njit(cache=True)
def compute_vwap_deviation(close: np.ndarray, volume: np.ndarray) -> np.ndarray:
    """VWAP deviation: (close - VWAP) / VWAP. Cumulative intraday reset not possible
    on 1m bars without session boundaries, so we use rolling 390-bar (≈1 session) VWAP."""
    n = len(close)
    vd = np.zeros(n, dtype=np.float64)
    window = 390  # ~6.5 hours
    if n < window:
        return vd

    sum_pv = 0.0
    sum_v = 0.0
    for i in range(window):
        sum_pv += close[i] * volume[i]
        sum_v += volume[i]
    if sum_v > 0.0:
        vwap = sum_pv / sum_v
        if vwap > 0.0:
            vd[window - 1] = (close[window - 1] - vwap) / vwap

    for i in range(window, n):
        old_pv = close[i - window] * volume[i - window]
        old_v = volume[i - window]
        sum_pv += close[i] * volume[i] - old_pv
        sum_v += volume[i] - old_v
        if sum_v > 0.0:
            vwap = sum_pv / sum_v
            if vwap > 0.0:
                vd[i] = (close[i] - vwap) / vwap
    return vd


@njit(cache=True)
def compute_volume_price_corr(returns: np.ndarray, rel_volume: np.ndarray,
                               window: int = 20) -> np.ndarray:
    """Rolling correlation between returns and relative volume."""
    n = len(returns)
    corr = np.zeros(n, dtype=np.float64)
    if n < window:
        return corr

    for i in range(window - 1, n):
        start = i - window + 1
        sum_x = 0.0; sum_y = 0.0; sum_xy = 0.0; sum_x2 = 0.0; sum_y2 = 0.0
        for j in range(start, i + 1):
            x = returns[j]
            y = rel_volume[j]
            sum_x += x; sum_y += y
            sum_xy += x * y
            sum_x2 += x * x; sum_y2 += y * y
        n_w = float(window)
        denom_x = sum_x2 - sum_x * sum_x / n_w
        denom_y = sum_y2 - sum_y * sum_y / n_w
        if denom_x > 1e-15 and denom_y > 1e-15:
            corr[i] = (sum_xy - sum_x * sum_y / n_w) / np.sqrt(denom_x * denom_y)
    return corr


# ═══════════════════════════════════════════════════════════════════
# F4: Funding Rate
# ═══════════════════════════════════════════════════════════════════

@njit(cache=True)
def compute_funding_zscore(funding_rate: np.ndarray, window: int = 100) -> np.ndarray:
    """Z-score of funding rate over rolling window."""
    n = len(funding_rate)
    zs = np.zeros(n, dtype=np.float64)
    if n < window:
        return zs

    sum1 = 0.0; sum2 = 0.0
    for i in range(window):
        sum1 += funding_rate[i]
        sum2 += funding_rate[i] * funding_rate[i]

    mean = sum1 / window
    var = sum2 / window - mean * mean
    std = np.sqrt(max(var, 0.0))
    if std > 1e-15:
        zs[window - 1] = (funding_rate[window - 1] - mean) / std

    for i in range(window, n):
        old = funding_rate[i - window]
        new = funding_rate[i]
        sum1 += new - old
        sum2 += new * new - old * old
        mean = sum1 / window
        var = sum2 / window - mean * mean
        std = np.sqrt(max(var, 0.0))
        if std > 1e-15:
            zs[i] = (new - mean) / std
    return zs


@njit(cache=True)
def compute_cumulative_funding(funding_rate: np.ndarray, window: int = 90) -> np.ndarray:
    """Rolling sum of funding rate over window (30 days * 3 = 90 8h periods)."""
    n = len(funding_rate)
    cf = np.zeros(n, dtype=np.float64)
    if n < window:
        return cf

    s = 0.0
    for i in range(window):
        s += funding_rate[i]
    cf[window - 1] = s
    for i in range(window, n):
        s += funding_rate[i] - funding_rate[i - window]
        cf[i] = s
    return cf


# ═══════════════════════════════════════════════════════════════════
# F5: Open Interest
# ═══════════════════════════════════════════════════════════════════

@njit(cache=True)
def compute_oi_change(oi: np.ndarray) -> np.ndarray:
    """OI change rate: (OI(t) - OI(t-1)) / OI(t-1)."""
    n = len(oi)
    oc = np.zeros(n, dtype=np.float64)
    for i in range(1, n):
        if oi[i - 1] > 0.0:
            oc[i] = (oi[i] - oi[i - 1]) / oi[i - 1]
    return oc


@njit(cache=True)
def compute_oi_relative(oi: np.ndarray, window: int = 20) -> np.ndarray:
    """OI relative to SMA(OI, window)."""
    n = len(oi)
    orel = np.zeros(n, dtype=np.float64)
    if n == 0:
        return orel

    cumsum = 0.0
    for i in range(min(window, n)):
        cumsum += oi[i]
        mean_val = cumsum / (i + 1)
        if mean_val > 0.0:
            orel[i] = oi[i] / mean_val

    if n > window:
        roll_sum = cumsum
        for i in range(window, n):
            roll_sum += oi[i] - oi[i - window]
            mean_val = roll_sum / window
            if mean_val > 0.0:
                orel[i] = oi[i] / mean_val
    return orel


@njit(cache=True)
def compute_oi_price_divergence(oi_change: np.ndarray, returns: np.ndarray) -> np.ndarray:
    """OI-price divergence: +1 if same direction, -1 if opposite, 0 if either ~0."""
    n = len(oi_change)
    div = np.zeros(n, dtype=np.float64)
    for i in range(n):
        if abs(oi_change[i]) > 1e-10 and abs(returns[i]) > 1e-10:
            if (oi_change[i] > 0 and returns[i] > 0) or (oi_change[i] < 0 and returns[i] < 0):
                div[i] = 1.0   # convergence — OI confirms price
            else:
                div[i] = -1.0  # divergence — OI contradicts price
    return div




# ═══════════════════════════════════════════════════════════════════
# V9: Wavelet Denoising — applied to OHLCV before indicator computation
# ═══════════════════════════════════════════════════════════════════

def wavelet_denoise(arr: np.ndarray, wavelet: str = 'coif4', level: int = 2,
                    mode: str = 'soft') -> np.ndarray:
    """Denoise a 1D array using wavelet decomposition.
    
    Uses coif4 wavelet with level-2 decomposition and soft thresholding.
    Research shows +25-41 dB SNR improvement on financial time series.
    Returns denoised array of same shape.
    """
    try:
        import pywt
    except ImportError:
        return arr  # graceful fallback if PyWavelets not installed
    
    if len(arr) < 2 ** (level + 1):
        return arr  # too short for decomposition
    
    # Decompose
    coeffs = pywt.wavedec(arr, wavelet, level=level)
    
    # Universal threshold (VisuShrink)
    # sigma estimated from finest detail coefficients (MAD estimator)
    detail = coeffs[-1]
    sigma = np.median(np.abs(detail)) / 0.6745
    threshold = sigma * np.sqrt(2 * np.log(len(arr)))
    
    # Apply soft thresholding to detail coefficients (keep approximation intact)
    denoised_coeffs = [coeffs[0]]  # keep approximation
    for c in coeffs[1:]:
        if mode == 'soft':
            denoised_coeffs.append(pywt.threshold(c, threshold, mode='soft'))
        else:
            denoised_coeffs.append(pywt.threshold(c, threshold, mode='hard'))
    
    # Reconstruct
    result = pywt.waverec(denoised_coeffs, wavelet)
    
    # waverec may add 1 sample; trim to original length
    return result[:len(arr)].astype(arr.dtype)


def denoise_ohlcv(d: dict) -> dict:
    """Apply wavelet denoising to close, high, low in a data split dict.
    Volume and funding/OI are NOT denoised (structural data, not price signals).
    Returns the same dict with denoised arrays added as _denoised variants.
    """
    for col in ('close', 'high', 'low'):
        if col in d:
            d[f'{col}_raw'] = d[col]  # preserve raw for backtesting
            d[col] = wavelet_denoise(d[col])
    return d

# ═══════════════════════════════════════════════════════════════════
# Enrichment: apply all factors to data_cache
# ═══════════════════════════════════════════════════════════════════

def enrich_data_cache(data_cache: Dict[str, Dict]) -> None:
    """Add nondimensional features to data_cache in-place.

    For each symbol, adds to both 'train' and 'holdout' splits:
        F1: returns, log_returns
        F2: normalized_range, normalized_atr, realized_vol, bollinger_bw, garman_klass
        F3: normalized_volume (=relative_volume), volume_ratio, vwap_deviation, volume_price_corr
        F4: funding_rate, funding_zscore, cumulative_funding (if funding data present)
        F5: oi_change, oi_relative, oi_price_divergence (if OI data present)
    """
    for sym, sym_data in data_cache.items():
        for split_name in ("train", "holdout"):
            if split_name not in sym_data:
                continue
            d = sym_data[split_name]
            
            # V9: Wavelet denoise OHLCV before indicator computation
            denoise_ohlcv(d)
            
            close = d["close"]
            high = d["high"]
            low = d["low"]
            volume = d["volume"]

            # F1: Momentum
            returns = compute_returns(close)
            log_ret = compute_log_returns(close)
            d["returns"] = returns
            d["log_returns"] = log_ret

            # F2: Volatility
            d["normalized_range"] = compute_normalized_range(high, low, close)
            d["normalized_atr"] = compute_normalized_atr(high, low, close, period=14)
            d["realized_vol"] = compute_realized_volatility(log_ret, window=20)
            d["bollinger_bw"] = compute_bollinger_bw(close, window=20)

            # Garman-Klass needs open
            open_arr = d.get("open")
            if open_arr is None:
                open_arr = np.roll(close, 1)
                open_arr[0] = close[0]
            d["garman_klass"] = compute_garman_klass(open_arr, high, low, close, window=20)

            # F3: Volume
            rel_vol = compute_relative_volume(volume, window=20)
            d["normalized_volume"] = rel_vol  # backward compat alias
            d["relative_volume"] = rel_vol
            d["volume_ratio"] = compute_volume_ratio(volume)
            d["vwap_deviation"] = compute_vwap_deviation(close, volume)
            d["volume_price_corr"] = compute_volume_price_corr(returns, rel_vol, window=20)

            # F4: Funding Rate (if loaded)
            if "funding_rate" in d:
                fr = d["funding_rate"]
                d["funding_zscore"] = compute_funding_zscore(fr, window=100)
                d["cumulative_funding"] = compute_cumulative_funding(fr, window=90)

            # F5: Open Interest (if loaded)
            if "oi" in d:
                oi = d["oi"]
                oi_chg = compute_oi_change(oi)
                d["oi_change"] = oi_chg
                d["oi_relative"] = compute_oi_relative(oi, window=20)
                d["oi_price_divergence"] = compute_oi_price_divergence(oi_chg, returns)
