"""Native RedisBloom service — V9 oneshot A3.

Connects to magi-bloom-1:6381 (Redis Stack with RedisBloom module).
Replaces the prior 215-line BITFIELD simulation with native BF.* commands.

Key: zangetsu:bloom:v9
Semantics:
- fail-open: if Redis unavailable, check() returns False (treat as "not seen"),
  add() is a no-op. Callers must not rely on bloom for correctness (it is a
  probabilistic accelerator only — authoritative dedup is in Postgres).

Usage:
    from services.bloom_service import bloom_init, bloom_check, bloom_add, bloom_count
    await bloom_init(capacity=200_000, fp_rate=0.001)
    if not await bloom_check(key):
        await bloom_add(key)
"""

import logging
import os
from typing import Optional

log = logging.getLogger("bloom_service")

_client = None
_bloom_key: str = "zangetsu:bloom:v9"
_initialized: bool = False
_using_redis: bool = False


async def bloom_init(capacity: int = 200_000, fp_rate: float = 0.001) -> None:
    """Initialize bloom filter on magi-bloom-1. Idempotent."""
    global _client, _initialized, _using_redis

    try:
        import redis.asyncio as aioredis
    except ImportError:
        log.warning("redis.asyncio not installed — bloom disabled")
        _initialized = True
        _using_redis = False
        return

    try:
        _client = aioredis.Redis(
            host=os.getenv("BLOOM_HOST", "127.0.0.1"),
            port=int(os.getenv("BLOOM_PORT", "6381")),
            decode_responses=False,
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
        )
        await _client.ping()

        try:
            await _client.execute_command("BF.RESERVE", _bloom_key, fp_rate, capacity)
            log.info(f"bloom: BF.RESERVE {_bloom_key} cap={capacity} fp={fp_rate}")
        except Exception as e:
            if "ERR item exists" in str(e):
                log.info(f"bloom: {_bloom_key} already exists, reusing")
            else:
                raise

        _using_redis = True
        _initialized = True
    except Exception as e:
        log.warning(f"bloom: Redis unavailable ({e}) — fail-open mode")
        _client = None
        _using_redis = False
        _initialized = True


async def bloom_check(key: str) -> bool:
    """Returns True if key probably in set. Fail-open: False on Redis error."""
    if not _using_redis or _client is None:
        return False
    try:
        result = await _client.execute_command("BF.EXISTS", _bloom_key, key)
        return bool(result)
    except Exception as e:
        log.debug(f"bloom_check({key}) failed: {e}")
        return False


async def bloom_add(key: str) -> None:
    """Add key to bloom. Fail-open: no-op on Redis error."""
    if not _using_redis or _client is None:
        return
    try:
        await _client.execute_command("BF.ADD", _bloom_key, key)
    except Exception as e:
        log.debug(f"bloom_add({key}) failed: {e}")


async def bloom_madd(keys: list) -> None:
    """Batch add. Fail-open."""
    if not _using_redis or _client is None or not keys:
        return
    try:
        await _client.execute_command("BF.MADD", _bloom_key, *keys)
    except Exception as e:
        log.debug(f"bloom_madd(len={len(keys)}) failed: {e}")


async def bloom_count() -> int:
    """Approximate number of items inserted."""
    if not _using_redis or _client is None:
        return 0
    try:
        info = await _client.execute_command("BF.INFO", _bloom_key)
        for i in range(0, len(info) - 1, 2):
            if info[i] in (b"Number of items inserted", "Number of items inserted"):
                return int(info[i + 1])
        return 0
    except Exception:
        return 0


async def bloom_reset() -> None:
    """Drop and recreate filter. Use with caution — irreversible."""
    global _initialized
    if not _using_redis or _client is None:
        return
    try:
        await _client.delete(_bloom_key)
        _initialized = False
    except Exception as e:
        log.warning(f"bloom_reset failed: {e}")
