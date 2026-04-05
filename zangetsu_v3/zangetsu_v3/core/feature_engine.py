"""FeatureEngine — the ONLY feature computation entry point (C23).

Computes exactly 4 columns using Polars, window=20:
  rolling_return : 1-bar pct_change of close
  realized_vol   : rolling std of rolling_return over window
  volume_zscore  : (volume - mean(volume, window)) / std(volume, window)
  range_zscore   : ((high-low)/close - mean of that, window) / std of that, window

Used by both RegimeLabeler offline fit AND OnlineRegimePredictor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import polars as pl


WINDOW: int = 20


@dataclass
class FeatureEngine:
    """Singleton feature computation entry point."""

    _instance: ClassVar["FeatureEngine | None"] = None

    @classmethod
    def instance(cls) -> "FeatureEngine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def compute(self, df: pl.DataFrame) -> pl.DataFrame:
        """Append the four base feature columns to *df* and return the result.

        Parameters
        ----------
        df:
            Must contain ``close``, ``high``, ``low``, ``volume`` columns.

        Returns
        -------
        pl.DataFrame
            Original columns plus ``rolling_return``, ``realized_vol``,
            ``volume_zscore``, ``range_zscore``.
        """
        required = {"close", "high", "low", "volume"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"DataFrame missing required columns: {missing}")

        # 1-bar log-style pct change: (close[i] - close[i-1]) / close[i-1]
        ret = pl.col("close").pct_change(1)

        # (high - low) / close ratio
        range_ratio = (pl.col("high") - pl.col("low")) / pl.col("close")

        return df.with_columns(
            [
                ret.alias("rolling_return"),
                ret.rolling_std(WINDOW).alias("realized_vol"),
                (
                    (pl.col("volume") - pl.col("volume").rolling_mean(WINDOW))
                    / pl.col("volume").rolling_std(WINDOW)
                ).alias("volume_zscore"),
                (
                    (range_ratio - range_ratio.rolling_mean(WINDOW))
                    / range_ratio.rolling_std(WINDOW)
                ).alias("range_zscore"),
            ]
        )


__all__ = ["FeatureEngine", "WINDOW"]
