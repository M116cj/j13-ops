"""Trade journal: append trades, query recent, generate daily summaries.

All writes go to the trade_journal table via PipelineDB.
Designed for post-trade logging by the live execution layer.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class TradeJournal:
    """Async trade journal backed by PostgreSQL.

    Usage:
        journal = TradeJournal(db)
        await journal.append_trade({...})
        recent = await journal.get_recent(20)
        summary = await journal.daily_summary()
    """

    TABLE = "trade_journal"

    def __init__(self, db: Any) -> None:
        """db: a PipelineDB instance (engine.components.db)."""
        self._db = db

    async def ensure_table(self) -> None:
        """Create trade_journal table if not exists."""
        await self._db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.TABLE} (
                id          BIGSERIAL PRIMARY KEY,
                ts          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                symbol      TEXT NOT NULL,
                side        TEXT NOT NULL,
                size_usd    DOUBLE PRECISION NOT NULL,
                entry_price DOUBLE PRECISION NOT NULL,
                exit_price  DOUBLE PRECISION,
                pnl         DOUBLE PRECISION,
                quant_class TEXT,
                regime      INTEGER,
                strategy_id TEXT,
                meta        JSONB DEFAULT '{{}}'::jsonb
            )
            """
        )

    async def append_trade(self, record: Dict[str, Any]) -> None:
        """Append a single trade record to the journal.

        Required keys: symbol, side, size_usd, entry_price.
        Optional keys: exit_price, pnl, quant_class, regime, strategy_id, meta.
        """
        await self._db.execute(
            f"""INSERT INTO {self.TABLE}
               (symbol, side, size_usd, entry_price, exit_price,
                pnl, quant_class, regime, strategy_id, meta)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb)""",
            record.get("symbol", ""),
            record.get("side", ""),
            float(record.get("size_usd", 0)),
            float(record.get("entry_price", 0)),
            record.get("exit_price"),
            record.get("pnl"),
            record.get("quant_class"),
            record.get("regime"),
            record.get("strategy_id"),
            json.dumps(record.get("meta", {})),
        )

    async def get_recent(self, n: int = 20) -> List[Dict[str, Any]]:
        """Fetch the N most recent trade records."""
        rows = await self._db.fetch(
            f"SELECT * FROM {self.TABLE} ORDER BY ts DESC LIMIT $1", n
        )
        return [dict(r) for r in rows]

    async def daily_summary(self, date: Optional[str] = None) -> Dict[str, Any]:
        """Generate a summary for a given date (default: today UTC).

        Returns: {date, total_trades, total_pnl, win_rate, by_class}.
        """
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        rows = await self._db.fetch(
            f"""SELECT quant_class, side, pnl
               FROM {self.TABLE}
               WHERE ts::date = $1::date""",
            date,
        )

        total = len(rows)
        if total == 0:
            return {
                "date": date,
                "total_trades": 0,
                "total_pnl": 0.0,
                "win_rate": 0.0,
                "by_class": {},
            }

        pnls = [float(r["pnl"]) for r in rows if r["pnl"] is not None]
        wins = sum(1 for p in pnls if p > 0)
        total_pnl = sum(pnls)

        # Breakdown by quant class
        by_class: Dict[str, Dict] = {}
        for r in rows:
            cls = r["quant_class"] or "unknown"
            if cls not in by_class:
                by_class[cls] = {"trades": 0, "pnl": 0.0, "wins": 0}
            by_class[cls]["trades"] += 1
            p = float(r["pnl"]) if r["pnl"] is not None else 0.0
            by_class[cls]["pnl"] += p
            if p > 0:
                by_class[cls]["wins"] += 1

        return {
            "date": date,
            "total_trades": total,
            "total_pnl": round(total_pnl, 4),
            "win_rate": round(wins / len(pnls), 4) if pnls else 0.0,
            "by_class": by_class,
        }
