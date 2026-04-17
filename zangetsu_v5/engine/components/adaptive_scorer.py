"""Adaptive family-level scoring for Zangetsu V5 Sharpe Quant doctrine.

Score_t(f) = ((Pi(s_i+eps)^w_i)^eta * (Sum w_i*s_i)^(1-eta)) - Penalty_t(f)

Sub-scores (all normalized to [0,1]):
1. win_rate_quality: holdout WR mapped to [0,1] via sigmoid around 0.55
2. unseen_pnl_quality: holdout PnL mapped to [0,1], 0 at breakeven, 1 at 5%+
3. wilson_readiness: wilson_lb / 0.50, capped at 1.0
4. train_holdout_retention: 1 - |train_wr - holdout_wr| / train_wr
5. segment_stability: 1 - variability (capped at 0)
6. trade_sufficiency: min(holdout_trades / 80, 1.0)
7. parameter_fragility: 1 - (a3_sharpe < 0) * 0.5 (penalize negative train sharpe)
8. novelty: 1.0 if unique family, 0.5 if has equivalents, 0.0 if duplicate

Penalties:
- duplicate_risk: 0 (already cleaned)
- equiv_signal_risk: 0.1 if indicators contain same-group pair
- context_mismatch: 0.1 if regime label doesn't match actual data regime
- overfit_risk: max(0, train_sharpe - holdout_sharpe) / 10 (penalize train >> holdout)
- regime_concentration: 0.05 per duplicate regime in candidate pool
"""
import math
from typing import Dict, List


def wilson_lb(wins: int, total: int, z: float = 1.96) -> float:
    """Wilson lower-bound confidence interval for win rate."""
    if total == 0:
        return 0.0
    p = wins / total
    d = 1 + z * z / total
    c = p + z * z / (2 * total)
    a = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return (c - a) / d


def sigmoid(x: float, center: float = 0.0, scale: float = 1.0) -> float:
    """Sigmoid mapping for normalizing metrics to [0,1]."""
    return 1.0 / (1.0 + math.exp(-(x - center) * scale))


class AdaptiveScorer:
    """Family-level adaptive scorer combining geometric + weighted-average blending."""

    def __init__(self):
        # Default weights (sum to 1.0)
        self.weights = {
            "win_rate": 0.20,
            "unseen_pnl": 0.15,
            "wilson_readiness": 0.20,
            "retention": 0.15,
            "stability": 0.10,
            "trade_sufficiency": 0.10,
            "fragility": 0.05,
            "novelty": 0.05,
        }
        self.eta = 0.3  # 30% geometric, 70% weighted average
        self.eps = 1e-6
        self.benchmark = 60.0  # cold start threshold
        self.benchmark_upper = 90.0

    def compute_subscores(self, family: Dict) -> Dict[str, float]:
        """Compute all 8 sub-scores normalized to [0,1]."""
        h_wr = family.get("holdout_wr", 0.5)
        h_pnl = family.get("holdout_pnl", 0.0)
        h_trades = family.get("holdout_trades", 0)
        h_sharpe = family.get("holdout_sharpe", 0.0)
        a3_sharpe = family.get("train_sharpe", 0.0)
        a1_wr = family.get("train_wr", 0.5)
        variability = family.get("variability", 1.0)
        is_unique = family.get("is_unique", True)

        return {
            "win_rate": sigmoid(h_wr, 0.55, 20),       # 0.55 WR -> 0.5 score, 0.65 -> 0.88
            "unseen_pnl": sigmoid(h_pnl, 0.02, 100),   # 2% PnL -> 0.5, 5% -> 0.95
            "wilson_readiness": min(
                wilson_lb(int(h_wr * h_trades), h_trades) / 0.50, 1.0
            ),
            "retention": max(0, 1.0 - abs(a1_wr - h_wr) / max(a1_wr, 0.01)),
            "stability": max(0, 1.0 - variability),
            "trade_sufficiency": min(h_trades / 80.0, 1.0),
            "fragility": 1.0 if a3_sharpe >= 0 else 0.5,
            "novelty": 1.0 if is_unique else 0.5,
        }

    def compute_penalties(self, family: Dict, all_families: List[Dict]) -> float:
        """Compute penalty deductions."""
        penalty = 0.0
        # Overfit risk: train sharpe >> holdout sharpe
        a3_s = family.get("train_sharpe", 0)
        h_s = family.get("holdout_sharpe", 0)
        if a3_s > h_s + 1.0:
            penalty += min((a3_s - h_s) / 10.0, 0.3)
        # Regime concentration
        my_regime = family.get("regime", "")
        same_regime = sum(1 for f in all_families if f.get("regime") == my_regime) - 1
        penalty += same_regime * 0.05
        return penalty

    def score_family(self, family: Dict, all_families: List[Dict]) -> float:
        """Score a single family. Returns 0-100."""
        subs = self.compute_subscores(family)
        penalty = self.compute_penalties(family, all_families)

        # Geometric component
        geo = 1.0
        for k, w in self.weights.items():
            geo *= (subs[k] + self.eps) ** w

        # Weighted average component
        wav = sum(self.weights[k] * subs[k] for k in self.weights)

        # Combined score (0-100 scale)
        raw = (geo ** self.eta) * (wav ** (1 - self.eta))
        score = raw * 100.0 - penalty * 100.0

        return max(0, min(100, score))

    def score_all(self, families: List[Dict]) -> List[Dict]:
        """Score all families, return sorted by adaptive_score descending."""
        results = []
        for f in families:
            score = self.score_family(f, families)
            subs = self.compute_subscores(f)
            results.append({
                **f,
                "adaptive_score": round(score, 2),
                "subscores": {k: round(v, 3) for k, v in subs.items()},
                "penalty": round(self.compute_penalties(f, families), 3),
                "cert_ready": score >= self.benchmark,
            })
        return sorted(results, key=lambda x: x["adaptive_score"], reverse=True)

    def update_benchmark(self, certified_scores: List[float]):
        """Smoothly adjust benchmark upward from certified family scores."""
        if not certified_scores:
            return
        recent_top = max(certified_scores)
        # Smooth upward adjustment
        self.benchmark = min(
            self.benchmark * 0.9 + recent_top * 0.1,
            self.benchmark_upper,
        )
