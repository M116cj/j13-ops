"""Tests for Arena 2 compression — uses synthetic data, no DB required."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import polars as pl
import pytest

# Allow importing from project root and inner package
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "zangetsu_v3"))

from scripts.arena2_compress import (
    DEDUP_THRESHOLD_TIGHT, DEDUP_THRESHOLD_RELAXED,
    MAX_FACTORS,
    MIN_FACTORS,
    compress,
    deduplicate,
    format_output,
    remove_weak_candidates,
    _pearson_corr,
)
from zangetsu_v3.factors.expr_eval import ExprEval


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
N_BARS = 2000
RNG = np.random.RandomState(42)


def _make_ohlcv(n: int = N_BARS) -> pl.DataFrame:
    """Generate synthetic OHLCV data."""
    close = 100.0 + np.cumsum(RNG.randn(n) * 0.5)
    high = close + np.abs(RNG.randn(n) * 0.3)
    low = close - np.abs(RNG.randn(n) * 0.3)
    open_ = close + RNG.randn(n) * 0.1
    volume = np.abs(RNG.randn(n) * 1000) + 500
    return pl.DataFrame({
        "timestamp": list(range(n)),
        "open": open_.tolist(),
        "high": high.tolist(),
        "low": low.tolist(),
        "close": close.tolist(),
        "volume": volume.tolist(),
    })


def _make_factor_df(ohlcv: pl.DataFrame) -> pl.DataFrame:
    """Add HFT-style factor columns + forward returns for testing."""
    close = ohlcv["close"].to_numpy().astype(np.float64)
    high = ohlcv["high"].to_numpy().astype(np.float64)
    low = ohlcv["low"].to_numpy().astype(np.float64)
    volume = ohlcv["volume"].to_numpy().astype(np.float64)
    n = len(close)

    extras = {}

    # Returns
    for lag in [1, 3, 5, 9]:
        ret = np.full(n, np.nan)
        ret[lag:] = (close[lag:] - close[:-lag]) / (close[:-lag] + 1e-12)
        extras[f"ret_{lag}"] = ret

    # Squared returns
    extras["ret5_sq"] = np.sign(extras["ret_5"]) * extras["ret_5"] ** 2
    extras["ret3_sq"] = np.sign(extras["ret_3"]) * extras["ret_3"] ** 2

    # Ranges
    for w in [3, 5, 10]:
        rng = np.full(n, np.nan)
        for i in range(w, n):
            rng[i] = (np.max(high[i - w + 1:i + 1]) - np.min(low[i - w + 1:i + 1])) / (close[i] + 1e-12)
        extras[f"range_{w}"] = rng

    # Volume surge
    for w in [3, 5]:
        vol_ma = np.full(n, np.nan)
        cs = np.nancumsum(volume)
        vol_ma[w - 1:] = (cs[w - 1:] - np.concatenate([[0], cs[:-w]])) / w
        extras[f"vol_surge_{w}"] = volume / (vol_ma + 1e-12)

    # Candle features
    hl_range = high - low + 1e-8
    extras["bar_body"] = (close - ohlcv["open"].to_numpy().astype(np.float64)) / hl_range
    extras["upper_shadow"] = (high - np.maximum(ohlcv["open"].to_numpy().astype(np.float64), close)) / hl_range
    extras["lower_shadow"] = (np.minimum(ohlcv["open"].to_numpy().astype(np.float64), close) - low) / hl_range

    # Volume-price corr placeholder
    extras["vol_price_corr_5"] = np.full(n, 0.0)

    # Forward returns (target)
    for horizon in [1, 3, 5, 10, 20]:
        fwd = np.full(n, np.nan)
        if horizon < n:
            fwd[:-horizon] = (close[horizon:] - close[:-horizon]) / (close[:-horizon] + 1e-12)
        extras[f"next_{horizon}_bar_return"] = fwd

    extra_df = pl.DataFrame(extras)
    return pl.concat([ohlcv, extra_df], how="horizontal")


def _make_candidates(
    n: int = 50,
    n_correlated_groups: int = 5,
    group_size: int = 4,
) -> List[Dict[str, Any]]:
    """Generate mock candidates.

    Creates groups of highly correlated candidates (same expression with small
    perturbations) plus independent ones.
    """
    base_expressions = [
        "ret_5",
        "ret_3",
        "range_3",
        "ret_1 * range_5",
        "ret_5 + range_3",
        "vol_surge_3",
        "bar_body",
        "ret_9",
        "range_10",
        "ret5_sq",
        "ret_5 * vol_surge_5",
        "range_5 * ret_3",
        "lower_shadow",
        "upper_shadow",
        "ret3_sq",
    ]
    regimes = ["BULL_TREND", "BEAR_TREND", "RANGE_BOUND", "HIGH_VOL", "LOW_VOL"]
    candidates = []

    idx = 0
    # Correlated groups: same expression → will have corr ~1.0
    for g in range(min(n_correlated_groups, len(base_expressions))):
        expr = base_expressions[g]
        for _ in range(group_size):
            candidates.append({
                "expression": expr,
                "raw_expression": expr,
                "complexity": RNG.randint(2, 10),
                "loss": float(RNG.uniform(0.0001, 0.01)),
                "score": float(RNG.uniform(0.01, 0.1)),
                "regime": regimes[g % len(regimes)],
                "horizon": int(RNG.choice([1, 3, 5, 10])),
            })
            idx += 1

    # Independent candidates with unique expressions
    remaining = n - idx
    for i in range(remaining):
        expr_idx = (n_correlated_groups + i) % len(base_expressions)
        expr = base_expressions[expr_idx]
        candidates.append({
            "expression": expr,
            "raw_expression": expr,
            "complexity": RNG.randint(2, 10),
            "loss": float(RNG.uniform(0.0001, 0.01)),
            "score": float(RNG.uniform(0.01, 0.1)),
            "regime": regimes[i % len(regimes)],
            "horizon": int(RNG.choice([1, 3, 5, 10])),
        })

    return candidates[:n]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestArena2Compression:
    """Integration tests for the Arena 2 compression pipeline."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.ohlcv = _make_ohlcv()
        self.df = _make_factor_df(self.ohlcv)
        self.evaluator = ExprEval()
        self.candidates = _make_candidates(50)

    def test_compression_output_count(self):
        """Compression should produce between 10 and 20 factors."""
        dfs = {"BTCUSDT": self.df}
        result = compress(self.candidates, dfs, self.evaluator)
        assert MIN_FACTORS <= len(result) <= MAX_FACTORS, (
            f"Expected {MIN_FACTORS}-{MAX_FACTORS} factors, got {len(result)}"
        )

    def test_no_high_correlation_pairs(self):
        """No pair in output should have abs(corr) > 0.7."""
        dfs = {"BTCUSDT": self.df}
        result = compress(self.candidates, dfs, self.evaluator)

        # Evaluate all result expressions
        series = []
        for cand in result:
            expr = cand.get("raw_expression") or cand["expression"]
            ts = self.evaluator.eval(expr, self.df)
            series.append(ts)

        # Check pairwise correlations
        for i in range(len(series)):
            for j in range(i + 1, len(series)):
                corr = abs(_pearson_corr(series[i], series[j]))
                assert corr <= DEDUP_THRESHOLD_RELAXED + 1e-6, (
                    f"Pair ({result[i]['expression']}, {result[j]['expression']}) "
                    f"has corr={corr:.4f} > {DEDUP_THRESHOLD_RELAXED}"
                )

    def test_output_json_schema(self):
        """Output JSON should have all required fields."""
        dfs = {"BTCUSDT": self.df}
        result = compress(self.candidates, dfs, self.evaluator)
        output = format_output(result)

        required_keys = {
            "index", "name", "expression", "raw_expression",
            "pysr_loss", "pysr_score", "lookback",
            "source_regime", "source_target",
        }

        for entry in output:
            missing = required_keys - set(entry.keys())
            assert not missing, f"Missing keys: {missing} in entry {entry}"
            assert isinstance(entry["index"], int)
            assert isinstance(entry["name"], str)
            assert entry["name"].startswith("factor_")
            assert isinstance(entry["pysr_loss"], float)
            assert isinstance(entry["pysr_score"], float)
            assert isinstance(entry["lookback"], int)

    def test_output_json_serializable(self):
        """Output must be JSON-serializable."""
        dfs = {"BTCUSDT": self.df}
        result = compress(self.candidates, dfs, self.evaluator)
        output = format_output(result)
        serialized = json.dumps(output)
        parsed = json.loads(serialized)
        assert len(parsed) == len(output)

    def test_output_written_to_file(self):
        """Verify file write round-trip."""
        dfs = {"BTCUSDT": self.df}
        result = compress(self.candidates, dfs, self.evaluator)
        output = format_output(result)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(output, f, indent=2)
            tmp_path = f.name

        try:
            with open(tmp_path) as f:
                loaded = json.load(f)
            assert len(loaded) == len(output)
            assert loaded[0]["name"] == "factor_001"
        finally:
            os.unlink(tmp_path)

    def test_dedup_removes_identical(self):
        """Identical expressions should be deduplicated to one."""
        # Create candidates all with same expression
        same_expr = [{
            "expression": "ret_5",
            "raw_expression": "ret_5",
            "complexity": 3,
            "loss": float(i * 0.001),
            "score": 0.05,
            "regime": "BULL_TREND",
            "horizon": 5,
        } for i in range(10)]

        # Evaluate to get series
        series_map = {}
        for i, c in enumerate(same_expr):
            ts = self.evaluator.eval(c["expression"], self.df)
            series_map[i] = ts

        deduped = deduplicate(same_expr, series_map, DEDUP_THRESHOLD_TIGHT)
        # All identical → only 1 should survive
        assert len(deduped) == 1
        # Should keep the one with lowest loss (index 0, loss=0.0)
        assert deduped[0]["loss"] == 0.0

    def test_pearson_corr_sanity(self):
        """Basic correlation sanity checks."""
        a = np.arange(100, dtype=np.float64)
        b = a * 2 + 1
        assert abs(_pearson_corr(a, b) - 1.0) < 1e-6

        c = -a
        assert abs(_pearson_corr(a, c) + 1.0) < 1e-6

        d = RNG.randn(100)
        corr = _pearson_corr(a, d)
        assert abs(corr) < 0.5  # Random should have low correlation

    def test_empty_candidates(self):
        """Empty input should produce empty output."""
        dfs = {"BTCUSDT": self.df}
        result = compress([], dfs, self.evaluator)
        assert result == []

    def test_format_output_indices(self):
        """Factor indices and names should be sequential."""
        factors = self.candidates[:15]
        output = format_output(factors)
        for i, entry in enumerate(output):
            assert entry["index"] == i
            assert entry["name"] == f"factor_{i + 1:03d}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
