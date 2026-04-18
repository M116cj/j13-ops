"""V10 Alpha Engine — Genetic Programming for alpha expression discovery.

Evolves mathematical expressions combining:
- Raw OHLCV (close, high, low, open, volume)
- 21 technical indicators x 6 periods = 126 cached arrays
- WorldQuant-style operators from alpha_primitives

Search modes:
- evolve(): DEAP GP with tournament selection
- sample_random(): Pure random AST generation
- hybrid(): Random bootstrap + GP refinement

V2 Design Notes:
- Indicator terminals are zero-arity closures reading from self.indicator_cache
- Array length auto-aligns (ops shaped relative to the 5 OHLCV args)
- Graceful fallback when alpha_primitives is not yet available (parallel build)
- Complexity penalty prevents GP bloat
- Hall-of-Fame preserves top-K across generations
"""

from __future__ import annotations

import hashlib
import logging
import random
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

log = logging.getLogger(__name__)

try:
    from deap import algorithms, base, creator, gp, tools
    HAS_DEAP = True
except ImportError:
    HAS_DEAP = False
    log.warning("DEAP not installed; AlphaEngine will be unusable")

# Import primitives (graceful fallback — Agent 2a may not be done yet)
try:
    from zangetsu.engine.components import alpha_primitives as prims  # type: ignore
    HAS_PRIMS = True
except Exception:  # noqa: BLE001
    HAS_PRIMS = False
    prims = None  # type: ignore
    log.warning("alpha_primitives not available; using internal fallback primitives")


# ---------------------------------------------------------------------------
# Internal fallback primitives (used only when alpha_primitives module absent)
# ---------------------------------------------------------------------------

class _FallbackPrims:
    """Minimal safe numpy-only primitives used when alpha_primitives is missing."""

    @staticmethod
    def _as_array(x: Any) -> np.ndarray:
        if isinstance(x, np.ndarray):
            return x.astype(np.float32, copy=False)
        return np.asarray(x, dtype=np.float32)

    @staticmethod
    def _align(a: np.ndarray, b: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        if a.shape == b.shape:
            return a, b
        n = min(a.size, b.size)
        if n == 0:
            return a, b
        return a[-n:], b[-n:]

    @classmethod
    def add(cls, a: Any, b: Any) -> np.ndarray:
        a, b = cls._align(cls._as_array(a), cls._as_array(b))
        return a + b

    @classmethod
    def sub(cls, a: Any, b: Any) -> np.ndarray:
        a, b = cls._align(cls._as_array(a), cls._as_array(b))
        return a - b

    @classmethod
    def mul(cls, a: Any, b: Any) -> np.ndarray:
        a, b = cls._align(cls._as_array(a), cls._as_array(b))
        return a * b

    @classmethod
    def protected_div(cls, a: Any, b: Any) -> np.ndarray:
        a, b = cls._align(cls._as_array(a), cls._as_array(b))
        safe = np.where(np.abs(b) < 1e-10, 1e-10, b)
        return a / safe

    @classmethod
    def neg(cls, a: Any) -> np.ndarray:
        return -cls._as_array(a)

    @classmethod
    def abs_x(cls, a: Any) -> np.ndarray:
        return np.abs(cls._as_array(a))

    @classmethod
    def sign_x(cls, a: Any) -> np.ndarray:
        return np.sign(cls._as_array(a)).astype(np.float32)

    @classmethod
    def tanh_x(cls, a: Any) -> np.ndarray:
        return np.tanh(cls._as_array(a)).astype(np.float32)

    @classmethod
    def power(cls, a: Any, p: int) -> np.ndarray:
        arr = cls._as_array(a)
        clipped = np.clip(arr, -1e6, 1e6)
        return np.power(clipped, int(p)).astype(np.float32)

    @classmethod
    def delta(cls, a: Any, d: int) -> np.ndarray:
        arr = cls._as_array(a)
        d = max(1, int(d))
        out = np.zeros_like(arr)
        if arr.size > d:
            out[d:] = arr[d:] - arr[:-d]
        return out

    @classmethod
    def ts_max(cls, a: Any, d: int) -> np.ndarray:
        arr = cls._as_array(a)
        d = max(1, int(d))
        n = arr.size
        out = np.zeros_like(arr)
        for i in range(n):
            lo = max(0, i - d + 1)
            out[i] = np.max(arr[lo : i + 1])
        return out

    @classmethod
    def ts_min(cls, a: Any, d: int) -> np.ndarray:
        arr = cls._as_array(a)
        d = max(1, int(d))
        n = arr.size
        out = np.zeros_like(arr)
        for i in range(n):
            lo = max(0, i - d + 1)
            out[i] = np.min(arr[lo : i + 1])
        return out

    @classmethod
    def ts_rank(cls, a: Any, d: int) -> np.ndarray:
        arr = cls._as_array(a)
        d = max(1, int(d))
        n = arr.size
        out = np.zeros(n, dtype=np.float32)
        for i in range(n):
            lo = max(0, i - d + 1)
            window = arr[lo : i + 1]
            rank = int((window <= arr[i]).sum()) - 1
            out[i] = rank / max(1, window.size - 1)
        return out

    @classmethod
    def correlation(cls, a: Any, b: Any, d: int) -> np.ndarray:
        a, b = cls._align(cls._as_array(a), cls._as_array(b))
        d = max(2, int(d))
        n = a.size
        out = np.zeros(n, dtype=np.float32)
        for i in range(n):
            lo = max(0, i - d + 1)
            wa, wb = a[lo : i + 1], b[lo : i + 1]
            if wa.size < 2:
                continue
            sa, sb = float(wa.std()), float(wb.std())
            if sa < 1e-10 or sb < 1e-10:
                continue
            out[i] = float(((wa - wa.mean()) * (wb - wb.mean())).mean() / (sa * sb))
        return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)

    @classmethod
    def decay_linear(cls, a: Any, d: int) -> np.ndarray:
        arr = cls._as_array(a)
        d = max(1, int(d))
        weights = np.arange(1, d + 1, dtype=np.float32)
        weights /= weights.sum()
        n = arr.size
        out = np.zeros(n, dtype=np.float32)
        for i in range(n):
            lo = max(0, i - d + 1)
            w = arr[lo : i + 1]
            ww = weights[-w.size :]
            denom = float(ww.sum())
            if denom < 1e-10:
                continue
            out[i] = float((w * ww).sum() / denom)
        return out

    @classmethod
    def scale(cls, a: Any) -> np.ndarray:
        arr = cls._as_array(a)
        denom = float(np.abs(arr).sum())
        if denom < 1e-10:
            return np.zeros_like(arr)
        return arr / denom


if not HAS_PRIMS:
    prims = _FallbackPrims  # type: ignore


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class AlphaResult:
    """Full metadata for a discovered alpha expression."""

    formula: str
    ast_json: List[Any]
    alpha_hash: str
    depth: int
    node_count: int
    used_indicators: List[str] = field(default_factory=list)
    used_operators: List[str] = field(default_factory=list)
    ic: float = 0.0
    ic_pvalue: float = 1.0
    dsr: float = 0.0
    stability: float = 0.0
    generation: int = 0
    parent_hash: Optional[str] = None

    @property
    def hash(self) -> str:  # noqa: A003 - legacy name
        """Backward-compat alias for .alpha_hash (arena_pipeline, signal_reconstructor)."""
        return self.alpha_hash

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "AlphaResult":
        allowed = {
            "formula", "ast_json", "alpha_hash", "depth", "node_count",
            "used_indicators", "used_operators", "ic", "ic_pvalue", "dsr",
            "stability", "generation", "parent_hash",
        }
        return cls(**{k: v for k, v in d.items() if k in allowed})

    def to_passport(self) -> dict:
        """Project for passport.alpha_expression field."""
        return {
            "formula": self.formula,
            "ast_json": self.ast_json,
            "alpha_hash": self.alpha_hash,
            "depth": self.depth,
            "node_count": self.node_count,
            "used_indicators": list(self.used_indicators),
            "used_operators": list(self.used_operators),
            "ic": float(self.ic),
            "ic_pvalue": float(self.ic_pvalue),
            "dsr": float(self.dsr),
            "stability": float(self.stability),
            "generation": int(self.generation),
            "parent_hash": self.parent_hash,
        }


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INDICATOR_NAMES: List[str] = [
    "rsi", "stochastic_k", "cci", "roc", "ppo", "cmo",
    "zscore", "trix", "tsi", "obv", "mfi", "vwap",
    "normalized_atr", "realized_vol", "bollinger_bw",
    "relative_volume", "vwap_deviation",
    "funding_rate", "funding_zscore", "oi_change", "oi_divergence",
]
PERIODS: List[int] = [7, 14, 20, 30, 50, 100]

OHLCV_ARGS: Tuple[str, ...] = ("close", "high", "low", "open", "volume")


# ---------------------------------------------------------------------------
# AlphaEngine
# ---------------------------------------------------------------------------

class AlphaEngine:
    """V10 GP Alpha Engine.

    Registers 131+ primitives (5 OHLCV + 126 indicators + ~25 operators)
    into a DEAP PrimitiveSet and runs tournament-selection evolution.

    Parameters
    ----------
    indicator_cache : dict[str, np.ndarray] | None
        Precomputed indicator arrays keyed as "<name>_<period>" (e.g. rsi_14).
        Built upstream by indicator_bridge **once per symbol at startup** (not
        per discovery cycle). Per-cycle rebuilds would be wasted work: indicator
        values for a fixed OHLCV window are deterministic, so cache invalidation
        is driven by new bar ingress, not by GP evolution passes.
    seed : int | None
        RNG seed for reproducibility.
    """

    MAX_DEPTH: int = 6
    MIN_DEPTH: int = 2

    def __init__(
        self,
        indicator_cache: Optional[Dict[str, np.ndarray]] = None,
        seed: Optional[int] = None,
    ) -> None:
        if not HAS_DEAP:
            raise ImportError("DEAP is required for AlphaEngine; pip install deap")
        if seed is not None:
            random.seed(int(seed))
            np.random.seed(int(seed))
        self.indicator_cache: Dict[str, np.ndarray] = dict(indicator_cache or {})
        self.pset: Any = None
        self.toolbox: Any = None
        self._indicator_terminal_names: List[str] = []
        self._operator_names: List[str] = []
        self._build_primitive_set()

    # ------------------------------------------------------------------
    # Primitive registration
    # ------------------------------------------------------------------

    def _build_primitive_set(self) -> None:
        pset = gp.PrimitiveSet("ALPHA", len(OHLCV_ARGS))
        pset.renameArguments(
            ARG0="close", ARG1="high", ARG2="low", ARG3="open", ARG4="volume"
        )

        # 126 indicator terminals bound to cache via closure.
        indicator_terminal_names: List[str] = []
        for ind in INDICATOR_NAMES:
            for period in PERIODS:
                term_name = f"{ind}_{period}"
                indicator_terminal_names.append(term_name)

                def _make_terminal(name: str) -> Callable[[], np.ndarray]:
                    def _fn() -> np.ndarray:
                        arr = self.indicator_cache.get(name)
                        if arr is None:
                            return np.zeros(1, dtype=np.float32)
                        return arr
                    _fn.__name__ = name
                    return _fn

                try:
                    pset.addTerminal(_make_terminal(term_name), name=term_name)
                except (TypeError, ValueError) as e:  # pragma: no cover
                    log.debug("skip terminal %s: %s", term_name, e)

        self._indicator_terminal_names = indicator_terminal_names

        # Binary arithmetic
        operator_names: List[str] = []
        pset.addPrimitive(prims.add, 2, name="add")
        pset.addPrimitive(prims.sub, 2, name="sub")
        pset.addPrimitive(prims.mul, 2, name="mul")
        pset.addPrimitive(prims.protected_div, 2, name="protected_div")
        operator_names.extend(["add", "sub", "mul", "protected_div"])

        # Unary math
        pset.addPrimitive(prims.neg, 1, name="neg")
        pset.addPrimitive(prims.abs_x, 1, name="abs_x")
        pset.addPrimitive(prims.sign_x, 1, name="sign_x")
        pset.addPrimitive(prims.tanh_x, 1, name="tanh_x")
        operator_names.extend(["neg", "abs_x", "sign_x", "tanh_x"])

        # Parametric power
        def _pow2(x: Any) -> np.ndarray:
            return prims.power(x, 2)

        def _pow3(x: Any) -> np.ndarray:
            return prims.power(x, 3)

        def _pow5(x: Any) -> np.ndarray:
            return prims.power(x, 5)

        pset.addPrimitive(_pow2, 1, name="pow2")
        pset.addPrimitive(_pow3, 1, name="pow3")
        pset.addPrimitive(_pow5, 1, name="pow5")
        operator_names.extend(["pow2", "pow3", "pow5"])

        # Time-series with fixed periods
        for d in (3, 5, 9, 20):
            pset.addPrimitive(
                (lambda x, dd=d: prims.delta(x, dd)), 1, name=f"delta_{d}"
            )
            pset.addPrimitive(
                (lambda x, dd=d: prims.ts_max(x, dd)), 1, name=f"ts_max_{d}"
            )
            pset.addPrimitive(
                (lambda x, dd=d: prims.ts_min(x, dd)), 1, name=f"ts_min_{d}"
            )
            pset.addPrimitive(
                (lambda x, dd=d: prims.ts_rank(x, dd)), 1, name=f"ts_rank_{d}"
            )
            pset.addPrimitive(
                (lambda x, dd=d: prims.decay_linear(x, dd)), 1, name=f"decay_{d}"
            )
            operator_names.extend([
                f"delta_{d}", f"ts_max_{d}", f"ts_min_{d}",
                f"ts_rank_{d}", f"decay_{d}",
            ])

        # Binary correlation at fixed periods
        for d in (5, 10, 20):
            pset.addPrimitive(
                (lambda a, b, dd=d: prims.correlation(a, b, dd)),
                2, name=f"correlation_{d}",
            )
            operator_names.append(f"correlation_{d}")

        pset.addPrimitive(prims.scale, 1, name="scale")
        operator_names.append("scale")

        self._operator_names = operator_names

        # DEAP types (once per process)
        if not hasattr(creator, "FitnessMax"):
            creator.create("FitnessMax", base.Fitness, weights=(1.0,))
        if not hasattr(creator, "Individual"):
            creator.create(
                "Individual", gp.PrimitiveTree, fitness=creator.FitnessMax
            )

        self.pset = pset
        self.toolbox = base.Toolbox()
        self.toolbox.register(
            "expr", gp.genHalfAndHalf, pset=pset,
            min_=self.MIN_DEPTH, max_=4,
        )
        self.toolbox.register(
            "individual", tools.initIterate, creator.Individual, self.toolbox.expr
        )
        self.toolbox.register(
            "population", tools.initRepeat, list, self.toolbox.individual
        )
        self.toolbox.register("compile", gp.compile, pset=pset)
        self.toolbox.register("select", tools.selTournament, tournsize=3)
        self.toolbox.register("mate", gp.cxOnePoint)
        self.toolbox.register(
            "expr_mut", gp.genHalfAndHalf, pset=pset, min_=0, max_=2
        )
        self.toolbox.register(
            "mutate", gp.mutUniform, expr=self.toolbox.expr_mut, pset=pset
        )
        self.toolbox.decorate(
            "mate", gp.staticLimit(lambda ind: ind.height, self.MAX_DEPTH)
        )
        self.toolbox.decorate(
            "mutate", gp.staticLimit(lambda ind: ind.height, self.MAX_DEPTH)
        )

        log.info(
            "AlphaEngine ready: %d indicator terminals, %d operators, has_prims=%s",
            len(indicator_terminal_names), len(operator_names), HAS_PRIMS,
        )

    # ------------------------------------------------------------------
    # Fitness helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_ic(
        alpha_values: np.ndarray, forward_returns: np.ndarray
    ) -> Tuple[float, float]:
        """Spearman rank correlation between alpha and forward returns."""
        try:
            from scipy.stats import spearmanr
        except ImportError:  # pragma: no cover
            return 0.0, 1.0

        a = np.asarray(alpha_values, dtype=np.float64)
        b = np.asarray(forward_returns, dtype=np.float64)
        if a.shape != b.shape:
            n = min(a.size, b.size)
            if n < 2:
                return 0.0, 1.0
            a, b = a[-n:], b[-n:]
        valid = ~(np.isnan(a) | np.isnan(b) | np.isinf(a) | np.isinf(b))
        if int(valid.sum()) < 100:
            return 0.0, 1.0
        corr, pval = spearmanr(a[valid], b[valid])
        ic = 0.0 if corr is None or np.isnan(corr) else float(corr)
        pv = 1.0 if pval is None or np.isnan(pval) else float(pval)
        return ic, pv

    @staticmethod
    def _broadcast_alpha(alpha: Any, target_len: int) -> Optional[np.ndarray]:
        """Coerce primitive output to np.ndarray aligned to target_len."""
        if isinstance(alpha, (int, float, np.floating, np.integer)):
            return np.full(target_len, float(alpha), dtype=np.float32)
        if not isinstance(alpha, np.ndarray):
            try:
                alpha = np.asarray(alpha, dtype=np.float32)
            except Exception:  # noqa: BLE001
                return None
        if alpha.ndim != 1:
            try:
                alpha = alpha.reshape(-1)
            except Exception:  # noqa: BLE001
                return None
        if alpha.size == target_len:
            return alpha.astype(np.float32, copy=False)
        if alpha.size == 1:
            return np.full(target_len, float(alpha.item()), dtype=np.float32)
        out = np.zeros(target_len, dtype=np.float32)
        n = min(alpha.size, target_len)
        out[-n:] = alpha[-n:].astype(np.float32, copy=False)
        return out

    def _evaluate(
        self,
        individual: Any,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        open_arr: np.ndarray,
        volume: np.ndarray,
        forward_returns: np.ndarray,
    ) -> Tuple[float]:
        """Evaluate an alpha tree. Returns (fitness,) for DEAP."""
        try:
            func = self.toolbox.compile(expr=individual)
            raw = func(close, high, low, open_arr, volume)
            alpha = self._broadcast_alpha(raw, len(close))
            if alpha is None:
                return (0.0,)
            alpha = np.nan_to_num(
                alpha, nan=0.0, posinf=0.0, neginf=0.0
            ).astype(np.float32)
            if float(np.std(alpha)) < 1e-10:
                return (0.0,)
            ic, _ = self._compute_ic(alpha, forward_returns)
            penalty = 0.001 * float(individual.height)
            return (abs(ic) - penalty,)
        except Exception as e:  # noqa: BLE001
            log.debug("evaluate failed: %s", e)
            return (0.0,)

    # ------------------------------------------------------------------
    # Search strategies
    # ------------------------------------------------------------------

    @staticmethod
    def _forward_returns(close: np.ndarray) -> np.ndarray:
        fr = np.zeros_like(close, dtype=np.float32)
        if close.size > 1:
            denom = np.maximum(close[:-1], 1e-10)
            fr[:-1] = ((close[1:] - close[:-1]) / denom).astype(np.float32)
        return fr

    def evolve(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        volume: np.ndarray,
        returns: Optional[np.ndarray] = None,
        *,
        open_arr: Optional[np.ndarray] = None,
        n_gen: int = 30,
        pop_size: int = 200,
        top_k: int = 20,
    ) -> List[AlphaResult]:
        """Run DEAP GP evolution; return top top_k alphas by |IC|.

        Signature accepts the legacy (close, high, low, volume, returns) positional
        form used by arena_pipeline / alpha_discovery. The `returns` positional is
        retained for API compatibility but forward returns are recomputed from close
        internally (guarantees alignment with IC evaluation).

        `open_arr` is keyword-only and falls back to close when omitted (adequate
        approximation for bar data where open ≈ prior close).
        """
        if open_arr is None:
            open_arr = close.copy()
        # `returns` positional retained for backward-compat; forward returns always
        # derived from close for IC consistency.
        _ = returns
        forward_returns = self._forward_returns(close)

        self.toolbox.register(
            "evaluate", self._evaluate,
            close=close, high=high, low=low, open_arr=open_arr,
            volume=volume, forward_returns=forward_returns,
        )

        pop = self.toolbox.population(n=int(pop_size))
        hof = tools.HallOfFame(int(top_k))

        try:
            pop, _logbook = algorithms.eaSimple(
                pop, self.toolbox,
                cxpb=0.5, mutpb=0.2, ngen=int(n_gen),
                halloffame=hof, verbose=False,
            )
        except Exception as e:  # noqa: BLE001
            log.error("GP evolution crashed: %s", e)
            return []

        results: List[AlphaResult] = []
        for ind in hof:
            results.append(
                self._individual_to_result(
                    ind,
                    close=close, high=high, low=low, open_arr=open_arr,
                    volume=volume, forward_returns=forward_returns,
                    generation=int(n_gen),
                )
            )
        results.sort(key=lambda r: abs(r.ic), reverse=True)
        return results

    def sample_random(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        open_arr: np.ndarray,
        volume: np.ndarray,
        n_samples: int = 500,
        top_k: int = 20,
        min_abs_ic: float = 0.005,
    ) -> List[AlphaResult]:
        """Pure random AST sampling — no selection pressure."""
        forward_returns = self._forward_returns(close)

        results: List[AlphaResult] = []
        for _ in range(int(n_samples)):
            try:
                ind = self.toolbox.individual()
            except Exception as e:  # noqa: BLE001
                log.debug("random individual gen failed: %s", e)
                continue
            try:
                func = self.toolbox.compile(expr=ind)
                raw = func(close, high, low, open_arr, volume)
                alpha = self._broadcast_alpha(raw, len(close))
                if alpha is None:
                    continue
                alpha = np.nan_to_num(
                    alpha, nan=0.0, posinf=0.0, neginf=0.0
                ).astype(np.float32)
                if float(np.std(alpha)) < 1e-10:
                    continue
                ic, pval = self._compute_ic(alpha, forward_returns)
                if abs(ic) < min_abs_ic:
                    continue
                results.append(
                    self._individual_to_result(
                        ind,
                        close=close, high=high, low=low, open_arr=open_arr,
                        volume=volume, forward_returns=forward_returns,
                        generation=0,
                        _precomputed=(ic, pval),
                    )
                )
            except Exception as e:  # noqa: BLE001
                log.debug("random sample eval failed: %s", e)

        results.sort(key=lambda r: abs(r.ic), reverse=True)
        return results[: int(top_k)]

    def hybrid(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        open_arr: np.ndarray,
        volume: np.ndarray,
        random_samples: int = 200,
        n_gen: int = 20,
        pop_size: int = 100,
        top_k: int = 20,
    ) -> List[AlphaResult]:
        """Random bootstrap + GP refinement. Merges & dedupes by hash."""
        random_alphas = self.sample_random(
            close, high, low, open_arr, volume,
            n_samples=int(random_samples), top_k=int(pop_size),
        )
        evolved = self.evolve(
            close, high, low, open_arr, volume,
            n_gen=int(n_gen), pop_size=int(pop_size), top_k=int(top_k),
        )
        seen: Dict[str, AlphaResult] = {}
        for r in list(random_alphas) + list(evolved):
            prev = seen.get(r.alpha_hash)
            if prev is None or abs(r.ic) > abs(prev.ic):
                seen[r.alpha_hash] = r
        merged = list(seen.values())
        merged.sort(key=lambda r: abs(r.ic), reverse=True)
        return merged[: int(top_k)]

    # ------------------------------------------------------------------
    # Result construction
    # ------------------------------------------------------------------

    def _individual_to_result(
        self,
        ind: Any,
        *,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        open_arr: np.ndarray,
        volume: np.ndarray,
        forward_returns: np.ndarray,
        generation: int,
        _precomputed: Optional[Tuple[float, float]] = None,
    ) -> AlphaResult:
        formula = str(ind)
        alpha_hash = hashlib.md5(formula.encode("utf-8")).hexdigest()[:16]
        if _precomputed is not None:
            ic, pval = _precomputed
        else:
            try:
                func = self.toolbox.compile(expr=ind)
                raw = func(close, high, low, open_arr, volume)
                alpha = self._broadcast_alpha(raw, len(close))
                if alpha is None:
                    ic, pval = 0.0, 1.0
                else:
                    alpha = np.nan_to_num(
                        alpha, nan=0.0, posinf=0.0, neginf=0.0
                    ).astype(np.float32)
                    ic, pval = self._compute_ic(alpha, forward_returns)
            except Exception as e:  # noqa: BLE001
                log.debug("post-hoc eval failed: %s", e)
                ic, pval = 0.0, 1.0

        used_indicators = [
            n for n in self._indicator_terminal_names if n in formula
        ]
        used_operators = sorted({
            n for n in self._operator_names if n in formula
        })

        return AlphaResult(
            formula=formula,
            ast_json=self._tree_to_ast_json(ind),
            alpha_hash=alpha_hash,
            depth=int(ind.height),
            node_count=int(len(ind)),
            used_indicators=used_indicators,
            used_operators=list(used_operators),
            ic=float(ic),
            ic_pvalue=float(pval),
            generation=int(generation),
        )

    # ------------------------------------------------------------------
    # AST (de)serialisation
    # ------------------------------------------------------------------

    def _tree_to_ast_json(self, ind: Any) -> List[Any]:
        """Serialise DEAP tree to a JSON-safe list of {name, arity} nodes."""
        try:
            nodes: List[Dict[str, Any]] = []
            for node in ind:
                nodes.append({
                    "name": getattr(node, "name", str(node)),
                    "arity": int(getattr(node, "arity", 0)),
                })
            return nodes
        except Exception as e:  # noqa: BLE001
            log.debug("ast serialise failed: %s", e)
            return [str(ind)]

    def compile_ast(self, ast_json: List[Any]) -> Callable[..., np.ndarray]:
        """Compile a stored AST back to a callable f(close, high, low, open, volume).

        Accepts either the node-list format from _tree_to_ast_json or
        a single-element [formula_str] fallback.
        """
        if not ast_json:
            raise ValueError("empty ast_json")
        if len(ast_json) == 1 and isinstance(ast_json[0], str):
            tree = gp.PrimitiveTree.from_string(ast_json[0], self.pset)
            return self.toolbox.compile(expr=tree)

        prim_by_name: Dict[str, Any] = {}
        term_by_name: Dict[str, Any] = {}
        for prim_list in self.pset.primitives.values():
            for p in prim_list:
                prim_by_name[p.name] = p
        for term_list in self.pset.terminals.values():
            for t in term_list:
                term_by_name[getattr(t, "name", str(t))] = t

        rebuilt: List[Any] = []
        for node in ast_json:
            if not isinstance(node, dict):
                raise ValueError(f"bad ast node: {node!r}")
            name = node.get("name")
            arity = int(node.get("arity", 0))
            if arity > 0:
                if name not in prim_by_name:
                    raise ValueError(f"unknown primitive: {name}")
                rebuilt.append(prim_by_name[name])
            else:
                if name not in term_by_name:
                    raise ValueError(f"unknown terminal: {name}")
                rebuilt.append(term_by_name[name])

        tree = gp.PrimitiveTree(rebuilt)
        return self.toolbox.compile(expr=tree)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def _all_indicator_names(self) -> List[str]:
        return list(self._indicator_terminal_names)

    def _all_operator_names(self) -> List[str]:
        return list(self._operator_names)

    def primitive_count(self) -> int:
        """Return total count of registered primitives + terminals."""
        return (
            len(self._indicator_terminal_names)
            + len(self._operator_names)
            + len(OHLCV_ARGS)
        )


__all__ = ["AlphaEngine", "AlphaResult", "INDICATOR_NAMES", "PERIODS"]
