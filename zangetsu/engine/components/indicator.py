"""Indicator computation via Rust PyO3 library + batch processing + dedup cache."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .data_loader import DatasetSnapshot


def _make_cache_key(indicator_name: str, params: Dict[str, Any], symbol: str) -> str:
    raw = f"{indicator_name}|{symbol}|{sorted(params.items())}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


INDICATOR_CATEGORIES = {
    "moving_average": ["sma", "ema", "wma", "dema", "tema", "kama", "t3", "vidya", "frama", "hma", "alma", "zlema", "swma", "trima"],
    "momentum": ["rsi", "macd", "stochastic_k", "stochastic_d", "cci", "roc", "williams_r", "mfi", "tsi", "ultimate_osc", "awesome_osc", "ppo", "pmo", "cmo", "dpo", "kst", "rvi", "stochrsi", "elder_ray_bull", "elder_ray_bear", "mass_index", "chande_forecast"],
    "trend": ["adx", "aroon_up", "aroon_down", "aroon_osc", "supertrend", "ichimoku_tenkan", "ichimoku_kijun", "ichimoku_senkou_a", "ichimoku_senkou_b", "psar", "linear_reg_slope", "linear_reg_intercept", "linear_reg_angle", "trix", "vortex_pos", "vortex_neg", "dmi_plus", "dmi_minus", "adxr", "apo", "fisher", "detrended_price", "choppiness", "rainbow_ma_1", "rainbow_ma_2", "rainbow_ma_3", "schaff_tc", "mcginley", "qstick", "hurst_exp"],
    "volatility": ["atr", "bollinger_upper", "bollinger_lower", "bollinger_mid", "bollinger_width", "keltner_upper", "keltner_lower", "keltner_mid", "donchian_upper", "donchian_lower", "donchian_width", "natr", "true_range", "ulcer_index", "chaikin_volatility", "historical_vol", "garman_klass", "parkinson", "rogers_satchell", "yang_zhang", "std_dev"],
    "volume_base": ["obv", "vwap", "mfi", "ad", "cmf", "eom", "force_index", "pvt", "nvi", "pvi", "vpt", "klinger", "volume_roc", "volume_sma", "volume_ema", "taker_buy_ratio", "relative_volume", "volume_profile_poc"],
    "volume_micro": ["tick_volume", "trade_intensity", "buy_sell_ratio", "large_trade_pct", "volume_imbalance", "micro_price", "trade_flow", "volume_clock", "bar_speed", "tick_speed", "aggressor_ratio", "kyle_lambda", "amihud_illiq", "roll_spread"],
    "price_action": ["pin_bar", "engulfing", "doji", "hammer", "shooting_star", "morning_star", "evening_star", "three_white", "three_black", "harami", "piercing", "dark_cloud", "tweezer_top", "tweezer_bottom", "marubozu", "spinning_top"],
    "cross_asset": ["btc_dominance", "eth_correlation", "btc_correlation", "sector_momentum", "alt_rotation", "stable_flow", "defi_tvl_change", "gas_price_norm", "hashrate_change", "difficulty_roc", "mempool_size"],
    "funding": ["funding_rate", "oi_total", "oi_delta", "long_short_ratio", "liquidation_volume", "basis_spread", "funding_predicted", "oi_weighted_price", "perp_premium", "funding_velocity", "oi_concentration"],
    "multi_timeframe": ["mtf_rsi", "mtf_macd", "mtf_adx", "mtf_bb_width", "mtf_volume", "mtf_atr"],
    "statistical": ["zscore", "skewness", "kurtosis", "hurst", "entropy", "autocorr", "variance_ratio"],
}

ALL_INDICATORS = []
for cat, names in INDICATOR_CATEGORIES.items():
    for name in names:
        ALL_INDICATORS.append((cat, name))


class IndicatorCompute:
    """Compute indicators via Rust PyO3 or fallback Python.

    Integration:
        - CONSOLE_HOOK: indicator_library_path, batch_size
        - DASHBOARD_HOOK: cache_size, cache_hit_rate, compute_time_ms
    """

    def __init__(self, config) -> None:
        self._lib_path = Path(config.indicator_library_path)
        self._rust_lib: Optional[Any] = None
        self._cache: Dict[str, np.ndarray] = {}
        self._cache_symbols: Dict[str, str] = {}
        self._hits: int = 0
        self._misses: int = 0
        self._total_compute_ms: float = 0.0
        self._load_rust_lib()

    def _load_rust_lib(self) -> None:
        if self._lib_path.exists():
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    "indicator_engine", str(self._lib_path)
                )
                if spec and spec.loader:
                    self._rust_lib = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(self._rust_lib)
            except Exception:
                self._rust_lib = None

    def compute_single(
        self,
        name: str,
        params: Dict[str, Any],
        snapshot: DatasetSnapshot,
    ) -> np.ndarray:
        key = _make_cache_key(name, params, snapshot.symbol)

        if key in self._cache:
            self._hits += 1
            return self._cache[key]

        self._misses += 1
        t0 = time.monotonic()

        if self._rust_lib and hasattr(self._rust_lib, "compute"):
            result = self._rust_lib.compute(
                name, params,
                snapshot.close, snapshot.high, snapshot.low, snapshot.volume,
            )
            result = np.asarray(result, dtype=np.float64)
        else:
            result = self._python_fallback(name, params, snapshot)

        elapsed = (time.monotonic() - t0) * 1000
        self._total_compute_ms += elapsed

        self._cache[key] = result
        self._cache_symbols[key] = snapshot.symbol
        return result

    def compute_batch(
        self,
        indicators: List[Tuple[str, Dict[str, Any]]],
        snapshot: DatasetSnapshot,
    ) -> Dict[str, np.ndarray]:
        results: Dict[str, np.ndarray] = {}
        for name, params in indicators:
            key = _make_cache_key(name, params, snapshot.symbol)
            results[key] = self.compute_single(name, params, snapshot)
        return results

    def _python_fallback(
        self, name: str, params: Dict[str, Any], snap: DatasetSnapshot
    ) -> np.ndarray:
        close = snap.close
        high = snap.high
        low = snap.low
        volume = snap.volume
        n = len(close)

        if name == "sma":
            period = params.get("period", 14)
            out = np.full(n, np.nan, dtype=np.float64)
            for i in range(period - 1, n):
                out[i] = np.mean(close[i - period + 1:i + 1])
            return out

        elif name == "ema":
            period = params.get("period", 14)
            alpha = 2.0 / (period + 1)
            out = np.empty(n, dtype=np.float64)
            out[0] = close[0]
            for i in range(1, n):
                out[i] = alpha * close[i] + (1 - alpha) * out[i - 1]
            return out

        elif name == "rsi":
            period = params.get("period", 14)
            out = np.full(n, 50.0, dtype=np.float64)
            if n < period + 1:
                return out
            deltas = np.diff(close)
            gains = np.where(deltas > 0, deltas, 0.0)
            losses = np.where(deltas < 0, -deltas, 0.0)
            avg_gain = np.mean(gains[:period])
            avg_loss = np.mean(losses[:period])
            if avg_loss > 0:
                out[period] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
            else:
                out[period] = 100.0
            for i in range(period, len(deltas)):
                avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                avg_loss = (avg_loss * (period - 1) + losses[i]) / period
                if avg_loss > 0:
                    out[i + 1] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
                else:
                    out[i + 1] = 100.0
            return out

        elif name == "atr":
            period = params.get("period", 14)
            tr = np.zeros(n, dtype=np.float64)
            for i in range(1, n):
                tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
            tr[0] = high[0] - low[0]
            out = np.zeros(n, dtype=np.float64)
            out[period - 1] = np.mean(tr[:period])
            for i in range(period, n):
                out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
            return out

        elif name == "macd":
            fast = params.get("fast", 12)
            slow = params.get("slow", 26)
            signal_period = params.get("signal", 9)
            ema_fast = self._python_fallback("ema", {"period": fast}, snap)
            ema_slow = self._python_fallback("ema", {"period": slow}, snap)
            macd_line = ema_fast - ema_slow
            return macd_line

        elif name == "bollinger_upper" or name == "bollinger_lower" or name == "bollinger_width":
            period = params.get("period", 20)
            std_mult = params.get("std", 2.0)
            sma = self._python_fallback("sma", {"period": period}, snap)
            std = np.full(n, np.nan, dtype=np.float64)
            for i in range(period - 1, n):
                std[i] = np.std(close[i - period + 1:i + 1])
            if name == "bollinger_upper":
                return sma + std_mult * std
            elif name == "bollinger_lower":
                return sma - std_mult * std
            else:
                return np.where(sma > 0, (2 * std_mult * std) / sma, 0.0)

        elif name == "obv":
            out = np.zeros(n, dtype=np.float64)
            for i in range(1, n):
                if close[i] > close[i - 1]:
                    out[i] = out[i - 1] + volume[i]
                elif close[i] < close[i - 1]:
                    out[i] = out[i - 1] - volume[i]
                else:
                    out[i] = out[i - 1]
            return out

        elif name == "adx":
            period = params.get("period", 14)
            return self._compute_adx(high, low, close, period)

        elif name == "stochastic_k":
            period = params.get("period", 14)
            out = np.full(n, 50.0, dtype=np.float64)
            for i in range(period - 1, n):
                hh = np.max(high[i - period + 1:i + 1])
                ll = np.min(low[i - period + 1:i + 1])
                if hh != ll:
                    out[i] = 100.0 * (close[i] - ll) / (hh - ll)
            return out

        elif name == "cci":
            period = params.get("period", 20)
            tp = (high + low + close) / 3.0
            out = np.zeros(n, dtype=np.float64)
            for i in range(period - 1, n):
                window = tp[i - period + 1:i + 1]
                mean_tp = np.mean(window)
                mean_dev = np.mean(np.abs(window - mean_tp))
                if mean_dev > 0:
                    out[i] = (tp[i] - mean_tp) / (0.015 * mean_dev)
            return out

        return np.zeros(n, dtype=np.float64)

    def _compute_adx(self, high, low, close, period):
        n = len(close)
        out = np.zeros(n, dtype=np.float64)
        if n < period * 2:
            return out
        tr = np.zeros(n)
        plus_dm = np.zeros(n)
        minus_dm = np.zeros(n)
        for i in range(1, n):
            tr[i] = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
            up = high[i] - high[i-1]
            down = low[i-1] - low[i]
            plus_dm[i] = up if (up > down and up > 0) else 0.0
            minus_dm[i] = down if (down > up and down > 0) else 0.0
        atr_s = np.mean(tr[1:period+1])
        plus_s = np.mean(plus_dm[1:period+1])
        minus_s = np.mean(minus_dm[1:period+1])
        dx_arr = np.zeros(n)
        for i in range(period, n):
            atr_s = (atr_s * (period-1) + tr[i]) / period
            plus_s = (plus_s * (period-1) + plus_dm[i]) / period
            minus_s = (minus_s * (period-1) + minus_dm[i]) / period
            di_plus = 100 * plus_s / atr_s if atr_s > 0 else 0
            di_minus = 100 * minus_s / atr_s if atr_s > 0 else 0
            di_sum = di_plus + di_minus
            dx_arr[i] = 100 * abs(di_plus - di_minus) / di_sum if di_sum > 0 else 0
        adx_start = period * 2
        if adx_start < n:
            out[adx_start] = np.mean(dx_arr[period:adx_start+1])
            for i in range(adx_start+1, n):
                out[i] = (out[i-1] * (period-1) + dx_arr[i]) / period
        return out

    def clear_cache(self, symbol: Optional[str] = None) -> int:
        if symbol is None:
            n = len(self._cache)
            self._cache.clear()
            self._cache_symbols.clear()
            return n
        to_remove = [k for k, s in self._cache_symbols.items() if s == symbol]
        for k in to_remove:
            del self._cache[k]
            del self._cache_symbols[k]
        return len(to_remove)

    def health_check(self) -> Dict:
        total = self._hits + self._misses
        return {
            "rust_loaded": self._rust_lib is not None,
            "cache_size": len(self._cache),
            "cache_hit_rate": round(self._hits / total, 4) if total > 0 else 0.0,
            "total_compute_ms": round(self._total_compute_ms, 2),
            "lib_path": str(self._lib_path),
            "available_categories": len(INDICATOR_CATEGORIES),
            "total_indicators": len(ALL_INDICATORS),
        }
