"""V9 indicator pre-computation via SharedMemory.

Computes each (symbol, indicator, period) once in the parent process and
publishes the result into POSIX shared memory. Worker processes read the
pre-computed numpy views instead of recomputing per-parameter-combo.

Key format:
    zv9_ind_{symbol}_{indicator}_{period}

Typical pipeline wiring:

    from services.shared_data import SharedDataManager
    from services.indicator_precompute import (
        precompute_all_indicators, get_shared_indicator,
    )

    mgr = SharedDataManager()
    mgr.load_and_share(symbols, data_dir, n_bars=200000, train_ratio=0.70)

    # 21 directional indicators, 8 periods = 168 matrices per symbol
    precompute_all_indicators(mgr, symbols, DIRECTIONAL_CONFIGS)

    # Workers:
    vals = get_shared_indicator("BTCUSDT", "rsi", 14)
"""
from __future__ import annotations

import json
import logging
from multiprocessing import shared_memory
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

log = logging.getLogger(__name__)

SHM_PREFIX = "zv9_ind_"
DTYPE = np.float32
META_FILENAME = "shm_indicator_meta.json"

# Factor indicators are pre-computed upstream in data_cache; do not recompute
# them via the Rust engine here.
FACTOR_INDICATORS = frozenset({
    "normalized_atr", "realized_vol", "bollinger_bw",
    "relative_volume", "vwap_deviation",
    "funding_rate", "funding_zscore", "oi_change", "oi_divergence",
})

# In-process cache of attached shm blocks (per worker) so we don't re-open
# the same shared-memory segment on every call.
_ATTACHED: Dict[str, shared_memory.SharedMemory] = {}
_META: Dict[str, Any] = {}


# ─────────────────────────────────────────────────────────────────────
# Key helpers
# ─────────────────────────────────────────────────────────────────────

def _shm_key(symbol: str, indicator: str, period: int) -> str:
    return f"{SHM_PREFIX}{symbol}_{indicator}_{period}"


def _meta_key(symbol: str, indicator: str, period: int) -> str:
    return f"{symbol}|{indicator}|{period}"


# ─────────────────────────────────────────────────────────────────────
# Parent-side publish
# ─────────────────────────────────────────────────────────────────────

def _load_rust_compute():
    """Import the Rust indicator library lazily; return None if unavailable."""
    try:
        import zangetsu_indicators as zi  # type: ignore
        return zi
    except Exception as exc:  # pragma: no cover
        log.warning("zangetsu_indicators not importable: %s", exc)
        return None


def _publish_array(shm_name: str, arr: np.ndarray) -> shared_memory.SharedMemory:
    """Create (or replace) a shared memory segment and copy arr into it."""
    arr = np.ascontiguousarray(arr, dtype=DTYPE)
    # Unlink any stale segment from a prior run.
    try:
        old = shared_memory.SharedMemory(name=shm_name, create=False)
        old.close()
        old.unlink()
    except FileNotFoundError:
        log.debug(f"No stale shm segment to unlink: {shm_name}")

    shm = shared_memory.SharedMemory(name=shm_name, create=True, size=arr.nbytes)
    view = np.ndarray(arr.shape, dtype=DTYPE, buffer=shm.buf)
    view[:] = arr[:]
    return shm


def precompute_all_indicators(
    shm_manager,
    symbols: Sequence[str],
    indicator_configs: Iterable[Tuple[str, Dict[str, Any]]],
    *,
    data_dir: Optional[Path] = None,
    split: str = "train",
    factor_cache: Optional[Dict[str, Dict[str, np.ndarray]]] = None,
) -> Dict[str, Any]:
    """Compute every (symbol, indicator, period) once and publish to shm.

    Args:
        shm_manager:      an attached SharedDataManager (see services.shared_data)
        symbols:          list of trading symbols, e.g. ["BTCUSDT", ...]
        indicator_configs: iterable of (indicator_name, params_dict).
                          Each params_dict must contain a "period" key.
        data_dir:         directory where shm_indicator_meta.json is written.
                          Defaults to "data".
        split:            which split of the shared OHLCV to use. Workers usually
                          train against the "train" split, holdout against
                          "holdout". Default: "train".
        factor_cache:     optional dict[symbol][indicator] -> np.ndarray for
                          pre-computed factor indicators that are NOT produced by
                          the Rust engine (e.g. funding_rate). Keys must match
                          `FACTOR_INDICATORS`.

    Returns:
        A meta dict describing every published array. Also written to disk as
        {data_dir}/shm_indicator_meta.json for worker discovery.

    Notes:
        * Indicator matrices that fail to compute (or have zero MAD) are simply
          skipped — workers fall back to their own computation path in that
          case. We never raise on a single bad cell.
        * This function holds references to every SharedMemory block it creates
          inside shm_manager._shm_blocks, so cleanup is centralized in the
          parent process.
    """
    if data_dir is None:
        data_dir = Path("data")
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    zi = _load_rust_compute()

    meta: Dict[str, Any] = {
        "prefix": SHM_PREFIX,
        "dtype": "float32",
        "split": split,
        "engine_hash": "zv5_v9",
        "arrays": {},
    }

    published = 0
    skipped = 0

    # Defensive: materialize iterable once (caller may pass a generator).
    configs = list(indicator_configs)

    for sym in symbols:
        close = shm_manager.get_array(sym, "close", split)
        high = shm_manager.get_array(sym, "high", split)
        low = shm_manager.get_array(sym, "low", split)
        volume = shm_manager.get_array(sym, "volume", split)

        if close is None or high is None or low is None or volume is None:
            log.warning("precompute: missing OHLCV for %s — skipping", sym)
            continue

        for name, params in configs:
            period = int(params.get("period", 14))
            shm_name = _shm_key(sym, name, period)

            # Factor indicators: copy straight from external cache if provided.
            if name in FACTOR_INDICATORS:
                vals = None
                if factor_cache is not None:
                    vals = factor_cache.get(sym, {}).get(name)
                if vals is None or len(vals) == 0:
                    skipped += 1
                    continue
                arr = np.asarray(vals, dtype=DTYPE)
                # Align to OHLCV window length if factor is longer/shorter.
                if len(arr) != len(close):
                    n = min(len(arr), len(close))
                    arr = arr[-n:]
            else:
                if zi is None:
                    skipped += 1
                    continue
                try:
                    raw = zi.compute(name, {"period": period}, close, high, low, volume)
                    arr = np.asarray(raw, dtype=DTYPE)
                except Exception as exc:
                    log.debug("precompute %s(%s,p=%d) failed: %s", sym, name, period, exc)
                    skipped += 1
                    continue

            # Reject degenerate series — workers can't use them anyway.
            if arr.size == 0 or not np.isfinite(arr).any():
                skipped += 1
                continue

            try:
                shm = _publish_array(shm_name, arr)
            except Exception as exc:
                log.warning("precompute: shm publish failed for %s: %s", shm_name, exc)
                skipped += 1
                continue

            # Retain ownership so the parent can unlink on shutdown.
            try:
                shm_manager._shm_blocks[shm_name] = shm
            except AttributeError:
                # Older manager variants may not expose _shm_blocks; leak-safe
                # because we still track in the meta file for unlink().
                pass

            meta["arrays"][_meta_key(sym, name, period)] = {
                "shm_name": shm_name,
                "shape": list(arr.shape),
                "symbol": sym,
                "indicator": name,
                "period": period,
            }
            published += 1

    meta_path = data_dir / META_FILENAME
    with open(meta_path, "w") as f:
        json.dump(meta, f)

    log.info(
        "precompute_all_indicators: published=%d skipped=%d symbols=%d configs=%d -> %s",
        published, skipped, len(symbols), len(configs), meta_path,
    )
    return meta


# ─────────────────────────────────────────────────────────────────────
# Worker-side consume
# ─────────────────────────────────────────────────────────────────────

def attach_indicator_meta(data_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Load the indicator meta manifest (idempotent). Workers call this once."""
    global _META
    if _META:
        return _META
    if data_dir is None:
        data_dir = Path("data")
    meta_path = Path(data_dir) / META_FILENAME
    if not meta_path.exists():
        _META = {"arrays": {}}
        return _META
    with open(meta_path) as f:
        _META = json.load(f)
    return _META


def get_shared_indicator(
    symbol: str,
    name: str,
    period: int,
    *,
    data_dir: Optional[Path] = None,
) -> Optional[np.ndarray]:
    """Return a numpy view backed by shared memory, or None if unavailable.

    The caller MUST treat the returned array as read-only. Writes will corrupt
    every other worker's view.
    """
    meta = attach_indicator_meta(data_dir)
    info = meta.get("arrays", {}).get(_meta_key(symbol, name, int(period)))
    if info is None:
        return None

    shm_name = info["shm_name"]
    shm = _ATTACHED.get(shm_name)
    if shm is None:
        try:
            shm = shared_memory.SharedMemory(name=shm_name, create=False)
        except FileNotFoundError:
            return None
        _ATTACHED[shm_name] = shm

    try:
        arr = np.ndarray(tuple(info["shape"]), dtype=DTYPE, buffer=shm.buf)
    except Exception as exc:
        log.debug("get_shared_indicator: rebuild view failed %s: %s", shm_name, exc)
        return None
    return arr


def compute_or_get_indicator(
    symbol: str,
    name: str,
    period: int,
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    volume: np.ndarray,
    *,
    data_dir: Optional[Path] = None,
) -> Optional[np.ndarray]:
    """Shm-first lookup with a fallback to Rust compute.

    Intended drop-in for arena_pipeline's indicator_cache warm-up.
    Returns None if both the shm hit and the Rust fallback fail.
    """
    arr = get_shared_indicator(symbol, name, period, data_dir=data_dir)
    if arr is not None:
        return arr

    if name in FACTOR_INDICATORS:
        # Factor indicators are never recomputed here.
        return None

    zi = _load_rust_compute()
    if zi is None:
        return None
    try:
        raw = zi.compute(name, {"period": int(period)}, close, high, low, volume)
        return np.asarray(raw, dtype=DTYPE)
    except Exception as exc:
        log.debug("compute_or_get_indicator rust fallback failed %s/%s/%d: %s",
                  symbol, name, period, exc)
        return None


def cleanup_indicator_shm(data_dir: Optional[Path] = None) -> int:
    """Unlink every indicator segment listed in the meta file.

    Call from the parent process on shutdown. Returns the number of segments
    successfully unlinked. Safe to call multiple times.
    """
    meta = attach_indicator_meta(data_dir)
    unlinked = 0
    for info in meta.get("arrays", {}).values():
        shm_name = info.get("shm_name")
        if not shm_name:
            continue
        try:
            shm = _ATTACHED.pop(shm_name, None)
            if shm is None:
                shm = shared_memory.SharedMemory(name=shm_name, create=False)
            shm.close()
            shm.unlink()
            unlinked += 1
        except FileNotFoundError:
            continue
        except Exception as exc:
            log.debug("cleanup_indicator_shm: %s -> %s", shm_name, exc)
    return unlinked


# ─────────────────────────────────────────────────────────────────────
# Config helper — build the standard V9 directional x period grid
# ─────────────────────────────────────────────────────────────────────

# Mirror of arena_pipeline.DIRECTIONAL (kept in sync manually; see §X2).
DIRECTIONAL = [
    "rsi", "stochastic_k", "cci", "roc", "ppo", "cmo",
    "zscore", "trix", "tsi", "obv", "mfi", "vwap",
    "normalized_atr", "realized_vol", "bollinger_bw",
    "relative_volume", "vwap_deviation",
    "funding_rate", "funding_zscore", "oi_change", "oi_divergence",
]

DEFAULT_PERIODS = (7, 14, 20, 30, 48, 50, 100, 200)


def build_directional_configs(
    indicators: Optional[Sequence[str]] = None,
    periods: Optional[Sequence[int]] = None,
) -> List[Tuple[str, Dict[str, Any]]]:
    """Cartesian product of indicators x periods as (name, params) tuples."""
    inds = list(indicators) if indicators is not None else list(DIRECTIONAL)
    pers = list(periods) if periods is not None else list(DEFAULT_PERIODS)
    return [(nm, {"period": int(p)}) for nm in inds for p in pers]
