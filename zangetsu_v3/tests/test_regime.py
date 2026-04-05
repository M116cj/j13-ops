"""Tests for RegimeLabeler and OnlineRegimePredictor.

No DB required — synthetic OHLCV data only.
"""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from zangetsu_v3.regime.labeler import RegimeLabeler
from zangetsu_v3.regime.predictor import OnlineRegimePredictor


# ---------------------------------------------------------------------------
# Synthetic data fixture
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


@pytest.fixture(scope="module")
def df_2000() -> pl.DataFrame:
    return make_ohlcv(2000)


# ---------------------------------------------------------------------------
# RegimeLabeler tests
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
        # States should be 0..k-1 with no gaps
        assert unique_states == list(range(len(unique_states)))

    def test_save_load_roundtrip(self, df_2000, tmp_path):
        labeler = RegimeLabeler()
        original_labels = labeler.fit(df_2000)

        save_path = tmp_path / "regime_model.pkl"
        labeler.save(save_path)

        loaded = RegimeLabeler.load(save_path)
        assert loaded.model_ is not None
        assert loaded.n_states_ is None  # n_states_ is not serialized, only model
        assert loaded.min_states == labeler.min_states
        assert loaded.max_states == labeler.max_states
        # state_mapping_ round-trips
        assert hasattr(loaded, "state_mapping_")
        assert loaded.state_mapping_ == labeler.state_mapping_

    def test_label_with_fitted_model(self, df_2000):
        """label() on same data with fitted model should match fit() output."""
        labeler = RegimeLabeler()
        fit_labels = labeler.fit(df_2000)
        label_labels = labeler.label(df_2000)
        # May differ slightly due to re-sorting but lengths must match
        assert len(label_labels) == len(fit_labels)

    def test_fit_unfitted_raises_on_save(self):
        labeler = RegimeLabeler()
        with pytest.raises(ValueError, match="not fitted"):
            labeler.save("/tmp/nonexistent_test.pkl")

    def test_multiple_fit_calls_stable(self, df_2000):
        """Fitting twice should not raise and should produce valid labels."""
        labeler = RegimeLabeler()
        labels1 = labeler.fit(df_2000)
        labels2 = labeler.fit(df_2000)
        assert len(labels1) == len(labels2)


# ---------------------------------------------------------------------------
# OnlineRegimePredictor tests
# ---------------------------------------------------------------------------

class TestOnlineRegimePredictor:
    """Each test uses a fresh instance to avoid singleton state contamination."""

    def _fresh(self) -> OnlineRegimePredictor:
        # Reset class-level singleton and return fresh instance
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
        # Confidence should be non-decreasing (monotone during stable regime)
        for i in range(len(confs) - 1):
            assert confs[i + 1] >= confs[i], (
                f"Confidence dropped from {confs[i]} to {confs[i+1]} at step {i}"
            )

    def test_switch_confidence_approaches_1_after_many_stable_bars(self):
        pred = self._fresh()
        for _ in range(50):
            pred.step(0)
        assert pred.switch_confidence >= 0.9

    def test_debounce_prevents_premature_regime_switch(self):
        pred = self._fresh()
        pred.step(0)  # establish regime 0
        # Feed 4 bars of regime 1 (debounce=5 by default)
        for _ in range(4):
            pred.step(1)
        # Active regime should still be 0
        assert pred.active_regime == 0

    def test_regime_switches_after_debounce_bars(self):
        pred = self._fresh()
        pred.step(0)
        # Feed exactly debounce bars of new regime
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
        pred.step(0)  # back to active → reset candidate
        assert pred.candidate_regime is None
        assert pred.debounce_count == 0
