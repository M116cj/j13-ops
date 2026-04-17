"""Three-layer regime detection for live trading.

L1 (Macro Trend):  4h EMA20/EMA50 + ADX > 20 → BULL / BEAR / NEUTRAL
L2 (Current Regime): 13-state classification on 1h bars, constrained by L1
L3 (Entry Decision): handled by voter/signal_utils — this module exposes L1+L2

CAUSAL ONLY — no lookahead (D026).
Rolling buffers capped to prevent unbounded growth.
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

import numpy as np


# ── Constants ────────────────────────────────────────────────────
_BARS_1H = 60       # 1m bars per 1h bar
_BARS_4H = 240      # 1m bars per 4h bar
_BUFFER_MAX = 250   # max rolling bars to keep (200 needed + margin)

_L1_L2_CONSTRAINTS = {
    "BULL": {
        "BULL_TREND", "BULL_PULLBACK", "DISTRIBUTION", "TOPPING",
        "CONSOLIDATION", "SQUEEZE",
    },
    "BEAR": {
        "BEAR_TREND", "BEAR_RALLY", "ACCUMULATION", "BOTTOMING",
        "CONSOLIDATION", "SQUEEZE",
    },
    "NEUTRAL": {"CONSOLIDATION", "CHOPPY_VOLATILE", "SQUEEZE"},
}

# Map engine 13-state integers to named regimes
_ENGINE_ID_TO_NAME = {
    0: "CONSOLIDATION",      # quiet_range → CONSOLIDATION
    1: "BULL_PULLBACK",      # trending_up_weak
    2: "BULL_TREND",         # trending_up_strong
    3: "BEAR_RALLY",         # trending_down_weak
    4: "BEAR_TREND",         # trending_down_strong
    5: "DISTRIBUTION",       # high_vol_up → DISTRIBUTION
    6: "ACCUMULATION",       # high_vol_down → ACCUMULATION
    7: "CONSOLIDATION",      # mean_revert → CONSOLIDATION
    8: "TOPPING",            # breakout_up → TOPPING
    9: "BOTTOMING",          # breakout_down → BOTTOMING
    10: "SQUEEZE",           # compression
    11: "BULL_TREND",        # expansion → BULL_TREND (directional resolved at L1)
    12: "CHOPPY_VOLATILE",   # choppy
}

# Damper regimes — force caution
_DAMPER_REGIMES = {"LIQUIDITY_CRISIS", "PARABOLIC"}


# ── Causal indicator helpers (mirrored from engine, no pandas) ───
def _ema(arr: np.ndarray, span: int) -> np.ndarray:
    out = np.empty_like(arr, dtype=np.float64)
    alpha = 2.0 / (span + 1)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def _true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    tr = np.empty(len(high), dtype=np.float64)
    tr[0] = high[0] - low[0]
    for i in range(1, len(high)):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )
    return tr


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray,
         period: int = 14) -> np.ndarray:
    tr = _true_range(high, low, close)
    return _ema(tr, period)


def _adx(high: np.ndarray, low: np.ndarray, close: np.ndarray,
         period: int = 14) -> np.ndarray:
    n = len(high)
    plus_dm = np.zeros(n, dtype=np.float64)
    minus_dm = np.zeros(n, dtype=np.float64)
    for i in range(1, n):
        up = high[i] - high[i - 1]
        down = low[i - 1] - low[i]
        if up > down and up > 0:
            plus_dm[i] = up
        if down > up and down > 0:
            minus_dm[i] = down
    atr_arr = _atr(high, low, close, period)
    smooth_plus = _ema(plus_dm, period)
    smooth_minus = _ema(minus_dm, period)
    plus_di = np.zeros(n, dtype=np.float64)
    minus_di = np.zeros(n, dtype=np.float64)
    dx = np.zeros(n, dtype=np.float64)
    for i in range(n):
        if atr_arr[i] > 0:
            plus_di[i] = 100.0 * smooth_plus[i] / atr_arr[i]
            minus_di[i] = 100.0 * smooth_minus[i] / atr_arr[i]
        di_sum = plus_di[i] + minus_di[i]
        if di_sum > 0:
            dx[i] = 100.0 * abs(plus_di[i] - minus_di[i]) / di_sum
    return _ema(dx, period)


def _rolling_std(arr: np.ndarray, window: int) -> np.ndarray:
    out = np.zeros(len(arr), dtype=np.float64)
    for i in range(len(arr)):
        start = max(0, i - window + 1)
        out[i] = np.std(arr[start:i + 1])
    return out


def _ema_slope(ema_arr: np.ndarray, lookback: int = 3) -> np.ndarray:
    slope = np.zeros(len(ema_arr), dtype=np.float64)
    for i in range(lookback, len(ema_arr)):
        slope[i] = ema_arr[i] - ema_arr[i - lookback]
    return slope


# ── L2 classification (reused from engine logic) ─────────────────
def _classify_bar_13state(
    adx_val: float, slope_val: float, atr_pct_val: float,
    atr_roc_val: float, close_val: float, ema_val: float,
    bb_upper_val: float, bb_lower_val: float, bw_pct_val: float,
    vol_val: float, vol_median: float,
) -> int:
    high_vol = atr_pct_val > 0.8
    squeeze = bw_pct_val < 0.1
    expanding = atr_roc_val > 0.15
    if squeeze and adx_val < 20:
        return 10
    if expanding and atr_roc_val > 0.2:
        return 11
    if close_val > bb_upper_val and slope_val > 0 and adx_val > 20:
        return 8
    if close_val < bb_lower_val and slope_val < 0 and adx_val > 20:
        return 9
    if high_vol and slope_val > 0:
        return 5
    if high_vol and slope_val < 0:
        return 6
    if adx_val > 25 and slope_val > 0:
        return 2
    if adx_val > 25 and slope_val < 0:
        return 4
    if 15 <= adx_val <= 25 and slope_val > 0:
        return 1
    if 15 <= adx_val <= 25 and slope_val < 0:
        return 3
    if adx_val < 15 and vol_val <= vol_median * 1.2:
        dist = abs(close_val - ema_val) / ema_val if ema_val > 0 else 1.0
        if dist < 0.01:
            return 7
    if adx_val < 15 and vol_val > vol_median * 0.8:
        return 12
    return 0


def _label_latest_from_arrays(
    high: np.ndarray, low: np.ndarray, close: np.ndarray,
    atr_period: int = 14, adx_period: int = 14, ema_period: int = 21,
    vol_window: int = 20, bb_window: int = 20, bb_mult: float = 2.0,
) -> int:
    """Compute 13-state label for the last bar in the arrays."""
    n = len(close)
    if n < 2:
        return 0
    atr = _atr(high, low, close, atr_period)
    adx = _adx(high, low, close, adx_period)
    ema = _ema(close, ema_period)
    slope = _ema_slope(ema, lookback=3)
    vol = _rolling_std(close, vol_window)
    # Bollinger for last bar
    i = n - 1
    start = max(0, i - bb_window + 1)
    bb_ma = np.mean(close[start:i + 1])
    bb_std = np.std(close[start:i + 1])
    bb_upper = bb_ma + bb_mult * bb_std
    bb_lower = bb_ma - bb_mult * bb_std
    # ATR percentile
    window = atr[max(0, i - 100):i + 1]
    atr_pct = np.sum(window <= atr[i]) / len(window)
    # ATR ROC
    atr_roc = 0.0
    if i >= 5 and atr[i - 5] > 0:
        atr_roc = (atr[i] - atr[i - 5]) / atr[i - 5]
    # BW squeeze
    bw = (bb_upper - bb_lower) / bb_ma if bb_ma > 0 else 0.0
    bw_arr = np.zeros(min(101, n), dtype=np.float64)
    for j in range(len(bw_arr)):
        idx = i - len(bw_arr) + 1 + j
        s = max(0, idx - bb_window + 1)
        m = np.mean(close[s:idx + 1])
        st = np.std(close[s:idx + 1])
        bw_arr[j] = ((m + bb_mult * st) - (m - bb_mult * st)) / m if m > 0 else 0
    bw_pct = np.sum(bw_arr <= bw) / len(bw_arr)
    vol_median = np.median(vol[max(0, i - 100):i + 1])
    return _classify_bar_13state(
        adx[i], slope[i], atr_pct, atr_roc, close[i], ema[i],
        bb_upper, bb_lower, bw_pct, vol[i], vol_median,
    )


# ── Per-symbol state ─────────────────────────────────────────────
class _SymbolState:
    __slots__ = (
        "buf_1m_h", "buf_1m_l", "buf_1m_c", "buf_1m_count",
        "buf_1h_h", "buf_1h_l", "buf_1h_c",
        "buf_4h_h", "buf_4h_l", "buf_4h_c",
        "agg_1h_high", "agg_1h_low", "agg_1h_open", "agg_1h_close",
        "agg_4h_high", "agg_4h_low", "agg_4h_open", "agg_4h_close",
        "bars_in_1h", "bars_in_4h",
        "l1", "l1_confidence", "l2", "l2_raw",
        "l2_bars_since_change", "last_l2_change_ts",
        "damper_active",
        "atr_1m_buf",
    )

    def __init__(self) -> None:
        # Rolling OHLC buffers for completed bars
        self.buf_1h_h: List[float] = []
        self.buf_1h_l: List[float] = []
        self.buf_1h_c: List[float] = []
        self.buf_4h_h: List[float] = []
        self.buf_4h_l: List[float] = []
        self.buf_4h_c: List[float] = []
        # Aggregation accumulators
        self.agg_1h_high = -np.inf
        self.agg_1h_low = np.inf
        self.agg_1h_open = 0.0
        self.agg_1h_close = 0.0
        self.agg_4h_high = -np.inf
        self.agg_4h_low = np.inf
        self.agg_4h_open = 0.0
        self.agg_4h_close = 0.0
        self.bars_in_1h = 0
        self.bars_in_4h = 0
        # Layer states
        self.l1 = "NEUTRAL"
        self.l1_confidence = 0.0
        self.l2 = "CONSOLIDATION"
        self.l2_raw = "CONSOLIDATION"
        self.l2_bars_since_change = 0
        self.last_l2_change_ts = 0.0
        self.damper_active = False
        # 1m ATR buffer for damper detection
        self.atr_1m_buf: List[float] = []


# ── Main class ───────────────────────────────────────────────────
class LiveRegimeLabeler:
    """Three-layer regime detection for live trading.

    Maintains rolling buffers of 4h and 1h bars.
    CAUSAL ONLY — no lookahead (D026).
    """

    def __init__(self, config: Any = None) -> None:
        self._config = config
        self._states: Dict[str, _SymbolState] = defaultdict(self._new_state)

    @staticmethod
    def _new_state() -> _SymbolState:
        return _SymbolState()

    # ── Public API ───────────────────────────────────────────────

    def update_1m_bar(self, symbol: str, bar: dict) -> None:
        """Called every 1m bar. Aggregates into 1h and 4h internally.

        bar must have keys: high, low, close (open optional).
        """
        s = self._states[symbol]
        h = float(bar["high"])
        l = float(bar["low"])  # noqa: E741
        c = float(bar["close"])
        o = float(bar.get("open", c))

        # ── Track 1m ATR for damper ──────────────────────────────
        self._update_1m_atr(s, h, l, c)

        # ── Aggregate into 1h ────────────────────────────────────
        s.bars_in_1h += 1
        if s.bars_in_1h == 1:
            s.agg_1h_open = o
        s.agg_1h_high = max(s.agg_1h_high, h)
        s.agg_1h_low = min(s.agg_1h_low, l)
        s.agg_1h_close = c

        # ── Aggregate into 4h ────────────────────────────────────
        s.bars_in_4h += 1
        if s.bars_in_4h == 1:
            s.agg_4h_open = o
        s.agg_4h_high = max(s.agg_4h_high, h)
        s.agg_4h_low = min(s.agg_4h_low, l)
        s.agg_4h_close = c

        # ── Complete 1h bar ──────────────────────────────────────
        if s.bars_in_1h >= _BARS_1H:
            self._commit_1h(s)
            self._update_l2(s)

        # ── Complete 4h bar ──────────────────────────────────────
        if s.bars_in_4h >= _BARS_4H:
            self._commit_4h(s)
            self._update_l1(s)

    def get_macro_trend(self, symbol: str) -> str:
        """Returns current L1: 'BULL', 'BEAR', or 'NEUTRAL'."""
        return self._states[symbol].l1 if symbol in self._states else "NEUTRAL"

    def get_current_regime(self, symbol: str) -> str:
        """Returns current L2: one of 13 regime states (named)."""
        return self._states[symbol].l2 if symbol in self._states else "CONSOLIDATION"

    def get_regime_state(self, symbol: str) -> dict:
        """Returns full state dict for L3 consumers."""
        s = self._states[symbol] if symbol in self._states else _SymbolState()
        allowed = _L1_L2_CONSTRAINTS.get(s.l1, set())
        return {
            "l1": s.l1,
            "l2": s.l2,
            "l1_confidence": round(s.l1_confidence, 4),
            "l2_bars_since_change": s.l2_bars_since_change,
            "allowed_l2": sorted(allowed),
            "damper_active": s.damper_active,
        }

    def is_damper_active(self, symbol: str) -> bool:
        """True if LIQUIDITY_CRISIS/PARABOLIC detected, or ATR > 3x normal."""
        return self._states[symbol].damper_active if symbol in self._states else False

    def health_check(self) -> dict:
        """Per-symbol regime state summary."""
        result: Dict[str, dict] = {}
        for sym, s in self._states.items():
            result[sym] = {
                "l1": s.l1,
                "l2": s.l2,
                "l1_confidence": round(s.l1_confidence, 4),
                "l2_bars_since_change": s.l2_bars_since_change,
                "damper_active": s.damper_active,
                "buf_1h_len": len(s.buf_1h_c),
                "buf_4h_len": len(s.buf_4h_c),
                "bars_in_current_1h": s.bars_in_1h,
                "bars_in_current_4h": s.bars_in_4h,
            }
        return result

    # ── Internal: bar aggregation ────────────────────────────────

    def _commit_1h(self, s: _SymbolState) -> None:
        s.buf_1h_h.append(s.agg_1h_high)
        s.buf_1h_l.append(s.agg_1h_low)
        s.buf_1h_c.append(s.agg_1h_close)
        # Trim to prevent unbounded growth
        if len(s.buf_1h_c) > _BUFFER_MAX:
            trim = len(s.buf_1h_c) - _BUFFER_MAX
            s.buf_1h_h = s.buf_1h_h[trim:]
            s.buf_1h_l = s.buf_1h_l[trim:]
            s.buf_1h_c = s.buf_1h_c[trim:]
        # Reset accumulator
        s.agg_1h_high = -np.inf
        s.agg_1h_low = np.inf
        s.agg_1h_open = 0.0
        s.agg_1h_close = 0.0
        s.bars_in_1h = 0

    def _commit_4h(self, s: _SymbolState) -> None:
        s.buf_4h_h.append(s.agg_4h_high)
        s.buf_4h_l.append(s.agg_4h_low)
        s.buf_4h_c.append(s.agg_4h_close)
        if len(s.buf_4h_c) > _BUFFER_MAX:
            trim = len(s.buf_4h_c) - _BUFFER_MAX
            s.buf_4h_h = s.buf_4h_h[trim:]
            s.buf_4h_l = s.buf_4h_l[trim:]
            s.buf_4h_c = s.buf_4h_c[trim:]
        s.agg_4h_high = -np.inf
        s.agg_4h_low = np.inf
        s.agg_4h_open = 0.0
        s.agg_4h_close = 0.0
        s.bars_in_4h = 0

    # ── Internal: L1 update (4h) ─────────────────────────────────

    def _update_l1(self, s: _SymbolState) -> None:
        """Recalculate L1 macro trend from 4h buffer."""
        n = len(s.buf_4h_c)
        if n < 50:
            s.l1 = "NEUTRAL"
            s.l1_confidence = 0.0
            return
        close = np.array(s.buf_4h_c, dtype=np.float64)
        high = np.array(s.buf_4h_h, dtype=np.float64)
        low = np.array(s.buf_4h_l, dtype=np.float64)
        ema20 = _ema(close, 20)
        ema50 = _ema(close, 50)
        adx = _adx(high, low, close, 14)
        last_ema20 = ema20[-1]
        last_ema50 = ema50[-1]
        last_adx = adx[-1]
        if last_adx <= 20:
            s.l1 = "NEUTRAL"
            s.l1_confidence = last_adx / 20.0  # 0-1 range
        elif last_ema20 > last_ema50:
            s.l1 = "BULL"
            s.l1_confidence = min(last_adx / 40.0, 1.0)
        else:
            s.l1 = "BEAR"
            s.l1_confidence = min(last_adx / 40.0, 1.0)

    # ── Internal: L2 update (1h) ─────────────────────────────────

    def _update_l2(self, s: _SymbolState) -> None:
        """Recalculate L2 regime from 1h buffer, constrained by L1."""
        n = len(s.buf_1h_c)
        if n < 30:
            s.l2 = "CONSOLIDATION"
            return
        high = np.array(s.buf_1h_h, dtype=np.float64)
        low = np.array(s.buf_1h_l, dtype=np.float64)
        close = np.array(s.buf_1h_c, dtype=np.float64)
        raw_id = _label_latest_from_arrays(high, low, close)
        raw_name = _ENGINE_ID_TO_NAME.get(raw_id, "CONSOLIDATION")
        s.l2_raw = raw_name
        # Apply L1 → L2 constraint
        allowed = _L1_L2_CONSTRAINTS.get(s.l1, _L1_L2_CONSTRAINTS["NEUTRAL"])
        if raw_name in allowed:
            new_l2 = raw_name
        else:
            new_l2 = "CONSOLIDATION"
        # Track regime change
        if new_l2 != s.l2:
            s.l2 = new_l2
            s.l2_bars_since_change = 0
            s.last_l2_change_ts = time.time()
        else:
            s.l2_bars_since_change += 1

    # ── Internal: 1m ATR damper ──────────────────────────────────

    def _update_1m_atr(self, s: _SymbolState, h: float, l: float, c: float) -> None:
        """Track 1m true range for damper detection."""
        if len(s.atr_1m_buf) == 0:
            tr = h - l
        else:
            prev_c = s.agg_1h_close if s.bars_in_1h > 0 else c
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        s.atr_1m_buf.append(tr)
        # Keep last 500 bars (enough for ATR14 + rolling median)
        if len(s.atr_1m_buf) > 500:
            s.atr_1m_buf = s.atr_1m_buf[-500:]
        # Compute damper: ATR(14) > 3x rolling median ATR
        regime_damper = s.l2 in _DAMPER_REGIMES or s.l2_raw in _DAMPER_REGIMES
        if len(s.atr_1m_buf) >= 14:
            recent = s.atr_1m_buf[-14:]
            atr_14 = sum(recent) / 14.0
            median_atr = float(np.median(s.atr_1m_buf))
            atr_damper = median_atr > 0 and atr_14 > 3.0 * median_atr
        else:
            atr_damper = False
        s.damper_active = regime_damper or atr_damper
