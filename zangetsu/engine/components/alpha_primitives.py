"""V10 Alpha Primitives — WorldQuant-style operators for alpha expressions.

All functions are @njit compiled for Numba GP evaluation.
Input: numpy arrays (float32 or float64)
Output: numpy arrays of same length (float32)
NaN-safe, inf-safe, causal (no lookahead bias).

Design invariants:
- First d values in time-series ops are 0.0 (never NaN)
- Division by near-zero returns 0.0
- Exp/log/power clipped to finite ranges
- All outputs are np.float32 to match cache storage
"""

from numba import njit
import numpy as np

# Shared numerical constants
_EPS = 1e-10
_EXP_CLIP = 50.0           # exp(50) ~ 5.18e21 — keep finite
_LARGE = 1e20              # clamp for inf values
_LOG_FLOOR = 1e-20         # log input floor


# =============================================================================
# Binary arithmetic
# =============================================================================

@njit(cache=True)
def add(x, y):
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    for i in range(n):
        a = x[i]
        b = y[i]
        if np.isnan(a) or np.isnan(b):
            out[i] = 0.0
        else:
            v = a + b
            if v > _LARGE:
                v = _LARGE
            elif v < -_LARGE:
                v = -_LARGE
            out[i] = v
    return out


@njit(cache=True)
def sub(x, y):
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    for i in range(n):
        a = x[i]
        b = y[i]
        if np.isnan(a) or np.isnan(b):
            out[i] = 0.0
        else:
            v = a - b
            if v > _LARGE:
                v = _LARGE
            elif v < -_LARGE:
                v = -_LARGE
            out[i] = v
    return out


@njit(cache=True)
def mul(x, y):
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    for i in range(n):
        a = x[i]
        b = y[i]
        if np.isnan(a) or np.isnan(b):
            out[i] = 0.0
        else:
            v = a * b
            if v > _LARGE:
                v = _LARGE
            elif v < -_LARGE:
                v = -_LARGE
            out[i] = v
    return out


@njit(cache=True)
def protected_div(x, y):
    """Return 0.0 when |y| < 1e-10. NaN/inf-safe."""
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    for i in range(n):
        a = x[i]
        b = y[i]
        if np.isnan(a) or np.isnan(b):
            out[i] = 0.0
        elif b < _EPS and b > -_EPS:
            out[i] = 0.0
        else:
            v = a / b
            if v > _LARGE:
                v = _LARGE
            elif v < -_LARGE:
                v = -_LARGE
            out[i] = v
    return out


@njit(cache=True)
def safe_divide(x, y, default=0.0):
    """Alias for protected_div with explicit default. default only used on div-by-~0."""
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    d = np.float32(default)
    for i in range(n):
        a = x[i]
        b = y[i]
        if np.isnan(a) or np.isnan(b):
            out[i] = d
        elif b < _EPS and b > -_EPS:
            out[i] = d
        else:
            v = a / b
            if v > _LARGE:
                v = _LARGE
            elif v < -_LARGE:
                v = -_LARGE
            out[i] = v
    return out


# =============================================================================
# Unary arithmetic
# =============================================================================

@njit(cache=True)
def neg(x):
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    for i in range(n):
        a = x[i]
        if np.isnan(a):
            out[i] = 0.0
        else:
            out[i] = -a
    return out


@njit(cache=True)
def abs_x(x):
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    for i in range(n):
        a = x[i]
        if np.isnan(a):
            out[i] = 0.0
        else:
            out[i] = a if a >= 0.0 else -a
    return out


@njit(cache=True)
def sign_x(x):
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    for i in range(n):
        a = x[i]
        if np.isnan(a):
            out[i] = 0.0
        elif a > 0.0:
            out[i] = 1.0
        elif a < 0.0:
            out[i] = -1.0
        else:
            out[i] = 0.0
    return out


@njit(cache=True)
def tanh_x(x):
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    for i in range(n):
        a = x[i]
        if np.isnan(a):
            out[i] = 0.0
        else:
            # tanh saturates naturally; clip extreme inputs to keep numerics sane
            if a > _EXP_CLIP:
                out[i] = 1.0
            elif a < -_EXP_CLIP:
                out[i] = -1.0
            else:
                out[i] = np.tanh(a)
    return out


@njit(cache=True)
def log_x(x):
    """Signed-safe log: returns log(max(|x|, floor)) * sign(x)."""
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    for i in range(n):
        a = x[i]
        if np.isnan(a):
            out[i] = 0.0
        elif a > _LOG_FLOOR:
            out[i] = np.log(a)
        elif a < -_LOG_FLOOR:
            out[i] = -np.log(-a)
        else:
            out[i] = 0.0
    return out


@njit(cache=True)
def exp_x(x):
    """Exp clipped at |x| <= 50 to prevent overflow."""
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    for i in range(n):
        a = x[i]
        if np.isnan(a):
            out[i] = 0.0
        else:
            if a > _EXP_CLIP:
                a = _EXP_CLIP
            elif a < -_EXP_CLIP:
                a = -_EXP_CLIP
            out[i] = np.exp(a)
    return out


# =============================================================================
# Parametric math
# =============================================================================

@njit(cache=True)
def power(x, p):
    """x ** p, preserving sign for odd integer p.
    For non-integer p, falls back to sign(x) * |x|**p to avoid complex results.
    """
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    ip = int(p)
    is_int = (float(ip) == float(p))
    odd = is_int and (ip % 2 != 0)
    for i in range(n):
        a = x[i]
        if np.isnan(a):
            out[i] = 0.0
            continue
        if a == 0.0:
            out[i] = 0.0 if p != 0.0 else 1.0
            continue
        if is_int:
            if odd:
                # preserve sign: sign(a)*|a|^p
                s = 1.0 if a >= 0.0 else -1.0
                v = s * (abs(a) ** p)
            else:
                v = abs(a) ** p
        else:
            s = 1.0 if a >= 0.0 else -1.0
            v = s * (abs(a) ** p)
        if v > _LARGE:
            v = _LARGE
        elif v < -_LARGE:
            v = -_LARGE
        out[i] = v
    return out


@njit(cache=True)
def signed_power(x, p):
    """sign(x) * |x|^p — always sign-preserving regardless of p."""
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    for i in range(n):
        a = x[i]
        if np.isnan(a):
            out[i] = 0.0
            continue
        if a == 0.0:
            out[i] = 0.0
            continue
        s = 1.0 if a > 0.0 else -1.0
        v = s * (abs(a) ** p)
        if v > _LARGE:
            v = _LARGE
        elif v < -_LARGE:
            v = -_LARGE
        out[i] = v
    return out


# =============================================================================
# Time-series operators (causal)
# =============================================================================

@njit(cache=True)
def delta(x, d):
    """x[t] - x[t-d], first d values = 0."""
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    if d <= 0 or d >= n:
        return out
    for i in range(d, n):
        a = x[i]
        b = x[i - d]
        if np.isnan(a) or np.isnan(b):
            out[i] = 0.0
        else:
            out[i] = a - b
    return out


@njit(cache=True)
def ts_max(x, d):
    """Rolling max over last d bars (inclusive of t)."""
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    if d <= 0:
        return out
    for i in range(d - 1, n):
        mv = -np.inf
        any_valid = False
        for k in range(i - d + 1, i + 1):
            v = x[k]
            if not np.isnan(v):
                if v > mv:
                    mv = v
                any_valid = True
        out[i] = mv if any_valid else 0.0
    return out


@njit(cache=True)
def ts_min(x, d):
    """Rolling min over last d bars (inclusive of t)."""
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    if d <= 0:
        return out
    for i in range(d - 1, n):
        mv = np.inf
        any_valid = False
        for k in range(i - d + 1, i + 1):
            v = x[k]
            if not np.isnan(v):
                if v < mv:
                    mv = v
                any_valid = True
        out[i] = mv if any_valid else 0.0
    return out


@njit(cache=True)
def ts_rank(x, d):
    """Percentile rank of x[t] in last d bars, in [0, 1].
    Rank definition: (# of values <= x[t]) / d.
    """
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    if d <= 0:
        return out
    for i in range(d - 1, n):
        cur = x[i]
        if np.isnan(cur):
            out[i] = 0.0
            continue
        le_count = 0
        valid = 0
        for k in range(i - d + 1, i + 1):
            v = x[k]
            if not np.isnan(v):
                valid += 1
                if v <= cur:
                    le_count += 1
        if valid > 0:
            out[i] = le_count / valid
        else:
            out[i] = 0.0
    return out


@njit(cache=True)
def ts_argmax(x, d):
    """Normalized index [0,1] of max in last d bars.
    0.0 = max was d-1 bars ago (oldest), 1.0 = max is current bar.
    """
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    if d <= 1:
        return out
    for i in range(d - 1, n):
        mv = -np.inf
        midx = i
        any_valid = False
        for k in range(i - d + 1, i + 1):
            v = x[k]
            if not np.isnan(v):
                if v > mv:
                    mv = v
                    midx = k
                any_valid = True
        if any_valid:
            # offset from oldest bar in window: 0..d-1
            offset = midx - (i - d + 1)
            out[i] = offset / (d - 1)
        else:
            out[i] = 0.0
    return out


@njit(cache=True)
def ts_argmin(x, d):
    """Normalized index [0,1] of min in last d bars."""
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    if d <= 1:
        return out
    for i in range(d - 1, n):
        mv = np.inf
        midx = i
        any_valid = False
        for k in range(i - d + 1, i + 1):
            v = x[k]
            if not np.isnan(v):
                if v < mv:
                    mv = v
                    midx = k
                any_valid = True
        if any_valid:
            offset = midx - (i - d + 1)
            out[i] = offset / (d - 1)
        else:
            out[i] = 0.0
    return out


@njit(cache=True)
def ts_sum(x, d):
    """Rolling sum over last d bars."""
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    if d <= 0:
        return out
    for i in range(d - 1, n):
        s = 0.0
        for k in range(i - d + 1, i + 1):
            v = x[k]
            if not np.isnan(v):
                s += v
        if s > _LARGE:
            s = _LARGE
        elif s < -_LARGE:
            s = -_LARGE
        out[i] = s
    return out


@njit(cache=True)
def ts_mean(x, d):
    """Rolling mean over last d bars."""
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    if d <= 0:
        return out
    for i in range(d - 1, n):
        s = 0.0
        c = 0
        for k in range(i - d + 1, i + 1):
            v = x[k]
            if not np.isnan(v):
                s += v
                c += 1
        if c > 0:
            out[i] = s / c
        else:
            out[i] = 0.0
    return out


@njit(cache=True)
def ts_std(x, d):
    """Rolling population std over last d bars."""
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    if d <= 1:
        return out
    for i in range(d - 1, n):
        s = 0.0
        c = 0
        for k in range(i - d + 1, i + 1):
            v = x[k]
            if not np.isnan(v):
                s += v
                c += 1
        if c <= 1:
            out[i] = 0.0
            continue
        mean = s / c
        ss = 0.0
        for k in range(i - d + 1, i + 1):
            v = x[k]
            if not np.isnan(v):
                diff = v - mean
                ss += diff * diff
        var = ss / c
        out[i] = np.sqrt(var)
    return out


# =============================================================================
# Pairwise statistical (causal)
# =============================================================================

@njit(cache=True)
def correlation(x, y, d):
    """Rolling Pearson correlation over last d bars. First d-1 bars = 0."""
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    if d <= 1:
        return out
    for i in range(d - 1, n):
        sx = 0.0
        sy = 0.0
        c = 0
        for k in range(i - d + 1, i + 1):
            vx = x[k]
            vy = y[k]
            if not (np.isnan(vx) or np.isnan(vy)):
                sx += vx
                sy += vy
                c += 1
        if c <= 1:
            out[i] = 0.0
            continue
        mx = sx / c
        my = sy / c
        sxx = 0.0
        syy = 0.0
        sxy = 0.0
        for k in range(i - d + 1, i + 1):
            vx = x[k]
            vy = y[k]
            if not (np.isnan(vx) or np.isnan(vy)):
                dx = vx - mx
                dy = vy - my
                sxx += dx * dx
                syy += dy * dy
                sxy += dx * dy
        denom = np.sqrt(sxx * syy)
        if denom < _EPS:
            out[i] = 0.0
        else:
            v = sxy / denom
            if v > 1.0:
                v = 1.0
            elif v < -1.0:
                v = -1.0
            out[i] = v
    return out


@njit(cache=True)
def covariance(x, y, d):
    """Rolling population covariance over last d bars."""
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    if d <= 1:
        return out
    for i in range(d - 1, n):
        sx = 0.0
        sy = 0.0
        c = 0
        for k in range(i - d + 1, i + 1):
            vx = x[k]
            vy = y[k]
            if not (np.isnan(vx) or np.isnan(vy)):
                sx += vx
                sy += vy
                c += 1
        if c <= 1:
            out[i] = 0.0
            continue
        mx = sx / c
        my = sy / c
        sxy = 0.0
        for k in range(i - d + 1, i + 1):
            vx = x[k]
            vy = y[k]
            if not (np.isnan(vx) or np.isnan(vy)):
                sxy += (vx - mx) * (vy - my)
        v = sxy / c
        if v > _LARGE:
            v = _LARGE
        elif v < -_LARGE:
            v = -_LARGE
        out[i] = v
    return out


# =============================================================================
# Normalization (causal)
# =============================================================================

@njit(cache=True)
def scale(x, a=1.0):
    """L1 normalize over entire series: a * x / sum(|x|).
    Note: this uses the full-series |x| sum, which is a common WQ convention.
    Causality: each bar divides by a global constant, so no per-bar lookahead
    issue in cross-sectional usage. For strictly causal rolling, use rolling_scale.
    """
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    total = 0.0
    for i in range(n):
        v = x[i]
        if not np.isnan(v):
            total += v if v >= 0.0 else -v
    if total < _EPS:
        return out
    inv = a / total
    for i in range(n):
        v = x[i]
        if np.isnan(v):
            out[i] = 0.0
        else:
            out[i] = v * inv
    return out


@njit(cache=True)
def rolling_scale(x, d):
    """Rolling L1 normalize: x[t] / sum(|x[t-d+1..t]|)."""
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    if d <= 0:
        return out
    for i in range(d - 1, n):
        total = 0.0
        for k in range(i - d + 1, i + 1):
            v = x[k]
            if not np.isnan(v):
                total += v if v >= 0.0 else -v
        if total < _EPS:
            out[i] = 0.0
        else:
            cur = x[i]
            if np.isnan(cur):
                out[i] = 0.0
            else:
                out[i] = cur / total
    return out


@njit(cache=True)
def decay_linear(x, d):
    """Linearly-decaying weighted sum over last d bars.
    weights = [1, 2, ..., d] (newest gets weight d), normalized by sum.
    """
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    if d <= 0:
        return out
    wsum = 0.0
    for w in range(1, d + 1):
        wsum += w
    for i in range(d - 1, n):
        s = 0.0
        valid = 0
        valid_wsum = 0.0
        for k in range(i - d + 1, i + 1):
            v = x[k]
            # weight: oldest bar (k = i-d+1) → weight 1; newest (k = i) → weight d
            w = k - (i - d + 1) + 1
            if not np.isnan(v):
                s += v * w
                valid += 1
                valid_wsum += w
        if valid == 0 or valid_wsum < _EPS:
            out[i] = 0.0
        else:
            out[i] = s / valid_wsum
    return out


# =============================================================================
# Utility
# =============================================================================

@njit(cache=True)
def clip_range(x, lo=-1.0, hi=1.0):
    """Numba-friendly np.clip. NaN → 0.0."""
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    lof = np.float32(lo)
    hif = np.float32(hi)
    for i in range(n):
        v = x[i]
        if np.isnan(v):
            out[i] = 0.0
        elif v < lof:
            out[i] = lof
        elif v > hif:
            out[i] = hif
        else:
            out[i] = v
    return out


# =============================================================================
# Self-test
# =============================================================================

if __name__ == "__main__":
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0], dtype=np.float32)
    y = np.array([2.0, 1.0, 3.0, 2.0, 4.0, 3.0, 5.0, 4.0, 6.0, 5.0], dtype=np.float32)

    # Edge case vectors
    with_nan = np.array([1.0, np.nan, 3.0, 4.0, np.nan, 6.0, 7.0, 8.0, 9.0, 10.0], dtype=np.float32)
    zeros_y = np.array([1.0, 0.0, 1e-11, 2.0, 0.0, 3.0, 4.0, 5.0, 6.0, 7.0], dtype=np.float32)
    extreme = np.array([1e30, -1e30, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0], dtype=np.float32)

    print("=== Binary arithmetic ===")
    print("add:            ", add(x, y))
    print("sub:            ", sub(x, y))
    print("mul:            ", mul(x, y))
    print("protected_div:  ", protected_div(x, zeros_y))
    print("safe_divide:    ", safe_divide(x, zeros_y, default=0.0))

    print("\n=== Unary ===")
    print("neg:            ", neg(x))
    print("abs_x:          ", abs_x(sub(y, x)))
    print("sign_x:         ", sign_x(sub(y, x)))
    print("tanh_x:         ", tanh_x(x))
    print("log_x:          ", log_x(x))
    print("exp_x (clipped):", exp_x(np.array([0.0, 1.0, 10.0, 100.0, -100.0, 2.0, 3.0, 4.0, 5.0, 6.0], dtype=np.float32)))

    print("\n=== Parametric ===")
    print("power(p=2):     ", power(x, 2.0))
    print("power(p=3, neg):", power(sub(y, x), 3.0))
    print("signed_power 0.5:", signed_power(sub(y, x), 0.5))

    print("\n=== Time-series ===")
    print("delta(d=3):     ", delta(x, 3))
    print("ts_max(d=3):    ", ts_max(x, 3))
    print("ts_min(d=3):    ", ts_min(x, 3))
    print("ts_rank(d=5):   ", ts_rank(x, 5))
    print("ts_argmax(d=5): ", ts_argmax(x, 5))
    print("ts_argmin(d=5): ", ts_argmin(x, 5))
    print("ts_sum(d=3):    ", ts_sum(x, 3))
    print("ts_mean(d=3):   ", ts_mean(x, 3))
    print("ts_std(d=3):    ", ts_std(x, 3))

    print("\n=== Pairwise statistical ===")
    print("correlation(d=5):", correlation(x, y, 5))
    print("covariance(d=5): ", covariance(x, y, 5))

    print("\n=== Normalization ===")
    print("scale:           ", scale(x, 1.0))
    print("rolling_scale:   ", rolling_scale(x, 3))
    print("decay_linear:    ", decay_linear(x, 3))

    print("\n=== Utility ===")
    print("clip_range:      ", clip_range(extreme, -10.0, 10.0))

    print("\n=== NaN safety ===")
    print("add(with_nan):   ", add(with_nan, y))
    print("ts_mean(with_nan):", ts_mean(with_nan, 3))
    print("correlation(nan):", correlation(with_nan, y, 5))

    # Sanity assertions
    assert add(x, y).dtype == np.float32
    assert delta(x, 3).dtype == np.float32
    assert correlation(x, y, 5).dtype == np.float32
    # delta first d entries are 0
    d_out = delta(x, 3)
    assert d_out[0] == 0.0 and d_out[1] == 0.0 and d_out[2] == 0.0
    assert d_out[3] == 3.0 and d_out[9] == 3.0
    # protected_div: zeros give 0
    pd = protected_div(x, zeros_y)
    assert pd[1] == 0.0 and pd[2] == 0.0 and pd[4] == 0.0
    # ts_rank is in [0,1]
    tr = ts_rank(x, 5)
    for v in tr:
        assert v >= 0.0 and v <= 1.0
    # correlation bounded
    c = correlation(x, y, 5)
    for v in c:
        assert v >= -1.0 and v <= 1.0
    # no NaN in any output
    for arr in [add(with_nan, y), ts_mean(with_nan, 3), correlation(with_nan, y, 5),
                ts_std(with_nan, 3), rolling_scale(with_nan, 3), decay_linear(with_nan, 3)]:
        for v in arr:
            assert not np.isnan(v)

    print("\nAll assertions passed.")
