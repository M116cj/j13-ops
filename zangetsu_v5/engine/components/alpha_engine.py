"""V9 GP Alpha Expression Engine — Genetic Programming for alpha factor discovery.

Evolves mathematical expressions from OHLCV + indicator primitives.
Produces alpha formulas like: tanh((close/EMA(close,20) - 1) * sign(RSI(14) - 50))

Usage:
    from engine.components.alpha_engine import AlphaEngine
    engine = AlphaEngine()
    best_alphas = engine.evolve(close, high, low, volume, returns, n_gen=50, pop_size=200)
    for alpha in best_alphas:
        print(alpha.formula, alpha.ic, alpha.sharpe)
"""
import numpy as np
import hashlib
import json
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

try:
    from deap import gp, base, creator, tools, algorithms
    HAS_DEAP = True
except ImportError:
    HAS_DEAP = False
    log.warning("DEAP not installed — GP alpha engine disabled")


# ═══════════════════════════════════════════════════════════════════
# Protected math primitives (no NaN/Inf)
# ═══════════════════════════════════════════════════════════════════

def _protected_div(a, b):
    with np.errstate(divide='ignore', invalid='ignore'):
        result = np.where(np.abs(b) > 1e-10, a / b, 0.0)
    return np.nan_to_num(result, nan=0.0, posinf=0.0, neginf=0.0)

def _protected_log(a):
    with np.errstate(divide='ignore', invalid='ignore'):
        result = np.where(a > 1e-10, np.log(a), 0.0)
    return np.nan_to_num(result, nan=0.0, posinf=0.0, neginf=0.0)

def _rolling_mean(a, window=20):
    result = np.empty_like(a)
    result[:window] = a[:window].mean()
    cs = np.cumsum(a)
    result[window:] = (cs[window:] - cs[:-window]) / window
    return result

def _rolling_std(a, window=20):
    result = np.empty_like(a)
    result[:window] = max(np.std(a[:window]), 1e-10)
    for i in range(window, len(a)):
        result[i] = max(np.std(a[i-window:i]), 1e-10)
    return result

def _ema(a, span=20):
    alpha = 2.0 / (span + 1)
    result = np.empty_like(a)
    result[0] = a[0]
    for i in range(1, len(a)):
        result[i] = alpha * a[i] + (1 - alpha) * result[i-1]
    return result

def _delay(a, d=1):
    result = np.empty_like(a)
    result[:d] = a[0]
    result[d:] = a[:-d]
    return result

def _delta(a, d=1):
    result = np.zeros_like(a)
    result[d:] = a[d:] - a[:-d]
    return result

def _ts_max(a, window=20):
    result = np.empty_like(a)
    for i in range(len(a)):
        start = max(0, i - window + 1)
        result[i] = np.max(a[start:i+1])
    return result

def _ts_min(a, window=20):
    result = np.empty_like(a)
    for i in range(len(a)):
        start = max(0, i - window + 1)
        result[i] = np.min(a[start:i+1])
    return result

def _rank(a):
    from scipy.stats import rankdata
    return rankdata(a) / len(a)

def _sign(a):
    return np.sign(a)

def _abs(a):
    return np.abs(a)

def _neg(a):
    return -a

def _tanh(a):
    return np.tanh(a)

def _clip(a):
    return np.clip(a, -1.0, 1.0)


# ═══════════════════════════════════════════════════════════════════
# Alpha data classes
# ═══════════════════════════════════════════════════════════════════

@dataclass
class AlphaResult:
    """A discovered alpha expression with its metrics."""
    formula: str                    # Human-readable formula string
    ast_json: list                  # Serializable AST
    ic: float = 0.0                # Information coefficient
    sharpe: float = 0.0            # Backtest Sharpe
    stability: float = 0.0         # IC stability across windows
    complexity: int = 0            # Tree depth
    hash: str = ""                 # Unique identifier
    generation: int = 0            # Which GP generation discovered this

    def to_passport_dict(self) -> dict:
        return {
            "formula": self.formula,
            "ast": self.ast_json,
            "ic": self.ic,
            "sharpe": self.sharpe,
            "stability": self.stability,
            "complexity": self.complexity,
            "hash": self.hash,
            "generation": self.generation,
        }


# ═══════════════════════════════════════════════════════════════════
# GP Alpha Engine
# ═══════════════════════════════════════════════════════════════════

class AlphaEngine:
    """Genetic Programming engine for evolving alpha expressions."""

    MAX_DEPTH = 6

    def __init__(self):
        if not HAS_DEAP:
            raise ImportError("DEAP required for AlphaEngine")
        self._setup_primitives()

    def _setup_primitives(self):
        """Define the GP primitive set."""
        # Input: 5 arrays (close, high, low, volume, returns)
        self.pset = gp.PrimitiveSet("ALPHA", 5)
        self.pset.renameArguments(
            ARG0="close", ARG1="high", ARG2="low", ARG3="volume", ARG4="returns"
        )

        # Arithmetic
        self.pset.addPrimitive(np.add, 2)
        self.pset.addPrimitive(np.subtract, 2)
        self.pset.addPrimitive(np.multiply, 2)
        self.pset.addPrimitive(_protected_div, 2)
        self.pset.addPrimitive(_neg, 1)
        self.pset.addPrimitive(_abs, 1)
        self.pset.addPrimitive(_sign, 1)
        self.pset.addPrimitive(_tanh, 1)
        self.pset.addPrimitive(_clip, 1)

        # Time-series
        self.pset.addPrimitive(_rolling_mean, 1)
        self.pset.addPrimitive(_rolling_std, 1)
        self.pset.addPrimitive(_ema, 1)
        self.pset.addPrimitive(_delay, 1)
        self.pset.addPrimitive(_delta, 1)
        self.pset.addPrimitive(_ts_max, 1)
        self.pset.addPrimitive(_ts_min, 1)
        self.pset.addPrimitive(_rank, 1)

        # Constants
        self.pset.addEphemeralConstant("const", lambda: np.full(1, np.random.choice([0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0])))

        # Setup DEAP types
        if not hasattr(creator, "FitnessMax"):
            creator.create("FitnessMax", base.Fitness, weights=(1.0,))
        if not hasattr(creator, "Individual"):
            creator.create("Individual", gp.PrimitiveTree, fitness=creator.FitnessMax)

        self.toolbox = base.Toolbox()
        self.toolbox.register("expr", gp.genHalfAndHalf, pset=self.pset, min_=1, max_=3)
        self.toolbox.register("individual", tools.initIterate, creator.Individual, self.toolbox.expr)
        self.toolbox.register("population", tools.initRepeat, list, self.toolbox.individual)
        self.toolbox.register("compile", gp.compile, pset=self.pset)
        self.toolbox.register("select", tools.selTournament, tournsize=3)
        self.toolbox.register("mate", gp.cxOnePoint)
        self.toolbox.register("mutate", gp.mutUniform, expr=self.toolbox.expr, pset=self.pset)

        # Bloat control
        self.toolbox.decorate("mate", gp.staticLimit(key=lambda ind: ind.height, max_value=self.MAX_DEPTH))
        self.toolbox.decorate("mutate", gp.staticLimit(key=lambda ind: ind.height, max_value=self.MAX_DEPTH))

    def _compute_ic(self, alpha_values: np.ndarray, forward_returns: np.ndarray) -> float:
        """Information Coefficient = rank correlation between alpha and forward returns."""
        from scipy.stats import spearmanr
        valid = ~(np.isnan(alpha_values) | np.isnan(forward_returns) |
                  np.isinf(alpha_values) | np.isinf(forward_returns))
        if valid.sum() < 50:
            return 0.0
        corr, _ = spearmanr(alpha_values[valid], forward_returns[valid])
        return float(corr) if not np.isnan(corr) else 0.0

    def _evaluate(self, individual, close, high, low, volume, returns, forward_returns):
        """Evaluate a GP individual. Returns (fitness,) tuple."""
        try:
            func = self.toolbox.compile(expr=individual)
            alpha = func(close, high, low, volume, returns)

            # Ensure valid output
            if not isinstance(alpha, np.ndarray):
                alpha = np.full_like(close, float(alpha) if np.isscalar(alpha) else 0.0)
            alpha = np.nan_to_num(alpha, nan=0.0, posinf=0.0, neginf=0.0)

            # IC as fitness
            ic = self._compute_ic(alpha, forward_returns)

            # Penalize constant outputs
            if np.std(alpha) < 1e-10:
                return (0.0,)

            return (abs(ic),)
        except Exception:
            return (0.0,)

    def evolve(self, close: np.ndarray, high: np.ndarray, low: np.ndarray,
               volume: np.ndarray, returns: np.ndarray,
               n_gen: int = 30, pop_size: int = 150,
               top_k: int = 10) -> List[AlphaResult]:
        """Run GP evolution and return top-k alpha expressions.

        Args:
            close/high/low/volume/returns: numpy arrays (train split)
            n_gen: number of generations
            pop_size: population size
            top_k: return this many best alphas

        Returns:
            List of AlphaResult, sorted by IC descending
        """
        # Forward returns for IC computation (1-bar forward)
        forward_returns = np.zeros_like(close)
        forward_returns[:-1] = (close[1:] - close[:-1]) / np.maximum(close[:-1], 1e-10)

        # Register evaluation
        self.toolbox.register("evaluate", self._evaluate,
                              close=close, high=high, low=low,
                              volume=volume, returns=returns,
                              forward_returns=forward_returns)

        # Initial population
        pop = self.toolbox.population(n=pop_size)
        hof = tools.HallOfFame(top_k)

        stats = tools.Statistics(lambda ind: ind.fitness.values)
        stats.register("avg", np.mean)
        stats.register("max", np.max)

        # Run evolution
        pop, logbook = algorithms.eaSimple(
            pop, self.toolbox,
            cxpb=0.5, mutpb=0.2,
            ngen=n_gen, halloffame=hof,
            stats=stats, verbose=False,
        )

        # Extract results
        results = []
        for ind in hof:
            formula = str(ind)
            alpha_hash = hashlib.md5(formula.encode()).hexdigest()[:12]

            # Compute alpha values for IC
            try:
                func = self.toolbox.compile(expr=ind)
                alpha_vals = func(close, high, low, volume, returns)
                alpha_vals = np.nan_to_num(alpha_vals, nan=0.0, posinf=0.0, neginf=0.0)
                ic = self._compute_ic(alpha_vals, forward_returns)
            except:
                ic = 0.0

            results.append(AlphaResult(
                formula=formula,
                ast_json=self._tree_to_json(ind),
                ic=ic,
                complexity=ind.height,
                hash=f"gp_{alpha_hash}",
                generation=n_gen,
            ))

        results.sort(key=lambda r: abs(r.ic), reverse=True)
        log.info(f"GP evolution: {n_gen} gen, pop={pop_size}, best IC={results[0].ic:.4f}" if results else "No results")
        return results

    def _tree_to_json(self, individual) -> list:
        """Convert DEAP tree to serializable JSON AST."""
        def _node_to_list(node_idx):
            node = individual[node_idx]
            if isinstance(node, gp.Terminal):
                return node.name if hasattr(node, 'name') else str(node.value)
            else:
                args = []
                child_idx = node_idx + 1
                for _ in range(node.arity):
                    args.append(_node_to_list(child_idx))
                    # Skip subtree
                    subtree_size = len(individual[child_idx:])
                    for j in range(child_idx + 1, len(individual)):
                        if isinstance(individual[j], gp.Primitive):
                            subtree_size = j - child_idx
                            break
                    child_idx += 1  # simplified traversal
                return [node.name] + args

        try:
            return _node_to_list(0)
        except:
            return [str(individual)]

    def compile_alpha(self, ast_json: list) -> callable:
        """Reconstruct a callable from stored AST JSON.
        For live deployment: alpha_fn(close, high, low, volume, returns) -> signal array.
        """
        # For now, use eval-based reconstruction from formula string
        # TODO: proper AST reconstruction
        raise NotImplementedError("Use evolve() output directly for now")
