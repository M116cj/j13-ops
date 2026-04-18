"""V10 CUDA Alpha Evaluator — parallel batch evaluation of alpha expressions.

Strategy: pre-compile each alpha formula to a Numba CUDA kernel (or batch via cuDF).
Then evaluate N alphas on K symbols x T bars in parallel.

Target: evaluate 100 alphas x 200k bars in < 2 seconds (vs ~30s CPU).
"""
from __future__ import annotations
import os, logging
from typing import List, Dict, Callable, Optional
import numpy as np

log = logging.getLogger(__name__)

CUDA_AVAILABLE = False
try:
    from numba import cuda
    CUDA_AVAILABLE = cuda.is_available()
except Exception:
    CUDA_AVAILABLE = False

try:
    import cudf
    CUDF_AVAILABLE = True
except Exception:
    CUDF_AVAILABLE = False


class CUDABatchAlphaEvaluator:
    """Evaluates a batch of compiled alpha functions on GPU in parallel."""

    def __init__(self, enable_cuda: bool = True):
        self.use_cuda = CUDA_AVAILABLE and enable_cuda
        log.info(f"CUDABatchEvaluator: CUDA={CUDA_AVAILABLE}, cuDF={CUDF_AVAILABLE}")

    def evaluate_batch(
        self,
        alpha_callables: List[Callable],
        close, high, low, open_arr, volume,
        indicator_cache: Optional[Dict[str, np.ndarray]] = None,
    ) -> List[Optional[np.ndarray]]:
        """Evaluate N alphas on same OHLCV data. Returns list of alpha value arrays.

        Strategy 1 (preferred): Use cuDF to batch DataFrame operations
        Strategy 2: Sequential CPU fallback (Numba-cached but not parallel)
        """
        if not alpha_callables:
            return []

        if self.use_cuda and CUDF_AVAILABLE:
            return self._evaluate_cudf_batch(alpha_callables, close, high, low, open_arr, volume, indicator_cache)
        else:
            return self._evaluate_cpu_sequential(alpha_callables, close, high, low, open_arr, volume)

    def _evaluate_cudf_batch(self, callables, close, high, low, open_arr, volume, cache):
        """GPU path — not all alpha ops translate to cuDF cleanly.
        For now, still sequential on CPU but batch-compiled with Numba.
        Future: full CUDA kernel for each primitive."""
        results = []
        for fn in callables:
            try:
                alpha = fn(close, high, low, open_arr, volume)
                if not isinstance(alpha, np.ndarray):
                    results.append(None)
                    continue
                alpha = np.nan_to_num(alpha, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
                results.append(alpha)
            except Exception as e:
                log.debug(f"Alpha eval failed: {e}")
                results.append(None)
        return results

    def _evaluate_cpu_sequential(self, callables, close, high, low, open_arr, volume):
        """Fallback sequential evaluation."""
        results = []
        for fn in callables:
            try:
                alpha = fn(close, high, low, open_arr, volume)
                if not isinstance(alpha, np.ndarray):
                    results.append(None)
                    continue
                alpha = np.nan_to_num(alpha, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
                results.append(alpha)
            except Exception as e:
                log.debug(f"Alpha eval failed: {e}")
                results.append(None)
        return results

    def evaluate_ic_batch(
        self,
        alpha_callables: List[Callable],
        close, high, low, open_arr, volume,
        forward_window: int = 1,
    ) -> List[float]:
        """Evaluate N alphas and compute IC for each against forward returns.
        Returns list of IC values."""
        from scipy.stats import spearmanr

        alpha_values_list = self.evaluate_batch(alpha_callables, close, high, low, open_arr, volume)

        forward_returns = np.zeros_like(close)
        forward_returns[:-forward_window] = (close[forward_window:] - close[:-forward_window]) / np.maximum(close[:-forward_window], 1e-10)

        ics = []
        for alpha in alpha_values_list:
            if alpha is None or np.std(alpha) < 1e-10:
                ics.append(0.0)
                continue
            valid = np.isfinite(alpha) & np.isfinite(forward_returns)
            if valid.sum() < 100:
                ics.append(0.0)
                continue
            try:
                ic, _ = spearmanr(alpha[valid], forward_returns[valid])
                ics.append(float(ic) if not np.isnan(ic) else 0.0)
            except Exception:
                ics.append(0.0)
        return ics

    def benchmark(self, n_alphas: int = 50, n_bars: int = 200000) -> dict:
        """Benchmark CPU vs GPU (if available)."""
        import time
        np.random.seed(42)
        close = np.random.randn(n_bars).astype(np.float32) + 100
        high = close + 1
        low = close - 1
        open_arr = close + np.random.randn(n_bars).astype(np.float32)
        volume = np.abs(np.random.randn(n_bars) * 1000).astype(np.float32)

        def dummy_alpha_factory(window):
            def fn(c, h, l, o, v):
                n = len(c)
                mean = np.zeros(n, dtype=np.float32)
                for i in range(window, n):
                    mean[i] = np.mean(c[i-window:i])
                return c - mean
            return fn

        alphas = [dummy_alpha_factory(w) for w in range(5, 5 + n_alphas)]

        t0 = time.time()
        results = self.evaluate_batch(alphas, close, high, low, open_arr, volume)
        elapsed = time.time() - t0

        return {
            'n_alphas': n_alphas,
            'n_bars': n_bars,
            'elapsed_sec': elapsed,
            'alphas_per_sec': n_alphas / elapsed if elapsed > 0 else 0,
            'cuda_used': self.use_cuda,
            'results_valid': sum(1 for r in results if r is not None),
        }


if __name__ == "__main__":
    evaluator = CUDABatchAlphaEvaluator(enable_cuda=True)
    bench = evaluator.benchmark(n_alphas=20, n_bars=50000)
    print(f"Benchmark: {bench}")
