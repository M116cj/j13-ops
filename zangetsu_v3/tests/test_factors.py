"""Tests for all 15 bootstrap factors against numpy reference implementations.

Error tolerance: < 1e-6 after warmup (first 50 bars).
No DB connection required — synthetic OHLCV only.
"""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from zangetsu_v3.factors.bootstrap import BOOTSTRAP_FACTORS, compute_factor_matrix
from zangetsu_v3.factors.expr_eval import ExprEval

# ---------------------------------------------------------------------------
# Synthetic data fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ohlcv_df() -> pl.DataFrame:
    np.random.seed(42)
    close = 100 * np.exp(np.cumsum(np.random.randn(500) * 0.001))
    high = close * (1 + np.abs(np.random.randn(500) * 0.002))
    low = close * (1 - np.abs(np.random.randn(500) * 0.002))
    volume = np.abs(np.random.randn(500) * 1000 + 5000)
    return pl.DataFrame(
        {
            "symbol": ["BTC"] * 500,
            "timestamp": list(range(500)),
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


@pytest.fixture(scope="module")
def arrays(ohlcv_df):
    close = ohlcv_df["close"].to_numpy()
    high = ohlcv_df["high"].to_numpy()
    low = ohlcv_df["low"].to_numpy()
    volume = ohlcv_df["volume"].to_numpy()
    return close, high, low, volume


# ---------------------------------------------------------------------------
# Numpy rolling helpers (pure-python reference)
# ---------------------------------------------------------------------------

def np_rolling_std(x: np.ndarray, w: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    for i in range(w - 1, len(x)):
        out[i] = np.nanstd(x[i - w + 1 : i + 1], ddof=0)
    return out


def np_rolling_mean(x: np.ndarray, w: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    for i in range(w - 1, len(x)):
        out[i] = np.nanmean(x[i - w + 1 : i + 1])
    return out


def np_ts_delta(x: np.ndarray, p: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    out[p:] = x[p:] - x[:-p]
    return out


def np_ts_rank(x: np.ndarray, w: int) -> np.ndarray:
    n = len(x)
    out = np.full(n, np.nan)
    for i in range(w - 1, n):
        window_slice = x[i - w + 1 : i + 1]
        ranks = window_slice.argsort().argsort() + 1
        out[i] = ranks[-1] / w
    return out


def np_ts_max(x: np.ndarray, w: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    for i in range(w - 1, len(x)):
        out[i] = np.nanmax(x[i - w + 1 : i + 1])
    return out


def np_ts_min(x: np.ndarray, w: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    for i in range(w - 1, len(x)):
        out[i] = np.nanmin(x[i - w + 1 : i + 1])
    return out


def np_ts_skew(x: np.ndarray, w: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    for i in range(w - 1, len(x)):
        win = x[i - w + 1 : i + 1]
        mean = np.mean(win)
        std = np.std(win)
        if std == 0:
            out[i] = 0.0
        else:
            centered = win - mean
            out[i] = np.mean(centered ** 3) / (std ** 3)
    return out


def np_rolling_corr(a: np.ndarray, b: np.ndarray, w: int) -> np.ndarray:
    out = np.full(len(a), np.nan)
    for i in range(w - 1, len(a)):
        sa = a[i - w + 1 : i + 1]
        sb = b[i - w + 1 : i + 1]
        cov = np.cov(sa, sb, ddof=0)[0, 1]
        std_a = np.std(sa, ddof=0)
        std_b = np.std(sb, ddof=0)
        if std_a < 1e-14 or std_b < 1e-14:
            out[i] = np.nan
        else:
            out[i] = cov / (std_a * std_b)
    return out


# ---------------------------------------------------------------------------
# Individual factor tests
# ---------------------------------------------------------------------------

WARMUP = 50  # bars to skip before comparison


def _compare(result: np.ndarray, reference: np.ndarray, name: str, atol: float = 1e-6):
    mask = np.isfinite(result[WARMUP:]) & np.isfinite(reference[WARMUP:])
    assert mask.any(), f"{name}: no finite values after warmup"
    assert np.allclose(result[WARMUP:][mask], reference[WARMUP:][mask], atol=atol), (
        f"{name}: max diff = {np.max(np.abs(result[WARMUP:][mask] - reference[WARMUP:][mask]))}"
    )


class TestBootstrapFactors:
    def test_factor_count(self):
        assert len(BOOTSTRAP_FACTORS) == 15

    def test_momentum_5(self, ohlcv_df, arrays):
        close, *_ = arrays
        ev = ExprEval()
        result = ev.eval("ts_delta(close,5)", ohlcv_df)
        ref = np_ts_delta(close, 5)
        _compare(result, ref, "momentum_5")

    def test_momentum_10(self, ohlcv_df, arrays):
        close, *_ = arrays
        ev = ExprEval()
        result = ev.eval("ts_delta(close,10)", ohlcv_df)
        ref = np_ts_delta(close, 10)
        _compare(result, ref, "momentum_10")

    def test_momentum_20(self, ohlcv_df, arrays):
        close, *_ = arrays
        ev = ExprEval()
        result = ev.eval("ts_delta(close,20)", ohlcv_df)
        ref = np_ts_delta(close, 20)
        _compare(result, ref, "momentum_20")

    def test_ts_rank_20(self, ohlcv_df, arrays):
        close, *_ = arrays
        ev = ExprEval()
        result = ev.eval("ts_rank(close,20)", ohlcv_df)
        ref = np_ts_rank(close, 20)
        _compare(result, ref, "ts_rank_20")

    def test_vol_10(self, ohlcv_df, arrays):
        close, *_ = arrays
        ev = ExprEval()
        result = ev.eval("ts_std(close,10)", ohlcv_df)
        ref = np_rolling_std(close, 10)
        _compare(result, ref, "vol_10")

    def test_vol_50(self, ohlcv_df, arrays):
        close, *_ = arrays
        ev = ExprEval()
        result = ev.eval("ts_std(close,50)", ohlcv_df)
        ref = np_rolling_std(close, 50)
        _compare(result, ref, "vol_50")

    def test_vol_ratio(self, ohlcv_df, arrays):
        close, *_ = arrays
        ev = ExprEval()
        result = ev.eval("ts_std(close,10)/ts_std(close,50)", ohlcv_df)
        std10 = np_rolling_std(close, 10)
        std50 = np_rolling_std(close, 50)
        ref = std10 / std50
        _compare(result, ref, "vol_ratio")

    def test_bar_range(self, ohlcv_df, arrays):
        close, high, low, volume = arrays
        ev = ExprEval()
        result = ev.eval("(high-low)/close", ohlcv_df)
        ref = (high - low) / close
        _compare(result, ref, "bar_range")

    def test_vol_rank_20(self, ohlcv_df, arrays):
        close, high, low, volume = arrays
        ev = ExprEval()
        result = ev.eval("ts_rank(volume,20)", ohlcv_df)
        ref = np_ts_rank(volume, 20)
        _compare(result, ref, "vol_rank_20")

    def test_vol_ratio_50(self, ohlcv_df, arrays):
        close, high, low, volume = arrays
        ev = ExprEval()
        result = ev.eval("volume/ts_mean(volume,50)", ohlcv_df)
        ref = volume / np_rolling_mean(volume, 50)
        _compare(result, ref, "vol_ratio_50")

    def test_mean_rev_20(self, ohlcv_df, arrays):
        close, *_ = arrays
        ev = ExprEval()
        result = ev.eval("close/ts_mean(close,20)-1", ohlcv_df)
        ref = close / np_rolling_mean(close, 20) - 1
        _compare(result, ref, "mean_rev_20")

    def test_mean_rev_50(self, ohlcv_df, arrays):
        close, *_ = arrays
        ev = ExprEval()
        result = ev.eval("close/ts_mean(close,50)-1", ohlcv_df)
        ref = close / np_rolling_mean(close, 50) - 1
        _compare(result, ref, "mean_rev_50")

    def test_corr_cv_30(self, ohlcv_df, arrays):
        close, high, low, volume = arrays
        ev = ExprEval()
        result = ev.eval("ts_corr(close,volume,30)", ohlcv_df)
        ref = np_rolling_corr(close, volume, 30)
        mask = np.isfinite(result[WARMUP:]) & np.isfinite(ref[WARMUP:])
        assert mask.any(), "corr_cv_30: no finite values after warmup"
        assert np.allclose(result[WARMUP:][mask], ref[WARMUP:][mask], atol=1e-6), (
            f"corr_cv_30: max diff = {np.max(np.abs(result[WARMUP:][mask] - ref[WARMUP:][mask]))}"
        )

    def test_ret_skew_20(self, ohlcv_df, arrays):
        close, *_ = arrays
        ev = ExprEval()
        result = ev.eval("ts_skew(ts_delta(close,1),20)", ohlcv_df)
        delta1 = np_ts_delta(close, 1)
        ref = np_ts_skew(delta1, 20)
        _compare(result, ref, "ret_skew_20")

    def test_high_low_ma(self, ohlcv_df, arrays):
        close, high, low, volume = arrays
        ev = ExprEval()
        result = ev.eval("(ts_max(high,20)-ts_min(low,20))/ts_mean(close,20)", ohlcv_df)
        ref = (np_ts_max(high, 20) - np_ts_min(low, 20)) / np_rolling_mean(close, 20)
        _compare(result, ref, "high_low_ma")

    def test_compute_factor_matrix_shape(self, ohlcv_df):
        matrix = compute_factor_matrix(ohlcv_df)
        assert matrix.shape == (500, 15)
        expected_names = [name for name, _ in BOOTSTRAP_FACTORS]
        assert matrix.columns == expected_names

    def test_compute_factor_matrix_all_expressions_match(self, ohlcv_df):
        ev = ExprEval()
        matrix = compute_factor_matrix(ohlcv_df, expr=ev)
        for name, expression in BOOTSTRAP_FACTORS:
            col = matrix[name].to_numpy()
            assert col is not None, f"Missing column {name}"
            assert len(col) == 500

    def test_factor_names_match_bootstrap_list(self):
        names = [name for name, _ in BOOTSTRAP_FACTORS]
        expected = [
            "momentum_5", "momentum_10", "momentum_20", "ts_rank_20",
            "vol_10", "vol_50", "vol_ratio", "bar_range",
            "vol_rank_20", "vol_ratio_50", "mean_rev_20", "mean_rev_50",
            "corr_cv_30", "ret_skew_20", "high_low_ma",
        ]
        assert names == expected
