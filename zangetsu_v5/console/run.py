import sys, os, time
sys.path.insert(0, "/home/j13/j13-ops")
os.chdir("/home/j13/j13-ops")

import structlog

from zangetsu_v5.config.settings import Settings
from zangetsu_v5.config.cost_model import CostModel


class _Health:
    def __init__(self, start_time):
        self._start_time = start_time

    def collect_all(self):
        uptime = round(time.monotonic() - self._start_time, 1)
        return {
            "status": "ok",
            "uptime_s": uptime,
            "components": {"console": {"status": "ok"}},
        }


class MinimalEngine:
    def __init__(self):
        self._start_time = time.monotonic()
        self.config = Settings()
        self.cost_model = CostModel()
        self.health = _Health(self._start_time)
        self.log = structlog.get_logger("console")
        self._arenas = {}
        self._arena_tasks = {}
        self._arena_paused = {}

    def status(self):
        uptime = round(time.monotonic() - self._start_time, 1)
        return {
            "components": {"console": {"status": "ok"}},
            "uptime": uptime,
            "arenas": self._arenas,
            "arena_paused": self._arena_paused,
        }

    def apply_config_update(self, overrides):
        return self.config.update(overrides)

    async def start_arena(self, name):
        self._arenas[name] = "running"

    async def stop_arena(self, name):
        self._arenas[name] = "stopped"

    async def pause_arena(self, name):
        self._arena_paused[name] = True

    async def resume_arena(self, name):
        self._arena_paused[name] = False


from zangetsu_v5.console.api import create_console_app

engine = MinimalEngine()
app = create_console_app(engine)
