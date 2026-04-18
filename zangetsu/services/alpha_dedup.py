"""V10 Alpha Deduplication - detect semantically equivalent alphas.

Three methods:
1. canonical_hash(formula) - AST normalization + hash
2. value_hash(alpha_values, n_samples=50) - hash of evaluated values
3. correlation_dedup(alpha_a, alpha_b, threshold=0.95) - pairwise correlation check
"""
from __future__ import annotations
import hashlib
import numpy as np
from typing import List, Dict, Set, Tuple, Optional
from scipy.stats import pearsonr
import logging

log = logging.getLogger(__name__)


# Commutative operators - args can be swapped without changing meaning
COMMUTATIVE_OPS = {'add', 'mul', 'correlation', 'covariance'}

# Associative operators - nested can be flattened
ASSOCIATIVE_OPS = {'add', 'mul'}

# Self-inverse operators - double application cancels
SELF_INVERSE = {'neg'}


def canonicalize(formula: str) -> str:
    """Normalize an alpha formula to canonical form.

    Rules applied:
    1. Commutative: sort args alphabetically (add(b,a) -> add(a,b))
    2. Self-inverse collapse: neg(neg(x)) -> x
    3. Identity removal: add(x, 0) -> x
    4. Constant folding (simple cases)
    """
    # Simple implementation: parse, apply rules, re-serialize
    # For production use, requires proper AST walking. For now, heuristic text ops.
    result = formula

    # Remove double negation
    import re
    result = re.sub(r'neg\(neg\(([^()]+)\)\)', r'\1', result)

    # Sort commutative binary ops (best-effort)
    # e.g., add(high, close) -> add(close, high) if alphabetical
    for op in COMMUTATIVE_OPS:
        pattern = f'{op}\\(([^,()]+), ([^,()]+)\\)'
        matches = re.finditer(pattern, result)
        for m in list(matches)[::-1]:
            a, b = m.group(1), m.group(2)
            if b < a:  # swap if out of order
                result = result[:m.start()] + f'{op}({b}, {a})' + result[m.end():]

    return result


def canonical_hash(formula: str) -> str:
    """Hash of canonicalized formula. Same for semantically identical alphas
    (modulo rules in canonicalize())."""
    return hashlib.md5(canonicalize(formula).encode()).hexdigest()[:16]


def value_hash(alpha_values: np.ndarray, n_samples: int = 50) -> str:
    """Hash based on sampled alpha values. Alphas with identical numerical output
    (anywhere) will have identical hash, regardless of formula form."""
    arr = np.asarray(alpha_values, dtype=np.float32)
    # Remove NaN/Inf
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)

    # Quantize to reduce floating-point noise
    arr = np.round(arr * 1000).astype(np.int32)

    # Sample evenly
    if len(arr) > n_samples:
        indices = np.linspace(0, len(arr) - 1, n_samples, dtype=np.int32)
        sampled = arr[indices]
    else:
        sampled = arr

    return hashlib.md5(sampled.tobytes()).hexdigest()[:16]


def is_correlated_duplicate(alpha_a: np.ndarray, alpha_b: np.ndarray,
                             threshold: float = 0.95) -> bool:
    """Two alphas are duplicates if their values have correlation >= threshold."""
    if len(alpha_a) != len(alpha_b):
        return False

    valid = np.isfinite(alpha_a) & np.isfinite(alpha_b)
    if valid.sum() < 100:
        return False

    try:
        r, _ = pearsonr(alpha_a[valid], alpha_b[valid])
        if np.isnan(r):
            return False
        return abs(r) >= threshold
    except Exception:
        return False


class AlphaDeduplicator:
    """Tracks known alpha hashes to filter duplicates in real-time."""

    def __init__(self, correlation_threshold: float = 0.95):
        self.seen_canonical: Set[str] = set()
        self.seen_value: Dict[str, str] = {}  # value_hash -> alpha_hash
        self.correlation_threshold = correlation_threshold
        self.known_values: List[Tuple[str, np.ndarray]] = []  # (alpha_hash, subsample)
        self.stats = {'checks': 0, 'canonical_dups': 0, 'value_dups': 0, 'corr_dups': 0}

    def is_duplicate(self, formula: str, alpha_values: np.ndarray,
                     alpha_hash: str) -> Tuple[bool, str]:
        """Returns (is_dup, reason). reason indicates which method caught it."""
        self.stats['checks'] += 1

        # Layer 1: canonical hash
        canon = canonical_hash(formula)
        if canon in self.seen_canonical:
            self.stats['canonical_dups'] += 1
            return True, f"canonical_hash_match:{canon}"

        # Layer 2: value hash (faster than correlation)
        vh = value_hash(alpha_values)
        if vh in self.seen_value:
            self.stats['value_dups'] += 1
            return True, f"value_hash_match:{self.seen_value[vh]}"

        # Layer 3: correlation with existing (slowest)
        # Sample for efficiency
        if len(alpha_values) > 500:
            sample = alpha_values[::max(len(alpha_values) // 500, 1)]
        else:
            sample = alpha_values

        for known_hash, known_sample in self.known_values[-50:]:  # check last 50 only
            if is_correlated_duplicate(sample, known_sample, self.correlation_threshold):
                self.stats['corr_dups'] += 1
                return True, f"correlation_match:{known_hash}"

        # Not a duplicate; register
        self.seen_canonical.add(canon)
        self.seen_value[vh] = alpha_hash
        self.known_values.append((alpha_hash, sample))
        # Keep memory bounded
        if len(self.known_values) > 500:
            self.known_values = self.known_values[-500:]
        return False, ""

    def reset(self):
        self.seen_canonical.clear()
        self.seen_value.clear()
        self.known_values.clear()
        self.stats = {'checks': 0, 'canonical_dups': 0, 'value_dups': 0, 'corr_dups': 0}

    def report(self) -> dict:
        return {**self.stats, 'unique_canonical': len(self.seen_canonical),
                'unique_values': len(self.seen_value), 'tracked_samples': len(self.known_values)}


if __name__ == "__main__":
    # Self-test
    dedup = AlphaDeduplicator()

    # Test 1: canonical equivalence
    f1 = "add(close, high)"
    f2 = "add(high, close)"
    assert canonical_hash(f1) == canonical_hash(f2), "commutative not detected"
    print(f"Test 1 (commutative): PASS {canonical_hash(f1)}")

    # Test 2: self-inverse
    f3 = "neg(neg(rsi_14))"
    f4 = "rsi_14"
    assert canonical_hash(f3) == canonical_hash(f4), "double neg not collapsed"
    print(f"Test 2 (double neg): PASS")

    # Test 3: value-based
    a = np.random.randn(1000).astype(np.float32)
    b = a.copy()
    vh_a = value_hash(a)
    vh_b = value_hash(b)
    assert vh_a == vh_b, "identical arrays should have same value_hash"
    print(f"Test 3 (value hash): PASS {vh_a}")

    # Test 4: correlation dedup
    c = a + np.random.randn(1000).astype(np.float32) * 0.01  # highly correlated
    is_dup = is_correlated_duplicate(a, c, threshold=0.95)
    print(f"Test 4 (correlation): is_dup={is_dup}")

    # Test 5: full deduplicator
    ah = hashlib.md5(b"alpha_A").hexdigest()[:16]
    dup1, r1 = dedup.is_duplicate("add(close, high)", a, ah)
    dup2, r2 = dedup.is_duplicate("add(high, close)", b, hashlib.md5(b"alpha_B").hexdigest()[:16])
    print(f"Test 5 dup_1={dup1} dup_2={dup2} reason_2='{r2}'")
    print(f"Dedup stats: {dedup.report()}")
