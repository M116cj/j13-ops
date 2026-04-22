"""V10 Alpha Signal Generator — Convert alpha values to trade signals.

Input: alpha_values from alpha_engine (continuous float array)
Output: signals (int8 array: 1=long, -1=short, 0=flat) + sizes (float array)

Replaces: generate_threshold_signals() in signal_utils.py
"""
import numpy as np
from numba import njit
import logging

log = logging.getLogger(__name__)


@njit(cache=True)
def alpha_to_signal(
    alpha: np.ndarray,
    entry_rank_threshold: float = 0.80,   # Enter when |rank| > 0.80
    exit_rank_threshold: float = 0.50,    # Exit when |rank| < 0.50
    rank_window: int = 500,               # Rolling rank window
    min_hold: int = 60,
    cooldown: int = 60,
) -> tuple:
    """
    Alpha continuous values → (signals, sizes, agreements)
    
    Strategy:
    1. Rolling percentile rank of alpha (causal, last 500 bars)
    2. Enter long if rank > 0.80, short if rank < 0.20
    3. Exit when rank returns to [0.30, 0.70]
    4. Position size = |rank - 0.5| × 2 (magnitude of signal)
    """
    n = len(alpha)
    signals = np.zeros(n, dtype=np.int8)
    sizes = np.zeros(n, dtype=np.float64)
    agreements = np.zeros(n, dtype=np.float32)
    
    position = 0
    hold_count = 0
    bars_since_exit = 0
    
    for i in range(rank_window, n):
        # Rolling rank: count of past values less than current
        window_start = max(0, i - rank_window)
        less = 0
        equal = 0
        for j in range(window_start, i + 1):
            if alpha[j] < alpha[i]:
                less += 1
            elif alpha[j] == alpha[i]:
                equal += 1
        rank = (less + equal * 0.5) / (i - window_start + 1)
        
        agreements[i] = abs(rank - 0.5) * 2.0  # 0 at median, 1 at extreme
        
        # Position sizing based on rank extremity
        size = abs(rank - 0.5) * 2.0
        
        if position == 0:
            bars_since_exit += 1
            if bars_since_exit >= cooldown and size >= 2 * entry_rank_threshold - 1.0:
                # Decide direction
                if rank > 0.5:
                    position = 1  # Long: alpha is high (bullish signal)
                elif rank < 0.5:
                    position = -1  # Short
                if position != 0:
                    signals[i] = position
                    sizes[i] = size
                    hold_count = 0
                    bars_since_exit = 0
        else:
            hold_count += 1
            # Exit conditions
            if hold_count >= min_hold and size < exit_rank_threshold:
                signals[i] = 0
                position = 0
                hold_count = 0
                bars_since_exit = 0
            else:
                signals[i] = position
                sizes[i] = size
    
    return signals, sizes, agreements


def generate_alpha_signals(
    alpha_values: np.ndarray,
    entry_threshold: float = 0.80,
    exit_threshold: float = 0.50,
    min_hold: int = 60,
    cooldown: int = 60,
    rank_window: int = 500,
) -> tuple:
    """Public API matching signal_utils.generate_threshold_signals signature.
    
    Returns (signals, sizes, agreements) — same tuple structure as V9.
    """
    if not isinstance(alpha_values, np.ndarray):
        alpha_values = np.asarray(alpha_values, dtype=np.float32)
    alpha_values = np.nan_to_num(alpha_values.astype(np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    
    return alpha_to_signal(
        alpha_values, entry_threshold, exit_threshold, rank_window, min_hold, cooldown
    )


if __name__ == "__main__":
    # Self-test
    np.random.seed(42)
    n = 2000
    # Create synthetic alpha with clear signal
    trend = np.cumsum(np.random.randn(n) * 0.01)
    alpha = np.sin(np.arange(n) * 0.05) + trend * 0.5
    alpha = alpha.astype(np.float32)
    
    signals, sizes, agreements = generate_alpha_signals(alpha)
    
    n_long = (signals == 1).sum()
    n_short = (signals == -1).sum()
    n_flat = (signals == 0).sum()
    print(f"Signal distribution: long={n_long} short={n_short} flat={n_flat}")
    print(f"Position size: min={sizes.min():.3f} max={sizes.max():.3f} mean={sizes[signals!=0].mean() if (signals!=0).any() else 0:.3f}")
    print(f"Agreement stats: min={agreements.min():.3f} max={agreements.max():.3f}")
    
    # Verify no NaN/Inf
    assert not np.any(np.isnan(sizes)), "NaN in sizes"
    assert not np.any(np.isnan(agreements)), "NaN in agreements"
    print("Self-test passed")
