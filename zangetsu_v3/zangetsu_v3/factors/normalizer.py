"""Robust z‑score normalisation (median + MAD * 1.4826)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

import polars as pl


SCALE = 1.4826
EPS = 1e-9


@dataclass
class RobustNormalizer:
    medians: Dict[str, float] = field(default_factory=dict)
    scales: Dict[str, float] = field(default_factory=dict)

    def fit(self, df: pl.DataFrame) -> None:
        for col in df.columns:
            series = df[col]
            med = float(series.median())
            mad = float((series - med).abs().median())
            scale = max(mad * SCALE, EPS)
            self.medians[col] = med
            self.scales[col] = scale

    def transform(self, df: pl.DataFrame) -> pl.DataFrame:
        # RISK-1 fix: never auto-fit — caller must fit on TRAIN only before calling transform
        if not self.medians:
            raise RuntimeError(
                "RobustNormalizer.transform() called before fit(). "
                "Call fit() on TRAIN data only to prevent lookahead contamination."
            )
        out_cols = []
        for col in df.columns:
            med = self.medians[col]
            scale = self.scales[col]
            out_cols.append(((df[col] - med) / scale).alias(col))
        return pl.DataFrame({c.name: c for c in out_cols})

    def add_factor(self, name: str, series: pl.Series) -> pl.Series:
        med = float(series.median())
        mad = float((series - med).abs().median())
        scale = max(mad * SCALE, EPS)
        self.medians[name] = med
        self.scales[name] = scale
        return (series - med) / scale


__all__ = ["RobustNormalizer", "SCALE"]

