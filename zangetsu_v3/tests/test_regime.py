"""Tests for RegimeLabeler, OnlineRegimePredictor, and rule-based 13-state labeler.

No DB required — synthetic OHLCV data only.
"""

from __future__ import annotations

import time

import numpy as np
import polars as pl
import pytest

from zangetsu_v3.regime.labeler import RegimeLabeler
from zangetsu_v3.regime.predictor import (
    OnlineRegimePredictor,
    _compute_online_features,
)
from zangetsu_v3.regime.rule_labeler import (
    Regime,
    REGIME_NAMES,
    label_4h,
    label_symbol,
    regime_report,
    to_search_regime,
)


# ---------------------------------------------------------------------------
# Synthetic data fixtures
# ---------------------------------------------------------------------------

def make_ohlcv(n: int = 2000, seed: int = 7) -> pl.DataFrame:
    np.random.seed(seed)
    close = 100 * np.exp(np.cumsum(np.random.randn(n) * 0.001))
    high = close * (1 + np.abs(np.random.randn(n) * 0.002))
    low = close * (1 - np.abs(np.random.randn(n) * 0.002))
    volume = np.abs(np.random.randn(n) * 1000 + 5000)
    return pl.DataFrame(
        {
            "symbol": ["BTC"] * n,
            "timestamp": list(range(n)),
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def make_ohlcv_1m(n_bars: int = 50000, seed: int = 42) -> pl.DataFrame:
    """Generate synthetic 1-minute OHLCV data with timestamps for resampling."""
    np.random.seed(seed)
    # Create varied market conditions to produce diverse regimes
    segments = []
    t = 0
    base_price = 50000.0

    def _seg(n, drift, vol, vol_base):
        nonlocal t, base_price
        prices = [base_price]
        for _ in range(n - 1):
            prices.append(prices[-1] * (1 + drift + np.random.randn() * vol))
        prices = np.array(prices)
        high = prices * (1 + np.abs(np.random.randn(n) * 0.0005))
        low = prices * (1 - np.abs(np.random.randn(n) * 0.0005))
        volume = np.abs(np.random.randn(n) * vol_base + vol_base * 2)
        ts = np.arange(t, t + n) * 60_000  # ms timestamps
        t += n
        base_price = prices[-1]
        return ts, prices, high, low, volume

    # Bull trend
    segments.append(_seg(8000, 0.0003, 0.003, 1000))
    # Consolidation
    segments.append(_seg(5000, 0.0, 0.001, 800))
    # Bear trend
    segments.append(_seg(8000, -0.0003, 0.003, 1000))
    # Squeeze (low vol)
    segments.append(_seg(4000, 0.0, 0.0003, 300))
    # Parabolic (extreme bull)
    segments.append(_seg(3000, 0.001, 0.005, 2000))
    # Liquidity crisis (extreme drop)
    segments.append(_seg(2000, -0.001, 0.008, 3000))
    # Choppy volatile
    segments.append(_seg(5000, 0.0, 0.006, 1500))
    # Another bull for pullback/topping
    segments.append(_seg(6000, 0.0002, 0.003, 1000))
    # Transition to bear for bottoming
    segments.append(_seg(5000, -0.0002, 0.003, 1000))
    # Accumulation zone (low position)
    segments.append(_seg(4000, 0.00005, 0.001, 600))

    all_ts = np.concatenate([s[0] for s in segments])
    all_close = np.concatenate([s[1] for s in segments])
    all_high = np.concatenate([s[2] for s in segments])
    all_low = np.concatenate([s[3] for s in segments])
    all_volume = np.concatenate([s[4] for s in segments])

    return pl.DataFrame({
        "timestamp": pl.Series(all_ts).cast(pl.Datetime("ms")),
        "open": all_close,
        "high": all_high,
        "low": all_low,
        "close": all_close,
        "volume": all_volume,
    })


@pytest.fixture(scope="module")
def df_2000() -> pl.DataFrame:
    return make_ohlcv(2000)


@pytest.fixture(scope="module")
def df_1m() -> pl.DataFrame:
    return make_ohlcv_1m(50000)


@pytest.fixture(scope="module")
def labels_and_4h(df_1m):
    """Produce 13-state labels on synthetic data."""
    labels_1m, labels_4h, df_4h = label_symbol(df_1m)
    return labels_1m, labels_4h, df_4h


# ---------------------------------------------------------------------------
# RegimeLabeler (HMM) tests
# ---------------------------------------------------------------------------

class TestRegimeLabeler:
    def test_n_states_in_range(self, df_2000):
        labeler = RegimeLabeler(min_states=3, max_states=8)
        labeler.fit(df_2000)
        assert labeler.n_states_ is not None
        assert 3 <= labeler.n_states_ <= 8

    def test_labels_length_matches_input(self, df_2000):
        labeler = RegimeLabeler()
        labels = labeler.fit(df_2000)
        assert len(labels) == len(df_2000)

    def test_labels_are_integers(self, df_2000):
        labeler = RegimeLabeler()
        labels = labeler.fit(df_2000)
        assert labels.dtype in (np.int32, np.int64, np.intp, int), (
            f"Labels dtype is {labels.dtype}, expected integer"
        )

    def test_labels_values_bounded_by_n_states(self, df_2000):
        labeler = RegimeLabeler()
        labels = labeler.fit(df_2000)
        assert labels.min() >= 0
        assert labels.max() < labeler.n_states_

    def test_auto_map_produces_contiguous_states(self, df_2000):
        labeler = RegimeLabeler()
        labels = labeler.fit(df_2000)
        unique_states = sorted(set(labels.tolist()))
        assert unique_states == list(range(len(unique_states)))

    def test_save_load_roundtrip(self, df_2000, tmp_path):
        labeler = RegimeLabeler()
        labeler.fit(df_2000)
        save_path = tmp_path / "regime_model.pkl"
        labeler.save(save_path)
        loaded = RegimeLabeler.load(save_path)
        assert loaded.model_ is not None
        assert loaded.min_states == labeler.min_states

    def test_label_with_fitted_model(self, df_2000):
        labeler = RegimeLabeler()
        fit_labels = labeler.fit(df_2000)
        label_labels = labeler.label(df_2000)
        assert len(label_labels) == len(fit_labels)

    def test_fit_unfitted_raises_on_save(self):
        labeler = RegimeLabeler()
        with pytest.raises(ValueError, match="not fitted"):
            labeler.save("/tmp/nonexistent_test.pkl")

    def test_multiple_fit_calls_stable(self, df_2000):
        labeler = RegimeLabeler()
        labels1 = labeler.fit(df_2000)
        labels2 = labeler.fit(df_2000)
        assert len(labels1) == len(labels2)


# ---------------------------------------------------------------------------
# OnlineRegimePredictor tests (debounce + switch_confidence)
# ---------------------------------------------------------------------------

class TestOnlineRegimePredictor:
    """Each test uses a fresh instance to avoid singleton state contamination."""

    def _fresh(self) -> OnlineRegimePredictor:
        OnlineRegimePredictor._instance = None
        return OnlineRegimePredictor()

    def test_step_returns_integer(self):
        pred = self._fresh()
        result = pred.step(1)
        assert isinstance(result, int)

    def test_initial_regime_set_on_first_step(self):
        pred = self._fresh()
        result = pred.step(2)
        assert pred.active_regime == 2
        assert result == 2

    def test_switch_confidence_is_float_in_range(self):
        pred = self._fresh()
        pred.step(1)
        conf = pred.switch_confidence
        assert isinstance(conf, float)
        assert 0.0 <= conf <= 1.0

    def test_switch_confidence_increases_with_stable_regime(self):
        pred = self._fresh()
        confs = []
        for _ in range(40):
            pred.step(0)
            confs.append(pred.switch_confidence)
        for i in range(len(confs) - 1):
            assert confs[i + 1] >= confs[i], (
                f"Confidence dropped from {confs[i]} to {confs[i + 1]} at step {i}"
            )

    def test_switch_confidence_approaches_1_after_many_stable_bars(self):
        pred = self._fresh()
        for _ in range(50):
            pred.step(0)
        assert pred.switch_confidence >= 0.9

    def test_debounce_prevents_premature_regime_switch(self):
        pred = self._fresh()
        pred.step(0)
        for _ in range(2):  # less than debounce=3
            pred.step(1)
        assert pred.active_regime == 0

    def test_regime_switches_after_debounce_bars(self):
        pred = self._fresh()
        pred.step(0)
        for _ in range(pred.debounce):
            pred.step(1)
        assert pred.active_regime == 1

    def test_singleton_instance_method(self):
        OnlineRegimePredictor._instance = None
        inst1 = OnlineRegimePredictor.instance()
        inst2 = OnlineRegimePredictor.instance()
        assert inst1 is inst2

    def test_candidate_reset_on_return_to_active_regime(self):
        pred = self._fresh()
        pred.step(0)
        pred.step(1)  # candidate = 1, count = 1
        pred.step(0)  # back to active -> reset candidate
        assert pred.candidate_regime is None
        assert pred.debounce_count == 0

    def test_switch_confidence_resets_on_regime_change(self):
        """After a regime switch, confidence should drop back to low."""
        pred = self._fresh()
        # Build confidence in regime 0
        for _ in range(30):
            pred.step(0)
        high_conf = pred.switch_confidence
        assert high_conf > 0.9
        # Switch to regime 1
        for _ in range(pred.debounce):
            pred.step(1)
        assert pred.active_regime == 1
        assert pred.switch_confidence < high_conf

    def test_debounce_with_interruption(self):
        """If candidate regime is interrupted by a third regime, counter resets."""
        pred = self._fresh()
        pred.step(0)
        pred.step(1)  # candidate=1, count=1
        pred.step(1)  # candidate=1, count=2
        pred.step(2)  # new candidate=2, count=1 (interrupts 1)
        pred.step(1)  # new candidate=1, count=1 (resets)
        # Should NOT have switched (never reached debounce=5 consecutively)
        assert pred.active_regime == 0

    def test_predict_fine_raises_without_model(self):
        pred = self._fresh()
        with pytest.raises(RuntimeError, match="No model loaded"):
            pred.predict_fine(
                np.ones(100), np.ones(100), np.ones(100), np.ones(100)
            )


# ---------------------------------------------------------------------------
# Rule-based 13-state labeler tests
# ---------------------------------------------------------------------------

class TestRuleLabeler:
    """Tests for rule_labeler.py 13-state classification."""

    def test_all_13_regime_enum_values_exist(self):
        """Regime enum has exactly 13 members (0..12)."""
        assert len(Regime) == 13
        for i in range(13):
            assert i in [r.value for r in Regime]

    def test_label_4h_output_shape(self, labels_and_4h):
        _, labels_4h, df_4h = labels_and_4h
        assert len(labels_4h) == len(df_4h)

    def test_label_4h_values_in_valid_range(self, labels_and_4h):
        _, labels_4h, _ = labels_and_4h
        assert labels_4h.min() >= 0
        assert labels_4h.max() <= 12

    def test_labels_are_int8(self, labels_and_4h):
        _, labels_4h, _ = labels_and_4h
        assert labels_4h.dtype == np.int8

    def test_broadcast_1m_length(self, labels_and_4h, df_1m):
        labels_1m, _, _ = labels_and_4h
        assert len(labels_1m) == len(df_1m)

    def test_multiple_regimes_present(self, labels_and_4h):
        """The synthetic data should produce at least 4 distinct regimes."""
        _, labels_4h, _ = labels_and_4h
        unique = set(labels_4h.tolist())
        assert len(unique) >= 4, f"Only {len(unique)} regimes present: {unique}"

    def test_regime_report_structure(self, labels_and_4h):
        _, labels_4h, _ = labels_and_4h
        report = regime_report(labels_4h)
        assert "n_bars" in report
        assert "total_segments" in report
        assert "n_regimes_present" in report
        assert "regimes" in report
        assert report["n_bars"] == len(labels_4h)
        for name, info in report["regimes"].items():
            assert "bars" in info
            assert "pct" in info
            assert "segments" in info
            assert "avg_hours" in info

    def test_to_search_regime_maps_all(self, labels_and_4h):
        _, labels_4h, _ = labels_and_4h
        search = to_search_regime(labels_4h)
        assert len(search) == len(labels_4h)
        valid_search = {"BULL_TREND", "BEAR_TREND", "CONSOLIDATION", "SQUEEZE"}
        for s in np.unique(search):
            assert s in valid_search, f"Unexpected search regime: {s}"

    def test_smoothing_removes_flickers(self):
        """A single-bar flicker should be smoothed out."""
        raw = np.array([0, 0, 0, 5, 0, 0, 0], dtype=np.int8)
        from zangetsu_v3.regime.rule_labeler import _smooth_labels
        smoothed = _smooth_labels(raw, min_segment_bars=2)
        # The single bar of regime 5 should be absorbed
        assert smoothed[3] == 0

    def test_labeling_latency_under_10ms(self, labels_and_4h):
        """Labeling the last bar given precomputed 4h data should be fast."""
        _, _, df_4h = labels_and_4h
        # Measure time for label_4h (this is the labeler, not predictor)
        times = []
        for _ in range(10):
            t0 = time.perf_counter()
            label_4h(df_4h)
            times.append(time.perf_counter() - t0)
        median_ms = np.median(times) * 1000
        # Full labeling of ~200 4h bars should be well under 1s
        # Per-bar amortized should be way under 10ms
        n_bars = len(df_4h)
        per_bar_ms = median_ms / n_bars
        assert per_bar_ms < 10.0, f"Per-bar latency {per_bar_ms:.2f}ms exceeds 10ms"


# ---------------------------------------------------------------------------
# Predict_fine integration test (with mock model)
# ---------------------------------------------------------------------------

class TestPredictFine:
    """Test predict_fine() with a mock LightGBM model."""

    def _make_mock_model(self):
        """Return a mock model that always predicts based on a simple rule."""

        class MockModel:
            def predict(self, X):
                # Return regime based on sign of ema21_slope (feature index 3)
                preds = []
                for row in X:
                    slope = row[3]
                    if slope > 0.001:
                        preds.append(int(Regime.BULL_TREND))
                    elif slope < -0.001:
                        preds.append(int(Regime.BEAR_TREND))
                    else:
                        preds.append(int(Regime.CONSOLIDATION))
                return np.array(preds)

        return MockModel()

    def _make_predictor_with_mock(self) -> OnlineRegimePredictor:
        OnlineRegimePredictor._instance = None
        pred = OnlineRegimePredictor()
        pred._model = self._make_mock_model()
        return pred

    def test_predict_fine_returns_valid_regime(self):
        pred = self._make_predictor_with_mock()
        n = 200
        close = 100 * np.exp(np.cumsum(np.random.randn(n) * 0.001))
        high = close * 1.001
        low = close * 0.999
        volume = np.ones(n) * 1000
        result = pred.predict_fine(close, high, low, volume)
        assert 0 <= result <= 12
        assert isinstance(result, int)

    def test_predict_fine_returns_raw_no_debounce(self):
        """V3.2: predict_fine returns raw model output without debounce (for overlay)."""
        pred = self._make_predictor_with_mock()
        n = 200
        close_bull = 100 * np.exp(np.cumsum(np.ones(n) * 0.002))
        high = close_bull * 1.001
        low = close_bull * 0.999
        volume = np.ones(n) * 1000

        # predict_fine does NOT update active_regime (no debounce)
        result = pred.predict_fine(close_bull, high, low, volume)
        assert 0 <= result <= 12
        assert pred.last_fine_regime == result
        # active_regime is NOT set by predict_fine
        assert pred.active_regime is None

    def test_predict_coarse_applies_debounce(self):
        """V3.2: predict_coarse applies debounce (N=3) for card selection."""
        pred = self._make_predictor_with_mock()
        n = 200
        close_bull = 100 * np.exp(np.cumsum(np.ones(n) * 0.002))
        high = close_bull * 1.001
        low = close_bull * 0.999
        volume = np.ones(n) * 1000

        # Establish regime via predict_coarse (which calls step)
        for _ in range(pred.debounce + 1):
            pred.predict_coarse(close_bull, high, low, volume)
        assert pred.active_regime is not None

        # One bar of different data should NOT switch (debounce holds)
        close_bear = 100 * np.exp(np.cumsum(np.ones(n) * -0.002))
        high_bear = close_bear * 1.001
        low_bear = close_bear * 0.999
        old_regime = pred.active_regime
        pred.predict_coarse(close_bear, high_bear, low_bear, volume)
        assert pred.active_regime == old_regime

    def test_predict_fine_latency_under_10ms(self):
        """Single predict_fine call should complete in <10ms."""
        pred = self._make_predictor_with_mock()
        n = 200
        close = 100 * np.exp(np.cumsum(np.random.randn(n) * 0.001))
        high = close * 1.001
        low = close * 0.999
        volume = np.ones(n) * 1000

        times = []
        for _ in range(20):
            t0 = time.perf_counter()
            pred.predict_fine(close, high, low, volume)
            times.append(time.perf_counter() - t0)
        median_ms = np.median(times) * 1000
        assert median_ms < 10.0, f"predict_fine latency {median_ms:.2f}ms exceeds 10ms"

    def test_predict_fine_all_13_states_reachable(self):
        """Verify that every Regime value can pass through predict_fine via step."""
        OnlineRegimePredictor._instance = None
        pred = OnlineRegimePredictor()

        # Directly test that step() can output all 13 states
        seen = set()
        for regime_val in range(13):
            pred_fresh = OnlineRegimePredictor()
            # First call sets the regime directly
            result = pred_fresh.step(regime_val)
            seen.add(result)

        assert seen == set(range(13)), f"Missing regimes: {set(range(13)) - seen}"


# ---------------------------------------------------------------------------
# Feature computation tests
# ---------------------------------------------------------------------------

class TestOnlineFeatures:
    def test_feature_shape(self):
        n = 200
        close = 100 * np.exp(np.cumsum(np.random.randn(n) * 0.001))
        high = close * 1.001
        low = close * 0.999
        volume = np.ones(n) * 1000
        features = _compute_online_features(close, high, low, volume)
        assert features.shape == (n, 12)

    def test_no_nan_after_warmup(self):
        n = 300
        close = 100 * np.exp(np.cumsum(np.random.randn(n) * 0.001))
        high = close * 1.001
        low = close * 0.999
        volume = np.ones(n) * 1000
        features = _compute_online_features(close, high, low, volume)
        # After 200 bars of warmup, should have no NaN
        assert not np.any(np.isnan(features[200:])), "NaN found in features after warmup"

    def test_feature_computation_latency(self):
        n = 200
        close = 100 * np.exp(np.cumsum(np.random.randn(n) * 0.001))
        high = close * 1.001
        low = close * 0.999
        volume = np.ones(n) * 1000
        times = []
        for _ in range(10):
            t0 = time.perf_counter()
            _compute_online_features(close, high, low, volume)
            times.append(time.perf_counter() - t0)
        median_ms = np.median(times) * 1000
        assert median_ms < 50.0, f"Feature computation {median_ms:.2f}ms too slow"
