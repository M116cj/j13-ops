"""Time-based train / embargo / holdout splitter (C07).

DataSplit.split() divides a sorted DataFrame into three non-overlapping
segments based on wall-clock time.  Both ``embargo_days`` and
``holdout_months`` are always constructor parameters — never hardcoded.

Rolling holdout (C27):
  DataSplit.roll(old_split, new_live_data) merges the old holdout back into
  training, appends ``new_live_data`` as the new holdout, and re-inserts an
  embargo gap between them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import NamedTuple

import polars as pl


class SplitResult(NamedTuple):
    train: pl.DataFrame
    embargo: pl.DataFrame
    holdout: pl.DataFrame


@dataclass
class DataSplit:
    """Configurable time-series splitter.

    Parameters
    ----------
    embargo_days:
        Number of calendar days to exclude between training and holdout.
    holdout_months:
        Number of calendar months (approximated as 30 days each) to reserve
        for the holdout set, counted back from the last timestamp.
    """

    embargo_days: int
    holdout_months: int

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def split(
        self,
        df: pl.DataFrame,
        embargo_days: int | None = None,
        holdout_months: int | None = None,
    ) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
        """Split *df* into (train, embargo, holdout).

        Parameters
        ----------
        df:
            Must contain a ``timestamp`` column (Datetime or Date dtype).
        embargo_days:
            Override instance embargo_days for this call only.
        holdout_months:
            Override instance holdout_months for this call only.

        Returns
        -------
        tuple[train_df, embargo_df, holdout_df]
        """
        _embargo_days = embargo_days if embargo_days is not None else self.embargo_days
        _holdout_months = holdout_months if holdout_months is not None else self.holdout_months

        if "timestamp" not in df.columns:
            raise ValueError("DataFrame must include a 'timestamp' column")

        if df.is_empty():
            return df, df, df

        df = df.sort("timestamp")
        end_ts = df[-1, "timestamp"]

        holdout_delta = timedelta(days=30 * _holdout_months)
        embargo_delta = timedelta(days=_embargo_days)

        holdout_start = end_ts - holdout_delta
        embargo_start = holdout_start - embargo_delta

        ts = pl.col("timestamp")
        train = df.filter(ts < embargo_start)
        embargo = df.filter((ts >= embargo_start) & (ts < holdout_start))
        holdout = df.filter(ts >= holdout_start)

        return train, embargo, holdout

    # ------------------------------------------------------------------
    # Rolling holdout (C27)
    # ------------------------------------------------------------------

    def roll(
        self,
        current_split: tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame],
        new_live_data: pl.DataFrame,
    ) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
        """Advance the holdout window by absorbing the old holdout into training.

        Algorithm
        ---------
        1. Concatenate current train + current embargo + current holdout to
           form the expanded historical block.
        2. Append ``new_live_data`` (must not overlap with the history block).
        3. Re-split the combined frame with the same embargo_days /
           holdout_months so that:
           - ``new_live_data`` (approximately) becomes the new holdout.
           - An embargo gap separates training from the new holdout.
           - The old holdout is absorbed into training.

        Parameters
        ----------
        current_split:
            The (train, embargo, holdout) tuple from the previous split.
        new_live_data:
            Fresh bars to append as the new holdout candidate.

        Returns
        -------
        tuple[new_train_df, new_embargo_df, new_holdout_df]
        """
        old_train, old_embargo, old_holdout = current_split

        if "timestamp" not in new_live_data.columns:
            raise ValueError("new_live_data must include a 'timestamp' column")

        # Merge old segments and new data into one sorted frame.
        combined = pl.concat(
            [old_train, old_embargo, old_holdout, new_live_data],
            how="diagonal_relaxed",
        ).sort("timestamp").unique(subset=["timestamp"], keep="last")

        return self.split(combined)


__all__ = ["DataSplit", "SplitResult"]
