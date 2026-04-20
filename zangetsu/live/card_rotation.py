"""Card rotation — hot-swap deployed cards when Arena 5 ELO #1 changes.

When a DEPLOYABLE strategy's ELO surpasses the current DEPLOYED strategy
in the same regime, trigger a three-phase rotation:
  Phase 1: Mark old card RETIRING (stop new entries)
  Phase 2: Wait for flat (no open positions)
  Phase 3: Swap — old→RETIRED, new→DEPLOYED
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

LOG = logging.getLogger("zangetsu.card_rotation")


@dataclass
class RotationEvent:
    """Record of a pending or completed rotation."""
    regime: str
    old_id: int
    new_id: int
    old_elo: float
    new_elo: float
    started_at: float
    completed_at: Optional[float] = None
    status: str = "PENDING"  # PENDING, RETIRING, COMPLETED, FAILED


class CardRotator:
    """Monitors ELO rankings and rotates deployed cards when #1 changes.

    Uses asyncpg via PipelineDB for all DB access, consistent with the
    rest of the Zangetsu V5 engine.
    """

    def __init__(self, db: Any, timeout_minutes: int = 120) -> None:
        """
        Args:
            db: PipelineDB instance (engine.components.db).
            timeout_minutes: max wait for flat before forced swap.
        """
        self._db = db
        self._timeout_minutes = timeout_minutes
        self._pending: Dict[str, RotationEvent] = {}  # regime -> event

    async def ensure_table(self) -> None:
        """Create rotation_log table if not exists."""
        async with self._db.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS rotation_log (
                    id          SERIAL PRIMARY KEY,
                    ts          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    regime      TEXT NOT NULL,
                    old_id      INTEGER NOT NULL,
                    new_id      INTEGER NOT NULL,
                    old_elo     DOUBLE PRECISION,
                    new_elo     DOUBLE PRECISION,
                    status      TEXT NOT NULL DEFAULT 'PENDING',
                    elapsed_s   DOUBLE PRECISION
                )
            """)

    async def check_rotation(self) -> List[Tuple[str, int, int, float, float]]:
        """Check if any regime's ELO #1 changed.

        Returns list of (regime, old_id, new_id, old_elo, new_elo) for
        regimes where a DEPLOYABLE card has higher ELO than the DEPLOYED one.
        """
        async with self._db.acquire() as conn:
            rows = await conn.fetch("""
                WITH deployed AS (
                    SELECT id, regime,
                           (passport->'arena5'->>'elo_rating')::float AS elo
                    FROM champion_pipeline_fresh
                    WHERE status = 'DEPLOYED'
                ),
                challengers AS (
                    SELECT id, regime,
                           (passport->'arena5'->>'elo_rating')::float AS elo
                    FROM champion_pipeline_fresh
                    WHERE status = 'DEPLOYABLE'
                )
                SELECT d.regime, d.id AS old_id, c.id AS new_id,
                       d.elo AS old_elo, c.elo AS new_elo
                FROM deployed d
                JOIN challengers c ON d.regime = c.regime
                WHERE c.elo > d.elo
                ORDER BY (c.elo - d.elo) DESC
            """)
        return [
            (r["regime"], r["old_id"], r["new_id"], r["old_elo"], r["new_elo"])
            for r in rows
        ]

    async def execute_rotation(
        self, regime: str, old_id: int, new_id: int,
        old_elo: float = 0.0, new_elo: float = 0.0,
    ) -> bool:
        """Three-phase rotation: stop entries -> wait flat -> swap.

        Returns True if rotation completed, False if timed out or failed.
        """
        event = RotationEvent(
            regime=regime, old_id=old_id, new_id=new_id,
            old_elo=old_elo, new_elo=new_elo, started_at=time.time(),
        )
        self._pending[regime] = event

        try:
            # Phase 1: Stop old card from opening new positions
            async with self._db.acquire() as conn:
                await conn.execute(
                    "UPDATE champion_pipeline_fresh SET status='RETIRING' WHERE id=$1",
                    old_id,
                )
            event.status = "RETIRING"
            LOG.info("Rotation P1: %s old=%s → RETIRING (elo %.0f → %.0f)",
                     regime, old_id, old_elo, new_elo)

            # Phase 2: Wait for flat (check position tracker)
            deadline = time.time() + self._timeout_minutes * 60
            while time.time() < deadline:
                if await self._is_flat(regime, old_id):
                    break
                await asyncio.sleep(10)
            else:
                LOG.warning("Rotation timeout: %s old=%s forced swap after %d min",
                            regime, old_id, self._timeout_minutes)

            # Phase 3: Swap
            async with self._db.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        "UPDATE champion_pipeline_fresh SET status='RETIRED' WHERE id=$1",
                        old_id,
                    )
                    await conn.execute(
                        "UPDATE champion_pipeline_fresh SET status='DEPLOYED' WHERE id=$1",
                        new_id,
                    )
            event.status = "COMPLETED"
            event.completed_at = time.time()
            LOG.info("Rotation complete: %s new=%s (%.1fs)",
                     regime, new_id, event.completed_at - event.started_at)

            # Log to DB
            await self._log_rotation(event)
            del self._pending[regime]
            return True

        except Exception:
            event.status = "FAILED"
            LOG.exception("Rotation failed: %s old=%s new=%s", regime, old_id, new_id)
            # Rollback: restore old card to DEPLOYED if swap didn't complete
            try:
                async with self._db.acquire() as conn:
                    await conn.execute(
                        "UPDATE champion_pipeline_fresh SET status='DEPLOYED' "
                        "WHERE id=$1 AND status='RETIRING'", old_id,
                    )
            except Exception:
                LOG.exception("Rotation rollback also failed for %s", old_id)
            del self._pending[regime]
            return False

    async def _is_flat(self, regime: str, card_id: int) -> bool:
        """Check if card has no open positions (via paper_trades table)."""
        async with self._db.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT COUNT(*) AS open_count
                FROM paper_trades
                WHERE card_id = $1::text AND exit_price IS NULL
            """, str(card_id))
        return row is None or row["open_count"] == 0

    async def _log_rotation(self, event: RotationEvent) -> None:
        """Persist rotation event to rotation_log."""
        elapsed = (event.completed_at or time.time()) - event.started_at
        async with self._db.acquire() as conn:
            await conn.execute("""
                INSERT INTO rotation_log (regime, old_id, new_id, old_elo, new_elo, status, elapsed_s)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, event.regime, event.old_id, event.new_id,
                event.old_elo, event.new_elo, event.status, elapsed)

    @property
    def pending_rotations(self) -> Dict[str, RotationEvent]:
        """Currently in-progress rotations by regime."""
        return dict(self._pending)

    def health_check(self) -> Dict[str, Any]:
        """Dashboard hook: rotation status."""
        return {
            "pending_count": len(self._pending),
            "pending_regimes": list(self._pending.keys()),
        }
