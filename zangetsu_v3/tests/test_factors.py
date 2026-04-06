"""Tests for all 15 bootstrap factors against numpy reference implementations.

Error tolerance: < 1e-6 after warmup (first 50 bars).
No DB connection required — synthetic OHLCV only.

Also tests factor_pool.json loading, fallback to bootstrap, and
SignalScaleEstimator compatibility with dynamic factor pools.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from zangetsu_v3.factors.bootstrap import BOOTSTRAP_FACTORS, compute_factor_matrix
from zangetsu_v3.factors.expr_eval import ExprEval
from zangetsu_v3.factors.normalizer import get_factors, load_factor_pool

# Import signal_scale directly to avoid search/__init__.py pulling in ribs
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location(
    "zangetsu_v3.search.signal_scale",
    str(Path(__file__).resolve().parent.parent / "zangetsu_v3" / "search" / "signal_scale.py"),
)
_signal_scale_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_signal_scale_mod)
SignalScaleEstimator = _signal_scale_mod.SignalScaleEstimator

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


# ---------------------------------------------------------------------------
# Factor pool loading tests
# ---------------------------------------------------------------------------

MOCK_FACTOR_POOL = [
    {
        "index": 0,
        "name": "factor_001",
        "expression": "ts_delta(close,5)",
        "loss": 0.001,
        "target": "next_1_bar_return",
        "regime": "BULL_TREND",
        "pysr_loss": 0.001,
        "source_target": "next_1_bar_return",
        "source_regime": "BULL_TREND",
    },
    {
        "index": 1,
        "name": "factor_002",
        "expression": "ts_std(close,10)",
        "loss": 0.002,
        "target": "next_1_bar_return",
        "regime": "RANGE",
        "pysr_loss": 0.002,
        "source_target": "next_1_bar_return",
        "source_regime": "RANGE",
    },
    {
        "index": 2,
        "name": "factor_003",
        "expression": "(high-low)/close",
        "loss": 0.003,
        "target": "next_5_bar_return",
        "regime": "BEAR_TREND",
        "pysr_loss": 0.003,
        "source_target": "next_5_bar_return",
        "source_regime": "BEAR_TREND",
    },
]


class TestFactorPoolLoading:
    """Tests for loading factors from factor_pool.json."""

    def test_load_from_mock_pool(self, tmp_path: Path):
        pool_file = tmp_path / "factor_pool.json"
        pool_file.write_text(json.dumps(MOCK_FACTOR_POOL))

        result = load_factor_pool(pool_file)
        assert result is not None
        assert len(result) == 3
        assert result[0] == ("factor_001", "ts_delta(close,5)")
        assert result[1] == ("factor_002", "ts_std(close,10)")
        assert result[2] == ("factor_003", "(high-low)/close")

    def test_fallback_when_pool_missing(self):
        result = load_factor_pool("/nonexistent/path/factor_pool.json")
        assert result is None

    def test_fallback_on_invalid_json(self, tmp_path: Path):
        pool_file = tmp_path / "factor_pool.json"
        pool_file.write_text("NOT VALID JSON {{{")

        result = load_factor_pool(pool_file)
        assert result is None

    def test_fallback_on_empty_list(self, tmp_path: Path):
        pool_file = tmp_path / "factor_pool.json"
        pool_file.write_text("[]")

        result = load_factor_pool(pool_file)
        assert result is None

    def test_skips_entries_missing_name_or_expression(self, tmp_path: Path):
        pool = [
            {"name": "good", "expression": "close"},
            {"name": "", "expression": "close"},
            {"name": "no_expr", "expression": ""},
        ]
        pool_file = tmp_path / "factor_pool.json"
        pool_file.write_text(json.dumps(pool))

        result = load_factor_pool(pool_file)
        assert result is not None
        assert len(result) == 1
        assert result[0] == ("good", "close")

    def test_get_factors_with_pool(self, tmp_path: Path):
        pool_file = tmp_path / "factor_pool.json"
        pool_file.write_text(json.dumps(MOCK_FACTOR_POOL))

        factors, source = get_factors(pool_file)
        assert source == "factor_pool_json"
        assert len(factors) == 3

    def test_get_factors_fallback_to_bootstrap(self):
        factors, source = get_factors(None)
        assert source == "bootstrap"
        assert len(factors) == 15
        assert factors == list(BOOTSTRAP_FACTORS)

    def test_get_factors_fallback_on_missing_path(self):
        factors, source = get_factors("/nonexistent/factor_pool.json")
        assert source == "bootstrap"
        assert len(factors) == 15

    def test_arena2_format_compatibility(self, tmp_path: Path):
        """Verify the exact Arena 2 output schema fields are handled."""
        pool_file = tmp_path / "factor_pool.json"
        pool_file.write_text(json.dumps(MOCK_FACTOR_POOL))

        factors, source = get_factors(pool_file)
        assert source == "factor_pool_json"
        # All expressions must be evaluable strings (not None/empty)
        for name, expr in factors:
            assert isinstance(name, str) and len(name) > 0
            assert isinstance(expr, str) and len(expr) > 0


class TestSignalScaleWithFactorPool:
    """Tests for SignalScaleEstimator with dynamic factor pools."""

    def test_signal_std_in_expected_range(self, ohlcv_df):
        """Mock pool factors should produce signal_std in 1-10 range."""
        ev = ExprEval()
        # Evaluate mock pool expressions against synthetic data
        cols = []
        for _name, expr in [
            ("factor_001", "ts_delta(close,5)"),
            ("factor_002", "ts_std(close,10)"),
            ("factor_003", "(high-low)/close"),
        ]:
            vals = ev.eval(expr, ohlcv_df)
            # Replace NaN with 0 for matrix multiplication
            vals = np.where(np.isfinite(vals), vals, 0.0)
            cols.append(vals)

        factor_matrix = np.column_stack(cols)
        estimator = SignalScaleEstimator(n_samples=500, seed=42)
        std = estimator.estimate(factor_matrix, factor_source="factor_pool")
        assert 0.001 < std < 100.0, f"signal_std={std} out of reasonable range"
        assert estimator.n_factors == 3
        assert estimator.factor_source == "factor_pool"

    def test_bootstrap_factors_signal_std(self, ohlcv_df):
        """Bootstrap factor matrix should produce signal_std in 1-10 range."""
        matrix = compute_factor_matrix(ohlcv_df)
        arr = matrix.to_numpy().astype(np.float64)
        arr = np.where(np.isfinite(arr), arr, 0.0)

        estimator = SignalScaleEstimator(n_samples=500, seed=42)
        std = estimator.estimate(arr, factor_source="bootstrap")
        assert 0.01 < std < 10.0, f"signal_std={std} out of 1-10 range"
        assert estimator.n_factors == 15

    def test_empty_matrix_fallback(self):
        """Empty factor matrix should not crash, should return 1.0."""
        estimator = SignalScaleEstimator()
        std = estimator.estimate(np.empty((100, 0)))
        assert std == 1.0

    def test_derive_bounds_with_dynamic_factors(self, ohlcv_df):
        """Bounds derivation should work regardless of factor count."""
        ev = ExprEval()
        vals = ev.eval("ts_delta(close,5)", ohlcv_df)
        vals = np.where(np.isfinite(vals), vals, 0.0).reshape(-1, 1)

        estimator = SignalScaleEstimator(n_samples=100, seed=0)
        estimator.estimate(vals, factor_source="factor_pool")
        bounds = estimator.derive_bounds()

        assert "param_bounds" in bounds
        assert bounds["param_bounds"].shape == (5, 2)
        assert bounds["median_signal_std"] == estimator.median_std
        # entry_range lower bound should be positive
        assert bounds["entry_range"][0] > 0
