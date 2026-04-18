"""Shared memory data loader for multi-worker OHLCV access.

Usage:
    # Parent process (before spawning workers):
    from services.shared_data import SharedDataManager
    mgr = SharedDataManager()
    mgr.load_and_share(symbols, data_dir, n_bars=200000, train_ratio=0.70)

    # Worker process:
    mgr = SharedDataManager()
    mgr.attach()
    close = mgr.get_array("BTCUSDT", "close", "train")
"""
import numpy as np
from multiprocessing import shared_memory
from pathlib import Path
import json
import logging

log = logging.getLogger(__name__)

SHM_PREFIX = "zv9_"
DTYPE = np.float32


class SharedDataManager:
    def __init__(self):
        self._shm_blocks = {}
        self._meta = {}

    def load_and_share(self, symbols: list, data_dir: Path, n_bars: int = 200000,
                       train_ratio: float = 0.70):
        """Load OHLCV from parquet, create shared memory blocks."""
        import polars as pl

        meta = {"symbols": symbols, "n_bars": n_bars, "train_ratio": train_ratio, "arrays": {}}

        for sym in symbols:
            path = data_dir / "ohlcv" / f"{sym}.parquet"
            if not path.exists():
                continue

            df = pl.read_parquet(str(path))
            cols = ["close", "high", "low", "volume"]
            if "open" in df.columns:
                cols.append("open")

            w = min(n_bars, len(df))
            split = int(w * train_ratio)

            for col in cols:
                arr = df[col].to_numpy()[-w:].astype(DTYPE)

                # Create shared memory
                shm_name = f"{SHM_PREFIX}{sym}_{col}"
                try:
                    old = shared_memory.SharedMemory(name=shm_name, create=False)
                    old.close()
                    old.unlink()
                except FileNotFoundError:
                    log.debug(f"No stale shm segment to unlink: {shm_name}")

                shm = shared_memory.SharedMemory(name=shm_name, create=True, size=arr.nbytes)
                shared_arr = np.ndarray(arr.shape, dtype=DTYPE, buffer=shm.buf)
                shared_arr[:] = arr[:]

                self._shm_blocks[shm_name] = shm
                meta["arrays"][f"{sym}_{col}"] = {
                    "shm_name": shm_name,
                    "shape": list(arr.shape),
                    "split": split,
                }

        self._meta = meta
        # Save meta for workers to discover
        meta_path = data_dir / "shm_meta.json"
        with open(meta_path, "w") as f:
            json.dump(meta, f)

        log.info(f"SharedDataManager: {len(self._shm_blocks)} arrays shared for {len(symbols)} symbols")

    def attach(self, data_dir: Path = None):
        """Attach to existing shared memory (called by workers)."""
        if data_dir is None:
            data_dir = Path("data")
        meta_path = data_dir / "shm_meta.json"
        with open(meta_path) as f:
            self._meta = json.load(f)

    def get_array(self, symbol: str, col: str, split: str = "train") -> np.ndarray:
        """Get a numpy view of shared data."""
        key = f"{symbol}_{col}"
        info = self._meta["arrays"].get(key)
        if info is None:
            return None

        shm_name = info["shm_name"]
        if shm_name not in self._shm_blocks:
            shm = shared_memory.SharedMemory(name=shm_name, create=False)
            self._shm_blocks[shm_name] = shm

        shm = self._shm_blocks[shm_name]
        arr = np.ndarray(tuple(info["shape"]), dtype=DTYPE, buffer=shm.buf)

        sp = info["split"]
        if split == "train":
            return arr[:sp]
        elif split == "holdout":
            return arr[sp:]
        return arr

    def cleanup(self):
        """Unlink all shared memory (call from parent on exit)."""
        for name, shm in self._shm_blocks.items():
            try:
                shm.close()
                shm.unlink()
            except Exception as e:
                log.debug(f"shm cleanup failed for {name}: {e}")
        self._shm_blocks.clear()
