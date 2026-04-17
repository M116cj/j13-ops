"""Dashboard runner — connects to real DB for live data."""
import sys, os
sys.path.insert(0, "/home/j13/j13-ops")
os.chdir("/home/j13/j13-ops")

import asyncpg
from zangetsu_v5.config.settings import Settings
from zangetsu_v5.config.cost_model import CostModel


class LiveDB:
    def __init__(self, settings):
        self._pool = None
        self._settings = settings

    async def connect(self):
        self._pool = await asyncpg.create_pool(
            host=self._settings.db_host,
            port=self._settings.db_port,
            database="zangetsu",
            user=self._settings.db_user,
            password=self._settings.db_password,
            min_size=1,
            max_size=3,
        )

    async def fetch(self, query, *args):
        if not self._pool:
            await self.connect()
        async with self._pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query, *args):
        if not self._pool:
            await self.connect()
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(query, *args)


class _GPU:
    def health_check(self):
        return {"available": False, "vram_used_mb": 0, "vram_total_mb": 12288}


class _Scorer:
    def rank(self, top_k=20):
        return []


class _Data:
    def health_check(self):
        return {"symbols_loaded": 14, "bars_total": 2800000}


class DashboardEngine:
    def __init__(self):
        self.config = Settings()
        self.cost_model = CostModel()
        self.db = LiveDB(self.config)
        self.gpu = _GPU()
        self.scorer = _Scorer()
        self.data = _Data()

    def status(self):
        return {"components": {"dashboard": {"status": "ok"}}}


from zangetsu_v5.dashboard.api import create_dashboard_app
engine = DashboardEngine()
app = create_dashboard_app(engine)
