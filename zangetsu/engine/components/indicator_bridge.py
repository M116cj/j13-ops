"""V10 Indicator Bridge — Pre-compute all indicators with rolling periods.
Integrates Rust zangetsu_indicators with alpha_engine's GP terminals.
"""
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging

log = logging.getLogger(__name__)

try:
    import zangetsu_indicators as zi
    HAS_RUST = True
except ImportError:
    HAS_RUST = False

INDICATORS = [
    "rsi", "stochastic_k", "cci", "roc", "ppo", "cmo",
    "zscore", "trix", "tsi", "obv", "mfi", "vwap",
    "normalized_atr", "realized_vol", "bollinger_bw",
    "relative_volume", "vwap_deviation"
]
FACTOR_INDICATORS = ["funding_rate", "funding_zscore", "oi_change", "oi_divergence"]
PERIODS = [7, 14, 20, 30, 50, 100]


def build_indicator_cache(
    close: np.ndarray, high: np.ndarray, low: np.ndarray, 
    volume: np.ndarray, 
    funding: Optional[np.ndarray] = None,
    oi: Optional[np.ndarray] = None,
) -> Dict[str, np.ndarray]:
    """Compute all (indicator, period) combos and return as cache dict.
    
    Rust engine requires float64 arrays.
    Output arrays are float32 for memory efficiency in GP evaluation.
    """
    if not HAS_RUST:
        log.warning("Rust indicators unavailable")
        return {}
    
    # Ensure float64 for Rust
    close64 = np.ascontiguousarray(close, dtype=np.float64)
    high64 = np.ascontiguousarray(high, dtype=np.float64)
    low64 = np.ascontiguousarray(low, dtype=np.float64)
    volume64 = np.ascontiguousarray(volume, dtype=np.float64)
    
    cache = {}
    
    # Price-based indicators with periods
    for ind in INDICATORS:
        for period in PERIODS:
            try:
                vals = zi.compute(ind, {"period": period}, close64, high64, low64, volume64)
                # Convert to float32 for storage
                cache[f"{ind}_{period}"] = np.nan_to_num(
                    vals.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0
                )
            except Exception as e:
                log.debug(f"Indicator {ind}_{period} failed: {e}")
                # Fill with zeros so GP doesn't break
                cache[f"{ind}_{period}"] = np.zeros(len(close), dtype=np.float32)
    
    # Factor indicators (funding rate, OI)
    if funding is not None:
        cache["funding_rate"] = np.nan_to_num(
            funding.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0
        )
        # funding_zscore with multiple windows
        for w in [50, 100, 200]:
            cache[f"funding_zscore_{w}"] = _rolling_zscore(funding, w).astype(np.float32)
    
    if oi is not None:
        cache["oi_raw"] = oi.astype(np.float32)
        for d in [1, 5, 14]:
            cache[f"oi_change_{d}"] = _rolling_pct_change(oi, d).astype(np.float32)
    
    log.info(f"Built indicator cache: {len(cache)} arrays, {sum(a.nbytes for a in cache.values()) / 1024 / 1024:.1f} MB")
    return cache


def _rolling_zscore(x: np.ndarray, window: int) -> np.ndarray:
    """Causal rolling z-score."""
    n = len(x)
    out = np.zeros(n, dtype=np.float64)
    for i in range(window, n):
        w = x[i-window:i]
        mean = np.nanmean(w)
        std = np.nanstd(w)
        if std > 1e-10:
            out[i] = (x[i] - mean) / std
    return out


def _rolling_pct_change(x: np.ndarray, d: int) -> np.ndarray:
    """Causal rolling percent change."""
    n = len(x)
    out = np.zeros(n, dtype=np.float64)
    for i in range(d, n):
        if abs(x[i-d]) > 1e-10:
            out[i] = (x[i] - x[i-d]) / x[i-d]
    return out


def estimate_cache_size(n_bars: int, n_symbols: int = 14) -> dict:
    """Estimate memory for indicator cache."""
    arrays_per_symbol = len(INDICATORS) * len(PERIODS) + 10  # + factors
    bytes_per_array = n_bars * 4  # float32
    total_bytes = arrays_per_symbol * bytes_per_array * n_symbols
    return {
        "arrays_per_symbol": arrays_per_symbol,
        "bytes_per_array_mb": bytes_per_array / 1024 / 1024,
        "total_symbols": n_symbols,
        "total_mb": total_bytes / 1024 / 1024,
        "total_gb": total_bytes / 1024 / 1024 / 1024,
    }


if __name__ == "__main__":
    # Self-test
    est = estimate_cache_size(200000, 14)
    print(f"Cache estimate: {est}")
    
    # Test with small synthetic data
    n = 1000
    close = np.cumprod(1 + np.random.randn(n) * 0.001) * 100
    high = close * 1.01
    low = close * 0.99
    vol = np.random.exponential(1000, n)
    
    cache = build_indicator_cache(close, high, low, vol)
    print(f"Cache built: {len(cache)} arrays")
    print(f"Sample keys: {list(cache.keys())[:10]}")
    print(f"RSI_14 sample: min={cache.get('rsi_14', [0]).min():.2f} max={cache.get('rsi_14', [0]).max():.2f}")
