"""gpu_config.py — VRAM budget between Ollama (LLM) and cuDF/RAPIDS.

Coexistence policy for the Alaya GPU
------------------------------------
* Ollama (Gemma models for Markl/Calcifer) holds an always-on reservation.
* cuDF / RAPIDS pool gets the remainder, capped to ``CUDF_MAX_VRAM_GB``.
* If the detected free VRAM is too small to satisfy both budgets, we
  fall back to the smaller of ``free - reserved`` and the hard cap and
  emit a warning — never silently over-commit.

Public API
----------
* ``get_cuda_memory_limit() -> int``: returns the cuDF pool size in bytes.
* ``setup_rmm_pool() -> int``: initialises the RAPIDS RMM pool and
  returns the actual pool size in bytes.

Both functions degrade gracefully when ``pynvml`` or ``rmm`` are not
installed (e.g. on developer laptops) — they log and return ``0``
rather than raising.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────
OLLAMA_RESERVED_VRAM_GB: float = 2.5
CUDF_MAX_VRAM_GB: float = 5.0

# Minimum usable pool size. Below this, we refuse to initialise RMM.
_MIN_POOL_GB: float = 0.5
_GB: int = 1024 ** 3


# ── VRAM detection ───────────────────────────────────────────────────
def _detect_free_vram_bytes() -> Optional[int]:
    """Return free VRAM on GPU 0 in bytes, or ``None`` if unavailable."""
    try:
        import pynvml  # type: ignore
    except ImportError:
        log.warning("pynvml not installed; cannot detect VRAM")
        return None

    try:
        pynvml.nvmlInit()
    except Exception as exc:  # pragma: no cover - hardware dependent
        log.warning("nvmlInit failed: %s", exc)
        return None

    try:
        count = pynvml.nvmlDeviceGetCount()
        if count == 0:
            log.warning("no CUDA devices reported by NVML")
            return None
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        return int(info.free)
    except Exception as exc:  # pragma: no cover - hardware dependent
        log.warning("NVML query failed: %s", exc)
        return None
    finally:
        try:
            pynvml.nvmlShutdown()
        except Exception:  # pragma: no cover
            pass


# ── Budget computation ───────────────────────────────────────────────
def get_cuda_memory_limit() -> int:
    """Return the cuDF/RAPIDS pool size in bytes.

    Policy: ``min(CUDF_MAX_VRAM_GB, free_vram - OLLAMA_RESERVED_VRAM_GB)``.
    Returns ``0`` if the GPU is not detected or the budget is too small.
    """
    free_bytes = _detect_free_vram_bytes()
    hard_cap = int(CUDF_MAX_VRAM_GB * _GB)

    if free_bytes is None:
        # No GPU / NVML — caller should skip RMM setup. Use hard cap as
        # the upper bound for any downstream config without committing.
        return 0

    reserved = int(OLLAMA_RESERVED_VRAM_GB * _GB)
    usable = free_bytes - reserved

    if usable < int(_MIN_POOL_GB * _GB):
        log.warning(
            "insufficient VRAM: free=%.2fGB reserved=%.2fGB usable=%.2fGB < %.2fGB minimum",
            free_bytes / _GB, reserved / _GB, usable / _GB, _MIN_POOL_GB,
        )
        return 0

    limit = min(hard_cap, usable)
    log.info(
        "cuDF pool budget: %.2fGB (free=%.2fGB, ollama_reserved=%.2fGB, cap=%.2fGB)",
        limit / _GB, free_bytes / _GB, reserved / _GB, hard_cap / _GB,
    )
    return limit


# ── RMM pool initialisation ──────────────────────────────────────────
def setup_rmm_pool() -> int:
    """Initialise the RAPIDS RMM pool with the computed limit.

    Returns the pool size in bytes actually configured (``0`` if skipped).
    Safe to call multiple times — subsequent calls re-initialise RMM
    which is what RAPIDS expects before cuDF/cuPy use.
    """
    limit = get_cuda_memory_limit()
    if limit <= 0:
        log.warning("skipping RMM pool init (no budget)")
        return 0

    try:
        import rmm  # type: ignore
    except ImportError:
        log.warning("rmm not installed; cannot initialise pool")
        return 0

    try:
        rmm.reinitialize(
            pool_allocator=True,
            managed_memory=False,
            initial_pool_size=limit,
            maximum_pool_size=limit,
        )
    except Exception as exc:  # pragma: no cover - hardware dependent
        log.error("rmm.reinitialize failed: %s", exc)
        return 0

    log.info("RMM pool initialised: %.2fGB", limit / _GB)
    return limit


__all__ = [
    "OLLAMA_RESERVED_VRAM_GB",
    "CUDF_MAX_VRAM_GB",
    "get_cuda_memory_limit",
    "setup_rmm_pool",
]
