"""V10 Factor Zoo — persistence layer for discovered alpha expressions.

Provides:
- store_alpha(result, metrics, symbol, regime): insert new alpha
- query_alphas(regime, symbol, ic_min, n_results): retrieve top alphas
- correlation_matrix(alpha_ids): compute pairwise correlation
- diversify_select(top_k, max_corr): select uncorrelated subset
- prune_stale(days_threshold): remove alphas with decaying IC
"""
from __future__ import annotations
import os
import json
import hashlib
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

import numpy as np
import asyncpg

log = logging.getLogger(__name__)


DSN = os.environ.get(
    "ZV5_DSN",
    f"postgresql://zangetsu:{os.environ['ZV5_DB_PASSWORD']}@127.0.0.1:5432/zangetsu"
)


@dataclass
class ZooEntry:
    """Summary of an alpha in the factor zoo."""
    id: int
    alpha_hash: str
    regime: str
    symbol: str
    formula: str
    ast_json: list
    ic: float
    ic_pvalue: float
    dsr: float
    depth: int
    used_indicators: List[str]
    used_operators: List[str]
    generation: int
    created_at: datetime
    card_status: str

    @classmethod
    def from_row(cls, row: dict) -> "ZooEntry":
        passport = row.get('passport', {})
        if isinstance(passport, str):
            passport = json.loads(passport)
        alpha_expr = passport.get('arena1', {}).get('alpha_expression', {})
        return cls(
            id=row['id'],
            alpha_hash=row.get('alpha_hash', alpha_expr.get('alpha_hash', '')),
            regime=row.get('regime', ''),
            symbol=alpha_expr.get('symbol', passport.get('arena1', {}).get('symbol', '')),
            formula=alpha_expr.get('formula', ''),
            ast_json=alpha_expr.get('ast_json', []),
            ic=float(alpha_expr.get('ic', 0.0)),
            ic_pvalue=float(alpha_expr.get('ic_pvalue', 1.0)),
            dsr=float(alpha_expr.get('dsr', 0.0)),
            depth=int(alpha_expr.get('depth', 0)),
            used_indicators=alpha_expr.get('used_indicators', []),
            used_operators=alpha_expr.get('used_operators', []),
            generation=int(alpha_expr.get('generation', 0)),
            created_at=row.get('created_at', datetime.now(timezone.utc)),
            card_status=row.get('card_status', 'DISCOVERED'),
        )


class FactorZoo:
    """Async PostgreSQL-backed alpha storage."""

    def __init__(self, dsn: str = DSN):
        self.dsn = dsn

    async def store(self, alpha_result, symbol: str, regime: str,
                    arena1_metrics: dict = None) -> int:
        """Insert alpha into factor zoo. Returns inserted champion_pipeline id."""
        arena1_metrics = arena1_metrics or {}

        passport = {
            "arena1": {
                "alpha_expression": alpha_result.to_dict() if hasattr(alpha_result, 'to_dict') else alpha_result,
                "symbol": symbol,
                "regime": regime,
                **arena1_metrics
            },
            "factor_zoo": {
                "inserted_at": datetime.now(timezone.utc).isoformat(),
                "version": "v10",
            }
        }

        alpha_hash = alpha_result.alpha_hash if hasattr(alpha_result, 'alpha_hash') else alpha_result.get('alpha_hash', '')
        indicator_hash = f"alpha_{alpha_hash}_{symbol}_{regime}"
        ic = float(alpha_result.ic if hasattr(alpha_result, 'ic') else alpha_result.get('ic', 0.0))

        conn = await asyncpg.connect(self.dsn)
        try:
            row_id = await conn.fetchval(
                """
                INSERT INTO champion_pipeline (
                    regime, indicator_hash, alpha_hash, status, n_indicators,
                    arena1_score, arena1_win_rate, arena1_pnl, arena1_n_trades,
                    passport, engine_hash, card_status, evolution_operator,
                    created_at, updated_at
                ) VALUES (
                    $1, $2, $3, 'DEPLOYABLE', 1,
                    $4, 0.5, 0.0, 0,
                    $5::jsonb, 'zv5_v10_alpha', 'DISCOVERED', 'alpha_engine_v10',
                    NOW(), NOW()
                )
                RETURNING id
                """,
                regime, indicator_hash, alpha_hash,
                abs(ic), json.dumps(passport, default=str)
            )
            log.info(f"FactorZoo: stored alpha {alpha_hash} id={row_id} ic={ic:.4f}")
            return row_id
        finally:
            await conn.close()

    async def query(self, regime: Optional[str] = None,
                    symbol: Optional[str] = None,
                    ic_min: float = 0.02,
                    n_results: int = 100,
                    card_status: str = 'DISCOVERED') -> List[ZooEntry]:
        """Query alphas matching criteria, sorted by |IC| descending."""
        conn = await asyncpg.connect(self.dsn)
        try:
            sql = """
            SELECT id, regime, indicator_hash, alpha_hash, passport,
                   card_status, created_at, arena1_score
            FROM champion_pipeline
            WHERE engine_hash = 'zv5_v10_alpha'
              AND card_status = $1
              AND arena1_score >= $2
            """
            args = [card_status, ic_min]
            idx = 3
            if regime:
                sql += f" AND regime = ${idx}"
                args.append(regime)
                idx += 1
            if symbol:
                sql += f" AND (passport->'arena1'->>'symbol' = ${idx})"
                args.append(symbol)
                idx += 1
            sql += f" ORDER BY arena1_score DESC LIMIT ${idx}"
            args.append(n_results)

            rows = await conn.fetch(sql, *args)
            return [ZooEntry.from_row(dict(r)) for r in rows]
        finally:
            await conn.close()

    async def count_by_regime(self) -> Dict[str, int]:
        """Count alphas per regime."""
        conn = await asyncpg.connect(self.dsn)
        try:
            rows = await conn.fetch(
                "SELECT regime, COUNT(*) as cnt FROM champion_pipeline "
                "WHERE engine_hash = 'zv5_v10_alpha' AND card_status = 'DISCOVERED' "
                "GROUP BY regime"
            )
            return {r['regime']: r['cnt'] for r in rows}
        finally:
            await conn.close()

    async def correlation_matrix(self, alpha_ids: List[int],
                                  close_data: np.ndarray) -> np.ndarray:
        """Compute pairwise correlation of alpha value series.
        Requires evaluating each alpha on same data."""
        # Simplified: return dummy matrix for now, caller must provide alpha values
        # Full implementation requires alpha evaluation infrastructure
        n = len(alpha_ids)
        return np.eye(n, dtype=np.float32)

    async def diversify_select(self, candidates: List[ZooEntry],
                                top_k: int = 20,
                                max_jaccard: float = 0.3) -> List[ZooEntry]:
        """Greedy low-correlation subset by indicator Jaccard similarity.
        Uses indicator/operator overlap as proxy for value correlation."""
        if not candidates:
            return []

        # Sort by IC
        sorted_cands = sorted(candidates, key=lambda c: abs(c.ic), reverse=True)
        selected = [sorted_cands[0]]

        for cand in sorted_cands[1:]:
            if len(selected) >= top_k:
                break
            # Compute max Jaccard with any already-selected
            cand_set = set(cand.used_indicators) | set(cand.used_operators)
            max_sim = 0.0
            for s in selected:
                s_set = set(s.used_indicators) | set(s.used_operators)
                if not cand_set or not s_set:
                    continue
                inter = len(cand_set & s_set)
                union = len(cand_set | s_set)
                jaccard = inter / max(union, 1)
                max_sim = max(max_sim, jaccard)

            if max_sim <= max_jaccard:
                selected.append(cand)

        return selected

    async def prune_stale(self, days_threshold: int = 30,
                          ic_degradation_pct: float = 0.5) -> int:
        """Archive alphas whose IC has degraded beyond threshold.
        Returns count of archived alphas."""
        # Placeholder: would need fresh IC re-validation
        # For now, just archive alphas older than threshold with low original IC
        conn = await asyncpg.connect(self.dsn)
        try:
            count = await conn.fetchval(
                """
                UPDATE champion_pipeline
                SET card_status = 'ARCHIVED'
                WHERE engine_hash = 'zv5_v10_alpha'
                  AND card_status = 'DISCOVERED'
                  AND created_at < NOW() - make_interval(days => $1)
                  AND arena1_score < 0.02
                RETURNING id
                """,
                days_threshold
            )
            return count if count else 0
        finally:
            await conn.close()

    async def stats(self) -> dict:
        """Overall zoo statistics."""
        conn = await asyncpg.connect(self.dsn)
        try:
            row = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE card_status = 'DISCOVERED') as active,
                    COUNT(*) FILTER (WHERE card_status = 'ARCHIVED') as archived,
                    AVG(arena1_score) as avg_ic,
                    MAX(arena1_score) as max_ic,
                    COUNT(DISTINCT regime) as n_regimes
                FROM champion_pipeline
                WHERE engine_hash = 'zv5_v10_alpha'
            """)
            return dict(row) if row else {}
        finally:
            await conn.close()


if __name__ == "__main__":
    import asyncio
    async def _test():
        zoo = FactorZoo()
        stats = await zoo.stats()
        print(f"Factor zoo stats: {stats}")
        counts = await zoo.count_by_regime()
        print(f"By regime: {counts}")
    asyncio.run(_test())
