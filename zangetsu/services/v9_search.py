"""V9 Guided Search — Optuna TPE + Curriculum Learning + Online Learning.

Replaces random indicator combination sampling with Bayesian-guided search.
Implements curriculum learning: 1-indicator → 2 → 3+ (only if simpler passes).
Adds online learning for adaptive indicator weights per regime.
"""
from __future__ import annotations

import json
import logging
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass, field

import numpy as np

log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# Curriculum Learning
# ═══════════════════════════════════════════════════════════════════

class CurriculumGate:
    """Tiered search: single indicator → 2 → 3+ based on proven success.

    An indicator can only appear in higher-tier combos if it already
    has a proven track record at a lower tier.
    """

    def __init__(self):
        self.tier1_passed: set = set()  # single-indicator combos that passed A3
        self.tier2_passed: list = []     # 2-indicator combos that passed A3
        self.min_tier1_passes = 3        # an indicator needs 3 single-indicator wins to be tier-2-eligible

    def allow_combo(self, indicator_names: List[str], tier: int) -> bool:
        """Check if a combo is allowed at current tier."""
        if tier == 1:
            return len(indicator_names) == 1

        if tier == 2:
            if len(indicator_names) != 2:
                return False
            # Both indicators must have tier-1 proof
            return all(ind in self.tier1_passed for ind in indicator_names)

        if tier >= 3:
            # Higher tier: at least 2 of the indicators must have tier-1 proof
            proven = sum(1 for ind in indicator_names if ind in self.tier1_passed)
            return proven >= 2

        return False

    def record_success(self, indicator_names: List[str]):
        """Called when a combo passes A3 — update eligibility."""
        if len(indicator_names) == 1:
            self.tier1_passed.add(indicator_names[0])
        elif len(indicator_names) == 2:
            self.tier2_passed.append(tuple(sorted(indicator_names)))

    def stats(self) -> dict:
        return {
            "tier1_proven_indicators": len(self.tier1_passed),
            "tier2_proven_combos": len(self.tier2_passed),
            "proven_indicator_list": sorted(self.tier1_passed),
        }


# ═══════════════════════════════════════════════════════════════════
# Optuna TPE Search
# ═══════════════════════════════════════════════════════════════════

class OptunaIndicatorSearch:
    """Bayesian-guided indicator combination search using Optuna TPE.

    Replaces random sampling with learned distribution over indicators.
    Uses PostgreSQL RDB storage for cross-worker coordination.
    """

    def __init__(self, indicator_pool: List[str], period_choices: List[int],
                 storage_url: str, study_name: str = "zv9_search",
                 constant_liar: bool = True):
        try:
            import optuna
        except ImportError:
            raise ImportError("Optuna required for V9 search")

        self.indicator_pool = indicator_pool
        self.period_choices = period_choices
        self.optuna = optuna

        # Create or resume study
        self.storage = optuna.storages.RDBStorage(
            url=storage_url,
            heartbeat_interval=60,
            engine_kwargs={"pool_size": 5, "max_overflow": 10},
        )

        sampler = optuna.samplers.TPESampler(
            n_startup_trials=30,
            constant_liar=constant_liar,  # prevent duplicate suggestions across workers
        )

        self.study = optuna.create_study(
            storage=self.storage,
            study_name=study_name,
            sampler=sampler,
            direction="maximize",
            load_if_exists=True,
        )
        log.info(f"OptunaSearch: study={study_name} trials_so_far={len(self.study.trials)}")

    def suggest(self, curriculum: Optional[CurriculumGate] = None,
                regime: str = "UNKNOWN") -> Tuple[object, Dict]:
        """Ask Optuna for next combination to try.

        Returns (trial_object, config_dict) where config has:
            - n_indicators: int
            - indicators: List[Tuple[name, period]]
            - entry_threshold: float
            - exit_threshold: float
            - regime: str (for conditioning)
        """
        trial = self.study.ask()

        # Decide tier based on curriculum progress
        if curriculum is not None and curriculum.tier1_passed:
            n_ind = trial.suggest_int("n_indicators", 1, 4)
        else:
            # Bootstrap phase: prefer simpler combos
            n_ind = trial.suggest_int("n_indicators", 1, 2)

        # Ordered selection to avoid duplicates
        remaining = list(self.indicator_pool)
        selected = []
        for i in range(n_ind):
            if not remaining:
                break
            ind = trial.suggest_categorical(f"ind_{i}", remaining)
            period = trial.suggest_categorical(f"period_{i}", self.period_choices)
            selected.append((ind, period))
            remaining = [r for r in remaining if r != ind]

        # Thresholds (continuous params)
        entry_thr = trial.suggest_float("entry_threshold", 0.45, 0.80)
        exit_thr = trial.suggest_float("exit_threshold", 0.15, 0.45)

        config = {
            "n_indicators": len(selected),
            "indicators": selected,
            "entry_threshold": entry_thr,
            "exit_threshold": exit_thr,
            "regime": regime,
            "trial_number": trial.number,
        }
        return trial, config

    def report(self, trial, score: float, extra: Optional[Dict] = None):
        """Tell Optuna how the combo performed."""
        self.study.tell(trial, score)
        if extra:
            for k, v in extra.items():
                try:
                    trial.set_user_attr(k, v)
                except Exception as e:
                    log.debug(f"optuna set_user_attr failed ({k}): {e}")

    def warm_start_from_history(self, historical_trials: List[Dict]):
        """Pre-populate study with N failed historical trials to accelerate TPE convergence."""
        from optuna.distributions import IntDistribution, FloatDistribution, CategoricalDistribution
        from optuna.trial import create_trial

        added = 0
        for h in historical_trials:
            try:
                # Build distributions matching our suggest_* calls
                dists = {
                    "n_indicators": IntDistribution(1, 4),
                    "entry_threshold": FloatDistribution(0.45, 0.80),
                    "exit_threshold": FloatDistribution(0.15, 0.45),
                }
                for i in range(h.get("n_indicators", 0)):
                    dists[f"ind_{i}"] = CategoricalDistribution(self.indicator_pool)
                    dists[f"period_{i}"] = CategoricalDistribution(self.period_choices)

                frozen = create_trial(
                    params=h["params"],
                    distributions=dists,
                    values=[h["score"]],
                )
                self.study.add_trial(frozen)
                added += 1
            except Exception as e:
                log.debug(f"Warm-start skip trial: {e}")
        log.info(f"OptunaSearch: warm-started with {added}/{len(historical_trials)} trials")


# ═══════════════════════════════════════════════════════════════════
# Online Learning Layer (River)
# ═══════════════════════════════════════════════════════════════════

class OnlineIndicatorWeights:
    """River-based online learner that adapts indicator weights from A3 feedback.

    Each (indicator, regime) pair has a weight. When a combo passes/fails A3,
    the weights update incrementally. Used to bias Optuna suggestions over time.
    """

    def __init__(self):
        try:
            from river import linear_model, preprocessing, compose
        except ImportError:
            raise ImportError("River required for online learning")

        # One logistic regression per regime
        self._models: Dict[str, object] = {}
        self._linear_model = linear_model
        self._preprocessing = preprocessing
        self._compose = compose

    def _get_model(self, regime: str):
        if regime not in self._models:
            self._models[regime] = self._compose.Pipeline(
                self._preprocessing.StandardScaler(),
                self._linear_model.LogisticRegression(),
            )
        return self._models[regime]

    def learn(self, indicator_names: List[str], regime: str, passed_a3: bool):
        """Update weights given outcome."""
        features = {ind: 1.0 for ind in indicator_names}
        # Add 'None' for missing indicators to let model learn absence
        model = self._get_model(regime)
        try:
            model.learn_one(features, int(passed_a3))
        except Exception as e:
            log.debug(f"OnlineLearner: learn_one failed: {e}")

    def score(self, indicator_names: List[str], regime: str) -> float:
        """Predict probability of passing A3 given this combo in this regime."""
        if regime not in self._models:
            return 0.5  # no data yet
        features = {ind: 1.0 for ind in indicator_names}
        model = self._models[regime]
        try:
            prob = model.predict_proba_one(features)
            return prob.get(True, prob.get(1, 0.5))
        except Exception:
            return 0.5

    def get_indicator_weights(self, regime: str) -> Dict[str, float]:
        """Extract current weights per indicator (for diagnostics)."""
        if regime not in self._models:
            return {}
        try:
            model = self._models[regime]
            # Navigate River pipeline to get weights
            lr = model["LogisticRegression"]
            return dict(lr.weights)
        except Exception:
            return {}


# ═══════════════════════════════════════════════════════════════════
# Integrated Search Coordinator
# ═══════════════════════════════════════════════════════════════════

@dataclass
class SearchRecommendation:
    """One suggestion from the search coordinator."""
    trial: object
    indicators: List[Tuple[str, int]]
    entry_threshold: float
    exit_threshold: float
    regime: str
    tier: int  # curriculum tier
    confidence: float  # online-learner prediction


class V9SearchCoordinator:
    """Unified interface: Optuna TPE + Curriculum + Online Learning."""

    def __init__(self, indicator_pool: List[str], period_choices: List[int],
                 storage_url: str, study_name: str = "zv9_search"):
        self.optuna_search = OptunaIndicatorSearch(
            indicator_pool, period_choices, storage_url, study_name
        )
        self.curriculum = CurriculumGate()
        self.online_learner = OnlineIndicatorWeights()

    def next_combo(self, regime: str) -> SearchRecommendation:
        trial, config = self.optuna_search.suggest(self.curriculum, regime)
        names = [ind for ind, _ in config["indicators"]]

        # Determine tier
        n = len(names)
        if n == 1:
            tier = 1
        elif n == 2:
            tier = 2
        else:
            tier = 3

        confidence = self.online_learner.score(names, regime)

        return SearchRecommendation(
            trial=trial,
            indicators=config["indicators"],
            entry_threshold=config["entry_threshold"],
            exit_threshold=config["exit_threshold"],
            regime=regime,
            tier=tier,
            confidence=confidence,
        )

    def report_result(self, rec: SearchRecommendation, a3_score: float, passed_a3: bool):
        """Feedback loop: Optuna tells() + curriculum updates + online learner trains."""
        names = [ind for ind, _ in rec.indicators]

        # Score for Optuna (higher = better)
        self.optuna_search.report(rec.trial, a3_score, extra={
            "regime": rec.regime,
            "tier": rec.tier,
            "n_indicators": len(names),
            "passed_a3": passed_a3,
        })

        # Curriculum gate
        if passed_a3:
            self.curriculum.record_success(names)

        # Online learning
        self.online_learner.learn(names, rec.regime, passed_a3)

    def stats(self) -> dict:
        return {
            "curriculum": self.curriculum.stats(),
            "optuna_trials": len(self.optuna_search.study.trials),
        }
