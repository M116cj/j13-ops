"""Audit trail helper for pipeline status transitions.

Writes every champion status change to pipeline_audit_log.
"""
import json
import logging
import asyncpg

logger = logging.getLogger(__name__)


async def log_transition(
    db: asyncpg.Connection,
    champion_id: int,
    old_status: str,
    new_status: str,
    worker_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Insert one row into pipeline_audit_log.

    Best-effort: logs warning on failure but never raises,
    so audit issues cannot break the pipeline.
    """
    try:
        await db.execute(
            """
            INSERT INTO pipeline_audit_log
                (champion_id, old_status, new_status, worker_id, metadata)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            """,
            champion_id,
            old_status,
            new_status,
            worker_id,
            json.dumps(metadata) if metadata else None,
        )
    except Exception as exc:
        logger.warning("audit log write failed for champion %s: %s", champion_id, exc)
