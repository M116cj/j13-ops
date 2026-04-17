"""
Shared Bloom Filter Service — Redis-backed with local fallback.

Replaces per-worker in-memory BloomFilter with a single shared bloom
stored in Redis BITFIELD. All 4 A1 workers share the same filter,
eliminating the 200-round DB re-sync and the 3,204 duplicate inserts.

Key prefix: zangetsu:bloom:v6:
Requires: redis[hiredis] (async via redis.asyncio)

Usage:
    from bloom_service import bloom_init, bloom_check, bloom_add, bloom_count

    await bloom_init(capacity=200_000, fp_rate=0.001)
    if not await bloom_check(f"{regime}|{config_hash}"):
        await bloom_add(f"{regime}|{config_hash}")
"""

import hashlib
import math
import logging
from typing import Optional

log = logging.getLogger("bloom_service")

# ── Module state ──
_redis = None  # redis.asyncio.Redis instance or None
_local: Optional["LocalBloomFilter"] = None  # fallback
_size: int = 0  # bit array size
_k: int = 0  # number of hash functions
_count_key: str = ""  # Redis key for approximate count
_bits_key: str = ""  # Redis key for the bit array
_initialized: bool = False
_using_redis: bool = False

PREFIX = "zangetsu:bloom:v6:"


# ── Math helpers (same as original BloomFilter) ──

def _optimal_size(n: int, p: float) -> int:
    m = -n * math.log(p) / (math.log(2) ** 2)
    return int(m) + 1


def _optimal_k(m: int, n: int) -> int:
    k = (m / max(n, 1)) * math.log(2)
    return max(1, int(k))


def _hashes(key: str, k: int, size: int) -> list[int]:
    """Double-hashing scheme: h1=MD5, h2=SHA1 — same as original."""
    h1 = int(hashlib.md5(key.encode()).hexdigest(), 16)
    h2 = int(hashlib.sha1(key.encode()).hexdigest(), 16)
    return [(h1 + i * h2) % size for i in range(k)]


# ── Local fallback ──

class LocalBloomFilter:
    """In-memory bloom filter — used when Redis is unavailable."""

    def __init__(self, size: int, k: int):
        self.size = size
        self.k = k
        self.bits = bytearray(size // 8 + 1)
        self.count = 0

    def add(self, key: str) -> None:
        for pos in _hashes(key, self.k, self.size):
            self.bits[pos // 8] |= (1 << (pos % 8))
        self.count += 1

    def check(self, key: str) -> bool:
        return all(
            self.bits[pos // 8] & (1 << (pos % 8))
            for pos in _hashes(key, self.k, self.size)
        )


# ── Public API ──

async def bloom_init(capacity: int = 200_000, fp_rate: float = 0.001) -> None:
    """Initialize the shared bloom filter. Tries Redis first, falls back to local."""
    global _redis, _local, _size, _k, _count_key, _bits_key, _initialized, _using_redis

    _size = _optimal_size(capacity, fp_rate)
    _k = _optimal_k(_size, capacity)
    _bits_key = f"{PREFIX}bits"
    _count_key = f"{PREFIX}count"

    # Try Redis connection
    try:
        import redis.asyncio as aioredis
        _redis = aioredis.Redis(
            host="localhost",
            port=6379,
            db=0,
            decode_responses=False,
            socket_connect_timeout=3,
            socket_timeout=2,
            retry_on_timeout=True,
        )
        await _redis.ping()
        _using_redis = True
        _local = None

        # Get current count from Redis (survives restarts)
        raw = await _redis.get(_count_key)
        current = int(raw) if raw else 0
        log.info(
            f"Bloom service initialized — Redis-backed | "
            f"size={_size} bits ({_size // 8 // 1024} KB), k={_k}, "
            f"existing entries~={current}"
        )
    except Exception as e:
        log.warning(f"Redis unavailable ({e}), falling back to local bloom filter")
        _redis = None
        _using_redis = False
        _local = LocalBloomFilter(_size, _k)

    _initialized = True


async def bloom_check(key: str) -> bool:
    """Returns True if key probably exists in the filter."""
    if not _initialized:
        raise RuntimeError("bloom_init() must be called first")

    if _using_redis and _redis is not None:
        try:
            positions = _hashes(key, _k, _size)
            # Pipeline GETBIT for all k positions
            pipe = _redis.pipeline(transaction=False)
            for pos in positions:
                pipe.getbit(_bits_key, pos)
            results = await pipe.execute()
            return all(results)
        except Exception as e:
            log.warning(f"Redis bloom_check failed ({e}), checking local fallback")
            if _local is not None:
                return _local.check(key)
            return False  # safe default: treat as not seen → may produce duplicate, but won't lose data

    if _local is not None:
        return _local.check(key)
    return False


async def bloom_add(key: str) -> None:
    """Add key to the bloom filter."""
    if not _initialized:
        raise RuntimeError("bloom_init() must be called first")

    if _using_redis and _redis is not None:
        try:
            positions = _hashes(key, _k, _size)
            pipe = _redis.pipeline(transaction=False)
            for pos in positions:
                pipe.setbit(_bits_key, pos, 1)
            pipe.incr(_count_key)
            await pipe.execute()
            return
        except Exception as e:
            log.warning(f"Redis bloom_add failed ({e}), adding to local fallback")
            # Fall through to local

    if _local is not None:
        _local.add(key)


async def bloom_count() -> int:
    """Returns approximate count of entries added."""
    if not _initialized:
        return 0

    if _using_redis and _redis is not None:
        try:
            raw = await _redis.get(_count_key)
            return int(raw) if raw else 0
        except Exception:
            pass

    if _local is not None:
        return _local.count
    return 0


async def bloom_bulk_add(keys: list[str]) -> int:
    """Bulk-add keys, returns count of newly added (not already present).

    Used during initial load from DB to populate the shared filter.
    """
    if not _initialized:
        raise RuntimeError("bloom_init() must be called first")

    added = 0
    for key in keys:
        if not await bloom_check(key):
            await bloom_add(key)
            added += 1
    return added


async def bloom_close() -> None:
    """Cleanup Redis connection."""
    global _redis, _initialized, _using_redis
    if _redis is not None:
        try:
            await _redis.close()
        except Exception:
            pass
    _redis = None
    _initialized = False
    _using_redis = False
