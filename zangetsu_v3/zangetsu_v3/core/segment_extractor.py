"""Per-regime training segment extraction from labeled 1m OHLCV data.

Extracts continuous runs of the same regime label within each symbol,
filters by minimum length, groups by regime across symbols, and splits
into TRAIN / HOLDOUT by time order for CMA-MAE search.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np
import polars as pl

from zangetsu_v3.regime.rule_labeler import Regime, REGIME_NAMES


@dataclass
class Segment:
    symbol: str
    regime: int           # Regime enum value
    start_idx: int        # index into original 1m dataframe
    end_idx: int          # exclusive
    bars: int
    days: float           # bars / 1440
    ohlcv: pl.DataFrame   # slice of 1m data for this segment
    labels_1m: np.ndarray # 13-state labels for this segment


class SegmentExtractor:
    """Extract per-regime continuous segments from labeled 1m data."""

    def __init__(self, min_segment_bars: int = 1440):
        self.min_segment_bars = min_segment_bars

    def extract_symbol(
        self, df_1m: pl.DataFrame, labels_1m: np.ndarray, symbol: str
    ) -> list[Segment]:
        """Extract all segments >= min_segment_bars from one symbol's labeled data.

        Finds continuous runs of the same label value.  For each run that meets
        the minimum bar count, creates a Segment with the corresponding OHLCV
        slice and label sub-array.
        """
        n = len(labels_1m)
        if n == 0 or len(df_1m) == 0:
            return []
        if len(df_1m) != n:
            raise ValueError(
                f"Length mismatch: df_1m has {len(df_1m)} rows, "
                f"labels_1m has {n} entries"
            )

        segments: list[Segment] = []

        # Detect run boundaries via diff != 0
        diff = np.diff(labels_1m)
        change_idxs = np.flatnonzero(diff)

        # Build (start, end) pairs for each run
        starts = np.empty(len(change_idxs) + 1, dtype=np.intp)
        ends = np.empty_like(starts)
        starts[0] = 0
        starts[1:] = change_idxs + 1
        ends[:-1] = change_idxs + 1
        ends[-1] = n

        for i in range(len(starts)):
            s, e = int(starts[i]), int(ends[i])
            length = e - s
            if length < self.min_segment_bars:
                continue
            regime_val = int(labels_1m[s])
            segments.append(Segment(
                symbol=symbol,
                regime=regime_val,
                start_idx=s,
                end_idx=e,
                bars=length,
                days=length / 1440.0,
                ohlcv=df_1m.slice(s, length),
                labels_1m=labels_1m[s:e].copy(),
            ))

        return segments

    def extract_all(
        self, symbol_data: dict[str, tuple[pl.DataFrame, np.ndarray]]
    ) -> dict[int, list[Segment]]:
        """Extract segments from all symbols, grouped by regime.

        Args:
            symbol_data: {symbol: (df_1m, labels_1m)}

        Returns:
            {regime_id: [Segment, ...]} sorted by the segment's start
            timestamp within each regime group.
        """
        by_regime: dict[int, list[Segment]] = {}

        for symbol, (df_1m, labels_1m) in symbol_data.items():
            segs = self.extract_symbol(df_1m, labels_1m, symbol)
            for seg in segs:
                by_regime.setdefault(seg.regime, []).append(seg)

        # Sort each regime's segments by the first timestamp in ohlcv
        for regime_id, seg_list in by_regime.items():
            seg_list.sort(key=self._segment_sort_key)

        return by_regime

    def split_train_holdout(
        self,
        segments: list[Segment],
        train_ratio: float = 0.7,
        embargo_days: int = 0,
    ) -> tuple[list[Segment], list[Segment]]:
        """Split segments into TRAIN / HOLDOUT by time order.

        Segments are assumed already sorted by time (as returned by
        ``extract_all``).  The first ``train_ratio`` fraction goes to TRAIN.
        If ``embargo_days > 0``, that many days worth of segments at the
        boundary are dropped to prevent leakage.

        Returns:
            (train_segments, holdout_segments)
        """
        n = len(segments)
        if n == 0:
            return [], []

        split_idx = max(1, int(n * train_ratio))
        train = segments[:split_idx]

        if embargo_days <= 0:
            holdout = segments[split_idx:]
            return train, holdout

        # Skip segments whose total days sum <= embargo_days
        embargo_bars = embargo_days * 1440
        skipped_bars = 0
        holdout_start = split_idx
        while holdout_start < n and skipped_bars < embargo_bars:
            skipped_bars += segments[holdout_start].bars
            holdout_start += 1

        holdout = segments[holdout_start:]
        return train, holdout

    def build_factor_matrix(
        self,
        segments: list[Segment],
        compute_factors_fn: Callable[[pl.DataFrame], pl.DataFrame],
    ) -> tuple[np.ndarray, list[int]]:
        """Build concatenated factor matrix from segments.

        For each segment, ``compute_factors_fn`` is called with the segment's
        OHLCV dataframe.  The returned dataframe's columns become factor
        features.  Rows with any NaN (warmup period) are dropped from the
        front of each segment independently.

        Returns:
            factor_matrix: np.ndarray of shape (total_valid_rows, n_factors)
            segment_boundaries: list of ints marking the start row index of
                each segment in the concatenated matrix.  Length equals the
                number of segments that contributed at least one row.
        """
        chunks: list[np.ndarray] = []
        boundaries: list[int] = []
        offset = 0

        for seg in segments:
            factors_df = compute_factors_fn(seg.ohlcv)
            arr = factors_df.to_numpy()

            # Drop leading NaN warmup rows
            valid_mask = ~np.isnan(arr).any(axis=1)
            if not valid_mask.any():
                continue

            # Find first valid row — drop everything before it
            first_valid = int(np.argmax(valid_mask))
            clean = arr[first_valid:]

            # Also drop any remaining interior NaN rows (shouldn't happen
            # normally, but defensive)
            interior_mask = ~np.isnan(clean).any(axis=1)
            clean = clean[interior_mask]

            if clean.shape[0] == 0:
                continue

            boundaries.append(offset)
            chunks.append(clean)
            offset += clean.shape[0]

        if not chunks:
            return np.empty((0, 0), dtype=np.float64), []

        factor_matrix = np.concatenate(chunks, axis=0)
        return factor_matrix, boundaries

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _segment_sort_key(seg: Segment) -> tuple:
        """Sort key: (first_timestamp, symbol) for deterministic ordering."""
        ts_col = seg.ohlcv.columns[0]  # assume first column is timestamp
        first_ts = seg.ohlcv[ts_col][0]
        return (first_ts, seg.symbol)


__all__ = [
    "Segment",
    "SegmentExtractor",
]
