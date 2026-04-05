"""Regime labelling using Gaussian HMM with BIC model selection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import joblib
import numpy as np
import polars as pl
from hmmlearn.hmm import GaussianHMM


def _compute_bic(model: GaussianHMM, data: np.ndarray) -> float:
    # hmmlearn 0.3.x returns dict from _get_n_fit_scalars_per_param; sum all values
    raw = model._get_n_fit_scalars_per_param()  # type: ignore[attr-defined]
    n_params = int(sum(raw.values()) if isinstance(raw, dict) else raw)
    log_likelihood = model.score(data)
    return -2 * log_likelihood + n_params * np.log(data.shape[0])


def _prep_features(df: pl.DataFrame) -> np.ndarray:
    close = df["close"].to_numpy()
    ret = np.diff(np.log(close), prepend=close[0])
    vol = np.abs(ret)
    return np.column_stack([ret, vol])


@dataclass
class RegimeLabeler:
    min_states: int = 3
    max_states: int = 8
    model_: Optional[GaussianHMM] = None
    n_states_: Optional[int] = None

    def fit(self, df: pl.DataFrame) -> np.ndarray:
        data = _prep_features(df)
        best_bic = float("inf")
        best_model: Optional[GaussianHMM] = None
        best_states = None
        for n in range(self.min_states, self.max_states + 1):
            try:
                model = GaussianHMM(
                    n_components=n,
                    covariance_type="full",
                    n_iter=200,
                    random_state=0,
                    min_covar=1e-3,  # prevent degenerate covariance
                )
                model.fit(data)
                bic = _compute_bic(model, data)
                if bic < best_bic:
                    best_bic = bic
                    best_model = model
                    best_states = n
            except (ValueError, np.linalg.LinAlgError):
                # Skip degenerate solutions for this n_states
                continue

        if best_model is None:
            # Fallback: use minimum states with diagonal covariance
            best_states = self.min_states
            best_model = GaussianHMM(
                n_components=best_states,
                covariance_type="diag",
                n_iter=100,
                random_state=0,
            )
            best_model.fit(data)

        self.model_ = best_model
        self.n_states_ = best_states
        labels = self.model_.predict(data)
        return self._auto_map(labels, data)

    def _auto_map(self, labels: np.ndarray, data: np.ndarray) -> np.ndarray:
        # Map states by mean return then volatility (ascending mean, then vol)
        ret = data[:, 0]
        vol = data[:, 1]
        stats = []
        for state in range(labels.max() + 1):
            mask = labels == state
            if mask.any():
                stats.append((state, ret[mask].mean(), vol[mask].mean()))
        # sort by mean return then vol
        stats_sorted = sorted(stats, key=lambda x: (x[1], x[2]))
        mapping = {old: new for new, (old, _, _) in enumerate(stats_sorted)}
        mapped = np.vectorize(lambda x: mapping.get(x, x))(labels)
        self.state_mapping_ = mapping
        return mapped

    def label(self, df: pl.DataFrame) -> np.ndarray:
        if self.model_ is None:
            return self.fit(df)
        data = _prep_features(df)
        labels = self.model_.predict(data)
        return self._auto_map(labels, data)

    def save(self, path: str | Path) -> None:
        if self.model_ is None:
            raise ValueError("Model not fitted")
        payload = {
            "min_states": self.min_states,
            "max_states": self.max_states,
            "model": self.model_,
            "mapping": getattr(self, "state_mapping_", {}),
        }
        joblib.dump(payload, path)

    @classmethod
    def load(cls, path: str | Path) -> "RegimeLabeler":
        payload = joblib.load(path)
        obj = cls(payload.get("min_states", 3), payload.get("max_states", 8))
        obj.model_ = payload["model"]
        obj.state_mapping_ = payload.get("mapping", {})
        return obj


__all__ = ["RegimeLabeler"]

