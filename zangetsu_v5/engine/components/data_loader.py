"""Parquet data loading and DatasetSnapshot management.

Reads OHLCV candle data from Parquet files, validates columns,
and produces immutable DatasetSnapshot objects for arena consumption.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pyarrow.parquet as pq


@dataclass(frozen=True)
class DatasetSnapshot:
    """Immutable view of OHLCV data for a single symbol.

    All arrays share the same time axis (index 0 = earliest bar).
    """
    symbol: str
    timestamps: np.ndarray    # int64 epoch ms
    open: np.ndarray          # float64
    high: np.ndarray          # float64
    low: np.ndarray           # float64
    close: np.ndarray         # float64
    volume: np.ndarray        # float64
    bar_count: int = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "bar_count", len(self.timestamps))

    def slice(self, start: int, end: int) -> "DatasetSnapshot":
        """Return a sub-range snapshot (zero-copy views where possible)."""
        return DatasetSnapshot(
            symbol=self.symbol,
            timestamps=self.timestamps[start:end],
            open=self.open[start:end],
            high=self.high[start:end],
            low=self.low[start:end],
            close=self.close[start:end],
            volume=self.volume[start:end],
        )


REQUIRED_COLUMNS = {"timestamp", "open", "high", "low", "close", "volume"}


class DataLoader:
    """Load and cache Parquet OHLCV data per symbol.

    Integration:
        - CONSOLE_HOOK: parquet_dir, symbols
        - DASHBOARD_HOOK: loaded_symbols, total_bars, load_time_ms
    """

    def __init__(self, config) -> None:
        self._parquet_dir = Path(config.parquet_dir)
        self._symbols: List[str] = list(config.symbols)
        self._cache: Dict[str, DatasetSnapshot] = {}
        self._load_times: Dict[str, float] = {}

    def load(self, symbol: str, force: bool = False) -> DatasetSnapshot:
        """Load a single symbol from Parquet. Returns cached if available."""
        if not force and symbol in self._cache:
            return self._cache[symbol]

        t0 = time.monotonic()
        path = self._find_parquet(symbol)
        table = pq.read_table(str(path))

        # Validate columns
        columns = set(table.column_names)
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(f"[DataLoader] {symbol}: missing columns {missing}")

        snap = DatasetSnapshot(
            symbol=symbol,
            timestamps=table.column("timestamp").to_numpy().astype(np.int64),
            open=table.column("open").to_numpy().astype(np.float64),
            high=table.column("high").to_numpy().astype(np.float64),
            low=table.column("low").to_numpy().astype(np.float64),
            close=table.column("close").to_numpy().astype(np.float64),
            volume=table.column("volume").to_numpy().astype(np.float64),
        )

        self._cache[symbol] = snap
        self._load_times[symbol] = (time.monotonic() - t0) * 1000
        return snap

    def load_all(self) -> Dict[str, DatasetSnapshot]:
        """Load all configured symbols."""
        return {sym: self.load(sym) for sym in self._symbols}

    def _find_parquet(self, symbol: str) -> Path:
        """Locate parquet file for symbol. Tries common naming patterns."""
        candidates = [
            self._parquet_dir / f"{symbol}.parquet",
            self._parquet_dir / f"{symbol.lower()}.parquet",
            self._parquet_dir / symbol / "data.parquet",
        ]
        for c in candidates:
            if c.exists():
                return c
        raise FileNotFoundError(
            f"[DataLoader] No parquet found for {symbol} in {self._parquet_dir}"
        )

    def invalidate(self, symbol: Optional[str] = None) -> None:
        """Clear cache for symbol or all."""
        if symbol:
            self._cache.pop(symbol, None)
        else:
            self._cache.clear()

    # DASHBOARD_HOOK: data_loader_status
    def health_check(self) -> Dict:
        return {
            "loaded_symbols": list(self._cache.keys()),
            "total_bars": sum(s.bar_count for s in self._cache.values()),
            "load_times_ms": dict(self._load_times),
            "parquet_dir": str(self._parquet_dir),
            "configured_symbols": self._symbols,
        }
