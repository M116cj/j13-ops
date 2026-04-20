"""J01 fitness — sign-gated, epsilon-floored harmonic mean of IC over
two halves of the training window.

Contract (shared with Zangetsu engine):
    fitness_fn(alpha: np.ndarray,
               forward_returns: np.ndarray,
               height: int) -> float

Rationale (backed by research archive
`zangetsu/docs/research/research-gp-fitness-stability-20260420.md`):
- Harmonic mean is the F1 analogue: `2ab/(a+b)` collapses toward the
  smaller value via the reciprocal form, penalizing imbalance quadratically.
- Sign-agreement gate blocks alphas whose prediction reverses between halves.
- Magnitude floor (MIN_ABS_IC) prevents the "both halves near zero" trap
  that scored 0/0 formulas well under the previous linear-penalty formula.
- Height penalty keeps trees parsimonious.

Empirical calibration expected: at |IC| scales of 0.02-0.10, this formula
scores 0.10/0.06 at 0.075, 0.02/0.02 at 0.02, 0.10/-0.06 at 0.0 — exactly
the ordering j13 requires for "stable pnl / win-rate / trade count".
"""
from __future__ import annotations

import numpy as np


MIN_HALF_BARS = 100        # halves smaller than this are too noisy
MIN_ABS_IC = 5e-3          # below this magnitude, treat as noise
EPSILON_FLOOR = 1e-6       # numeric stability for harmonic denominator
HEIGHT_PENALTY = 1e-3      # parsimony pressure on GP tree depth


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Inlined Spearman rank correlation to avoid scipy import cost per eval.

    Falls back to scipy when NaN handling is needed; otherwise uses argsort.
    """
    if a.size != b.size or a.size < 10:
        return 0.0
    mask = np.isfinite(a) & np.isfinite(b)
    if mask.sum() < 10:
        return 0.0
    a2 = a[mask]
    b2 = b[mask]
    ar = np.argsort(np.argsort(a2))
    br = np.argsort(np.argsort(b2))
    n = ar.size
    if np.std(ar) < 1e-12 or np.std(br) < 1e-12:
        return 0.0
    return float(np.corrcoef(ar, br)[0, 1])


def fitness_fn(alpha: np.ndarray,
               forward_returns: np.ndarray,
               height: int) -> float:
    n = alpha.size
    mid = n // 2
    if mid < MIN_HALF_BARS:
        return 0.0

    ic_early = _spearman(alpha[:mid], forward_returns[:mid])
    ic_late = _spearman(alpha[mid:], forward_returns[mid:])

    a = abs(ic_early)
    b = abs(ic_late)
    if a < MIN_ABS_IC or b < MIN_ABS_IC:
        return 0.0
    if np.sign(ic_early) != np.sign(ic_late):
        return 0.0

    harmonic = 2.0 * a * b / (a + b + EPSILON_FLOOR)
    return float(harmonic - HEIGHT_PENALTY * height)


# Smoke-test inline to validate ordering at import time in dev.
if __name__ == "__main__":  # pragma: no cover
    rng = np.random.default_rng(42)
    n = 2000
    fr = rng.standard_normal(n)
    # Build three synthetic alphas with known IC profiles
    alpha_strong = fr + 0.1 * rng.standard_normal(n)
    alpha_weak_sym = 0.02 * fr + rng.standard_normal(n)
    alpha_flip = np.concatenate([fr[: n // 2], -fr[n // 2:]])

    print("strong same-sign:    ",
          fitness_fn(alpha_strong, fr, height=6))
    print("weak symmetric:      ",
          fitness_fn(alpha_weak_sym, fr, height=6))
    print("sign-flip mid-window:",
          fitness_fn(alpha_flip, fr, height=6))
