"""TF2 Signal Aggregation — prototype helper.

TEAM ORDER: 0-9Y-TF2-SIGNAL-AGGREGATION-PROTOTYPE
Status:     prototype, default OFF, SHADOW-only.

Mission: reduce trade frequency / increase per-trade quality WITHOUT changing
validation thresholds, cost model, A2_MIN_TRADES, champion promotion, or
deployable semantics. The live arena_pipeline path remains untouched unless
explicitly invoked with a non-OFF profile.

Architecture
------------
This module operates on (signals, sizes, strength) NumPy arrays that come
out of `engine.components.alpha_signal.generate_alpha_signals(...)` and
filters at **entry transitions** (i.e. bars where signals[i-1]==0 and
signals[i]!=0). Filtering at the trade level — not bar level — preserves
the state-machine invariant downstream backtester expects.

Profiles
--------
- OFF / BASELINE     : pass-through (regression sentinel)
- STRENGTH_FILTER    : keep entries with strength >= q-th quantile
- TOP_K_PER_BAR      : keep top-K strongest entries (across the series)
- HYBRID_TOPK_STRENGTH : STRENGTH_FILTER then TOP_K
- CONSENSUS_2_OF_3   : deferred (multi-alpha context required)

Safety
------
- Pure function: returns new arrays; input arrays are not mutated.
- Unknown profile raises ValueError (fails closed).
- NaN strengths treated as -inf (always suppressed).
- Deterministic: stable argsort + index tiebreak.
- No look-ahead: only inspects strength at the entry bar.
- No coupling to validation, cost, A2, alpha_zoo, CANARY, production flags.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import numpy as np


# --- profile names (string constants used in telemetry) ---------------------
PROFILE_OFF = "OFF"
PROFILE_BASELINE = "BASELINE"  # alias of OFF for telemetry clarity
PROFILE_STRENGTH_FILTER = "STRENGTH_FILTER"
PROFILE_TOP_K_PER_BAR = "TOP_K_PER_BAR"
PROFILE_HYBRID = "HYBRID_TOPK_STRENGTH"
PROFILE_CONSENSUS = "CONSENSUS_2_OF_3"  # deferred

ALLOWED_PROFILES = frozenset({
    PROFILE_OFF,
    PROFILE_BASELINE,
    PROFILE_STRENGTH_FILTER,
    PROFILE_TOP_K_PER_BAR,
    PROFILE_HYBRID,
    PROFILE_CONSENSUS,
})

PASS_THROUGH_PROFILES = frozenset({PROFILE_OFF, PROFILE_BASELINE})


# --- skip reason constants ---------------------------------------------------
SKIP_REASON_STRENGTH_BELOW_Q = "strength_below_quantile"
SKIP_REASON_BELOW_TOPK_RANK = "below_topk_rank"
SKIP_REASON_NAN_STRENGTH = "nan_strength"
SKIP_REASON_HYBRID_STRENGTH = "hybrid_strength_below_q"
SKIP_REASON_HYBRID_TOPK = "hybrid_below_topk_rank"


@dataclass(frozen=True)
class AggregationResult:
    """Output of `apply_signal_aggregation`.

    Fields
    ------
    signals : int8 ndarray
        Filtered signals. Length = len(input_signals). Suppressed trade
        segments are zeroed bar-by-bar from entry through (next 0).
    sizes : float64 ndarray
        Filtered sizes (zeroed where signals are zeroed).
    kept : bool ndarray, length = number of entry edges in input
        True where the i-th entry edge was kept; False if suppressed.
    profile : str
    entered_count : int
        Number of entry edges in input signal series.
    kept_count : int
        Number of entries kept after aggregation.
    skipped_count : int
        entered_count - kept_count.
    metadata : dict
        Per-profile diagnostic fields:
        - "strength_threshold" : float | None
        - "top_k"              : int   | None
        - "skip_reason_distribution" : Dict[str, int]
        - "mean_strength_kept" : float | None
        - "mean_strength_skipped" : float | None
        - "deferred_not_implemented" : bool (only for CONSENSUS_2_OF_3)
    """
    signals: np.ndarray
    sizes: np.ndarray
    kept: np.ndarray
    profile: str
    entered_count: int
    kept_count: int
    skipped_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)


def _entry_edges(signals: np.ndarray) -> np.ndarray:
    """Return indices i where signals[i-1]==0 and signals[i]!=0.

    Implementation: prepend a 0 so signals[-1] is treated as 0.
    """
    if signals.size == 0:
        return np.zeros(0, dtype=np.int64)
    prev = np.empty_like(signals)
    prev[0] = 0
    prev[1:] = signals[:-1]
    edges = np.where((prev == 0) & (signals != 0))[0]
    return edges.astype(np.int64)


def _exit_indices(signals: np.ndarray, entries: np.ndarray) -> np.ndarray:
    """For each entry index e, return the exit index x (first bar at-or-after
    e where signals==0). If signal stays non-zero through end, x = N.
    """
    n = signals.size
    exits = np.zeros_like(entries)
    for k, e in enumerate(entries):
        x = e + 1
        while x < n and signals[x] != 0:
            x += 1
        exits[k] = x
    return exits


def _suppress_segment(signals: np.ndarray, sizes: np.ndarray,
                      e: int, x: int) -> None:
    """In-place zero out [e:x). Used on COPIES of input; never on caller's data."""
    signals[e:x] = 0
    sizes[e:x] = 0.0


def _replace_nan(strength: np.ndarray) -> np.ndarray:
    """Replace NaN with -inf so they sort to the bottom and never pass any threshold."""
    out = np.asarray(strength, dtype=np.float64).copy()
    mask = np.isnan(out)
    if mask.any():
        out[mask] = -np.inf
    return out


def apply_signal_aggregation(
    signals: np.ndarray,
    sizes: np.ndarray,
    *,
    profile: str = PROFILE_OFF,
    strength: Optional[np.ndarray] = None,
    strength_quantile: Optional[float] = None,
    top_k: Optional[int] = None,
) -> AggregationResult:
    """Apply TF2 signal aggregation to a single (signals, sizes) pair.

    Parameters
    ----------
    signals : int8/int ndarray
        State-machine signal output: +1 long, -1 short, 0 flat.
    sizes : float ndarray
        Position size per bar. Same length as signals.
    profile : str
        One of the ALLOWED_PROFILES constants. OFF/BASELINE = pass-through.
    strength : ndarray, optional
        Per-bar signal strength. If None, defaults to `sizes` (which is
        |rank-0.5|*2 in the current alpha_signal.py contract).
    strength_quantile : float, optional
        Required for STRENGTH_FILTER and HYBRID. e.g. 0.90 = top 10%.
    top_k : int, optional
        Required for TOP_K_PER_BAR and HYBRID. Number of strongest entries to keep.

    Returns
    -------
    AggregationResult

    Raises
    ------
    ValueError
        If `profile` is not in ALLOWED_PROFILES, or required parameters
        for the chosen profile are missing.
    """
    if profile not in ALLOWED_PROFILES:
        raise ValueError(
            f"unknown profile {profile!r}; allowed: {sorted(ALLOWED_PROFILES)}"
        )

    sig_arr = np.asarray(signals, dtype=np.int8)
    size_arr = np.asarray(sizes, dtype=np.float64)
    if sig_arr.shape != size_arr.shape:
        raise ValueError(
            f"signals and sizes must have same shape: {sig_arr.shape} vs {size_arr.shape}"
        )

    # Always operate on copies so caller's arrays are never mutated.
    out_sig = sig_arr.copy()
    out_size = size_arr.copy()

    entries = _entry_edges(sig_arr)
    entered_count = int(entries.size)

    # Pass-through profiles (and deferred CONSENSUS) ---------------------------
    if profile in PASS_THROUGH_PROFILES:
        return AggregationResult(
            signals=out_sig,
            sizes=out_size,
            kept=np.ones(entered_count, dtype=bool),
            profile=profile,
            entered_count=entered_count,
            kept_count=entered_count,
            skipped_count=0,
            metadata={
                "strength_threshold": None,
                "top_k": None,
                "skip_reason_distribution": {},
                "mean_strength_kept": None,
                "mean_strength_skipped": None,
            },
        )

    if profile == PROFILE_CONSENSUS:
        # Deferred: returns input unchanged with explicit metadata flag.
        # This is INTENTIONAL — consensus requires multi-alpha context not
        # available in the single-alpha pipeline. Marked explicitly so
        # SHADOW evaluation can record "no-op" rather than silent skip.
        return AggregationResult(
            signals=out_sig,
            sizes=out_size,
            kept=np.ones(entered_count, dtype=bool),
            profile=profile,
            entered_count=entered_count,
            kept_count=entered_count,
            skipped_count=0,
            metadata={
                "strength_threshold": None,
                "top_k": None,
                "skip_reason_distribution": {},
                "mean_strength_kept": None,
                "mean_strength_skipped": None,
                "deferred_not_implemented": True,
            },
        )

    # Profiles below require entries to operate on.
    if entered_count == 0:
        # No entries to filter — return pass-through with profile recorded.
        return AggregationResult(
            signals=out_sig,
            sizes=out_size,
            kept=np.zeros(0, dtype=bool),
            profile=profile,
            entered_count=0,
            kept_count=0,
            skipped_count=0,
            metadata={
                "strength_threshold": None,
                "top_k": None,
                "skip_reason_distribution": {},
                "mean_strength_kept": None,
                "mean_strength_skipped": None,
            },
        )

    # Resolve strength source.
    if strength is None:
        strength_arr = size_arr.astype(np.float64, copy=True)
    else:
        strength_arr = np.asarray(strength, dtype=np.float64)
        if strength_arr.shape != sig_arr.shape:
            raise ValueError(
                f"strength must have same shape as signals: {strength_arr.shape} vs {sig_arr.shape}"
            )
    strength_arr = _replace_nan(strength_arr)
    entry_strength = strength_arr[entries]  # length = entered_count

    # NaN tracking (post-replace, NaN became -inf — count them for telemetry)
    nan_mask = ~np.isfinite(entry_strength)  # True where -inf (was NaN) or +inf
    nan_count = int(nan_mask.sum())

    kept_mask = np.ones(entered_count, dtype=bool)
    skip_dist: Dict[str, int] = {}
    threshold_used: Optional[float] = None
    top_k_used: Optional[int] = None

    if profile == PROFILE_STRENGTH_FILTER:
        if strength_quantile is None:
            raise ValueError("STRENGTH_FILTER requires strength_quantile")
        if not (0.0 < strength_quantile < 1.0):
            raise ValueError(
                f"strength_quantile must be in (0,1); got {strength_quantile}"
            )
        # Quantile over finite entry strengths only; if all are -inf, threshold = -inf.
        finite = entry_strength[np.isfinite(entry_strength)]
        if finite.size > 0:
            threshold = float(np.quantile(finite, strength_quantile))
        else:
            threshold = float("-inf")
        threshold_used = threshold
        below_q = entry_strength < threshold
        # NaN-derived -inf entries are below threshold by construction; record reason.
        kept_mask &= ~below_q
        n_below = int(below_q.sum() - nan_count)
        if n_below > 0:
            skip_dist[SKIP_REASON_STRENGTH_BELOW_Q] = n_below
        if nan_count > 0:
            skip_dist[SKIP_REASON_NAN_STRENGTH] = nan_count

    elif profile == PROFILE_TOP_K_PER_BAR:
        if top_k is None:
            raise ValueError("TOP_K_PER_BAR requires top_k")
        if top_k < 0:
            raise ValueError(f"top_k must be >= 0; got {top_k}")
        top_k_used = int(top_k)
        if top_k >= entered_count:
            # K large enough to keep all
            pass
        else:
            # Stable sort: equal-strength ties broken by earliest index.
            # Sort descending by strength; tiebreak: smaller original index first.
            order = np.lexsort((np.arange(entered_count), -entry_strength))
            keep_idx = np.zeros(entered_count, dtype=bool)
            keep_idx[order[:top_k]] = True
            below_topk = ~keep_idx
            kept_mask &= ~below_topk
            n_below = int(below_topk.sum() - nan_count)
            if n_below > 0:
                skip_dist[SKIP_REASON_BELOW_TOPK_RANK] = n_below
            if nan_count > 0:
                skip_dist[SKIP_REASON_NAN_STRENGTH] = nan_count

    elif profile == PROFILE_HYBRID:
        if strength_quantile is None or top_k is None:
            raise ValueError(
                "HYBRID_TOPK_STRENGTH requires both strength_quantile and top_k"
            )
        if not (0.0 < strength_quantile < 1.0):
            raise ValueError(
                f"strength_quantile must be in (0,1); got {strength_quantile}"
            )
        if top_k < 0:
            raise ValueError(f"top_k must be >= 0; got {top_k}")
        # Step 1: strength filter
        finite = entry_strength[np.isfinite(entry_strength)]
        if finite.size > 0:
            threshold = float(np.quantile(finite, strength_quantile))
        else:
            threshold = float("-inf")
        threshold_used = threshold
        top_k_used = int(top_k)
        below_q = entry_strength < threshold
        n_below_q = int(below_q.sum() - nan_count)
        if n_below_q > 0:
            skip_dist[SKIP_REASON_HYBRID_STRENGTH] = n_below_q
        # Step 2: top-K among survivors
        survivors = ~below_q
        survivor_idx = np.where(survivors)[0]
        if survivor_idx.size > top_k:
            sub_strength = entry_strength[survivor_idx]
            order = np.lexsort((survivor_idx, -sub_strength))
            keep_within_survivors = np.zeros(survivor_idx.size, dtype=bool)
            keep_within_survivors[order[:top_k]] = True
            keep_full = np.zeros(entered_count, dtype=bool)
            keep_full[survivor_idx[keep_within_survivors]] = True
            n_below_topk = int(survivor_idx.size - top_k)
            if n_below_topk > 0:
                skip_dist[SKIP_REASON_HYBRID_TOPK] = n_below_topk
            kept_mask = keep_full
        else:
            # All survivors fit within top-K
            kept_mask = survivors
        if nan_count > 0:
            skip_dist[SKIP_REASON_NAN_STRENGTH] = nan_count

    # Apply suppression to copies.
    if not kept_mask.all():
        exits = _exit_indices(sig_arr, entries)
        for k in range(entered_count):
            if not kept_mask[k]:
                _suppress_segment(out_sig, out_size, int(entries[k]), int(exits[k]))

    kept_count = int(kept_mask.sum())
    skipped_count = entered_count - kept_count
    if kept_count > 0:
        kept_strength_vals = entry_strength[kept_mask & np.isfinite(entry_strength)]
        mean_kept = float(kept_strength_vals.mean()) if kept_strength_vals.size else None
    else:
        mean_kept = None
    if skipped_count > 0:
        skipped_strength_vals = entry_strength[(~kept_mask) & np.isfinite(entry_strength)]
        mean_skipped = (
            float(skipped_strength_vals.mean()) if skipped_strength_vals.size else None
        )
    else:
        mean_skipped = None

    return AggregationResult(
        signals=out_sig,
        sizes=out_size,
        kept=kept_mask,
        profile=profile,
        entered_count=entered_count,
        kept_count=kept_count,
        skipped_count=skipped_count,
        metadata={
            "strength_threshold": threshold_used,
            "top_k": top_k_used,
            "skip_reason_distribution": skip_dist,
            "mean_strength_kept": mean_kept,
            "mean_strength_skipped": mean_skipped,
        },
    )
