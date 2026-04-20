"""J02 fitness — ICIR-style mean minus lambda*std over K=5 folds.

Contract (shared with Zangetsu engine):
    fitness_fn(alpha: np.ndarray,
               forward_returns: np.ndarray,
               height: int) -> float

Research motivation:
- Single-split (K=2) fitness is degenerate CPCV; López de Prado and
  practitioner papers recommend K>=5 folds with cross-fold stability.
- AlphaForge (arXiv 2406.18394), Warm-Start GP (arXiv 2412.00896),
  Numerai scoring all use mean(IC_t)/std(IC_t) as the canonical
  stability-aware fitness.
- Shi et al. 2025 (Computational Economics 10.1007/s10614-025-11289-1)
  showed K=5 NSGA-II on (mean_IC, -std_IC) as 2025 SOTA.
- Ruan 2024 warned against zombie factor collapse when fitness
  over-rewards symmetry at low magnitude — mitigated here by the
  per-fold magnitude floor and sign-agreement requirement.

Formula:
    mean = mean(|IC_1|, ..., |IC_K|)
    std  = std(|IC_1|, ..., |IC_K|)
    fitness = mean - LAMBDA_STD * std - HEIGHT_PENALTY * height

Gates applied before scoring:
- all K folds must have same sign (directional consistency)
- all K |IC| must exceed MIN_ABS_IC (no near-zero folds)
- each fold must have at least MIN_FOLD_BARS samples
"""
from __future__ import annotations

import numpy as np


K_FOLDS = 5
MIN_FOLD_BARS = 100
MIN_ABS_IC = 3e-3           # per-fold magnitude floor
LAMBDA_STD = 1.0            # std penalty weight
HEIGHT_PENALTY = 1e-3


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    if a.size != b.size or a.size < 10:
        return 0.0
    mask = np.isfinite(a) & np.isfinite(b)
    if mask.sum() < 10:
        return 0.0
    a2 = a[mask]
    b2 = b[mask]
    ar = np.argsort(np.argsort(a2))
    br = np.argsort(np.argsort(b2))
    if np.std(ar) < 1e-12 or np.std(br) < 1e-12:
        return 0.0
    return float(np.corrcoef(ar, br)[0, 1])


def fitness_fn(alpha: np.ndarray,
               forward_returns: np.ndarray,
               height: int) -> float:
    n = alpha.size
    if n < K_FOLDS * MIN_FOLD_BARS:
        return 0.0

    folds_alpha = np.array_split(alpha, K_FOLDS)
    folds_fr = np.array_split(forward_returns, K_FOLDS)

    ics: list[float] = []
    for a_k, fr_k in zip(folds_alpha, folds_fr):
        if a_k.size < MIN_FOLD_BARS:
            return 0.0
        ic = _spearman(a_k, fr_k)
        if not np.isfinite(ic):
            return 0.0
        ics.append(ic)

    arr = np.asarray(ics, dtype=np.float64)
    abs_arr = np.abs(arr)

    # per-fold magnitude floor
    if np.any(abs_arr < MIN_ABS_IC):
        return 0.0

    # sign-agreement across ALL folds
    signs = np.sign(arr)
    if np.any(signs != signs[0]):
        return 0.0

    mean_abs_ic = float(np.mean(abs_arr))
    std_abs_ic = float(np.std(abs_arr))

    return mean_abs_ic - LAMBDA_STD * std_abs_ic - HEIGHT_PENALTY * height


if __name__ == "__main__":  # pragma: no cover
    rng = np.random.default_rng(7)
    n = 2500
    fr = rng.standard_normal(n)

    alpha_consistent = fr + 0.1 * rng.standard_normal(n)
    alpha_volatile = np.concatenate([
        fr[:n // 5] + 0.01 * rng.standard_normal(n // 5),
        0.5 * fr[n // 5:2 * n // 5] + rng.standard_normal(n // 5),
        rng.standard_normal(n - 2 * (n // 5)),
    ])
    alpha_flip = np.concatenate([
        fr[:n // 2] + 0.1 * rng.standard_normal(n // 2),
        -fr[n // 2:] + 0.1 * rng.standard_normal(n - n // 2),
    ])

    print("consistent across 5 folds:", fitness_fn(alpha_consistent, fr, height=6))
    print("volatile (high std):       ", fitness_fn(alpha_volatile, fr, height=6))
    print("sign-flip between folds:   ", fitness_fn(alpha_flip, fr, height=6))
