"""PostgreSQL connection pool with SKIP LOCKED job queue and COPY batch inserts."""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False


class PipelineDB:
    """PostgreSQL connection pool with SKIP LOCKED and COPY support.

    Integration:
        - CONSOLE_HOOK: db_pool_min, db_pool_max, db_statement_timeout_ms
        - DASHBOARD_HOOK: pool_status, query_stats, queue_depth
    """

    def __init__(self, config) -> None:
        self._host: str = config.db_host
        self._port: int = config.db_port
        self._dbname: str = config.db_name
        self._user: str = config.db_user
        self._password: str = config.db_password
        self._pool_min: int = config.db_pool_min
        self._pool_max: int = config.db_pool_max
        self._timeout: int = config.db_statement_timeout
        self._pool: Optional[Any] = None
        self._query_count: int = 0
        self._total_query_ms: float = 0.0

    async def connect(self) -> None:
        if not HAS_ASYNCPG:
            raise RuntimeError("asyncpg not installed — pip install asyncpg")
        self._pool = await asyncpg.create_pool(
            host=self._host,
            port=self._port,
            database=self._dbname,
            user=self._user,
            password=self._password,
            min_size=self._pool_min,
            max_size=self._pool_max,
            command_timeout=self._timeout / 1000.0,
        )

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[Any]:
        if not self._pool:
            raise RuntimeError("PipelineDB not connected — call connect() first")
        async with self._pool.acquire() as conn:
            yield conn

    async def execute(self, query: str, *args: Any) -> str:
        t0 = time.monotonic()
        async with self.acquire() as conn:
            result = await conn.execute(query, *args)
        self._track_query(t0)
        return result

    async def fetch(self, query: str, *args: Any) -> List[Any]:
        t0 = time.monotonic()
        async with self.acquire() as conn:
            rows = await conn.fetch(query, *args)
        self._track_query(t0)
        return rows

    async def fetchrow(self, query: str, *args: Any) -> Optional[Any]:
        t0 = time.monotonic()
        async with self.acquire() as conn:
            row = await conn.fetchrow(query, *args)
        self._track_query(t0)
        return row

    async def dequeue_job(self, queue_name: str, batch_size: int = 1) -> List[Dict]:
        query = """
            DELETE FROM job_queue
            WHERE id IN (
                SELECT id FROM job_queue
                WHERE queue = $1 AND status = 'pending'
                ORDER BY priority DESC, created_at ASC
                LIMIT $2
                FOR UPDATE SKIP LOCKED
            )
            RETURNING id, payload, created_at
        """
        rows = await self.fetch(query, queue_name, batch_size)
        return [dict(r) for r in rows]

    async def enqueue_job(self, queue_name: str, payload: Dict, priority: int = 0) -> int:
        import json
        row = await self.fetchrow(
            """INSERT INTO job_queue (queue, payload, priority, status)
               VALUES ($1, $2::jsonb, $3, 'pending') RETURNING id""",
            queue_name,
            json.dumps(payload),
            priority,
        )
        return row["id"] if row else -1

    async def copy_batch(
        self,
        table: str,
        columns: List[str],
        records: List[Tuple],
    ) -> int:
        if not records:
            return 0
        async with self.acquire() as conn:
            result = await conn.copy_records_to_table(
                table,
                columns=columns,
                records=records,
            )
        return int(result.split()[-1]) if result else len(records)

    async def save_strategy(self, strategy: Dict) -> None:
        import json
        await self.execute(
            """INSERT INTO champion_pipeline
               (indicator_hash, regime, status, n_indicators, passport, engine_hash)
               VALUES ($1, $2, $3, $4, $5::jsonb, $6)
               ON CONFLICT (indicator_hash) DO UPDATE SET
                   status = EXCLUDED.status,
                   passport = EXCLUDED.passport,
                   updated_at = NOW()""",
            strategy["indicator_hash"],
            strategy["regime"],
            strategy.get("status", "ARENA1_READY"),
            strategy.get("n_indicators", 0),
            json.dumps(strategy.get("passport", {})),
            strategy.get("engine_hash", ""),
        )

    async def get_queue_depth(self, queue_name: str) -> int:
        row = await self.fetchrow(
            "SELECT COUNT(*) as cnt FROM job_queue WHERE queue = $1 AND status = 'pending'",
            queue_name,
        )
        return row["cnt"] if row else 0

    def _track_query(self, t0: float) -> None:
        self._query_count += 1
        self._total_query_ms += (time.monotonic() - t0) * 1000

    def health_check(self) -> Dict:
        return {
            "connected": self._pool is not None,
            "pool_min": self._pool_min,
            "pool_max": self._pool_max,
            "query_count": self._query_count,
            "avg_query_ms": (
                round(self._total_query_ms / self._query_count, 2)
                if self._query_count > 0 else 0.0
            ),
            "host": self._host,
            "database": self._dbname,
        }
