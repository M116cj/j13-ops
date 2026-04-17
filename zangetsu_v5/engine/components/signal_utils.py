"""Shared signal generation — V7.1 Semantic Continuous Signals.
Indicator-specific interpretation with continuous [-1,+1] strength signals.
Optimized: Numba JIT for inner loop.
V7.1: All indicators output continuous strength instead of binary votes."""
from __future__ import annotations
import numpy as np
from typing import Dict, List, Tuple, Callable

try:
    from numba import njit
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False
    def njit(*args, **kwargs):
        def wrapper(fn):
            return fn
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return wrapper


# ═══ V7.1: Continuous signal lambdas [-1, +1] ═══

# --- Overbought/Oversold group ---
def _ob_os_signal(v: np.ndarray, buy_thr: float, sell_thr: float) -> np.ndarray:
    """Continuous signal for bounded OB/OS indicators."""
    result = np.zeros(len(v), dtype=np.float64)
    buy_mask = v < buy_thr
    sell_mask = v > sell_thr
    result[buy_mask] = np.clip((buy_thr - v[buy_mask]) / buy_thr, 0.1, 1.0)
    result[sell_mask] = -np.clip((v[sell_mask] - sell_thr) / (100.0 - sell_thr), 0.1, 1.0)
    return result

# --- Zero-crossing group: uses tanh(value / MAD) ---
def _zero_cross_signal(v: np.ndarray) -> np.ndarray:
    """Continuous signal for zero-crossing indicators using tanh normalization."""
    mad = np.median(np.abs(v - np.median(v)))
    if mad < 1e-12:
        mad = np.std(v)
    if mad < 1e-12:
        return np.zeros(len(v), dtype=np.float64)
    return np.tanh(v / mad).astype(np.float64)

# --- Mean-reversion group ---
def _mean_rev_signal(v: np.ndarray, threshold: float) -> np.ndarray:
    """Continuous signal for mean-reversion indicators (zscore, vwap)."""
    result = np.zeros(len(v), dtype=np.float64)
    buy_mask = v < -threshold
    sell_mask = v > threshold
    result[buy_mask] = np.clip((-threshold - v[buy_mask]) / threshold, 0.1, 1.0)
    result[sell_mask] = -np.clip((v[sell_mask] - threshold) / threshold, 0.1, 1.0)
    return result


INDICATOR_SIGNALS: Dict[str, Callable] = {
    # Overbought/Oversold
    "rsi":          lambda v: _ob_os_signal(v, 30.0, 70.0),
    "stochastic_k": lambda v: _ob_os_signal(v, 20.0, 80.0),
    "stochastic_d": lambda v: _ob_os_signal(v, 20.0, 80.0),
    "mfi":          lambda v: _ob_os_signal(v, 20.0, 80.0),
    "stochrsi":     lambda v: _ob_os_signal(v, 20.0, 80.0),
    # CCI: buy < -100, sell > 100 — treat as OB/OS with shifted scale
    "cci":          lambda v: np.where(v < -100, np.clip((-100 - v) / 100, 0.1, 1.0),
                                np.where(v > 100, -np.clip((v - 100) / 100, 0.1, 1.0), 0.0)).astype(np.float64),
    # Williams %R: buy < -80, sell > -20 (inverted scale)
    "williams_r":   lambda v: np.where(v < -80, np.clip((-80 - v) / 20, 0.1, 1.0),
                                np.where(v > -20, -np.clip((v + 20) / 20, 0.1, 1.0), 0.0)).astype(np.float64),
    # Zero-crossing
    "roc":          _zero_cross_signal,
    "ppo":          _zero_cross_signal,
    "cmo":          _zero_cross_signal,
    "tsi":          _zero_cross_signal,
    "awesome_osc":  _zero_cross_signal,
    "trix":         _zero_cross_signal,
    "fisher":       _zero_cross_signal,
    "obv":          _zero_cross_signal,
    # Aroon oscillator: bounded [-100, 100] zero-cross
    "aroon_osc":    lambda v: np.tanh(v / 50.0).astype(np.float64),
    # Mean-reversion
    "zscore":       lambda v: _mean_rev_signal(v, 1.5),
    "vwap":         lambda v: _mean_rev_signal(v, 1.0),
    # ADX: trending strength (>25 trend, <15 no trend)
    "adx":          lambda v: np.where(v > 25, np.clip((v - 25) / 25, 0.1, 1.0),
                                np.where(v > -20, -np.clip((v + 20) / 20, 0.1, 1.0), 0.0)).astype(np.float64),
    # ── F2: Volatility factor signals ──
    # High vol = caution (negative), low vol = opportunity (positive)
    "normalized_atr": lambda v: -np.tanh((np.nan_to_num(v, nan=0.0) - np.nanmedian(v)) / max(np.nanstd(v), 1e-12)).astype(np.float64),
    "realized_vol":   lambda v: -np.tanh((np.nan_to_num(v, nan=0.0) - np.nanmedian(v)) / max(np.nanstd(v), 1e-12)).astype(np.float64),
    "bollinger_bw":   lambda v: -np.tanh((np.nan_to_num(v, nan=0.0) - np.nanmedian(v)) / max(np.nanstd(v), 1e-12)).astype(np.float64),
    # ── F3: Volume factor signals ──
    # High relative volume = confirmation strength
    "relative_volume": lambda v: np.tanh((v - 1.0) / 0.5).astype(np.float64),
    "vwap_deviation":  lambda v: _mean_rev_signal(v, 0.005),
    # ── F4: Funding Rate signals ──
    # Positive funding = longs pay shorts = contrarian SHORT signal; Negative = shorts pay longs = contrarian LONG
    "funding_rate":   lambda v: np.where(v < -0.0001, np.clip((-0.0001 - v) / 0.0003, 0.1, 1.0),
                                  np.where(v > 0.0003, -np.clip((v - 0.0003) / 0.0003, 0.1, 1.0), 0.0)).astype(np.float64),
    "funding_zscore": lambda v: _mean_rev_signal(v, 2.0),
    # ── F5: OI signals ──
    # Rising OI = trend confirmation, falling = exhaustion
    "oi_change":      _zero_cross_signal,
    "oi_divergence":  lambda v: -v.astype(np.float64),  # FIXED: divergence(+1)=reversal signal, convergence(-1)=trend confirms
}

# Regimes where momentum-based voting should be used instead of mean-reversion
TRENDING_REGIMES = frozenset({"BULL_TREND", "BULL_PULLBACK", "BEAR_TREND", "BEAR_RALLY"})

_BOUNDED_INDICATORS = frozenset({
    "rsi", "stochastic_k", "stochastic_d", "williams_r", "mfi", "stochrsi", "adx",
})


def _trend_vote(name: str, values: np.ndarray, regime: str) -> np.ndarray:
    """V7.1: Continuous momentum-based voting for trending regimes.
    Output: continuous [-1, +1] strength via tanh(delta / avg_delta)."""
    n = len(values)
    votes = np.zeros(n, dtype=np.float64)
    lookback = 14
    is_bull = regime.startswith("BULL")

    if n <= lookback:
        return votes

    # Precompute average absolute delta for normalization
    deltas = np.abs(np.diff(values[::lookback]))
    avg_delta = np.median(deltas) if len(deltas) > 0 else 1.0
    if avg_delta < 1e-12:
        avg_delta = np.std(values) if np.std(values) > 1e-12 else 1.0

    if name in _BOUNDED_INDICATORS:
        for i in range(lookback, n):
            delta = values[i] - values[i - lookback]
            short_delta = values[i] - values[i - 5] if i >= lookback + 5 else delta
            combined = (delta + short_delta) / 2.0
            strength = float(np.tanh(combined / avg_delta))
            if is_bull:
                votes[i] = strength
            else:
                votes[i] = -strength
    else:
        for i in range(lookback, n):
            val = values[i]
            delta = values[i] - values[i - lookback]
            combined = val + delta
            strength = float(np.tanh(combined / avg_delta))
            if is_bull:
                votes[i] = strength
            else:
                votes[i] = -strength

    return votes


def indicator_vote(name: str, values: np.ndarray, regime: str = "") -> np.ndarray:
    """V7.1: Vote based on indicator values. Returns continuous [-1, +1] strength."""
    if regime in TRENDING_REGIMES:
        return _trend_vote(name, values, regime)
    if name in INDICATOR_SIGNALS:
        return INDICATOR_SIGNALS[name](values)
    # Fallback: tanh normalization for unknown indicators
    med = np.median(values)
    mad = np.median(np.abs(values - med))
    if mad < 1e-12:
        mad = np.std(values)
    if mad < 1e-12:
        return np.zeros(len(values), dtype=np.float64)
    return np.tanh((values - med) / mad).astype(np.float64)


@njit(cache=True)
def _threshold_signals_numba(
    vote_matrix: np.ndarray,
    entry_threshold: float,
    exit_threshold: float,
    min_hold: int,
    cooldown: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """V7.1: Numba-jitted inner loop for signal generation.
    vote_matrix: float64 [-1, +1] continuous votes.
    Returns: (signals, sizes, agreements)."""
    n_bars = vote_matrix.shape[0]
    n_ind = vote_matrix.shape[1]

    signals = np.zeros(n_bars, dtype=np.int8)
    sizes = np.zeros(n_bars, dtype=np.float64)
    agreements = np.zeros(n_bars, dtype=np.float32)
    position = 0
    hold_count = 0
    bars_since_exit = cooldown

    for i in range(n_bars):
        # Count nonzero votes (|v| > 0.05 threshold)
        n_voters = 0
        long_count = 0
        short_count = 0
        abs_sum = 0.0
        for j in range(n_ind):
            v = vote_matrix[i, j]
            if abs(v) > 0.05:
                n_voters += 1
                abs_sum += abs(v)
                if v > 0:
                    long_count += 1
                else:
                    short_count += 1

        if n_voters == 0:
            agreements[i] = 0.0
            sizes[i] = 0.0
            if position != 0 and hold_count >= min_hold:
                signals[i] = 0
                position = 0
                bars_since_exit = 0
                hold_count = 0
            elif position != 0:
                signals[i] = position
                hold_count += 1
            else:
                bars_since_exit += 1
            continue

        if long_count > short_count:
            agreement_rate = long_count / n_voters
        elif short_count > long_count:
            agreement_rate = short_count / n_voters
        else:
            agreement_rate = 0.0  # FIXED BUG-8: tie = abstain (was defaulting SHORT)
        agreements[i] = agreement_rate

        # V7.1: strength = mean(|vote_values|) for nonzero votes
        strength = abs_sum / n_voters
        sizes[i] = strength

        if position == 0:
            bars_since_exit += 1
            if bars_since_exit >= cooldown and agreement_rate >= entry_threshold and n_voters >= 2:
                if long_count > short_count:
                    position = 1
                else:
                    position = -1
                signals[i] = position
                hold_count = 0
        else:
            hold_count += 1
            if hold_count >= min_hold:
                if long_count > short_count:
                    current_dir = 1
                else:
                    current_dir = -1
                if agreement_rate < exit_threshold or current_dir == -position:
                    signals[i] = 0
                    position = 0
                    bars_since_exit = 0
                    hold_count = 0
                else:
                    signals[i] = position
            else:
                signals[i] = position

    return signals, sizes, agreements


def generate_threshold_signals(
    indicator_names: List[str],
    indicator_values: List[np.ndarray],
    entry_threshold: float = 0.60,
    exit_threshold: float = 0.30,
    min_hold: int = 60,
    cooldown: int = 60,
    regime: str = "",
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """V7.1: Generate threshold signals with continuous voting.
    Returns: (signals, sizes, agreements) — 3-tuple for drop-in composite replacement."""
    n_bars = len(indicator_values[0])
    n_ind = len(indicator_names)

    vote_matrix = np.zeros((n_bars, n_ind), dtype=np.float64)
    for j, (name, vals) in enumerate(zip(indicator_names, indicator_values)):
        vote_matrix[:, j] = indicator_vote(name, vals, regime=regime)

    return _threshold_signals_numba(vote_matrix, entry_threshold, exit_threshold, min_hold, cooldown)


def compute_signal_strength(
    indicator_names: List[str],
    indicator_values: List[np.ndarray],
    agreements: np.ndarray,
    close: np.ndarray,
    vol_window: int = 60,
    regime: str = "",
) -> np.ndarray:
    n_bars = len(agreements)
    strengths = np.zeros(n_bars, dtype=np.float64)
    returns = np.diff(close, prepend=close[0]) / np.maximum(close, 1e-12)
    rolling_vol = np.zeros(n_bars, dtype=np.float64)
    for i in range(vol_window, n_bars):
        rolling_vol[i] = np.std(returns[i - vol_window:i])
    median_vol = np.median(rolling_vol[rolling_vol > 0]) if np.any(rolling_vol > 0) else 1e-12

    n_ind = len(indicator_names)
    vote_matrix = np.zeros((n_bars, n_ind), dtype=np.float64)
    for j, (name, vals) in enumerate(zip(indicator_names, indicator_values)):
        vote_matrix[:, j] = indicator_vote(name, vals, regime=regime)

    for i in range(n_bars):
        if agreements[i] == 0:
            continue
        nz = np.abs(vote_matrix[i]) > 0.05
        if not np.any(nz):
            continue
        base = agreements[i] * np.mean(np.abs(vote_matrix[i][nz]))
        vol_ratio = max(rolling_vol[i] / median_vol, 0.5) if median_vol > 0 else 0.5
        strengths[i] = base / vol_ratio
    return strengths


def grade_signal(strength: float) -> str:
    if strength >= 3.0:
        return "HIGH"
    elif strength >= 1.5:
        return "MED"
    return "LOW"


def grade_multiplier(grade: str) -> float:
    return {"HIGH": 1.0, "MED": 0.66, "LOW": 0.33}.get(grade, 0.33)
