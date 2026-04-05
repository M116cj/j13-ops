"""Live trade journal: append trades to the card's live_journal.parquet (C29).

Writes are atomic: read → append → write_parquet (temp) → rename.
This prevents partial-write corruption if the process is killed mid-write.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import polars as pl

from zangetsu_v3.cards.exporter import DEFAULT_JOURNAL_SCHEMA


@dataclass
class TradeRecord:
    timestamp: str          # ISO-8601
    symbol: str
    side: str               # "buy" | "sell"
    quantity: float
    entry_price: float
    exit_price: float
    pnl: float
    pnl_pct: float
    max_drawdown: float
    regime_id: int
    card_version: str
    slippage_bps: float
    funding: float
    hold_bars: int = 0
    notes: str = ""

    def to_row(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "max_drawdown": self.max_drawdown,
            "regime_id": self.regime_id,
            "card_version": self.card_version,
            "slippage_bps": self.slippage_bps,
            "funding": self.funding,
            "hold_bars": self.hold_bars,
            "notes": self.notes,
        }


class LiveJournal:
    """Append-only trade journal backed by a parquet file.

    Parameters
    ----------
    journal_path:
        Path to ``live_journal.parquet`` produced by CardExporter.
    """

    _SCHEMA = {
        "timestamp": pl.Utf8,
        "symbol": pl.Utf8,
        "side": pl.Utf8,
        "quantity": pl.Float64,
        "entry_price": pl.Float64,
        "exit_price": pl.Float64,
        "pnl": pl.Float64,
        "pnl_pct": pl.Float64,
        "max_drawdown": pl.Float64,
        "regime_id": pl.Int64,
        "card_version": pl.Utf8,
        "slippage_bps": pl.Float64,
        "funding": pl.Float64,
        "hold_bars": pl.Int64,
        "notes": pl.Utf8,
    }

    def __init__(self, journal_path: str | Path) -> None:
        self._path = Path(journal_path)
        if not self._path.exists():
            pl.DataFrame(schema=self._SCHEMA).write_parquet(self._path)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def append(self, record: TradeRecord) -> None:
        """Atomically append one trade record to the journal."""
        self._atomic_append([record.to_row()])

    def append_many(self, records: list[TradeRecord]) -> None:
        """Atomically append multiple trade records."""
        if not records:
            return
        self._atomic_append([r.to_row() for r in records])

    def read(self) -> pl.DataFrame:
        """Return the full journal as a Polars DataFrame."""
        return pl.read_parquet(self._path)

    def stats(self) -> dict:
        """Summary statistics: n_trades, total_pnl, win_rate."""
        df = self.read()
        if len(df) == 0:
            return {"n_trades": 0, "total_pnl": 0.0, "win_rate": 0.0}
        n = len(df)
        total_pnl = float(df["pnl"].sum())
        win_rate = float((df["pnl"] > 0).sum()) / n
        return {"n_trades": n, "total_pnl": total_pnl, "win_rate": win_rate}

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _atomic_append(self, rows: list[Dict[str, Any]]) -> None:
        existing = pl.read_parquet(self._path)
        new_rows = pl.DataFrame(rows)
        new_rows = new_rows.cast({c: d for c, d in self._SCHEMA.items() if c in new_rows.columns})
        if existing.is_empty():
            combined = new_rows.select(self._SCHEMA.keys())
        else:
            combined = pl.concat([existing, new_rows], how="vertical")

        tmp = self._path.with_suffix(".tmp.parquet")
        combined.write_parquet(tmp)
        os.replace(tmp, self._path)  # atomic on POSIX


__all__ = ["LiveJournal", "TradeRecord"]
