"""V10 Alpha Quality Gates — rigorous filtering before factor zoo entry.

Applies 6 gates:
  1. DSR > 0.95 (statistically genuine after multiple testing correction)
  2. PBO < 0.5 (low probability of being an overfit artifact)
  3. IC stability (std/|mean| < 1.5)
  4. Regime robust (positive IC in >= 50% of regimes)
  5. Turnover bounded (< 50% sign flips per 100 bars)
  6. Monotonic spread (Q5 - Q1 return > 0)

Usage:
    gates = AlphaQualityGates()
    result = gates.validate(alpha_values, forward_returns, regime_labels, n_trials)
    if result.passed:
        store_to_zoo(alpha)
"""
from __future__ import annotations
import numpy as np
from scipy.stats import spearmanr, norm
from dataclasses import dataclass
from typing import Optional, List
import logging

log = logging.getLogger(__name__)


@dataclass
class GateResult:
    passed: bool
    failed_gates: List[str]
    metrics: dict

    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        return f"GateResult({status}, failed={self.failed_gates}, {self.metrics})"


class AlphaQualityGates:
    """Apply all quality gates to an alpha's predicted values."""

    def __init__(self,
                 dsr_threshold: float = 0.95,
                 pbo_threshold: float = 0.5,
                 ic_stability_threshold: float = 1.5,
                 regime_robustness_min_positive_ratio: float = 0.5,
                 turnover_max: float = 0.5,
                 monotonic_quintile_check: bool = True,
                 total_trials_multiplier: int = 100):
        self.dsr_threshold = dsr_threshold
        self.pbo_threshold = pbo_threshold
        self.ic_stability_threshold = ic_stability_threshold
        self.regime_robustness_min_positive_ratio = regime_robustness_min_positive_ratio
        self.turnover_max = turnover_max
        self.monotonic_quintile_check = monotonic_quintile_check
        self.total_trials_multiplier = total_trials_multiplier

    def validate(self,
                 alpha_values: np.ndarray,
                 forward_returns: np.ndarray,
                 regime_labels: Optional[np.ndarray] = None,
                 num_alphas_tried: int = 100) -> GateResult:
        """Run all gates and return combined result."""
        metrics = {}
        failed = []

        # Prep valid data
        valid = np.isfinite(alpha_values) & np.isfinite(forward_returns)
        if valid.sum() < 200:
            return GateResult(False, ['insufficient_data'], {'valid_n': int(valid.sum())})

        alpha_v = alpha_values[valid]
        fwd_v = forward_returns[valid]

        # Gate 1: DSR
        try:
            dsr = self._compute_dsr(alpha_v, fwd_v, num_alphas_tried)
            metrics['dsr'] = dsr
            if dsr < self.dsr_threshold:
                failed.append('dsr')
        except Exception as e:
            metrics['dsr_error'] = str(e)
            failed.append('dsr')

        # Gate 2: PBO
        try:
            pbo = self._compute_pbo(alpha_v, fwd_v, n_splits=10)
            metrics['pbo'] = pbo
            if pbo > self.pbo_threshold:
                failed.append('pbo')
        except Exception as e:
            metrics['pbo_error'] = str(e)
            failed.append('pbo')

        # Gate 3: IC Stability
        try:
            stability = self._compute_ic_stability(alpha_v, fwd_v, window=500, step=100)
            metrics['ic_stability'] = stability
            if stability > self.ic_stability_threshold:
                failed.append('ic_stability')
        except Exception as e:
            metrics['stability_error'] = str(e)
            failed.append('ic_stability')

        # Gate 4: Regime robustness
        if regime_labels is not None:
            try:
                regime_ics = self._compute_regime_ics(alpha_v, fwd_v, regime_labels[valid])
                metrics['regime_ics'] = regime_ics
                positive_ratio = sum(1 for ic in regime_ics.values() if ic > 0) / max(len(regime_ics), 1)
                metrics['regime_positive_ratio'] = positive_ratio
                if positive_ratio < self.regime_robustness_min_positive_ratio:
                    failed.append('regime_robustness')
            except Exception as e:
                metrics['regime_error'] = str(e)

        # Gate 5: Turnover (for signal built from alpha)
        try:
            signals = np.sign(alpha_v - np.median(alpha_v))
            flips = np.sum(signals[1:] != signals[:-1])
            turnover = flips / max(len(signals), 1)
            metrics['turnover'] = turnover
            if turnover > self.turnover_max:
                failed.append('turnover')
        except Exception as e:
            metrics['turnover_error'] = str(e)

        # Gate 6: Monotonic quintile
        if self.monotonic_quintile_check:
            try:
                quintile_spread = self._compute_quintile_monotonicity(alpha_v, fwd_v)
                metrics['quintile_spread'] = quintile_spread
                if quintile_spread <= 0:
                    failed.append('monotonicity')
            except Exception as e:
                metrics['monotonicity_error'] = str(e)

        return GateResult(
            passed=len(failed) == 0,
            failed_gates=failed,
            metrics=metrics
        )

    def _compute_dsr(self, alpha, fwd, n_trials):
        """Deflated Sharpe Ratio (Bailey-López de Prado)."""
        ic, _ = spearmanr(alpha, fwd)
        if np.isnan(ic):
            return 0.0
        T = len(alpha)
        sr = ic * np.sqrt(T)  # rough SR proxy
        sr_std = 1.0  # simplified
        gamma = 0.5772156649015329
        z = norm.ppf(1 - 1.0 / max(n_trials, 2))
        sr0 = sr_std * ((1 - gamma) * z + gamma * norm.ppf(1 - 1.0 / (n_trials * np.e)))
        sr_var = 1.0 / (T - 1)
        return float(norm.cdf((sr - sr0) / max(np.sqrt(sr_var), 1e-10)))

    def _compute_pbo(self, alpha, fwd, n_splits=10):
        """Probability of Backtest Overfitting — combinatorial symmetric CV.
        Simplified: split into n chunks, measure rank correlation between
        in-sample and out-of-sample IC rankings."""
        T = len(alpha)
        chunk_size = T // n_splits
        if chunk_size < 50:
            return 1.0

        in_sample_ics = []
        out_sample_ics = []
        for i in range(n_splits):
            start = i * chunk_size
            end = start + chunk_size
            # In: this chunk
            in_alpha = alpha[start:end]
            in_fwd = fwd[start:end]
            # Out: rest
            mask = np.ones(T, dtype=bool)
            mask[start:end] = False
            out_alpha = alpha[mask]
            out_fwd = fwd[mask]

            try:
                in_ic, _ = spearmanr(in_alpha, in_fwd)
                out_ic, _ = spearmanr(out_alpha, out_fwd)
                if not (np.isnan(in_ic) or np.isnan(out_ic)):
                    in_sample_ics.append(in_ic)
                    out_sample_ics.append(out_ic)
            except:
                continue

        if len(in_sample_ics) < 3:
            return 1.0

        # PBO: fraction of times IS rank doesn't match OOS rank
        in_ranks = np.argsort(in_sample_ics)
        out_ranks = np.argsort(out_sample_ics)
        # How often does best IS produce below-median OOS?
        median_out = np.median(out_sample_ics)
        best_is_idx = int(np.argmax(in_sample_ics))
        pbo_indicator = 1.0 if out_sample_ics[best_is_idx] < median_out else 0.0
        return pbo_indicator

    def _compute_ic_stability(self, alpha, fwd, window=500, step=100):
        """Std/|mean| of rolling IC. Lower = more stable."""
        T = len(alpha)
        if T < window + step:
            return 999.0

        ics = []
        for start in range(0, T - window, step):
            try:
                ic, _ = spearmanr(alpha[start:start+window], fwd[start:start+window])
                if not np.isnan(ic):
                    ics.append(ic)
            except:
                continue

        if len(ics) < 3:
            return 999.0

        mean_ic = np.mean(ics)
        std_ic = np.std(ics)
        return float(std_ic / max(abs(mean_ic), 1e-6))

    def _compute_regime_ics(self, alpha, fwd, regimes):
        """IC per regime label."""
        unique = np.unique(regimes)
        result = {}
        for r in unique:
            mask = regimes == r
            if mask.sum() < 100:
                continue
            try:
                ic, _ = spearmanr(alpha[mask], fwd[mask])
                if not np.isnan(ic):
                    result[str(r)] = float(ic)
            except:
                continue
        return result

    def _compute_quintile_monotonicity(self, alpha, fwd):
        """Q5 - Q1 forward return spread."""
        q = np.percentile(alpha, [20, 40, 60, 80])
        q1_mask = alpha <= q[0]
        q5_mask = alpha >= q[3]
        if q1_mask.sum() < 10 or q5_mask.sum() < 10:
            return 0.0
        return float(np.mean(fwd[q5_mask]) - np.mean(fwd[q1_mask]))


if __name__ == "__main__":
    # Self-test
    np.random.seed(42)
    n = 5000
    alpha = np.random.randn(n).astype(np.float32)
    fwd = alpha * 0.1 + np.random.randn(n) * 0.5  # moderate signal
    regimes = np.random.choice(['BULL', 'BEAR', 'CONS'], size=n)

    gates = AlphaQualityGates()
    result = gates.validate(alpha, fwd, regimes, num_alphas_tried=100)
    print(result)
