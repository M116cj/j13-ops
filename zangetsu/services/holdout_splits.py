"""Holdout 3-way split helper for the new arena gate pipeline.

Convention for A2/A3/A4:
    A2 evaluates on the FIRST third  (coarse OOS PnL gate).
    A3 evaluates on the MIDDLE third (time-segment stability gate).
    A4 evaluates on the LAST third   (regime stability gate).

Independent segments prevent data reuse across gates — each surviving
alpha has paid its way through three disjoint OOS windows before any
tier=historical DEPLOYABLE label is granted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, TypeVar

import numpy as np

T = TypeVar("T")


@dataclass(frozen=True)
class HoldoutSplit:
    """Three disjoint slices of a holdout sequence."""

    a2: np.ndarray
    a3: np.ndarray
    a4: np.ndarray

    @property
    def sizes(self) -> tuple[int, int, int]:
        return (len(self.a2), len(self.a3), len(self.a4))


def split_holdout_three_ways(bars: Sequence[T] | np.ndarray) -> HoldoutSplit:
    """Split a holdout sequence into three contiguous equal thirds.

    Any remainder is attached to the last segment so every bar is used
    exactly once. Callers that need strict equal sizes must trim upstream.
    """
    arr = np.asarray(bars)
    n = arr.shape[0]
    if n < 3:
        raise ValueError(f"holdout too small to three-way split: n={n}")
    third = n // 3
    return HoldoutSplit(
        a2=arr[:third],
        a3=arr[third : 2 * third],
        a4=arr[2 * third :],
    )


def split_into_segments(bars: Sequence[T] | np.ndarray, n_segments: int) -> list[np.ndarray]:
    """Split into `n_segments` contiguous equal pieces for A3 stability.

    Uses np.array_split so an uneven total length is handled by giving the
    first few segments one extra element rather than dropping bars.
    """
    if n_segments < 2:
        raise ValueError(f"n_segments must be >= 2, got {n_segments}")
    arr = np.asarray(bars)
    if arr.shape[0] < n_segments:
        raise ValueError(f"sequence length {arr.shape[0]} < n_segments {n_segments}")
    return [np.asarray(seg) for seg in np.array_split(arr, n_segments)]


def split_into_k_folds(bars, k: int) -> list[np.ndarray]:
    """Split into k contiguous equal folds for ICIR-style stability scoring."""
    if k < 2:
        raise ValueError(f"k must be >= 2, got {k}")
    arr = np.asarray(bars)
    if arr.shape[0] < k:
        raise ValueError(f"sequence length {arr.shape[0]} < k {k}")
    return [np.asarray(seg) for seg in np.array_split(arr, k)]
