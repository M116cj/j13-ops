"""S10 end-to-end pipeline test.

Full Zangetsu V3 flow without a live database:
  synthetic OHLCV → feature engine → data split → normalizer
  → regime fit → regime predictor → factor matrix
  → CMA-MAE search (20 gen) → Gate1 / Gate2 / Gate3
  → CardExporter → on_new_bar live loop

Success criteria S01–S10 verified.
"""
from __future__ import annotations

import json
import tempfile
from collections import deque
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from zangetsu_v3.core.feature_engine import FeatureEngine
from zangetsu_v3.core.data_split import DataSplit
from zangetsu_v3.factors.bootstrap import compute_factor_matrix
from zangetsu_v3.factors.normalizer import RobustNormalizer
from zangetsu_v3.regime.labeler import RegimeLabeler
from zangetsu_v3.regime.predictor import OnlineRegimePredictor
from zangetsu_v3.search.backtest import HFTBacktest
from zangetsu_v3.search.hyperband import ZeroConfigPipeline
from zangetsu_v3.search.scheduler import RegimeScheduler, DEFAULT_PARAM_BOUNDS
from zangetsu_v3.gates.gate1 import Gate1
from zangetsu_v3.gates.gate2 import DeflatedSharpeGate
from zangetsu_v3.gates.gate3 import HoldoutGate
from zangetsu_v3.cards.exporter import CardExporter
from zangetsu_v3.live.journal import LiveJournal
from zangetsu_v3.live.monitor import LiveMonitor
from zangetsu_v3.live.risk_manager import RiskLimits
from zangetsu_v3.live.main_loop import build_live_state, on_new_bar

N_WEIGHTS = 15
N_PARAMS = 5   # entry_thr, exit_thr, stop_mult, pos_frac, hold_max
SOLUTION_DIM = N_WEIGHTS + N_PARAMS


def _make_ohlcv(n: int = 2000, seed: int = 42) -> pl.DataFrame:
    from datetime import datetime, timedelta
    rng = np.random.default_rng(seed)
    log_ret = rng.normal(0.0002, 0.01, n)
    close = 50000.0 * np.exp(np.cumsum(log_ret))
    open_ = close * (1 + rng.uniform(-0.002, 0.002, n))
    high = np.maximum(close, open_) * (1 + rng.uniform(0, 0.005, n))
    low = np.minimum(close, open_) * (1 - rng.uniform(0, 0.005, n))
    volume = rng.lognormal(10, 1, n)
    start = datetime(2024, 1, 1)
    timestamps = [start + timedelta(hours=i) for i in range(n)]
    return pl.DataFrame({"timestamp": timestamps, "open": open_, "high": high,
                         "low": low, "close": close, "volume": volume})


class TestS10EndToEnd:

    @pytest.fixture(scope="class")
    def pipeline(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("e2e")
        raw = _make_ohlcv(2000)

        # S01 — Feature engine
        fe = FeatureEngine()
        featured = fe.compute(raw)
        for col in ("rolling_return", "realized_vol", "volume_zscore", "range_zscore"):
            assert col in featured.columns

        # S02 — Data split
        ds = DataSplit(embargo_days=5, holdout_months=2)
        train, embargo, holdout = ds.split(featured)
        assert len(embargo) > 0
        assert len(holdout) > 0
        assert len(train) + len(embargo) + len(holdout) == len(featured)

        # S03 — Normalizer: fit only on train
        feature_cols = ["rolling_return", "realized_vol", "volume_zscore", "range_zscore"]
        normalizer = RobustNormalizer()
        normalizer.fit(train.select(feature_cols))
        train_norm = normalizer.transform(train.select(feature_cols))
        assert train_norm.shape == train.select(feature_cols).shape

        # S04 — Regime labeler
        labeler = RegimeLabeler(min_states=2, max_states=4)
        train_labels = labeler.fit(train)
        n_regimes = len(np.unique(train_labels))
        assert 2 <= n_regimes <= 4

        # S05 — Online predictor
        predictor = OnlineRegimePredictor(debounce=3)
        for lbl in train_labels[:10]:
            predictor.step(int(lbl))
        assert predictor.active_regime is not None
        assert 0.0 <= predictor.switch_confidence <= 1.0

        # S06 — Factor matrix
        factor_df = compute_factor_matrix(train)
        factor_names = factor_df.columns
        factor_matrix = factor_df.to_numpy()
        assert factor_matrix.shape[0] == len(train)
        assert factor_matrix.shape[1] > 0
        # Pad or trim to N_WEIGHTS
        if factor_matrix.shape[1] < N_WEIGHTS:
            factor_matrix = np.hstack([factor_matrix,
                                       np.zeros((len(train), N_WEIGHTS - factor_matrix.shape[1]))])
        elif factor_matrix.shape[1] > N_WEIGHTS:
            factor_matrix = factor_matrix[:, :N_WEIGHTS]
            factor_names = factor_names[:N_WEIGHTS]
        # Drop warmup NaN rows (rolling windows need ~50 bars)
        valid_mask = ~np.any(np.isnan(factor_matrix), axis=1)
        factor_matrix = factor_matrix[valid_mask]
        train = train.filter(pl.Series(valid_mask))
        train_labels = train_labels[valid_mask] if hasattr(train_labels, '__getitem__') else np.array(train_labels)[valid_mask]
        assert not np.any(np.isnan(factor_matrix))
        assert len(factor_matrix) > 100, "Need enough rows after dropping warmup NaNs"

        # S07 — CMA-MAE search
        target_regime = int(train_labels[-1])
        close_arr = train["close"].to_numpy()
        engine = HFTBacktest()
        scheduler = RegimeScheduler(solution_dim=SOLUTION_DIM)

        # Build segments for ZeroConfigPipeline
        segments = [{
            "factor_matrix": factor_matrix,
            "close": close_arr,
            "cost_bps": 3.0,
            "funding_rate": 0.0001,
        }]
        hyper = ZeroConfigPipeline(
            scheduler=scheduler,
            segments=segments,
            n_weights=N_WEIGHTS,
            param_bounds=DEFAULT_PARAM_BOUNDS,
            n_jobs=2,
        )
        hyper.run(generations=20)

        n_elites = scheduler.archive.stats.num_elites
        assert n_elites > 0, "Archive must have at least 1 elite after 20 gen"

        # S08 — Gates
        best_sol = scheduler.archive.best_elite["solution"]
        weights = best_sol[:N_WEIGHTS]
        best_params = scheduler.denormalize_params(best_sol)

        signal = factor_matrix @ weights
        train_result = engine.evaluate(
            signal=signal,
            close=close_arr,
            params=best_params,
            cost_bps=3.0,
            funding_rate=0.0001,
        )

        g1 = Gate1()
        g1_pass = g1.evaluate(train_result)

        g2 = DeflatedSharpeGate(threshold=0.0)
        g2.increment_trials(20)
        g2_pass = g2.gate(
            observed_sharpe=train_result.sharpe,
            n_observations=len(signal),
            n_trials=20,
        )

        holdout_fm = compute_factor_matrix(holdout).to_numpy()
        if holdout_fm.shape[1] < N_WEIGHTS:
            holdout_fm = np.hstack([holdout_fm,
                                    np.zeros((holdout_fm.shape[0], N_WEIGHTS - holdout_fm.shape[1]))])
        elif holdout_fm.shape[1] > N_WEIGHTS:
            holdout_fm = holdout_fm[:, :N_WEIGHTS]
        holdout_labels = labeler.label(holdout)
        # Drop warmup NaN rows for holdout
        ho_valid = ~np.any(np.isnan(holdout_fm), axis=1)
        holdout_fm = holdout_fm[ho_valid]
        holdout = holdout.filter(pl.Series(ho_valid))
        holdout_labels = holdout_labels[ho_valid] if hasattr(holdout_labels, '__getitem__') else np.array(holdout_labels)[ho_valid]
        holdout_sig = holdout_fm @ weights
        holdout_result = engine.evaluate(
            signal=holdout_sig,
            close=holdout["close"].to_numpy(),
            params=best_params,
            cost_bps=3.0,
            funding_rate=0.0001,
        )
        g3 = HoldoutGate()
        g3_pass, g3_reason = g3.gate(holdout_result=holdout_result)

        # S09 — Card export
        labeler.save(tmp / "regime.pkl")
        loaded_labeler = RegimeLabeler.load(tmp / "regime.pkl")

        card_payload = {
            "version": "3.0",
            "id": "e2e-test-card",
            "regime": target_regime,
            "warmup_bars": 20,
            "status": "PASSED_HOLDOUT" if g3_pass else "FAILED_HOLDOUT",
            "normalization": {
                "medians": normalizer.medians,
                "scales": normalizer.scales,
            },
            "factors": {
                "names": factor_names,
                "weights": weights.tolist(),
            },
            "params": {**best_params, "entry_threshold": 1.2,
                       "exit_threshold": 0.5, "position_frac": 0.1},
            "cost_model": {"trading_bps": 3, "funding_rate_avg": 0.0001},
            "backtest": {
                "windows": [
                    {"sharpe": train_result.sharpe, "max_drawdown": train_result.max_drawdown,
                     "total_return": train_result.total_return,
                     "trades_per_day": train_result.trades_per_day,
                     "win_rate": train_result.win_rate}
                ] * 5
            },
            "validation": {
                "gate1_pass": g1_pass, "gate2_pass": g2_pass,
                "gate3_pass": g3_pass, "gate3_reason": g3_reason,
            },
            "regime_labeler": {"n_states": n_regimes},
            "deployment_hints": {"symbol": "BTC/USDT", "timeframe": "1m"},
            "regime_includes": [target_regime],
            "applicable_symbols": ["BTC/USDT"],
            "style": "hft",
        }

        exporter = CardExporter(version="3.0")
        card_dir = tmp / "cards"
        exporter.export(card_dir, card_payload, loaded_labeler)

        card_path = card_dir / "card.json"
        assert card_path.exists()
        with card_path.open() as f:
            card_json = json.load(f)
        assert card_json["card_id"] == "e2e-test-card"
        assert (card_dir / "checksum.sha256").exists()
        assert (card_dir / "live_journal.parquet").exists()

        return {
            "card_json": card_json,
            "card_dir": card_dir,
            "weights": weights,
            "normalizer": normalizer,
            "labeler": loaded_labeler,
            "factor_names": factor_names,
            "n_regimes": n_regimes,
            "target_regime": target_regime,
            "tmp": tmp,
        }

    def test_s01_s06_pass(self, pipeline):
        """S01–S06: features, split, normalizer, regime, predictor, factor matrix."""
        assert 2 <= pipeline["n_regimes"] <= 4

    def test_s07_cma_mae_has_elites(self, pipeline):
        """S07: CMA-MAE archive has elites after 20 gen."""
        pass  # asserted in fixture

    def test_s08_card_fields(self, pipeline):
        """S08: card.json has all REQUIRED_CARD_FIELDS."""
        required = {
            "card_id", "version", "regime", "warmup_bars", "status",
            "normalization", "factors", "params", "cost_model",
            "backtest", "validation", "regime_labeler", "deployment_hints",
        }
        missing = required - set(pipeline["card_json"].keys())
        assert not missing, f"Missing card fields: {missing}"

    def test_s09_checksum_present(self, pipeline):
        """S09: checksum.sha256 alongside card.json."""
        assert (pipeline["card_dir"] / "checksum.sha256").exists()

    def test_s10_live_loop(self, pipeline):
        """S10: on_new_bar runs 180 bars, all actions valid, max latency < 50ms."""
        card = pipeline["card_json"]
        weights = np.array(pipeline["weights"])
        journal = LiveJournal(pipeline["card_dir"] / "live_journal.parquet")
        monitor = LiveMonitor()

        state = build_live_state(
            card=card,
            weights=weights,
            normalizer=pipeline["normalizer"],
            labeler=pipeline["labeler"],
            predictor=OnlineRegimePredictor(debounce=3),
            risk_limits=RiskLimits(),
            max_stale_seconds=60,
            lookback=60,
        )

        raw = _make_ohlcv(200, seed=99)
        fe = FeatureEngine()
        featured = fe.compute(raw)
        fm = compute_factor_matrix(featured).to_numpy()
        if fm.shape[1] < N_WEIGHTS:
            fm = np.hstack([fm, np.zeros((fm.shape[0], N_WEIGHTS - fm.shape[1]))])
        elif fm.shape[1] > N_WEIGHTS:
            fm = fm[:, :N_WEIGHTS]

        valid_actions = {
            "entry_long", "entry_short", "exit", "hold",
            "risk_blocked", "stale", "warming_up",
        }
        open_positions: dict = {}
        latencies = []

        for i in range(len(featured)):
            bar_row = featured.slice(i, 1)
            open_positions, result = on_new_bar(
                symbol="BTC/USDT",
                bar_df=bar_row,
                factor_row=fm[i],
                state=state,
                open_positions=open_positions,
                journal=journal,
                monitor=monitor,
            )
            assert result.action in valid_actions, f"Unknown action: {result.action}"
            latencies.append(result.latency_ms)

        max_lat = max(latencies)
        assert max_lat < 50.0, f"Max latency {max_lat:.1f}ms exceeds C29 limit of 50ms"
