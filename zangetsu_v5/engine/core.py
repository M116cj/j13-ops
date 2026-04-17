"""Arena Engine — assembly and lifecycle management.

The ArenaEngine is the shared infrastructure layer. Each Arena calls
engine components; no Arena implements its own data loading, indicator
computation, backtesting, or database access.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

try:
    from config.settings import Settings
    from config.cost_model import CostModel
except ImportError:
    from ..config.settings import Settings
    from ..config.cost_model import CostModel
from .components.data_loader import DataLoader
from .components.indicator import IndicatorCompute
from .components.normalizer import Normalizer
from .components.voter import Voter
from .components.backtester import Backtester
from .components.scorer import Scorer
from .components.db import PipelineDB
from .components.gpu_pool import GPUPool
from .components.checkpoint import Checkpointer
from .components.health import HealthMonitor
from .components.logger import StructuredLogger


class ArenaEngine:
    """Shared infrastructure. Each Arena calls engine, not implements.

    Lifecycle:
        engine = ArenaEngine(settings)
        await engine.startup()
        # ... run arenas ...
        await engine.shutdown()
    """

    _COMPONENTS = [
        "data", "indicator", "normalizer", "voter",
        "backtest", "scorer", "db", "gpu", "checkpoint",
    ]

    def __init__(self, config: Optional[Settings] = None) -> None:
        self.config = config or Settings()
        self.cost_model = CostModel()

        # Component assembly
        self.data = DataLoader(self.config)             # CONSOLE_HOOK: parquet_dir, symbols
        self.indicator = IndicatorCompute(self.config)   # CONSOLE_HOOK: indicator_library_path
        self.normalizer = Normalizer(self.config)        # CONSOLE_HOOK: drift_threshold
        self.voter = Voter(self.config)                  # CONSOLE_HOOK: default_agreement_threshold
        self.backtest = Backtester(self.config)           # CONSOLE_HOOK: cost_bps_override
        self.scorer = Scorer(self.config)                 # CONSOLE_HOOK: decay_tau, scoring_weights
        self.db = PipelineDB(self.config)
        self.gpu = GPUPool(self.config)                   # CONSOLE_HOOK: batch_size, gpu_enabled
        self.checkpoint = Checkpointer(self.db)
        self.checkpoint.configure(self.config)
        self.health = HealthMonitor(port=self.config.health_port)  # DASHBOARD_HOOK: all metrics
        self.log = StructuredLogger(
            level=self.config.log_level,
            log_file=self.config.log_file,
            rotation_mb=self.config.log_rotation_mb,
        )

        # Register all components with health monitor
        self.health.register("data", self.data.health_check)
        self.health.register("indicator", self.indicator.health_check)
        self.health.register("normalizer", self.normalizer.health_check)
        self.health.register("voter", self.voter.health_check)
        self.health.register("backtest", self.backtest.health_check)
        self.health.register("scorer", self.scorer.health_check)
        self.health.register("db", self.db.health_check)
        self.health.register("gpu", self.gpu.health_check)
        self.health.register("checkpoint", self.checkpoint.health_check)
        self.health.register("log", self.log.health_check)

        self._started = False

        # Arena registry and lifecycle
        self._arenas: Dict[str, Any] = {}          # name -> ArenaPlugin
        self._arena_tasks: Dict[str, asyncio.Task] = {}  # name -> running Task
        self._arena_paused: Dict[str, bool] = {}   # name -> pause flag

    async def startup(self) -> None:
        """Initialize all components that require async setup."""
        self.log.info("ArenaEngine starting up")
        await self.db.connect()
        await self.health.start()
        self.data.load_all()
        self._started = True
        self.log.info(
            "ArenaEngine ready",
            symbols=self.config.symbols,
            gpu=self.gpu.available,
        )

    async def shutdown(self) -> None:
        """Gracefully shut down all components."""
        self.log.info("ArenaEngine shutting down")
        # Stop all running arenas
        for name in list(self._arena_tasks):
            try:
                await self.stop_arena(name)
            except Exception:
                pass
        await self.health.stop()
        self.gpu.release_all()
        await self.db.close()
        self._started = False
        self.log.info("ArenaEngine stopped")


    # ── Arena Registry & Lifecycle ───────────────────────────────

    def register_arena(self, name: str, arena: Any) -> None:
        """Register an arena plugin instance."""
        self._arenas[name] = arena
        self._arena_paused[name] = False
        self.log.info("Arena registered", arena=name)

    def get_arena(self, name: str) -> Any:
        """Get a registered arena by name. Raises KeyError if not found."""
        if name not in self._arenas:
            raise KeyError(f"Arena not registered: {name}")
        return self._arenas[name]

    async def start_arena(self, name: str) -> None:
        """Start an arena's run_round loop as an asyncio task."""
        if name not in self._arenas:
            raise KeyError(f"Arena not registered: {name}")
        if name in self._arena_tasks and not self._arena_tasks[name].done():
            raise RuntimeError(f"Arena already running: {name}")

        arena = self._arenas[name]
        self._arena_paused[name] = False

        async def _arena_loop() -> None:
            await arena.setup()
            round_num = 0
            try:
                while True:
                    # Check pause flag
                    while self._arena_paused.get(name, False):
                        await asyncio.sleep(0.5)
                    # Run one round for each configured symbol
                    for symbol in self.config.symbols:
                        result = await arena.run_round(round_num, symbol)
                        if arena.should_stop(round_num, result):
                            self.log.info("Arena stopped (convergence)", arena=name, round=round_num)
                            return
                    round_num += 1
            except asyncio.CancelledError:
                self.log.info("Arena task cancelled", arena=name)
            finally:
                await arena.teardown()

        task = asyncio.create_task(_arena_loop())
        self._arena_tasks[name] = task
        self.log.info("Arena started", arena=name)

    async def stop_arena(self, name: str) -> None:
        """Stop a running arena by cancelling its task."""
        if name not in self._arenas:
            raise KeyError(f"Arena not registered: {name}")
        task = self._arena_tasks.get(name)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._arena_tasks.pop(name, None)
        self._arena_paused[name] = False
        self.log.info("Arena stopped", arena=name)

    async def pause_arena(self, name: str) -> None:
        """Pause a running arena (loop will spin-wait)."""
        if name not in self._arenas:
            raise KeyError(f"Arena not registered: {name}")
        task = self._arena_tasks.get(name)
        if not task or task.done():
            raise RuntimeError(f"Arena not running: {name}")
        self._arena_paused[name] = True
        self.log.info("Arena paused", arena=name)

    async def resume_arena(self, name: str) -> None:
        """Resume a paused arena."""
        if name not in self._arenas:
            raise KeyError(f"Arena not registered: {name}")
        if not self._arena_paused.get(name, False):
            raise RuntimeError(f"Arena not paused: {name}")
        self._arena_paused[name] = False
        self.log.info("Arena resumed", arena=name)

    # DASHBOARD_HOOK: engine_status
    def status(self) -> Dict[str, Any]:
        """Aggregate status from all components."""
        result: Dict[str, Any] = {
            "started": self._started,
            "components": {},
        }
        for comp_name in self._COMPONENTS:
            comp = getattr(self, comp_name, None)
            if comp and hasattr(comp, "health_check"):
                try:
                    result["components"][comp_name] = comp.health_check()
                except Exception as e:
                    result["components"][comp_name] = {"error": str(e)}
        return result

    def apply_config_update(self, overrides: Dict[str, Any]) -> List[str]:
        """Apply runtime configuration changes from console API.

        Returns list of changed field names.
        """
        changed = self.config.update(overrides)
        if changed:
            self.log.info("Config updated", changed_fields=changed)
            # Re-configure components that need it
            if any(f.startswith("normalizer_") for f in changed):
                self.normalizer = Normalizer(self.config)
                self.health.register("normalizer", self.normalizer.health_check)
            if any(f.startswith("voter_") for f in changed):
                self.voter = Voter(self.config)
                self.health.register("voter", self.voter.health_check)
            if any(f.startswith("checkpoint_") for f in changed):
                self.checkpoint.configure(self.config)
        return changed
