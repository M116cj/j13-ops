"""Mid-round checkpointing and resume support."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .db import PipelineDB


@dataclass
class CheckpointData:
    arena_name: str
    round_number: int
    symbol: str
    state: Dict[str, Any]
    created_at: float
    version: int


class Checkpointer:
    """Mid-round checkpoint manager.

    Integration:
        - CONSOLE_HOOK: checkpoint_interval_rounds, checkpoint_max_age_hours
        - DASHBOARD_HOOK: checkpoint_count, last_checkpoint_age
    """

    def __init__(self, db: PipelineDB) -> None:
        self._db = db
        self._interval: int = 5
        self._max_age_h: int = 48
        self._last_checkpoint: Optional[CheckpointData] = None
        self._checkpoint_count: int = 0

    def configure(self, config) -> None:
        self._interval = config.checkpoint_interval_rounds
        self._max_age_h = config.checkpoint_max_age_hours

    def should_checkpoint(self, round_number: int) -> bool:
        return round_number > 0 and round_number % self._interval == 0

    async def save(
        self,
        arena_name: str,
        round_number: int,
        symbol: str,
        state: Dict[str, Any],
    ) -> None:
        version = self._checkpoint_count + 1
        cp = CheckpointData(
            arena_name=arena_name,
            round_number=round_number,
            symbol=symbol,
            state=state,
            created_at=time.time(),
            version=version,
        )

        await self._db.execute(
            """INSERT INTO round_checkpoints (arena_id, round_number, checkpoint_data, contestants_done, total_contestants)
               VALUES ($1, $2, $3::jsonb, $4, $5)""",
            arena_name,
            round_number,
            json.dumps({"symbol": symbol, "state": state, "version": version}),
            0,
            0,
        )

        self._last_checkpoint = cp
        self._checkpoint_count += 1

    async def load(self, arena_name: str, symbol: str) -> Optional[CheckpointData]:
        row = await self._db.fetchrow(
            """SELECT arena_id, round_number, checkpoint_data,
                      EXTRACT(EPOCH FROM created_at) as created_at
               FROM round_checkpoints
               WHERE arena_id = $1
               ORDER BY created_at DESC LIMIT 1""",
            arena_name,
        )
        if not row:
            return None

        age_hours = (time.time() - row["created_at"]) / 3600
        if age_hours > self._max_age_h:
            return None

        data = json.loads(row["checkpoint_data"]) if isinstance(row["checkpoint_data"], str) else row["checkpoint_data"]
        return CheckpointData(
            arena_name=row["arena_id"],
            round_number=row["round_number"],
            symbol=data.get("symbol", ""),
            state=data.get("state", {}),
            created_at=row["created_at"],
            version=data.get("version", 0),
        )

    async def cleanup_stale(self) -> int:
        result = await self._db.execute(
            "DELETE FROM round_checkpoints WHERE created_at < NOW() - INTERVAL '$1 hours'",
            self._max_age_h,
        )
        try:
            return int(result.split()[-1])
        except (ValueError, IndexError):
            return 0

    def health_check(self) -> Dict:
        return {
            "checkpoint_count": self._checkpoint_count,
            "interval_rounds": self._interval,
            "max_age_hours": self._max_age_h,
            "last_checkpoint": (
                {
                    "arena": self._last_checkpoint.arena_name,
                    "round": self._last_checkpoint.round_number,
                    "age_s": round(time.time() - self._last_checkpoint.created_at, 1),
                }
                if self._last_checkpoint else None
            ),
        }
