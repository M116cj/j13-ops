"""Live trading main loop: on_new_bar() entry point (C28 + C29).

Architecture:
  on_new_bar(symbol, bar_df, factor_row, state, open_positions, journal, monitor)
    → stale check
    → regime prediction: labeler.label(window) → predictor.step()
    → signal = weights @ factor_row  (C04 at deploy time)
    → risk check before open
    → entry / exit logic
    → journal append
    → monitor emit
    → return (updated_open_positions, BarResult)

Latency target: < 50 ms per bar per symbol (C29).
All heavy state (model, factor_matrix, normalizer) is pre-loaded in LiveState —
on_new_bar() itself does zero I/O and zero model loading.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Deque, Dict, Optional, Tuple

import numpy as np
import polars as pl

from zangetsu_v3.factors.normalizer import RobustNormalizer
from zangetsu_v3.live.journal import LiveJournal, TradeRecord
from zangetsu_v3.live.monitor import LiveMonitor
from zangetsu_v3.live.risk_manager import Position, RiskLimits, RiskManager
from zangetsu_v3.live.stale_breaker import StaleBreaker, StaleFeedError
from zangetsu_v3.regime.labeler import RegimeLabeler
from zangetsu_v3.regime.predictor import OnlineRegimePredictor


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
    labeler: RegimeLabeler              # loaded HMM model
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

    bar_buffer: Deque[pl.DataFrame] = field(default_factory=deque, repr=False)

    def __post_init__(self) -> None:
        # Ensure deque has a maxlen matching lookback
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
        Pre-loaded LiveState — no I/O inside this function.
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

    # ── 1. Stale-data check ──────────────────────────────────────────
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

    # ── 2. Buffer management + regime prediction ─────────────────────
    state.bar_buffer.append(bar_df)

    if len(state.bar_buffer) < state.lookback:
        # Not enough history yet — skip trading
        latency_ms = (time.monotonic() - t_start) * 1000
        regime_id = state.predictor.active_regime if state.predictor.active_regime is not None else 0
        monitor.bar_processed(symbol, bar_ts, regime_id, 0.0, latency_ms)
        return open_positions, BarResult(
            symbol=symbol, regime_id=regime_id, signal=0.0,
            action="warming_up", latency_ms=latency_ms,
        )

    window_df = pl.concat(list(state.bar_buffer))
    labels = state.labeler.label(window_df)
    raw_regime = int(labels[-1])

    old_regime = state.predictor.active_regime
    regime_id = state.predictor.step(raw_regime)
    confidence = state.predictor.switch_confidence

    if old_regime is not None and old_regime != regime_id:
        monitor.regime_switch(symbol, old_regime, regime_id, confidence)

    # ── 3. Signal = weights @ factor_row  (C04) ──────────────────────
    signal = float(state.weights @ factor_row)

    # ── 4. Position management ───────────────────────────────────────
    action = "hold"
    trade: Optional[TradeRecord] = None
    has_position = symbol in open_positions

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
        candidate = Position(
            symbol=symbol,
            regime_id=regime_id,
            side=side,
            quantity=state.position_frac,
            entry_price=close_price,
        )
        allowed, reason = state.risk_manager.check_new_position(candidate, open_positions)
        if allowed:
            open_positions[symbol] = candidate
            monitor.position_opened(symbol, side, state.position_frac, close_price, regime_id)
            action = f"entry_{side}"
        else:
            monitor.risk_blocked(symbol, reason)
            action = "risk_blocked"

    # ── 5. Metrics ───────────────────────────────────────────────────
    latency_ms = (time.monotonic() - t_start) * 1000
    monitor.bar_processed(symbol, bar_ts, regime_id, signal, latency_ms)
    monitor.portfolio_snapshot(state.risk_manager.portfolio_stats(open_positions))

    return open_positions, BarResult(
        symbol=symbol,
        regime_id=regime_id,
        signal=signal,
        action=action,
        latency_ms=latency_ms,
        trade=trade,
    )


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
    labeler: RegimeLabeler,
    predictor: Optional[OnlineRegimePredictor] = None,
    risk_limits: Optional[RiskLimits] = None,
    max_stale_seconds: int = 60,
    lookback: int = 60,
) -> LiveState:
    """Convenience builder — wire up LiveState from card + pre-loaded objects."""
    params = card.get("params", {})
    cost_model = card.get("cost_model", {})
    return LiveState(
        card=card,
        weights=weights,
        normalizer=normalizer,
        labeler=labeler,
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
    )


__all__ = ["on_new_bar", "build_live_state", "LiveState", "BarResult"]
