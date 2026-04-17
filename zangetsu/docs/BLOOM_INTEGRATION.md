# Bloom Service Integration Guide

## Overview

Replace per-worker `BloomFilter` in `arena_pipeline.py` with the shared
Redis-backed `bloom_service`. All 4 A1 workers will share a single bloom
filter, eliminating:
- The 200-round DB re-sync (lines 470-488)
- 3,204+ duplicate `indicator_hash` entries in DB
- ~4x redundant memory usage (each worker allocating its own bitarray)

## File: `services/arena_pipeline.py`

### Step 1: Add import (top of file, near other imports)

```python
# Add after existing imports
from bloom_service import bloom_init, bloom_check, bloom_add, bloom_count, bloom_close
```

Place `bloom_service.py` in `services/` alongside `arena_pipeline.py`.

### Step 2: Remove the local BloomFilter class (lines 197-233)

Delete the entire `class BloomFilter:` block (lines 197-233). It is fully
replaced by the shared service.

### Step 3: Replace bloom initialization (line 411)

**Remove:**
```python
    bloom = BloomFilter(capacity=200_000, fp_rate=0.001)
```

**Replace with:**
```python
    await bloom_init(capacity=200_000, fp_rate=0.001)
```

### Step 4: Replace initial DB load (lines 412-424)

**Remove:**
```python
    try:
        existing_hashes = await db.fetch("""
            SELECT DISTINCT regime, passport->'arena1'->>'config_hash' as ch
            FROM champion_pipeline
            WHERE status NOT LIKE 'LEGACY%'
              AND passport->'arena1'->>'config_hash' IS NOT NULL
        """)
        for row in existing_hashes:
            bloom_key = f"{row['regime']}|{row['ch']}"
            bloom.add(bloom_key)
        log.info(f"Bloom filter loaded: {bloom.count} unique (regime,hash) pairs from ALL statuses")
    except Exception as e:
        log.warning(f"Bloom filter load failed: {e}")
```

**Replace with:**
```python
    try:
        existing_hashes = await db.fetch("""
            SELECT DISTINCT regime, passport->'arena1'->>'config_hash' as ch
            FROM champion_pipeline
            WHERE status NOT LIKE 'LEGACY%'
              AND passport->'arena1'->>'config_hash' IS NOT NULL
        """)
        from bloom_service import bloom_bulk_add
        _keys = [f"{row['regime']}|{row['ch']}" for row in existing_hashes]
        _loaded = await bloom_bulk_add(_keys)
        _count = await bloom_count()
        log.info(f"Bloom filter loaded: {_loaded} new + {_count} total entries (shared Redis)")
    except Exception as e:
        log.warning(f"Bloom filter load failed: {e}")
```

**Note:** Only the first worker to start will actually populate Redis. Subsequent
workers will find most keys already present (bloom_check returns True), so
`bloom_bulk_add` will add 0 new entries — this is correct behavior.

### Step 5: Remove the 200-round DB re-sync (lines 470-488)

**Delete the entire block:**
```python
        # ── Bloom periodic refresh: sync cross-worker discoveries every 200 rounds ──
        if round_number % 200 == 0 and round_number > 0:
            ...
```

This is no longer needed because all workers write to the same Redis bloom.
A key added by worker 2 is immediately visible to worker 0.

### Step 6: Replace `bloom_key in bloom` checks

**Line 568** (quick-path check):
```python
# Old:
            if _bloom_key in bloom:
# New:
            if await bloom_check(_bloom_key):
```

**Line 679** (full-backtest check):
```python
# Old:
        if _bloom_key in bloom:
# New:
        if await bloom_check(_bloom_key):
```

### Step 7: Replace `bloom.add()` calls

**Line 695:**
```python
# Old:
            bloom.add(_bloom_key)
# New:
            await bloom_add(_bloom_key)
```

**Line 702:**
```python
# Old:
        bloom.add(_bloom_key)
# New:
        await bloom_add(_bloom_key)
```

### Step 8: Replace `bloom.count` references

**Line 434** (startup log):
```python
# Old:
        f"bloom={bloom.count} entries, "
# New:
        f"bloom={await bloom_count()} entries, "
```

**Line 764** (stats log):
```python
# Old:
        f"bloom_size={bloom.count}"
# New:
        f"bloom_size={await bloom_count()}"
```

### Step 9: Add cleanup at shutdown

Near the end of `main()`, before the process exits:
```python
    await bloom_close()
```

## Deployment Notes

1. **Redis dependency**: Redis is already running on Alaya at localhost:6379
   (used by AKASHA). No additional setup needed.

2. **Fallback**: If Redis goes down, each worker automatically falls back to
   a local in-memory bloom filter. This degrades to V5 behavior (per-worker
   dedup) but does not crash.

3. **Memory**: The Redis bitfield uses ~360KB for 200k capacity at 0.1% FPR.
   Negligible compared to the ~1MB per worker previously.

4. **Key cleanup**: To reset the bloom (e.g., after schema changes):
   ```bash
   redis-cli DEL zangetsu:bloom:v9:bits zangetsu:bloom:v9:count
   ```

5. **Monitoring**: Check shared bloom health:
   ```bash
   redis-cli STRLEN zangetsu:bloom:v9:bits   # bytes used
   redis-cli GET zangetsu:bloom:v9:count      # approx entries
   ```
