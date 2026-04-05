"""Quarterly rolling holdout splitter (C27)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Tuple

import polars as pl

from zangetsu_v3.core.data_split import DataSplit


@dataclass
class RollingHoldout:
    embargo_days: int = 90
    holdout_months: int = 3

    def rotate(self, train: pl.DataFrame, holdout: pl.DataFrame, new_data: pl.DataFrame) -> Tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
        """Move previous holdout into train and form a new holdout from the latest quarter."""

        combined = pl.concat([train, holdout, new_data], how="diagonal_relaxed")
        splitter = DataSplit(self.embargo_days, self.holdout_months)
        return splitter.split(combined)


__all__ = ["RollingHoldout"]

