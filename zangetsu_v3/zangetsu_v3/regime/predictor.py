"""OnlineRegimePredictor with debounce, switch confidence, predict_coarse/predict_fine (V3.2 C3).

Two output methods:
  - predict_coarse(features) -> one of 11 search regime names (for card selection)
  - predict_fine(features)   -> one of 13 state names (for position overlay)

Debounce: N=3 consecutive identical coarse predictions before switching
  (at 4h bar = 12h minimum regime duration)
switch_confidence: after confirmed switch, 0.3 -> 1.0 linearly over 30 bars
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Dict, Optional

import numpy as np

from zangetsu_v3.regime.rule_labeler import Regime, REGIME_NAMES


# ------------------------------------------------------------------ #
# Fine (13) -> Coarse (11) mapping                                    #
# ------------------------------------------------------------------ #
# Identity for search regimes 0..10; LIQUIDITY_CRISIS(11)->BEAR_TREND(1);
# PARABOLIC(12)->BULL_TREND(0).

FINE_TO_COARSE: Dict[int, int] = {
    Regime.BULL_TREND: Regime.BULL_TREND,
    Regime.BEAR_TREND: Regime.BEAR_TREND,
    Regime.BULL_PULLBACK: Regime.BULL_PULLBACK,
    Regime.BEAR_RALLY: Regime.BEAR_RALLY,
    Regime.DISTRIBUTION: Regime.DISTRIBUTION,
    Regime.ACCUMULATION: Regime.ACCUMULATION,
    Regime.CONSOLIDATION: Regime.CONSOLIDATION,
    Regime.CHOPPY_VOLATILE: Regime.CHOPPY_VOLATILE,
    Regime.SQUEEZE: Regime.SQUEEZE,
    Regime.TOPPING: Regime.TOPPING,
    Regime.BOTTOMING: Regime.BOTTOMING,
    Regime.LIQUIDITY_CRISIS: Regime.BEAR_TREND,      # overlay-only -> closest trend
    Regime.PARABOLIC: Regime.BULL_TREND,              # overlay-only -> closest trend
}

COARSE_REGIME_NAMES = {v: REGIME_NAMES[v] for v in set(FINE_TO_COARSE.values())}


def _confidence(bars_since_switch: int) -> float:
    """Linear ramp: 0.3 -> 1.0 over 30 bars after confirmed switch."""
    return min(1.0, 0.3 + 0.7 * (bars_since_switch / 30.0))


def _compute_online_features(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    volume: np.ndarray,
) -> np.ndarray:
    """Compute the same 12 features as train_predictor.compute_features(),
    but accepts raw numpy arrays (4h bars). Returns (n, 12) array.

    Feature order must match training: adx, atr_pct, bb_width_pct,
    ema21_slope, ema55_slope, vol_z, hh_pattern,
    close_vs_ema21, close_vs_ema200, ema21_vs_ema55, plus_di, minus_di.
    """
    n = len(close)

    def _ema(x: np.ndarray, p: int) -> np.ndarray:
        out = np.zeros(n)
        out[0] = x[0]
        alpha = 2.0 / (p + 1)
        for i in range(1, n):
            out[i] = alpha * x[i] + (1 - alpha) * out[i - 1]
        return out

    def _atr(p: int) -> np.ndarray:
        tr = np.maximum(
            high[1:] - low[1:],
            np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])),
        )
        tr = np.concatenate([[high[0] - low[0]], tr])
        return _ema(tr, p)

    def _rolling_pct(x: np.ndarray, w: int) -> np.ndarray:
        out = np.full(n, 50.0)
        for i in range(w, n):
            window = x[i - w : i + 1]
            out[i] = np.sum(window <= x[i]) / len(window) * 100
        return out

    ema21 = _ema(close, 21)
    ema55 = _ema(close, 55)
    ema200 = _ema(close, 200)
    atr14 = _atr(14)
    atr_pct = _rolling_pct(atr14, 100)

    # BB width
    bb_mean = np.convolve(close, np.ones(20) / 20, mode="same")
    bb_std = np.array([np.std(close[max(0, i - 19) : i + 1]) for i in range(n)])
    bb_width = 2 * bb_std / (bb_mean + 1e-12)
    bb_width_pct = _rolling_pct(bb_width, 100)

    # ADX
    plus_dm = np.maximum(np.diff(high, prepend=high[0]), 0)
    minus_dm = np.maximum(-np.diff(low, prepend=low[0]), 0)
    mask = plus_dm > minus_dm
    minus_dm[mask] = 0
    plus_dm[~mask] = 0
    plus_di = _ema(plus_dm, 14) / (atr14 + 1e-12) * 100
    minus_di = _ema(minus_dm, 14) / (atr14 + 1e-12) * 100
    dx = np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-12) * 100
    adx = _ema(dx, 14)

    # Slopes
    ema21_slope = np.zeros(n)
    ema21_slope[5:] = (ema21[5:] - ema21[:-5]) / (ema21[:-5] + 1e-12)
    ema55_slope = np.zeros(n)
    ema55_slope[10:] = (ema55[10:] - ema55[:-10]) / (ema55[:-10] + 1e-12)

    # Volume z-score
    vol_ma = np.convolve(volume, np.ones(20) / 20, mode="same")
    vol_std = np.array([np.std(volume[max(0, i - 19) : i + 1]) for i in range(n)])
    vol_z = (volume - vol_ma) / (vol_std + 1e-12)

    # Higher highs / lower lows pattern
    hh = np.zeros(n)
    for i in range(3, n):
        hh[i] = (
            1
            if high[i] > high[i - 1] > high[i - 2]
            else (-1 if low[i] < low[i - 1] < low[i - 2] else 0)
        )

    # Close relative to EMAs
    close_vs_ema21 = (close - ema21) / (atr14 + 1e-12)
    close_vs_ema200 = (close - ema200) / (atr14 + 1e-12)
    ema21_vs_ema55 = (ema21 - ema55) / (atr14 + 1e-12)

    return np.column_stack([
        adx,
        atr_pct,
        bb_width_pct,
        ema21_slope,
        ema55_slope,
        vol_z,
        hh,
        close_vs_ema21,
        close_vs_ema200,
        ema21_vs_ema55,
        plus_di,
        minus_di,
    ])


FEATURE_NAMES = [
    "adx", "atr_pct", "bb_width_pct",
    "ema21_slope", "ema55_slope",
    "vol_z", "hh_pattern",
    "close_vs_ema21", "close_vs_ema200", "ema21_vs_ema55",
    "plus_di", "minus_di",
]


@dataclass
class OnlineRegimePredictor:
    """Online regime predictor with N=3 debounce and dual output (coarse/fine).

    Debounce logic operates on COARSE regimes (11 states) for card selection.
    Fine regime (13 states) is available for position overlay without debounce.
    """
    lookback: int = 60
    debounce: int = 3                   # V3.2: N=3 (was 5), 4h bars = 12h min duration
    _instance: ClassVar["OnlineRegimePredictor | None"] = None

    active_regime: int | None = None    # coarse regime after debounce
    candidate_regime: int | None = None
    debounce_count: int = 0
    bars_since_switch: int = 0
    _last_fine_regime: int | None = None  # most recent fine prediction (no debounce)

    # Model state (loaded lazily)
    _model: Optional[object] = field(default=None, repr=False)
    _model_path: Optional[str] = field(default=None, repr=False)

    @classmethod
    def instance(cls) -> "OnlineRegimePredictor":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_model(self, path: str | Path) -> None:
        """Load a trained LightGBM model from disk."""
        import joblib

        payload = joblib.load(path)
        self._model = payload["model"]
        self._model_path = str(path)

    def predict_fine(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        volume: np.ndarray,
    ) -> int:
        """Predict the fine-grained 13-state regime from OHLCV 4h bar history.

        Returns an integer from Regime (0..12). No debounce applied --
        this is raw model output for position overlay dampers.

        Raises:
            RuntimeError: If no model has been loaded via load_model().
        """
        if self._model is None:
            raise RuntimeError(
                "No model loaded. Call load_model(path) first."
            )

        features = _compute_online_features(close, high, low, volume)
        last_features = features[-1:].astype(np.float64)
        raw_pred = int(self._model.predict(last_features)[0])
        raw_pred = max(0, min(raw_pred, 12))
        self._last_fine_regime = raw_pred
        return raw_pred

    def predict_coarse(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        volume: np.ndarray,
    ) -> int:
        """Predict coarse regime (11 states) for card selection.

        Calls predict_fine() internally then maps 13->11 and applies debounce.
        Returns the debounced coarse regime integer.

        Raises:
            RuntimeError: If no model has been loaded via load_model().
        """
        fine = self.predict_fine(close, high, low, volume)
        coarse = FINE_TO_COARSE.get(fine, fine)
        return self.step(coarse)

    def predict_coarse_name(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        volume: np.ndarray,
    ) -> str:
        """Predict coarse regime name (string) for card selection."""
        coarse_id = self.predict_coarse(close, high, low, volume)
        return REGIME_NAMES.get(coarse_id, f"UNKNOWN_{coarse_id}")

    def predict_fine_name(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        volume: np.ndarray,
    ) -> str:
        """Predict fine regime name (string) for position overlay."""
        fine_id = self.predict_fine(close, high, low, volume)
        return REGIME_NAMES.get(fine_id, f"UNKNOWN_{fine_id}")

    def step(self, predicted_regime: int) -> int:
        """Update predictor with a new regime prediction (coarse level).

        The active regime only changes after ``debounce`` (N=3) consecutive
        observations of a new regime. At 4h bars this means 12h minimum
        regime duration.
        """
        if self.active_regime is None:
            self.active_regime = predicted_regime
            self.bars_since_switch = 1
            return self.active_regime

        if predicted_regime == self.active_regime:
            self.candidate_regime = None
            self.debounce_count = 0
            self.bars_since_switch += 1
            return self.active_regime

        # new candidate
        if self.candidate_regime != predicted_regime:
            self.candidate_regime = predicted_regime
            self.debounce_count = 1
        else:
            self.debounce_count += 1

        if self.debounce_count >= self.debounce:
            self.active_regime = self.candidate_regime
            self.bars_since_switch = 1
            self.candidate_regime = None
            self.debounce_count = 0
        else:
            self.bars_since_switch += 1

        return self.active_regime

    @property
    def switch_confidence(self) -> float:
        """Confidence ramp: 0.3 -> 1.0 linearly over 30 bars after switch."""
        return _confidence(self.bars_since_switch)

    @property
    def last_fine_regime(self) -> Optional[int]:
        """Most recent fine regime prediction (no debounce). None if never predicted."""
        return self._last_fine_regime


__all__ = [
    "OnlineRegimePredictor",
    "FEATURE_NAMES",
    "FINE_TO_COARSE",
    "COARSE_REGIME_NAMES",
    "_compute_online_features",
]
