"""Live trading main loop: on_new_bar() entry point (C28 + C29 + C7/V3.2).

Architecture:
  on_new_bar(symbol, bar_df, factor_row, state, open_positions, journal, monitor)
    -> stale check
    -> regime prediction: rule_labeler.label_symbol(window) -> predictor.step()
    -> signal = weights @ factor_row  (C04 at deploy time)
    -> risk check before open
    -> entry / exit logic
    -> journal append
    -> monitor emit
    -> DB writes (trade_journal INSERT + runtime_status UPSERT) -- V3.2 C7
    -> return (updated_open_positions, BarResult)

Latency target: < 50 ms per bar per symbol (C29).
All heavy state (model, factor_matrix, normalizer) is pre-loaded in LiveState --
on_new_bar() itself does zero blocking I/O and zero model loading.
DB writes are fire-and-forget via a background thread pool.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, Optional, Tuple

import numpy as np
import polars as pl

from zangetsu_v3.factors.normalizer import RobustNormalizer
from zangetsu_v3.live.journal import LiveJournal, TradeRecord
from zangetsu_v3.live.monitor import LiveMonitor
from zangetsu_v3.live.position_overlay import OVERLAY_DAMPERS, position_overlay
from zangetsu_v3.live.risk_manager import Position, RiskLimits, RiskManager
from zangetsu_v3.live.stale_breaker import StaleBreaker, StaleFeedError
from zangetsu_v3.regime.rule_labeler import label_symbol, Regime, REGIME_NAMES
from zangetsu_v3.regime.predictor import OnlineRegimePredictor

# [F8] Engine version verification
def _verify_engine_hash(card: dict) -> bool:
    """Check if current engine matches the card's engine_hash. Returns True if ok or no hash stored."""
    engine_hash = card.get("engine_hash")
    if not engine_hash or engine_hash == "unknown":
        return True  # pre-F8 card, no hash to check
    try:
        from scripts.engine_version import preflight_check
        ok, msg = preflight_check(engine_hash)
        if not ok:
            log.error(f"[F8] ENGINE MISMATCH: {msg}")
            return False
        log.info(f"[F8] Engine verified: {engine_hash[:20]}...")
        return True
    except Exception as e:
        log.error(f"[F8] Engine verification failed: {e}")
        return False

log = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# DB connection pool (module-level singleton, lazy init)              #
# ------------------------------------------------------------------ #

_db_pool: Optional[Any] = None
_db_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="db_write")


def _get_db_dsn() -> str:
    return os.environ.get(
        "ZV3_DB_DSN",
        "dbname=zangetsu user=zangetsu password=9c424966bebb05a42966186bb22d7480 host=127.0.0.1 port=5432",
    )


def _get_db_conn():
    """Get or create a psycopg2 connection. Thread-local via pool."""
    import psycopg2
    import psycopg2.pool

    global _db_pool
    if _db_pool is None:
        try:
            _db_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1, maxconn=4, dsn=_get_db_dsn(),
            )
        except Exception as e:
            log.error("DB pool init failed: %s", e)
            return None
    try:
        return _db_pool.getconn()
    except Exception as e:
        log.error("DB getconn failed: %s", e)
        return None


def _put_db_conn(conn):
    global _db_pool
    if _db_pool is not None and conn is not None:
        try:
            _db_pool.putconn(conn)
        except Exception:
            pass


# ------------------------------------------------------------------ #
# DB write functions (run in background thread)                       #
# ------------------------------------------------------------------ #

def _db_insert_trade_journal(
    card_id: Optional[int],
    symbol: str,
    timestamp: str,
    direction: str,
    signal_value: float,
    expected_price: float,
    actual_fill_price: float,
    slippage_bps: float,
    position_size: float,
    regime_at_entry: str,
    regime_confidence: float,
    switch_confidence: float,
    pnl_pct: float,
    hold_bars: int,
) -> None:
    """INSERT INTO trade_journal. Fire-and-forget."""
    conn = _get_db_conn()
    if conn is None:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO trade_journal
                   (card_id, symbol, timestamp, direction, signal_value,
                    expected_price, actual_fill_price, slippage_bps,
                    position_size, regime_at_entry, regime_confidence,
                    switch_confidence, pnl_pct, hold_bars)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (card_id, symbol, timestamp, direction, signal_value,
                 expected_price, actual_fill_price, slippage_bps,
                 position_size, regime_at_entry, regime_confidence,
                 switch_confidence, pnl_pct, hold_bars),
            )
        conn.commit()
    except Exception as e:
        log.error("trade_journal INSERT failed: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        _put_db_conn(conn)


def _db_upsert_runtime_status(
    regime: str,
    confidence: float,
    bars_since_switch: int,
    switch_confidence: float,
    active_card_id: Optional[int],
    fine_regime: str,
    overlay_damper: float,
    stale_status: str,
    last_bar_time: str,
    today_pnl: float,
    cumulative_pnl: float,
    today_trades: int,
    open_positions_json: str,
    net_exposure: float,
    gross_exposure: float,
) -> None:
    """UPSERT runtime_status singleton row (id=1). Fire-and-forget."""
    conn = _get_db_conn()
    if conn is None:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO runtime_status
                   (id, regime, confidence, bars_since_switch, switch_confidence,
                    active_card_id, fine_regime, overlay_damper, stale_status,
                    last_bar_time, today_pnl, cumulative_pnl, today_trades,
                    open_positions, net_exposure, gross_exposure, updated_at)
                   VALUES (1,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,NOW())
                   ON CONFLICT (id) DO UPDATE SET
                     regime=EXCLUDED.regime,
                     confidence=EXCLUDED.confidence,
                     bars_since_switch=EXCLUDED.bars_since_switch,
                     switch_confidence=EXCLUDED.switch_confidence,
                     active_card_id=EXCLUDED.active_card_id,
                     fine_regime=EXCLUDED.fine_regime,
                     overlay_damper=EXCLUDED.overlay_damper,
                     stale_status=EXCLUDED.stale_status,
                     last_bar_time=EXCLUDED.last_bar_time,
                     today_pnl=EXCLUDED.today_pnl,
                     cumulative_pnl=EXCLUDED.cumulative_pnl,
                     today_trades=EXCLUDED.today_trades,
                     open_positions=EXCLUDED.open_positions,
                     net_exposure=EXCLUDED.net_exposure,
                     gross_exposure=EXCLUDED.gross_exposure,
                     updated_at=NOW()""",
                (regime, confidence, bars_since_switch, switch_confidence,
                 active_card_id, fine_regime, overlay_damper, stale_status,
                 last_bar_time, today_pnl, cumulative_pnl, today_trades,
                 open_positions_json, net_exposure, gross_exposure),
            )
        conn.commit()
    except Exception as e:
        log.error("runtime_status UPSERT failed: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        _put_db_conn(conn)


def _db_check_card_reload(regime_name: str) -> Optional[Dict[str, Any]]:
    """Check DB for newer card version for the current regime.

    Returns dict with {id, strategy_id, created_at, genome} or None.
    Uses regime_fitness jsonb to find cards matching this regime.
    """
    conn = _get_db_conn()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            # strategy_champions has regime_fitness jsonb, not a plain regime column.
            # Match cards where regime_fitness contains the regime key and status='active'.
            cur.execute(
                """SELECT id, strategy_id, created_at, genome
                   FROM strategy_champions
                   WHERE status = 'active'
                     AND regime_fitness ? %s
                   ORDER BY created_at DESC
                   LIMIT 1""",
                (regime_name,),
            )
            row = cur.fetchone()
            if row:
                return {
                    "id": row[0],
                    "strategy_id": row[1],
                    "created_at": str(row[2]),
                    "genome": row[3],
                }
        return None
    except Exception as e:
        log.error("card reload query failed: %s", e)
        return None
    finally:
        _put_db_conn(conn)


# ------------------------------------------------------------------ #
# Pre-loaded live state (built once at startup)                       #
# ------------------------------------------------------------------ #

@dataclass
class LiveState:
    """All pre-loaded state needed for zero-latency on_new_bar().

    Build once at startup via build_live_state(); pass immutably to every call.
    bar_buffer is mutated per bar to maintain the HMM lookback window.
    """
    card: Dict[str, Any]
    weights: np.ndarray                 # (n_factors,) from card["factors"]
    normalizer: RobustNormalizer        # fitted on train data
    predictor: OnlineRegimePredictor    # debounce singleton
    risk_manager: RiskManager
    stale_breaker: StaleBreaker
    card_version: str
    entry_threshold: float
    exit_threshold: float
    cost_bps: float
    funding_rate: float
    position_frac: float
    lookback: int                       # HMM lookback window size
    card_id: Optional[int] = None       # DB card id for trade_journal writes

    bar_buffer: Deque[pl.DataFrame] = field(default_factory=deque, repr=False)

    # Card reload tracking
    _last_card_check_bar: int = 0
    _card_check_interval: int = 150     # check every ~150 bars (10h at 4min bars)

    def __post_init__(self) -> None:
        if not isinstance(self.bar_buffer, deque) or self.bar_buffer.maxlen != self.lookback:
            self.bar_buffer = deque(maxlen=self.lookback)


@dataclass
class BarResult:
    symbol: str
    regime_id: int
    signal: float
    action: str   # "entry_long" | "entry_short" | "exit" | "hold" | "risk_blocked" | "stale" | "warming_up"
    latency_ms: float
    trade: Optional[TradeRecord] = None


# ------------------------------------------------------------------ #
# Core per-bar function                                               #
# ------------------------------------------------------------------ #

def on_new_bar(
    symbol: str,
    bar_df: pl.DataFrame,
    factor_row: np.ndarray,             # (n_factors,) pre-computed for this bar (C04)
    state: LiveState,
    open_positions: Dict[str, Position],
    journal: LiveJournal,
    monitor: LiveMonitor,
) -> Tuple[Dict[str, Position], BarResult]:
    """Process one new bar for a symbol.

    Parameters
    ----------
    symbol:
        e.g. "BTC/USDT"
    bar_df:
        Single-row Polars DataFrame of the latest OHLCV bar.
    factor_row:
        Pre-computed (n_factors,) factor vector for this bar.
    state:
        Pre-loaded LiveState -- no I/O inside this function.
    open_positions:
        Mutable dict of currently open positions.
    journal, monitor:
        Injected for append + metrics emission.

    Returns
    -------
    (updated_open_positions, BarResult)
    """
    t_start = time.monotonic()
    bar_ts = _bar_timestamp(bar_df)
    close_price = float(bar_df["close"][0])

    # -- 1. Stale-data check -----------------------------------------------
    state.stale_breaker.record_bar(symbol)
    try:
        state.stale_breaker.check(symbol)
    except StaleFeedError:
        age = state.stale_breaker.age_seconds(symbol)
        monitor.stale_feed(symbol, age)
        latency_ms = (time.monotonic() - t_start) * 1000
        return open_positions, BarResult(
            symbol=symbol, regime_id=-1, signal=0.0,
            action="stale", latency_ms=latency_ms,
        )

    # -- 2. Buffer management + regime prediction --------------------------
    state.bar_buffer.append(bar_df)

    if len(state.bar_buffer) < state.lookback:
        latency_ms = (time.monotonic() - t_start) * 1000
        regime_id = state.predictor.active_regime if state.predictor.active_regime is not None else 0
        monitor.bar_processed(symbol, bar_ts, regime_id, 0.0, latency_ms)
        return open_positions, BarResult(
            symbol=symbol, regime_id=regime_id, signal=0.0,
            action="warming_up", latency_ms=latency_ms,
        )

    window_df = pl.concat(list(state.bar_buffer))
    _, labels_4h, _ = label_symbol(window_df)
    labels = labels_4h
    raw_regime = int(labels[-1])

    old_regime = state.predictor.active_regime
    regime_id = state.predictor.step(raw_regime)
    confidence = state.predictor.switch_confidence

    if old_regime is not None and old_regime != regime_id:
        monitor.regime_switch(symbol, old_regime, regime_id, confidence)

    # -- 3. Signal = weights @ factor_row  (C04) ---------------------------
    signal = float(state.weights @ factor_row)

    # -- 4. Position management --------------------------------------------
    action = "hold"
    trade: Optional[TradeRecord] = None
    has_position = symbol in open_positions
    fine_regime = regime_id
    damper = 1.0

    if has_position:
        pos = open_positions[symbol]
        should_exit = (
            abs(signal) < state.exit_threshold
            or regime_id != pos.regime_id
        )
        if should_exit:
            trade = _close_position(pos, close_price, bar_ts, state)
            del open_positions[symbol]
            journal.append(trade)
            monitor.position_closed(
                symbol=symbol,
                pnl=trade.pnl,
                pnl_pct=trade.pnl_pct,
                slippage_bps=trade.slippage_bps,
                funding=trade.funding,
            )
            action = "exit"

    elif abs(signal) > state.entry_threshold:
        side = "long" if signal > 0 else "short"

        # 4-layer position sizing: base x pm x sw_conf x overlay
        base_size = state.position_frac
        sw_conf = confidence
        fine_regime = regime_id
        if state.predictor._model is not None:
            try:
                close_arr = window_df["close"].to_numpy()
                high_arr = window_df["high"].to_numpy()
                low_arr = window_df["low"].to_numpy()
                vol_arr = window_df["volume"].to_numpy()
                fine_regime = state.predictor.predict_fine(close_arr, high_arr, low_arr, vol_arr)
            except Exception:
                pass
        damper = OVERLAY_DAMPERS.get(fine_regime, 1.0)
        final_size = base_size * sw_conf * damper

        if final_size < 1e-9:
            action = "hold"
        else:
            candidate = Position(
                symbol=symbol,
                regime_id=regime_id,
                side=side,
                quantity=final_size,
                entry_price=close_price,
            )
            allowed, reason = state.risk_manager.check_new_position(candidate, open_positions)
            if allowed:
                open_positions[symbol] = candidate
                monitor.position_opened(symbol, side, final_size, close_price, regime_id)
                action = f"entry_{side}"
            else:
                monitor.risk_blocked(symbol, reason)
                action = "risk_blocked"

    # -- 5. Metrics --------------------------------------------------------
    latency_ms = (time.monotonic() - t_start) * 1000
    monitor.bar_processed(symbol, bar_ts, regime_id, signal, latency_ms)
    monitor.portfolio_snapshot(state.risk_manager.portfolio_stats(open_positions))

    # -- 6. DB writes (non-blocking, fire-and-forget) ----------------------
    _schedule_db_writes(state, symbol, bar_ts, regime_id, action, signal, close_price,
                        open_positions, journal, trade, fine_regime, damper)

    # -- 7. Card reload check (periodic, non-blocking) --------------------
    state._last_card_check_bar += 1
    if state._last_card_check_bar >= state._card_check_interval:
        state._last_card_check_bar = 0
        regime_name = REGIME_NAMES.get(regime_id, f"UNKNOWN_{regime_id}")
        _db_executor.submit(_card_reload_check, state, regime_name)

    return open_positions, BarResult(
        symbol=symbol,
        regime_id=regime_id,
        signal=signal,
        action=action,
        latency_ms=latency_ms,
        trade=trade,
    )


# ------------------------------------------------------------------ #
# DB write scheduler (non-blocking)                                   #
# ------------------------------------------------------------------ #

def _schedule_db_writes(
    state: LiveState,
    symbol: str,
    bar_ts: str,
    regime_id: int,
    action: str,
    signal: float,
    close_price: float,
    open_positions: Dict[str, Position],
    journal: LiveJournal,
    trade: Optional[TradeRecord],
    fine_regime: int,
    overlay_damper: float,
) -> None:
    """Submit DB writes to background thread pool. Never blocks the hot path."""
    regime_name = REGIME_NAMES.get(regime_id, f"UNKNOWN_{regime_id}")
    fine_regime_name = REGIME_NAMES.get(fine_regime, f"UNKNOWN_{fine_regime}")
    stats = state.risk_manager.portfolio_stats(open_positions)
    j_stats = journal.stats()

    # Serialize open_positions to JSON for DB
    positions_list = []
    for sym, pos in open_positions.items():
        positions_list.append({
            "symbol": pos.symbol,
            "side": pos.side,
            "quantity": pos.quantity,
            "entry_price": pos.entry_price,
            "regime_id": pos.regime_id,
        })
    positions_json = json.dumps(positions_list)

    # 1. runtime_status UPSERT (every bar)
    _db_executor.submit(
        _db_upsert_runtime_status,
        regime=regime_name,
        confidence=state.predictor.switch_confidence,
        bars_since_switch=state.predictor.bars_since_switch,
        switch_confidence=state.predictor.switch_confidence,
        active_card_id=state.card_id,
        fine_regime=fine_regime_name,
        overlay_damper=overlay_damper,
        stale_status="stale" if action == "stale" else "ok",
        last_bar_time=bar_ts,
        today_pnl=j_stats.get("total_pnl", 0.0),
        cumulative_pnl=j_stats.get("total_pnl", 0.0),
        today_trades=j_stats.get("n_trades", 0),
        open_positions_json=positions_json,
        net_exposure=stats["net_exposure"],
        gross_exposure=stats["gross_exposure"],
    )

    # 2. trade_journal INSERT (only on entry/exit)
    if trade is not None and action == "exit":
        _db_executor.submit(
            _db_insert_trade_journal,
            card_id=state.card_id,
            symbol=trade.symbol,
            timestamp=bar_ts,
            direction=trade.side,
            signal_value=signal,
            expected_price=trade.entry_price,
            actual_fill_price=trade.exit_price,
            slippage_bps=trade.slippage_bps,
            position_size=trade.quantity,
            regime_at_entry=regime_name,
            regime_confidence=state.predictor.switch_confidence,
            switch_confidence=state.predictor.switch_confidence,
            pnl_pct=trade.pnl_pct,
            hold_bars=trade.hold_bars,
        )
    elif action.startswith("entry_"):
        _db_executor.submit(
            _db_insert_trade_journal,
            card_id=state.card_id,
            symbol=symbol,
            timestamp=bar_ts,
            direction=action.replace("entry_", ""),
            signal_value=signal,
            expected_price=close_price,
            actual_fill_price=close_price,
            slippage_bps=state.cost_bps,
            position_size=open_positions[symbol].quantity if symbol in open_positions else 0.0,
            regime_at_entry=regime_name,
            regime_confidence=state.predictor.switch_confidence,
            switch_confidence=state.predictor.switch_confidence,
            pnl_pct=0.0,
            hold_bars=0,
        )


def _card_reload_check(state: LiveState, regime_name: str) -> None:
    """Background check for newer card deployment. Logs only -- actual reload
    requires the orchestrator to rebuild LiveState."""
    try:
        result = _db_check_card_reload(regime_name)
        if result is not None:
            current_id = state.card_id
            new_id = result["id"]
            if current_id is None or new_id != current_id:
                log.info(
                    "Newer card available for regime %s: id=%s strategy=%s (current=%s)",
                    regime_name, new_id, result["strategy_id"], current_id,
                )
    except Exception as e:
        log.error("Card reload check failed: %s", e)


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _bar_timestamp(bar_df: pl.DataFrame) -> str:
    if "timestamp" in bar_df.columns:
        return str(bar_df["timestamp"][0])
    return datetime.now(timezone.utc).isoformat()


def _close_position(
    pos: Position,
    exit_price: float,
    bar_ts: str,
    state: LiveState,
) -> TradeRecord:
    sign = 1.0 if pos.side == "long" else -1.0
    raw_pnl_pct = sign * (exit_price - pos.entry_price) / max(pos.entry_price, 1e-12)
    slippage_frac = state.cost_bps / 10_000.0
    funding = abs(state.funding_rate) * pos.quantity
    net_pnl_pct = raw_pnl_pct - slippage_frac - (funding / max(pos.quantity, 1e-12))
    pnl = net_pnl_pct * pos.quantity
    max_dd = max(0.0, -pnl)

    return TradeRecord(
        timestamp=bar_ts,
        symbol=pos.symbol,
        side=pos.side,
        quantity=pos.quantity,
        entry_price=pos.entry_price,
        exit_price=exit_price,
        pnl=pnl,
        pnl_pct=net_pnl_pct,
        max_drawdown=max_dd,
        regime_id=pos.regime_id,
        card_version=state.card_version,
        slippage_bps=state.cost_bps,
        funding=funding,
        notes="",
    )


def build_live_state(
    card: Dict[str, Any],
    weights: np.ndarray,
    normalizer: RobustNormalizer,
    predictor: Optional[OnlineRegimePredictor] = None,
    risk_limits: Optional[RiskLimits] = None,
    max_stale_seconds: int = 60,
    lookback: int = 60,
    card_id: Optional[int] = None,
) -> LiveState:
    """Convenience builder -- wire up LiveState from card + pre-loaded objects.

    V3.2: removed status_json_path, added card_id for DB writes.
    """
    # [F8] Verify engine hash before building live state
    if not _verify_engine_hash(card):
        raise RuntimeError(
            f"[F8] Engine hash mismatch for card {card.get('card_id', '?')}. "
            f"Cannot proceed — strategy was trained on a different engine version."
        )
    params = card.get("params", {})
    cost_model = card.get("cost_model", {})
    return LiveState(
        card=card,
        weights=weights,
        normalizer=normalizer,
        predictor=predictor or OnlineRegimePredictor(),
        risk_manager=RiskManager(limits=risk_limits or RiskLimits()),
        stale_breaker=StaleBreaker(max_stale_seconds=max_stale_seconds),
        card_version=card.get("version", "3.0"),
        entry_threshold=float(params.get("entry_threshold", 1.2)),
        exit_threshold=float(params.get("exit_threshold", 0.5)),
        cost_bps=float(cost_model.get("trading_bps", 3)),
        funding_rate=float(cost_model.get("funding_rate_avg", 0.0001)),
        position_frac=float(params.get("position_frac", 0.1)),
        lookback=lookback,
        card_id=card_id,
    )


def shutdown_db_pool() -> None:
    """Cleanly shut down the DB connection pool. Call on process exit."""
    global _db_pool
    _db_executor.shutdown(wait=True, cancel_futures=False)
    if _db_pool is not None:
        try:
            _db_pool.closeall()
        except Exception:
            pass
        _db_pool = None


__all__ = ["on_new_bar", "build_live_state", "LiveState", "BarResult", "shutdown_db_pool"]
