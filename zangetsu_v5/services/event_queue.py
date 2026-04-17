"""event_queue.py — PGQueuer wrapper for Zangetsu V9 stage orchestration.

Purpose
-------
Thin ``EventQueue`` adapter around ``pgqueuer`` (0.26.3) that the A23 and
A45 orchestrators can use to hand stage transitions between the pipeline
stages. This module **only** exposes the queue primitives — the actual
integration into the orchestrators is deferred to a later phase.

Design
------
* Single async connection via ``asyncpg`` (same credentials as the rest
  of the pipeline — no separate DSN).
* ``enqueue(stage, champion_id)`` pushes one job with a JSON payload.
* ``listen(callback)`` binds an entrypoint per stage and starts the
  ``QueueManager`` loop. The callback is invoked with the decoded
  ``(stage, champion_id)`` tuple.
* ``close()`` cancels the manager and closes the connection cleanly.

Failure handling
----------------
* Connection is established lazily on first ``enqueue``/``listen``.
* Payload decode errors are logged and the job is marked as exception
  so PGQueuer can retry or move to DLQ depending on queue policy.
* ``close()`` is idempotent.

References
----------
PGQueuer docs: https://pgqueuer.readthedocs.io/  (version 0.26.3)
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Awaitable, Callable, Optional

import asyncpg
from pgqueuer import PgQueuer
from pgqueuer.db import AsyncpgDriver
from pgqueuer.queries import Queries
from pgqueuer.models import Job

from config.settings import Settings

log = logging.getLogger(__name__)

# Type alias for user callbacks: (stage, champion_id) -> awaitable
StageCallback = Callable[[str, str], Awaitable[None]]

# Default entrypoint used by enqueue(); listen() binds one per stage.
DEFAULT_ENTRYPOINT = "zangetsu_stage_event"


class EventQueue:
    """Async PGQueuer wrapper scoped to Zangetsu V9 stage events."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: str = "zangetsu",
        user: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        _s = Settings()
        self._host = host or _s.db_host
        self._port = port or _s.db_port
        self._database = database
        self._user = user or _s.db_user
        self._password = password or _s.db_password

        self._conn: Optional[asyncpg.Connection] = None
        self._driver: Optional[AsyncpgDriver] = None
        self._queries: Optional[Queries] = None
        self._pgq: Optional[PgQueuer] = None
        self._manager_task: Optional[asyncio.Task] = None
        self._closed: bool = False

    # ------------------------------------------------------------------
    # connection management
    # ------------------------------------------------------------------
    async def _ensure_connected(self) -> None:
        if self._conn is not None and not self._conn.is_closed():
            return
        if self._closed:
            raise RuntimeError("EventQueue has been closed")

        self._conn = await asyncpg.connect(
            host=self._host,
            port=self._port,
            database=self._database,
            user=self._user,
            password=self._password,
        )
        self._driver = AsyncpgDriver(self._conn)
        self._queries = Queries(self._driver)
        log.info(
            "EventQueue connected to %s:%s/%s",
            self._host, self._port, self._database,
        )

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    async def enqueue(
        self,
        stage: str,
        champion_id: str,
        *,
        priority: int = 0,
    ) -> None:
        """Push a single stage event job onto the queue.

        Parameters
        ----------
        stage:
            Logical stage name (e.g. ``"A23"``, ``"A45"``, ``"A45_DONE"``).
        champion_id:
            Identifier for the champion strategy being advanced.
        priority:
            Optional PGQueuer priority (higher runs first).
        """
        if not stage or not champion_id:
            raise ValueError("stage and champion_id must be non-empty strings")

        await self._ensure_connected()
        assert self._queries is not None

        payload = json.dumps(
            {"stage": stage, "champion_id": champion_id}
        ).encode("utf-8")

        await self._queries.enqueue(
            [DEFAULT_ENTRYPOINT],
            [payload],
            [priority],
        )
        log.debug("enqueued stage=%s champion=%s", stage, champion_id)

    async def listen(self, callback: StageCallback) -> None:
        """Start the PGQueuer loop and route jobs to ``callback``.

        The callback is invoked with ``(stage, champion_id)`` after the
        job payload is decoded. Exceptions bubble up to PGQueuer which
        will mark the job as failed.
        """
        await self._ensure_connected()
        assert self._driver is not None

        pgq = PgQueuer(self._driver)

        @pgq.entrypoint(DEFAULT_ENTRYPOINT)
        async def _handle(job: Job) -> None:  # noqa: WPS430
            raw = job.payload or b""
            try:
                data = json.loads(raw.decode("utf-8"))
                stage = data["stage"]
                champion_id = data["champion_id"]
            except (json.JSONDecodeError, KeyError, UnicodeDecodeError) as exc:
                log.error("invalid event payload: %s", exc)
                raise

            await callback(stage, champion_id)

        self._pgq = pgq
        # Run the manager loop in the background so callers can await
        # other work; close() will cancel it cleanly.
        self._manager_task = asyncio.create_task(pgq.run())
        log.info("EventQueue listener started on entrypoint=%s", DEFAULT_ENTRYPOINT)

    async def close(self) -> None:
        """Cancel the manager loop and close the PG connection."""
        if self._closed:
            return
        self._closed = True

        if self._manager_task is not None:
            self._manager_task.cancel()
            try:
                await self._manager_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._manager_task = None

        if self._conn is not None and not self._conn.is_closed():
            await self._conn.close()
        self._conn = None
        self._driver = None
        self._queries = None
        self._pgq = None
        log.info("EventQueue closed")


__all__ = ["EventQueue", "DEFAULT_ENTRYPOINT"]
