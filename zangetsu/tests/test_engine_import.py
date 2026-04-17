"""OBSOLETE — V5-era tests, references removed modules (voter, data_weight).
Marked skip pending rewrite for V9 architecture. See TODO.
"""
import pytest
pytest.skip("V5-era tests — modules voter/data_weight deprecated in V9 unification", allow_module_level=True)

"""Smoke tests — verify all modules import without error.

zangetsu is a package with relative imports (engine.core uses ..config).
Tests must run from ~/j13-ops/ so that zangetsu is the top-level package.
Run: cd ~/j13-ops && python3 -m pytest zangetsu/tests/ -v
"""
import sys
import os
import unittest

# Ensure ~/j13-ops is on path so zangetsu is importable as package
PROJECT_PARENT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_PARENT not in sys.path:
    sys.path.insert(0, PROJECT_PARENT)


class TestEngineComponentImports(unittest.TestCase):
    """All engine components should import successfully."""

    def test_import_data_loader(self):
        from zangetsu.engine.components.data_loader import DataLoader
        self.assertTrue(DataLoader)

    def test_import_indicator(self):
        from zangetsu.engine.components.indicator import IndicatorCompute
        self.assertTrue(IndicatorCompute)

    def test_import_normalizer(self):
        from zangetsu.engine.components.normalizer import Normalizer
        self.assertTrue(Normalizer)

    def test_import_voter(self):
        from zangetsu.engine.components.voter import Voter
        self.assertTrue(Voter)

    def test_import_backtester(self):
        from zangetsu.engine.components.backtester import Backtester
        self.assertTrue(Backtester)

    def test_import_scorer(self):
        from zangetsu.engine.components.scorer import Scorer
        self.assertTrue(Scorer)

    def test_import_db(self):
        from zangetsu.engine.components.db import PipelineDB
        self.assertTrue(PipelineDB)

    def test_import_gpu_pool(self):
        from zangetsu.engine.components.gpu_pool import GPUPool
        self.assertTrue(GPUPool)

    def test_import_checkpoint(self):
        from zangetsu.engine.components.checkpoint import Checkpointer
        self.assertTrue(Checkpointer)

    def test_import_health(self):
        from zangetsu.engine.components.health import HealthMonitor
        self.assertTrue(HealthMonitor)

    def test_import_logger(self):
        from zangetsu.engine.components.logger import StructuredLogger
        self.assertTrue(StructuredLogger)

    def test_import_watchdog(self):
        from zangetsu.engine.components.watchdog import Watchdog
        self.assertTrue(Watchdog)

    def test_components_init_exports(self):
        """All components accessible via engine.components."""
        from zangetsu.engine.components import (
            DataLoader, IndicatorCompute, Normalizer, Voter,
            Backtester, Scorer, PipelineDB, GPUPool,
            Checkpointer, HealthMonitor, StructuredLogger, Watchdog,
        )
        self.assertEqual(len([
            DataLoader, IndicatorCompute, Normalizer, Voter,
            Backtester, Scorer, PipelineDB, GPUPool,
            Checkpointer, HealthMonitor, StructuredLogger, Watchdog,
        ]), 12)


class TestEngineCoreAssembly(unittest.TestCase):
    """Engine core.py should import and ArenaEngine class should exist."""

    def test_import_arena_engine(self):
        from zangetsu.engine.core import ArenaEngine
        self.assertTrue(ArenaEngine)

    def test_engine_init_export(self):
        from zangetsu.engine import ArenaEngine
        self.assertTrue(ArenaEngine)


class TestArenaImports(unittest.TestCase):
    """All arena files should import successfully."""

    def test_import_base(self):
        from zangetsu.arena.base import ArenaPlugin, ArenaResult
        self.assertTrue(ArenaPlugin)
        self.assertTrue(ArenaResult)

    def test_import_arena1(self):
        from zangetsu.arena.arena1_discover import Arena1Discover
        self.assertTrue(Arena1Discover)

    def test_import_arena2(self):
        from zangetsu.arena.arena2_threshold import Arena2Threshold
        self.assertTrue(Arena2Threshold)

    def test_import_arena3(self):
        from zangetsu.arena.arena3_pnl import Arena3PnL
        self.assertTrue(Arena3PnL)

    def test_import_arena4(self):
        from zangetsu.arena.arena4_validate import Arena4Validate
        self.assertTrue(Arena4Validate)

    def test_import_arena5(self):
        from zangetsu.arena.arena5_elo import Arena5ELO
        self.assertTrue(Arena5ELO)

    def test_import_arena13(self):
        from zangetsu.arena.arena13_evolve import Arena13Evolve
        self.assertTrue(Arena13Evolve)

    def test_arena_init_exports(self):
        from zangetsu.arena import (
            ArenaPlugin, ArenaResult,
            Arena1Discover, Arena2Threshold, Arena3PnL,
            Arena4Validate, Arena5ELO, Arena13Evolve,
        )
        self.assertEqual(len([
            ArenaPlugin, ArenaResult,
            Arena1Discover, Arena2Threshold, Arena3PnL,
            Arena4Validate, Arena5ELO, Arena13Evolve,
        ]), 8)


class TestConfigImports(unittest.TestCase):
    """Config module should load successfully."""

    def test_import_settings(self):
        from zangetsu.config.settings import Settings
        self.assertTrue(Settings)

    def test_import_cost_model(self):
        from zangetsu.config.cost_model import CostModel
        self.assertTrue(CostModel)

    def test_config_init_exports(self):
        from zangetsu.config import Settings, CostModel
        self.assertTrue(Settings)
        self.assertTrue(CostModel)

    def test_settings_instantiate(self):
        """Settings should instantiate with defaults."""
        from zangetsu.config.settings import Settings
        s = Settings()
        self.assertIsNotNone(s)


if __name__ == "__main__":
    unittest.main()
