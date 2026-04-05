"""OnlineRegimePredictor singleton with debounce and switch confidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


def _confidence(bars_since_switch: int) -> float:
    return min(1.0, 0.3 + 0.7 * (bars_since_switch / 30.0))


@dataclass
class OnlineRegimePredictor:
    lookback: int = 60
    debounce: int = 5
    _instance: ClassVar["OnlineRegimePredictor" | None] = None

    active_regime: int | None = None
    candidate_regime: int | None = None
    debounce_count: int = 0
    bars_since_switch: int = 0

    @classmethod
    def instance(cls) -> "OnlineRegimePredictor":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def step(self, predicted_regime: int) -> int:
        """Update predictor with a new regime prediction.

        The active regime only changes after ``debounce`` consecutive
        observations of a new regime.
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
        return _confidence(self.bars_since_switch)


__all__ = ["OnlineRegimePredictor"]

