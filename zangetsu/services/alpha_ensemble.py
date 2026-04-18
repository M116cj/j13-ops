"""V10 Alpha Ensemble — combine top low-correlation alphas into unified signal.

Usage:
    ensemble = AlphaEnsemble(zoo, method='ic_weighted')
    await ensemble.build(regime='BULL_TREND', top_k=20, max_jaccard=0.3)
    signal = ensemble.evaluate(ohlcv, indicator_cache)
"""
import numpy as np
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class EnsembleMember:
    alpha_hash: str
    formula: str
    ast_json: list
    ic: float
    weight: float


class AlphaEnsemble:
    """Weighted combination of diverse alpha expressions."""
    
    METHODS = ('ic_weighted', 'equal', 'inverse_variance', 'rank_weighted')
    
    def __init__(self, zoo, method: str = 'ic_weighted', regime: Optional[str] = None):
        self.zoo = zoo
        self.method = method if method in self.METHODS else 'ic_weighted'
        self.regime = regime
        self.members: List[EnsembleMember] = []
    
    async def build(self, top_k: int = 20, ic_min: float = 0.02, max_jaccard: float = 0.3):
        """Select top-k uncorrelated alphas from factor zoo."""
        candidates = await self.zoo.query(
            regime=self.regime, ic_min=ic_min, n_results=top_k * 5
        )
        if not candidates:
            log.warning(f"No alpha candidates for regime={self.regime}")
            return
        
        # Greedy diversification by Jaccard similarity
        selected = await self.zoo.diversify_select(
            candidates, top_k=top_k, max_jaccard=max_jaccard
        )
        
        # Compute weights
        if self.method == 'equal':
            weights = np.ones(len(selected)) / max(len(selected), 1)
        elif self.method == 'ic_weighted':
            ics = np.array([abs(s.ic) for s in selected])
            total = ics.sum()
            weights = ics / total if total > 0 else np.ones(len(selected)) / len(selected)
        elif self.method == 'inverse_variance':
            # Use 1/ic_pvalue as proxy for inverse variance
            variances = np.array([max(s.ic_pvalue, 1e-6) for s in selected])
            inv_var = 1.0 / variances
            weights = inv_var / inv_var.sum()
        elif self.method == 'rank_weighted':
            # Rank-based weights: rank 1 gets highest weight
            ranks = np.arange(len(selected), 0, -1)
            weights = ranks / ranks.sum()
        
        self.members = [
            EnsembleMember(
                alpha_hash=s.alpha_hash,
                formula=s.formula,
                ast_json=s.ast_json,
                ic=s.ic,
                weight=float(weights[i])
            )
            for i, s in enumerate(selected)
        ]
        log.info(f"Ensemble built: {len(self.members)} alphas, method={self.method}, regime={self.regime}")
    
    def evaluate(self, close, high, low, open_arr, volume, indicator_cache: dict = None) -> np.ndarray:
        """Compute ensemble signal values by weighted sum of individual alpha outputs."""
        if not self.members:
            return np.zeros_like(close, dtype=np.float32)
        
        from zangetsu.engine.components.alpha_engine import AlphaEngine
        from deap import gp
        
        engine = AlphaEngine(indicator_cache=indicator_cache or {})
        
        n = len(close)
        ensemble_values = np.zeros(n, dtype=np.float32)
        total_weight = 0.0
        n_failed_members = 0
        
        for member in self.members:
            try:
                tree = gp.PrimitiveTree.from_string(member.formula, engine.pset)
                func = engine.toolbox.compile(expr=tree)
                alpha_vals = func(close, high, low, open_arr, volume)
                alpha_vals = np.nan_to_num(alpha_vals, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
                
                # Standardize to [-1, +1] via rolling rank or tanh
                alpha_std = _rolling_zscore(alpha_vals, window=500)
                alpha_bounded = np.tanh(alpha_std).astype(np.float32)
                
                ensemble_values += member.weight * alpha_bounded
                total_weight += member.weight
            except (KeyError, ValueError, TypeError, AttributeError) as e:
                n_failed_members += 1
                log.warning(
                    "AlphaEnsemble member %s eval failed: %s: %s",
                    member.alpha_hash, type(e).__name__, e,
                )
                continue
        if n_failed_members:
            log.warning(
                "AlphaEnsemble.evaluate: %d/%d members failed (regime=%s, method=%s)",
                n_failed_members, len(self.members), self.regime, self.method,
            )
        
        if total_weight > 0:
            ensemble_values /= total_weight
        
        return np.clip(ensemble_values, -1.0, 1.0)
    
    def to_dict(self) -> dict:
        return {
            'method': self.method,
            'regime': self.regime,
            'n_members': len(self.members),
            'members': [
                {'hash': m.alpha_hash, 'ic': m.ic, 'weight': m.weight}
                for m in self.members
            ]
        }


def _rolling_zscore(x, window=500):
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    for i in range(window, n):
        w = x[i-window:i]
        m = np.mean(w)
        s = np.std(w)
        if s > 1e-10:
            out[i] = (x[i] - m) / s
    return out
