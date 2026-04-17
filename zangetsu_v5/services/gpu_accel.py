"""V9 GPU Acceleration Wrapper.

Optional cuDF-accelerated operations. All functions fall back to numpy/pandas
if cuDF unavailable or operation fails.

Usage:
    from services.gpu_accel import accelerate_df, GPU_AVAILABLE
    if GPU_AVAILABLE:
        df = accelerate_df(df)  # converts to cudf
    # All subsequent operations run on GPU until .to_pandas() called
"""
from __future__ import annotations
import logging
import numpy as np

log = logging.getLogger(__name__)

GPU_AVAILABLE = False
try:
    import cudf
    # Quick functional test
    _test = cudf.Series([1.0, 2.0])
    _ = _test.rolling(2).mean()
    GPU_AVAILABLE = True
    log.info(f"cuDF {cudf.__version__} detected and functional")
except Exception as e:
    log.info(f"GPU acceleration unavailable: {e}")
    cudf = None


def accelerate_df(df):
    """Convert pandas DataFrame or polars DataFrame to cuDF if GPU available.
    
    Returns cuDF DataFrame on success, original df on failure.
    """
    if not GPU_AVAILABLE:
        return df
    try:
        import pandas as pd
        if isinstance(df, pd.DataFrame):
            return cudf.from_pandas(df)
        # polars -> pandas -> cudf
        if hasattr(df, "to_pandas"):
            return cudf.from_pandas(df.to_pandas())
    except Exception as e:
        log.warning(f"GPU accel failed, falling back: {e}")
    return df


def rolling_mean_gpu(arr: np.ndarray, window: int) -> np.ndarray:
    """Rolling mean on GPU if available, else numpy."""
    if not GPU_AVAILABLE or len(arr) < 1000:  # Skip GPU for small arrays (overhead dominates)
        # Numpy fallback
        cs = np.cumsum(arr)
        result = np.empty_like(arr)
        result[:window] = arr[:window].mean()
        result[window:] = (cs[window:] - cs[:-window]) / window
        return result
    try:
        s = cudf.Series(arr)
        result = s.rolling(window).mean().to_numpy()
        return np.nan_to_num(result, nan=arr[0] if len(arr) > 0 else 0.0)
    except Exception:
        cs = np.cumsum(arr)
        result = np.empty_like(arr)
        result[:window] = arr[:window].mean()
        result[window:] = (cs[window:] - cs[:-window]) / window
        return result


def rolling_std_gpu(arr: np.ndarray, window: int) -> np.ndarray:
    """Rolling std on GPU if available."""
    if not GPU_AVAILABLE or len(arr) < 1000:
        result = np.empty_like(arr)
        result[:window] = max(np.std(arr[:window]), 1e-10)
        for i in range(window, len(arr)):
            result[i] = max(np.std(arr[i-window:i]), 1e-10)
        return result
    try:
        s = cudf.Series(arr)
        result = s.rolling(window).std().to_numpy()
        return np.nan_to_num(result, nan=1e-10)
    except Exception:
        result = np.empty_like(arr)
        result[:window] = max(np.std(arr[:window]), 1e-10)
        for i in range(window, len(arr)):
            result[i] = max(np.std(arr[i-window:i]), 1e-10)
        return result


def benchmark_vs_cpu(n: int = 1_000_000, window: int = 100) -> dict:
    """Quick benchmark: GPU vs CPU for rolling operations."""
    import time
    arr = np.random.randn(n).astype(np.float64)
    
    t0 = time.time()
    cpu_result = np.convolve(arr, np.ones(window)/window, mode="same")
    cpu_time = time.time() - t0
    
    t0 = time.time()
    gpu_result = rolling_mean_gpu(arr, window)
    gpu_time = time.time() - t0
    
    return {
        "n": n,
        "window": window,
        "cpu_time_s": cpu_time,
        "gpu_time_s": gpu_time,
        "speedup": cpu_time / max(gpu_time, 1e-6),
        "gpu_available": GPU_AVAILABLE,
    }
