"""HFT factor pool: 15 factors with lookback ≤ 10 bars.

Derived from Arena 1 PySR search (ret_5, ret_9, range_3 as top signals)
+ directional extensions + microstructure.
"""
from __future__ import annotations

import numpy as np
import polars as pl

FACTOR_NAMES = [
    "ret_1", "ret_3", "ret_5", "ret_9",
    "ret5_sq", "ret3_sq",
    "range_3", "range_5", "range_10",
    "vol_surge_3", "vol_surge_5",
    "bar_body", "upper_shadow", "lower_shadow",
    "vol_price_corr_5",
]

N_FACTORS = len(FACTOR_NAMES)  # 15


def compute_hft_factors(df: pl.DataFrame) -> pl.DataFrame:
    """Compute 15 HFT factors from OHLCV DataFrame.

    Expects columns: open, high, low, close, volume.
    All lookbacks ≤ 10 bars. Warmup = 10 bars (first 10 rows will have NaN).
    Returns DataFrame with 15 factor columns.
    """
    close = df["close"].to_numpy().astype(np.float64)
    high = df["high"].to_numpy().astype(np.float64)
    low = df["low"].to_numpy().astype(np.float64)
    open_ = df["open"].to_numpy().astype(np.float64)
    volume = df["volume"].to_numpy().astype(np.float64)
    n = len(close)

    factors = {}

    # Returns (1, 3, 5, 9 bar)
    for lag in [1, 3, 5, 9]:
        ret = np.full(n, np.nan)
        ret[lag:] = (close[lag:] - close[:-lag]) / (close[:-lag] + 1e-12)
        factors[f"ret_{lag}"] = ret

    # Signed square returns (mean reversion signal from PySR, stable distribution)
    r5 = factors["ret_5"]
    r3 = factors["ret_3"]
    factors["ret5_sq"] = np.sign(r5) * r5 ** 2
    factors["ret3_sq"] = np.sign(r3) * r3 ** 2

    # Range (3, 5, 10 bar)
    for w in [3, 5, 10]:
        rng = np.full(n, np.nan)
        for i in range(w, n):
            rng[i] = (np.max(high[i - w + 1:i + 1]) - np.min(low[i - w + 1:i + 1])) / (close[i] + 1e-12)
        factors[f"range_{w}"] = rng

    # Volume surge (vs 3 and 5 bar MA)
    for w in [3, 5]:
        vol_ma = np.full(n, np.nan)
        cs = np.nancumsum(volume)
        vol_ma[w - 1:] = (cs[w - 1:] - np.concatenate([[0], cs[:-w]])) / w
        factors[f"vol_surge_{w}"] = volume / (vol_ma + 1e-12)

    # Candle microstructure
    hl_range = high - low + 1e-8
    factors["bar_body"] = (close - open_) / hl_range
    factors["upper_shadow"] = (high - np.maximum(open_, close)) / hl_range
    factors["lower_shadow"] = (np.minimum(open_, close) - low) / hl_range

    # Volume-price correlation (5 bar rolling)
    vol_price_corr = np.full(n, np.nan)
    for i in range(4, n):
        c_win = close[i - 4:i + 1]
        v_win = volume[i - 4:i + 1]
        if np.std(c_win) > 1e-12 and np.std(v_win) > 1e-12:
            vol_price_corr[i] = np.corrcoef(c_win, v_win)[0, 1]
        else:
            vol_price_corr[i] = 0.0
    factors["vol_price_corr_5"] = vol_price_corr

    return pl.DataFrame({name: factors[name] for name in FACTOR_NAMES})


__all__ = ["compute_hft_factors", "FACTOR_NAMES", "N_FACTORS"]
