"""Database backed OHLCV loader.

Tier 0 component: fetches data from the Postgres instance on Alaya and
returns Polars DataFrames.  No pandas dependency is introduced.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional
from datetime import datetime

import psycopg2
import polars as pl

from .config import DatabaseConfig, load_config


@dataclass
class DataLoader:
    db_config: DatabaseConfig | None = None

    def _conn(self):
        cfg = self.db_config or load_config().database
        return psycopg2.connect(
            host=cfg.host,
            port=cfg.port,
            user=cfg.user,
            password=cfg.password,
            dbname=cfg.dbname,
        )

    def load_ohlcv(
        self,
        symbols: str | Iterable[str],
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> pl.DataFrame:
        """Load OHLCV data for one or more symbols.

        Parameters
        ----------
        symbols
            Single symbol or iterable of symbols.
        start / end
            Optional datetime bounds; if omitted the full series is pulled.
        limit
            Optional maximum rows to fetch (per query result).
        """

        sym_list = [symbols] if isinstance(symbols, str) else list(symbols)
        placeholders = ",".join(["%s"] * len(sym_list))
        clauses = [f"symbol IN ({placeholders})"]
        params: list = sym_list.copy()
        if start is not None:
            clauses.append("timestamp >= %s")
            params.append(start)
        if end is not None:
            clauses.append("timestamp <= %s")
            params.append(end)

        where_sql = " AND ".join(clauses)
        sql = (
            "SELECT symbol, timestamp, open, high, low, close, volume "
            "FROM ohlcv_1m WHERE "
            + where_sql
            + " ORDER BY timestamp"
        )
        if limit is not None:
            sql += " LIMIT %s"
            params.append(limit)

        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        if not rows:
            return pl.DataFrame(
                {"symbol": [], "timestamp": [], "open": [], "high": [], "low": [], "close": [], "volume": []}
            )

        df = pl.DataFrame(
            rows,
            schema=["symbol", "timestamp", "open", "high", "low", "close", "volume"],
        )
        return df.with_columns(pl.col("timestamp").cast(pl.Datetime))


__all__ = ["DataLoader"]

