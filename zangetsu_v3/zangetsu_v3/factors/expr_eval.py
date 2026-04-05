"""Expression evaluator for bootstrap factors.

The evaluator translates a tiny, whitelisted AST into numpy operations
and provides light caching (approx 8 GB budget as per C25).  Only the
operations needed by the 15 bootstrap factors are implemented.
"""

from __future__ import annotations

import ast
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Dict

import numpy as np
import numba as nb
import polars as pl

CacheKey = tuple[int, str, str]


@nb.njit
def _rolling_corr(a: np.ndarray, b: np.ndarray, window: int) -> np.ndarray:
    n = len(a)
    out = np.empty(n, dtype=np.float64)
    out[:] = np.nan
    for i in range(window - 1, n):
        s1 = 0.0
        s2 = 0.0
        s12 = 0.0
        s11 = 0.0
        s22 = 0.0
        for j in range(i - window + 1, i + 1):
            x = a[j]
            y = b[j]
            s1 += x
            s2 += y
            s12 += x * y
            s11 += x * x
            s22 += y * y
        cov = s12 / window - (s1 / window) * (s2 / window)
        var1 = s11 / window - (s1 / window) ** 2
        var2 = s22 / window - (s2 / window) ** 2
        if var1 <= 0.0 or var2 <= 0.0:
            out[i] = np.nan
        else:
            out[i] = cov / np.sqrt(var1 * var2)
    return out


def ts_delta(x: np.ndarray, period: int) -> np.ndarray:
    out = np.empty_like(x, dtype=np.float64)
    out[:] = np.nan
    out[period:] = x[period:] - x[:-period]
    return out


def ts_rank(x: np.ndarray, window: int) -> np.ndarray:
    n = len(x)
    out = np.empty(n, dtype=np.float64)
    out[:] = np.nan
    for i in range(window - 1, n):
        window_slice = x[i - window + 1 : i + 1]
        ranks = window_slice.argsort().argsort() + 1  # 1-based rank
        out[i] = ranks[-1] / window
    return out


def ts_std(x: np.ndarray, window: int) -> np.ndarray:
    n = len(x)
    out = np.empty(n, dtype=np.float64)
    out[:] = np.nan
    for i in range(window - 1, n):
        window_slice = x[i - window + 1 : i + 1]
        out[i] = np.nanstd(window_slice, ddof=0)
    return out


def ts_mean(x: np.ndarray, window: int) -> np.ndarray:
    n = len(x)
    out = np.empty(n, dtype=np.float64)
    out[:] = np.nan
    for i in range(window - 1, n):
        out[i] = np.nanmean(x[i - window + 1 : i + 1])
    return out


def ts_corr(a: np.ndarray, b: np.ndarray, window: int) -> np.ndarray:
    return _rolling_corr(a, b, window)


def ts_skew(x: np.ndarray, window: int) -> np.ndarray:
    n = len(x)
    out = np.empty(n, dtype=np.float64)
    out[:] = np.nan
    for i in range(window - 1, n):
        w = x[i - window + 1 : i + 1]
        mean = np.mean(w)
        std = np.std(w)
        if std == 0:
            out[i] = 0.0
        else:
            centered = w - mean
            out[i] = np.mean(centered**3) / (std**3)
    return out


def ts_max(x: np.ndarray, window: int) -> np.ndarray:
    n = len(x)
    out = np.empty(n, dtype=np.float64)
    out[:] = np.nan
    for i in range(window - 1, n):
        out[i] = np.nanmax(x[i - window + 1 : i + 1])
    return out


def ts_min(x: np.ndarray, window: int) -> np.ndarray:
    n = len(x)
    out = np.empty(n, dtype=np.float64)
    out[:] = np.nan
    for i in range(window - 1, n):
        out[i] = np.nanmin(x[i - window + 1 : i + 1])
    return out


FUNC_MAP: Dict[str, Callable[..., np.ndarray]] = {
    "ts_delta": ts_delta,
    "ts_rank": ts_rank,
    "ts_std": ts_std,
    "ts_mean": ts_mean,
    "ts_corr": ts_corr,
    "ts_skew": ts_skew,
    "ts_max": ts_max,
    "ts_min": ts_min,
}


SAFE_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.USub,
    ast.Call,
    ast.Load,
    ast.Name,
    ast.Constant,
)


def _ensure_safe(node: ast.AST) -> None:
    for child in ast.walk(node):
        if not isinstance(child, SAFE_NODES):
            raise ValueError(f"Unsupported AST node: {type(child).__name__}")


def _eval(node: ast.AST, namespace: Dict[str, Any]) -> Any:
    if isinstance(node, ast.Expression):
        return _eval(node.body, namespace)
    if isinstance(node, ast.BinOp):
        left = _eval(node.left, namespace)
        right = _eval(node.right, namespace)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Pow):
            return left ** right
        raise ValueError("Unsupported binary operator")
    if isinstance(node, ast.UnaryOp):
        operand = _eval(node.operand, namespace)
        if isinstance(node.op, ast.USub):
            return -operand
        raise ValueError("Unsupported unary operator")
    if isinstance(node, ast.Name):
        if node.id not in namespace:
            raise ValueError(f"Unknown identifier {node.id}")
        return namespace[node.id]
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Call):
        func_name = getattr(node.func, "id", None)
        if func_name not in FUNC_MAP:
            raise ValueError(f"Unknown function {func_name}")
        args = [_eval(arg, namespace) for arg in node.args]
        return FUNC_MAP[func_name](*args)
    raise ValueError(f"Unhandled AST node {type(node).__name__}")


@dataclass
class ExprEval:
    cache_bytes: int = 8 * 1024**3

    def __post_init__(self):
        self._cache: OrderedDict[CacheKey, np.ndarray] = OrderedDict()
        self._bytes = 0

    def _evict(self):
        while self._bytes > self.cache_bytes and self._cache:
            _, arr = self._cache.popitem(last=False)
            self._bytes -= arr.nbytes

    def eval(
        self, expr: str, data: pl.DataFrame, symbol: str = "*", data_version: str = "default"
    ) -> np.ndarray:
        tree = ast.parse(expr, mode="eval")
        _ensure_safe(tree)
        ast_hash = hash(ast.dump(tree))
        key = (ast_hash, symbol, data_version)
        if key in self._cache:
            # move to end (most recent)
            arr = self._cache.pop(key)
            self._cache[key] = arr
            return arr

        namespace: Dict[str, Any] = {c: data[c].to_numpy() for c in data.columns}
        arr = _eval(tree, namespace)
        if not isinstance(arr, np.ndarray):
            arr = np.asarray(arr, dtype=np.float64)
        self._cache[key] = arr
        self._bytes += arr.nbytes
        self._evict()
        return arr


__all__ = [
    "ExprEval",
    "ts_delta",
    "ts_rank",
    "ts_std",
    "ts_mean",
    "ts_corr",
    "ts_skew",
    "ts_max",
    "ts_min",
]

