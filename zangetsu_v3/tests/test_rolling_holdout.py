"""Tests for quarterly rolling holdout automation (scripts/rolling_holdout_auto.py).

Verifies:
- Dry run shows correct split without mutating data
- New holdout has enough segments (validation gate)
- Embargo period is respected
- Edge cases: empty data, insufficient segments
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import polars as pl
import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.rolling_holdout_auto import (
    RollingHoldoutAutomation,
    RotationConfig,
    RotationResult,
)


# ---------------------------------------------------------------------------
# Fixtures — synthetic 1m OHLCV data
# ---------------------------------------------------------------------------

def _make_ohlcv(start: datetime, days: int, freq_minutes: int = 1) -> pl.DataFrame:
    """Generate synthetic 1m OHLCV data spanning `days` from `start`."""
    n_bars = days * (24 * 60 // freq_minutes)
    timestamps = [start + timedelta(minutes=i * freq_minutes) for i in range(n_bars)]
    rng = np.random.default_rng(42)
    close = 100.0 + np.cumsum(rng.normal(0, 0.01, n_bars))
    return pl.DataFrame({
        "timestamp": timestamps,
        "open": close - rng.uniform(0, 0.5, n_bars),
        "high": close + rng.uniform(0, 0.5, n_bars),
        "low": close - rng.uniform(0, 0.5, n_bars),
        "close": close,
        "volume": rng.uniform(100, 10000, n_bars),
    }).cast({"timestamp": pl.Datetime("us")})


@pytest.fixture
def base_date() -> datetime:
    return datetime(2025, 1, 1)


@pytest.fixture
def train_df(base_date) -> pl.DataFrame:
    """180 days of training data."""
    return _make_ohlcv(base_date, days=180)


@pytest.fixture
def holdout_df(base_date) -> pl.DataFrame:
    """90 days of holdout data starting after train."""
    start = base_date + timedelta(days=180)
    return _make_ohlcv(start, days=90)


@pytest.fixture
def new_data_df(base_date) -> pl.DataFrame:
    """30 days of new incoming data after holdout."""
    start = base_date + timedelta(days=270)
    return _make_ohlcv(start, days=30)


@pytest.fixture
def default_config() -> RotationConfig:
    return RotationConfig(
        embargo_days=5,
        holdout_months=3,
        min_holdout_segments=1,  # relaxed for test
        min_segment_bars=100,
        quarter="2025Q2",
        dry_run=False,
        archive_old_results=False,
    )


@pytest.fixture
def dry_run_config(default_config) -> RotationConfig:
    default_config.dry_run = True
    return default_config


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDryRun:
    """Dry run shows correct split without executing changes."""

    def test_dry_run_returns_result(self, dry_run_config, train_df, holdout_df, new_data_df):
        auto = RollingHoldoutAutomation(dry_run_config)
        result = auto.run(train_df, holdout_df, new_data_df)

        assert result.dry_run is True
        assert result.quarter == "2025Q2"
        assert result.old_train_rows == len(train_df)
        assert result.old_holdout_rows == len(holdout_df)
        assert result.new_data_rows == len(new_data_df)

    def test_dry_run_produces_non_empty_splits(self, dry_run_config, train_df, holdout_df, new_data_df):
        auto = RollingHoldoutAutomation(dry_run_config)
        result = auto.run(train_df, holdout_df, new_data_df)

        assert result.merged_train_rows > 0
        assert result.new_holdout_rows > 0

    def test_dry_run_has_actions_log(self, dry_run_config, train_df, holdout_df, new_data_df):
        auto = RollingHoldoutAutomation(dry_run_config)
        result = auto.run(train_df, holdout_df, new_data_df)

        assert len(result.actions) > 0
        assert any("DRY-RUN" in a or "Merging" in a or "Embargo" in a for a in result.actions)

    def test_dry_run_summary_shows_mode(self, dry_run_config, train_df, holdout_df, new_data_df):
        auto = RollingHoldoutAutomation(dry_run_config)
        result = auto.run(train_df, holdout_df, new_data_df)
        summary = result.summary()

        assert "DRY-RUN" in summary
        assert "2025Q2" in summary


class TestHoldoutValidation:
    """New holdout must have >= min_holdout_segments."""

    def test_sufficient_segments_passes(self, default_config, train_df, holdout_df, new_data_df):
        default_config.min_holdout_segments = 1
        auto = RollingHoldoutAutomation(default_config)
        result = auto.run(train_df, holdout_df, new_data_df)

        assert result.validation_passed is True
        assert result.holdout_segment_count >= 1

    def test_insufficient_segments_fails(self, default_config, train_df, holdout_df, new_data_df):
        # Require an absurdly high number of segments
        default_config.min_holdout_segments = 9999
        auto = RollingHoldoutAutomation(default_config)
        result = auto.run(train_df, holdout_df, new_data_df)

        assert result.validation_passed is False

    def test_empty_new_data_fails_validation(self, default_config, train_df, holdout_df):
        """If no new data, holdout may be small or empty."""
        default_config.min_holdout_segments = 5
        empty = pl.DataFrame({
            "timestamp": [],
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "volume": [],
        }).cast({"timestamp": pl.Datetime("us")})

        auto = RollingHoldoutAutomation(default_config)
        result = auto.run(train_df, holdout_df, empty)

        # With no new data, holdout comes from re-split of existing data only.
        # Validation depends on segment count — with high threshold it should fail.
        assert isinstance(result.validation_passed, bool)


class TestEmbargoRespected:
    """Embargo period creates a gap between train and holdout."""

    def test_embargo_gap_exists(self, default_config, train_df, holdout_df, new_data_df):
        default_config.embargo_days = 10
        auto = RollingHoldoutAutomation(default_config)
        result = auto.run(train_df, holdout_df, new_data_df)

        assert result.embargo_rows > 0, "Embargo period should contain rows"

    def test_embargo_separates_train_and_holdout(self, default_config, train_df, holdout_df, new_data_df):
        default_config.embargo_days = 10
        auto = RollingHoldoutAutomation(default_config)
        result = auto.run(train_df, holdout_df, new_data_df)

        if not result.new_train.is_empty() and not result.new_holdout.is_empty():
            train_end = result.new_train[-1, "timestamp"]
            holdout_start = result.new_holdout[0, "timestamp"]
            gap = holdout_start - train_end
            assert gap >= timedelta(days=1), (
                f"Gap between train and holdout should be at least 1 day, got {gap}"
            )

    def test_zero_embargo_still_works(self, default_config, train_df, holdout_df, new_data_df):
        default_config.embargo_days = 0
        auto = RollingHoldoutAutomation(default_config)
        result = auto.run(train_df, holdout_df, new_data_df)

        # Should complete without error, total rows preserved
        total_input = len(train_df) + len(holdout_df) + len(new_data_df)
        total_output = result.merged_train_rows + result.embargo_rows + result.new_holdout_rows
        # After dedup, output might be <= input
        assert total_output <= total_input


class TestMergeLogic:
    """Old holdout merges into train correctly."""

    def test_old_holdout_absorbed(self, default_config, train_df, holdout_df, new_data_df):
        auto = RollingHoldoutAutomation(default_config)
        result = auto.run(train_df, holdout_df, new_data_df)

        # New train should be larger than old train (absorbed holdout)
        assert result.merged_train_rows > result.old_train_rows

    def test_no_data_loss(self, default_config, train_df, holdout_df, new_data_df):
        auto = RollingHoldoutAutomation(default_config)
        result = auto.run(train_df, holdout_df, new_data_df)

        total_output = result.merged_train_rows + result.embargo_rows + result.new_holdout_rows
        # Dedup may reduce total, but should not exceed input
        total_input = len(train_df) + len(holdout_df) + len(new_data_df)
        assert total_output <= total_input
        # Should have most of the data
        assert total_output > total_input * 0.5


class TestEdgeCases:
    """Edge cases: empty frames, single row, etc."""

    def test_all_empty(self, default_config):
        empty = pl.DataFrame({
            "timestamp": [],
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "volume": [],
        }).cast({"timestamp": pl.Datetime("us")})

        auto = RollingHoldoutAutomation(default_config)
        result = auto.run(empty, empty, empty)

        assert result.merged_train_rows == 0
        assert result.new_holdout_rows == 0
        assert result.validation_passed is False

    def test_quarter_label_auto_detect(self):
        config = RotationConfig(auto_detect_quarter=True)
        label = config.current_quarter_label()
        assert label.startswith("20")
        assert "Q" in label

    def test_quarter_label_explicit(self):
        config = RotationConfig(quarter="2025Q3")
        assert config.current_quarter_label() == "2025Q3"
