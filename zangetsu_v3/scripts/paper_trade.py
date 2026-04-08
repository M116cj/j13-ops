#!/usr/bin/env python3
"""Zangetsu V5 — Paper Trading Main Loop Orchestrator.

Top-level async loop: loads cards, connects WS feed, runs 1-minute tick
cycle with signal computation, position entry/exit, risk management,
and structured logging.  Designed for tmux soak testing.

Signal Contract Compliance:
  Rule 1: raw normalization via card medians/mads, clip +/-5
  Rule 2: entries ONLY at 4h boundary (bar_count % 240 == 0)
  Rule 3: thresholds = mult * card.signal_std
  Rule 4: signal = normalized @ weights (float64)
  Rule 5: indicators on 4h resampled bars, constant between boundaries
  Rule 6: regime via rule_labeler (causal rolling window, known divergence)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

# ── project imports ──────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import zangetsu_indicators as zi
from scripts.engine_version import compute_engine_hash, preflight_check
from zangetsu_v3.live.journal import write_to_db
from zangetsu_v3.live.monitor import LiveMonitor
from zangetsu_v3.live.position_tracker import PositionTracker
from zangetsu_v3.live.risk_manager import (
    PortfolioRiskManager,
    Position,
    RiskManager,
)
from zangetsu_v3.live.stale_breaker import StaleBreaker, StaleFeedError
from zangetsu_v3.live.ws_feed import BinanceFuturesWS
from zangetsu_v3.regime.rule_labeler import (
    Regime,
    REGIME_NAMES,
    label_symbol,
    resample_to_4h,
)

# ── constants ────────────────────────────────────────────────────────
LOG = logging.getLogger("zangetsu.paper_trade")

ACTIVE_REGIMES = [
    "BULL_TREND", "BEAR_TREND", "BEAR_RALLY",
    "TOPPING", "BOTTOMING", "SQUEEZE", "CONSOLIDATION",
]
EXCLUDED_REGIMES = ["BULL_PULLBACK", "CHOPPY_VOLATILE"]
MARGINAL_SIZE_PENALTY = 0.5           # 50% sizing for MARGINAL cards
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
TICK_OFFSET_S = 5                     # seconds past minute boundary
PREFILL_MIN_BARS = 240                # need >= 1 full 4h bar in buffer
BAR_BUFFER_SIZE = 500
STATUS_PATH = Path("logs/paper_status.json")
MONITOR_LOG = Path("logs/paper_monitor.jsonl")


# ── card loading ─────────────────────────────────────────────────────

def load_cards(strategies_dir: Path) -> dict[str, dict]:
    """Load card.json for each active regime. Validate schema."""
    cards: dict[str, dict] = {}
    for regime in ACTIVE_REGIMES:
        card_path = strategies_dir / f"{regime}_expert" / "card.json"
        if not card_path.exists():
            raise FileNotFoundError(f"Card not found: {card_path}")
        with open(card_path) as f:
            card = json.load(f)
        # validate signal_std presence (21-key schema)
        if "signal_std" not in card:
            raise ValueError(f"Card {regime} missing signal_std (20-key schema)")
        if card["signal_std"] <= 0:
            raise ValueError(f"Card {regime} has invalid signal_std={card['signal_std']}")
        # validate essential fields
        for key in ("weights", "normalization", "entry_thr_mult", "exit_thr_mult",
                     "stop_mult", "pos_frac", "hold_max", "grace_period",
                     "indicator_configs", "engine_hash"):
            if key not in card:
                raise ValueError(f"Card {regime} missing key: {key}")
        cards[regime] = card
    LOG.info("Loaded %d cards: %s", len(cards), list(cards.keys()))
    return cards


def validate_engine_hash(cards: dict[str, dict]) -> str:
    """F8 preflight: all cards must share the same engine hash, matching current."""
    hashes = {r: c["engine_hash"] for r, c in cards.items()}
    unique = set(hashes.values())
    if len(unique) != 1:
        raise RuntimeError(f"Cards have mismatched engine hashes: {hashes}")
    expected_hash = unique.pop()
    ok, msg = preflight_check(expected_hash)
    if not ok:
        raise RuntimeError(f"Engine preflight FAIL: {msg}")
    LOG.info("Engine hash verified: %s", expected_hash[:20])
    return expected_hash


# ── indicator / signal computation ───────────────────────────────────

def bars_to_polars(bars: list[dict]) -> pl.DataFrame:
    """Convert ws_feed bar dicts to a polars DataFrame for regime labeler."""
    return pl.DataFrame({
        "timestamp": [datetime.fromtimestamp(b["timestamp"] / 1000.0, tz=timezone.utc)
                       for b in bars],
        "open": [b["open"] for b in bars],
        "high": [b["high"] for b in bars],
        "low": [b["low"] for b in bars],
        "close": [b["close"] for b in bars],
        "volume": [b["volume"] for b in bars],
    })


def compute_regime(bars_df: pl.DataFrame) -> int:
    """Run rule_labeler on bars, return latest 4h regime label."""
    _, labels_4h, _ = label_symbol(bars_df, smooth_bars=2)
    if len(labels_4h) == 0:
        return -1
    return int(labels_4h[-1])


def compute_signal(
    bars_4h_df: pl.DataFrame,
    card: dict,
) -> tuple[np.ndarray, float]:
    """Compute indicator matrix → normalize → signal.

    Returns (signal_array_for_all_4h_bars, latest_signal_scalar).
    Rule 1: (raw - medians) / mads, clip +/-5
    Rule 4: signal = normalized @ weights
    Rule 5: indicators computed on 4h bars
    """
    o = bars_4h_df["open"].to_numpy(zero_copy_only=False).astype(np.float64)
    h = bars_4h_df["high"].to_numpy(zero_copy_only=False).astype(np.float64)
    lo = bars_4h_df["low"].to_numpy(zero_copy_only=False).astype(np.float64)
    c = bars_4h_df["close"].to_numpy(zero_copy_only=False).astype(np.float64)
    v = bars_4h_df["volume"].to_numpy(zero_copy_only=False).astype(np.float64)

    configs_json = json.dumps(card["indicator_configs"])
    matrix, _names = zi.compute_indicator_set(o, h, lo, c, v, configs_json)

    # NaN guard: if any indicator in the last row is NaN, skip this bar
    if np.isnan(matrix[-1]).any():
        nan_indicators = [name for name, val in zip(_names, matrix[-1]) if np.isnan(val)]
        LOG.warning("signal=skip reason=nan_in_indicators count=%d names=%s",
                    len(nan_indicators), nan_indicators[:3])
        return np.array([0.0]), 0.0

    medians = np.array(card["normalization"]["medians"], dtype=np.float64)
    mads = np.array(card["normalization"]["mads"], dtype=np.float64)
    mads[mads < 1e-10] = 1.0  # match training guard

    normalized = np.clip((matrix - medians) / mads, -5, 5)
    weights = np.array(card["weights"], dtype=np.float64)
    signals = normalized @ weights  # float64

    return signals, float(signals[-1])


# ── main loop ────────────────────────────────────────────────────────

class PaperTrader:
    """Stateful paper trading orchestrator."""

    def __init__(self, project_root: Path) -> None:
        self.root = project_root
        self.cards = load_cards(project_root / "strategies")
        validate_engine_hash(self.cards)

        cost_bps = {s: self.cards[ACTIVE_REGIMES[0]].get("cost_bps", 2.0)
                     for s in SYMBOLS}
        taker_bps = {s: self.cards[ACTIVE_REGIMES[0]].get("taker_bps", 4.0)
                      for s in SYMBOLS}

        self.ws = BinanceFuturesWS(SYMBOLS, buffer_size=BAR_BUFFER_SIZE)
        self.tracker = PositionTracker(SYMBOLS, cost_bps, taker_bps)
        self.portfolio_risk = PortfolioRiskManager(max_drawdown=0.05)
        self.risk_mgr = RiskManager()
        self.stale = StaleBreaker(max_stale_seconds=120)
        self.monitor = LiveMonitor(log_path=str(project_root / MONITOR_LOG))

        self.status_path = project_root / STATUS_PATH
        self.status_path.parent.mkdir(parents=True, exist_ok=True)

        self.db_dsn = os.environ.get("ZV3_DB_DSN")

        # per-symbol state
        self._current_regime: dict[str, int] = {s: -1 for s in SYMBOLS}
        self._regime_bar_count: dict[str, int] = {s: 0 for s in SYMBOLS}
        self._regime_changed_at: dict[str, int] = {s: -999 for s in SYMBOLS}
        self._cached_signal: dict[str, float] = {s: 0.0 for s in SYMBOLS}
        self._tick_count: int = 0
        self._start_time: float = time.time()
        self._today_trades: int = 0
        self._shutdown = False

    # ── startup ──────────────────────────────────────────────────────

    async def run(self) -> None:
        """Main entry: start WS, wait for prefill, run tick loop."""
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._request_shutdown)

        # Start WS in background
        ws_task = asyncio.create_task(self.ws.start())

        # Wait for prefill: all symbols must have >= PREFILL_MIN_BARS
        LOG.info("Waiting for WS prefill (%d bars per symbol)...", PREFILL_MIN_BARS)
        await self._wait_for_prefill()
        LOG.info("Prefill complete. Starting tick loop.")

        try:
            await self._tick_loop()
        except asyncio.CancelledError:
            pass
        finally:
            await self._shutdown_sequence()
            ws_task.cancel()
            try:
                await ws_task
            except asyncio.CancelledError:
                pass

    async def _wait_for_prefill(self) -> None:
        """Block until all symbols have enough bars in the WS buffer."""
        while not self._shutdown:
            ready = True
            for sym in SYMBOLS:
                bars = self.ws.get_bars(sym, PREFILL_MIN_BARS)
                if len(bars) < PREFILL_MIN_BARS:
                    ready = False
                    break
            if ready:
                return
            await asyncio.sleep(2.0)
        raise asyncio.CancelledError("Shutdown during prefill")

    # ── tick loop ────────────────────────────────────────────────────

    async def _tick_loop(self) -> None:
        """Run once per minute, offset +5s past minute boundary."""
        while not self._shutdown:
            # Wait until HH:MM:05
            now = time.time()
            current_sec = now % 60
            if current_sec < TICK_OFFSET_S:
                wait = TICK_OFFSET_S - current_sec
            else:
                wait = 60 - current_sec + TICK_OFFSET_S
            await asyncio.sleep(wait)

            if self._shutdown:
                break

            tick_start = time.time()
            self._tick_count += 1

            try:
                await self._process_tick()
            except Exception:
                LOG.exception("Tick %d failed", self._tick_count)
                self.monitor.error(
                    f"tick_{self._tick_count}_failed",
                    exc=sys.exc_info()[1],
                )

            elapsed_ms = (time.time() - tick_start) * 1000
            if elapsed_ms > 5000:
                LOG.warning("Tick %d took %.0fms (>5s)", self._tick_count, elapsed_ms)

    async def _process_tick(self) -> None:
        """Single tick: iterate all symbols, compute signals, manage positions."""
        is_4h_boundary = (self._tick_count % 240) == 0

        for sym in SYMBOLS:
            try:
                self._process_symbol_tick(sym, is_4h_boundary)
            except StaleFeedError as e:
                LOG.warning("Stale feed for %s: %s", sym, e)
                self.monitor.stale_feed(sym, self.stale.age_seconds(sym))
            except Exception:
                LOG.exception("Error processing %s at tick %d", sym, self._tick_count)

        # Portfolio-level updates
        self.tracker.tick()  # increment hold_bars for all open positions

        for sym in SYMBOLS:
            bar = self.ws.latest_bar(sym)
            if bar:
                self.tracker.mark_to_market(sym, bar["close"])

        # Kill switch check
        equity = self.tracker.portfolio_pnl()
        just_killed = self.portfolio_risk.update(equity)
        if just_killed:
            LOG.critical("KILL SWITCH TRIGGERED: %s", self.portfolio_risk.kill_reason)
            self.monitor.error(f"kill_switch: {self.portfolio_risk.kill_reason}")
            await self._close_all_positions("kill_switch")

        # Status + monitoring
        self._write_status()
        stats = self.risk_mgr.portfolio_stats(self._build_risk_positions())
        self.monitor.portfolio_snapshot({
            **stats,
            "aggregate_pnl": equity,
            "tick": self._tick_count,
        })

    def _process_symbol_tick(self, sym: str, is_4h_boundary: bool) -> None:
        """Process one symbol for one tick."""
        bars = self.ws.get_bars(sym, BAR_BUFFER_SIZE)
        if not bars:
            return

        # Staleness check
        self.stale.record_bar(sym)

        latest_price = bars[-1]["close"]

        # At 4h boundary: recompute regime + indicators
        if is_4h_boundary and len(bars) >= PREFILL_MIN_BARS:
            bars_df = bars_to_polars(bars)
            new_regime = compute_regime(bars_df)
            old_regime = self._current_regime[sym]

            if new_regime != old_regime:
                self._regime_changed_at[sym] = self._tick_count
                self.monitor.regime_switch(
                    sym, old_regime, new_regime, confidence=1.0,
                )
                LOG.info("Regime switch %s: %s -> %s", sym,
                         REGIME_NAMES.get(old_regime, "?"),
                         REGIME_NAMES.get(new_regime, "?"))
            self._current_regime[sym] = new_regime
            self._regime_bar_count[sym] = 0

            # Compute signal with the active card
            regime_name = REGIME_NAMES.get(new_regime, "")
            if regime_name in self.cards:
                card = self.cards[regime_name]
                # Use pre-built 4h bar buffer (not resampled from 1m)
                bars_4h = self.ws.get_4h_bars(sym, 200)
                if len(bars_4h) >= 50:  # need enough 4h bars for indicators
                    df_4h = bars_to_polars(bars_4h)
                    _, sig = compute_signal(df_4h, card)
                    self._cached_signal[sym] = sig
                else:
                    LOG.warning("signal=skip sym=%s reason=insufficient_4h_bars count=%d",
                                sym, len(bars_4h))
                    self._cached_signal[sym] = 0.0
            else:
                self._cached_signal[sym] = 0.0

        self._regime_bar_count[sym] += 1
        regime_id = self._current_regime[sym]
        regime_name = REGIME_NAMES.get(regime_id, "")
        sig = self._cached_signal[sym]

        # ── Exit decisions (every bar) ───────────────────────────────
        if self.tracker.has_position(sym):
            pos = self.tracker.get_position(sym)
            close_reason = self._check_exit(sym, pos, sig, regime_name, latest_price)
            if close_reason:
                record = self.tracker.close_position(sym, latest_price, close_reason)
                if record:
                    self._journal_write(record)
                    self._today_trades += 1
                    self.monitor.position_closed(
                        sym,
                        pnl=record.get("pnl_pct", 0.0),
                        pnl_pct=record.get("pnl_pct", 0.0),
                        slippage_bps=record.get("slippage_bps", 0.0),
                        funding=0.0,
                    )

        # ── Entry decisions (ONLY at 4h boundary — Rule 2) ──────────
        if is_4h_boundary and not self.tracker.has_position(sym):
            if regime_name in self.cards and not self.portfolio_risk.is_killed():
                self._try_entry(sym, sig, regime_name, latest_price)

        # Monitor emit
        self.monitor.bar_processed(
            sym,
            bar_timestamp=str(bars[-1]["timestamp"]),
            regime_id=regime_id,
            signal=sig,
            latency_ms=0.0,
        )

    def _check_exit(
        self, sym: str, pos: dict, sig: float, regime_name: str, price: float,
    ) -> str:
        """Check exit conditions. Returns reason string or empty string."""
        card = self.cards.get(pos["regime"])
        if card is None:
            # Regime no longer active — treat as regime exit
            return "regime_card_removed"

        # Rule 3: thresholds
        exit_thr = card["exit_thr_mult"] * card["signal_std"]

        # Signal exit
        direction = pos["direction"]
        if direction == 1 and sig < -exit_thr:
            return "signal"
        if direction == -1 and sig > exit_thr:
            return "signal"

        # Stop loss: unrealized loss > stop_mult * ATR approximation
        # Use a simple % stop since we don't have ATR directly here
        stop_pct = card["stop_mult"] * 0.01  # rough ATR proxy: 1% per mult
        entry_px = pos["entry_price"]
        if direction == 1:
            loss_pct = (entry_px - price) / max(entry_px, 1e-10)
        else:
            loss_pct = (price - entry_px) / max(entry_px, 1e-10)
        if loss_pct > stop_pct:
            return "stop"

        # Hold max
        if pos["hold_bars"] >= card["hold_max"]:
            return "hold_max"

        # Regime exit with grace period
        current_regime = REGIME_NAMES.get(self._current_regime[sym], "")
        if current_regime != pos["regime"]:
            bars_since_change = self._tick_count - self._regime_changed_at[sym]
            if bars_since_change > card["grace_period"]:
                return "regime"

        return ""

    def _try_entry(
        self, sym: str, sig: float, regime_name: str, price: float,
    ) -> None:
        """Attempt to open a position. Rule 2 + Rule 3 enforced."""
        card = self.cards[regime_name]
        entry_thr = card["entry_thr_mult"] * card["signal_std"]

        if abs(sig) <= entry_thr:
            return

        direction = 1 if sig > 0 else -1
        size = card["pos_frac"] * MARGINAL_SIZE_PENALTY

        # Risk check
        candidate = Position(
            symbol=sym,
            regime_id=Regime[regime_name].value,
            side="long" if direction == 1 else "short",
            quantity=size,
            entry_price=price,
        )
        risk_positions = self._build_risk_positions()
        allowed, reason = self.risk_mgr.check_new_position(candidate, risk_positions)
        if not allowed:
            LOG.info("Risk blocked %s: %s", sym, reason)
            self.monitor.risk_blocked(sym, reason)
            return

        card_id = f"{regime_name}_v{card.get('version', '?')}"
        pos = self.tracker.open_position(
            symbol=sym,
            direction=direction,
            size=size,
            entry_price=price,
            regime=regime_name,
            signal_value=sig,
            card_id=card_id,
        )
        self.monitor.position_opened(
            sym,
            side="long" if direction == 1 else "short",
            quantity=size,
            price=price,
            regime_id=Regime[regime_name].value,
        )

    def _build_risk_positions(self) -> dict[str, Position]:
        """Convert tracker positions to RiskManager Position objects."""
        result: dict[str, Position] = {}
        for pos in self.tracker.all_positions():
            regime_name = pos.get("regime", "")
            regime_id = Regime[regime_name].value if regime_name in Regime.__members__ else 0
            result[pos["symbol"]] = Position(
                symbol=pos["symbol"],
                regime_id=regime_id,
                side="long" if pos["direction"] == 1 else "short",
                quantity=pos["size"],
                entry_price=pos["entry_price"],
            )
        return result

    def _journal_write(self, record: dict) -> None:
        """Write trade to DB. Non-blocking, never crashes."""
        try:
            write_to_db(record, dsn=self.db_dsn)
        except Exception:
            LOG.exception("Journal DB write failed for %s", record.get("symbol"))

    # ── status snapshot ──────────────────────────────────────────────

    def _write_status(self) -> None:
        """Write logs/paper_status.json — called every tick."""
        positions = self.tracker.all_positions()
        status = {
            "uptime_seconds": int(time.time() - self._start_time),
            "tick_count": self._tick_count,
            "ws_healthy": self.ws.is_healthy(),
            "ws_reconnect_count": 0,
            "open_positions": [
                {
                    "symbol": p["symbol"],
                    "direction": "long" if p["direction"] == 1 else "short",
                    "unrealized_pnl": round(p["unrealized_pnl"], 6),
                    "hold_bars": p["hold_bars"],
                }
                for p in positions
            ],
            "aggregate_pnl": round(self.tracker.portfolio_pnl(), 6),
            "kill_switch": self.portfolio_risk.is_killed(),
            "current_regime": {
                s: REGIME_NAMES.get(self._current_regime[s], "UNKNOWN")
                for s in SYMBOLS
            },
            "today_trades": self._today_trades,
            "last_tick_time": datetime.now(timezone.utc).isoformat(),
            "active_regimes": ACTIVE_REGIMES,
            "signal_values": {
                s: round(self._cached_signal[s], 6) for s in SYMBOLS
            },
        }
        tmp = self.status_path.with_suffix(".tmp")
        try:
            with open(tmp, "w") as f:
                json.dump(status, f, indent=2)
            os.replace(tmp, self.status_path)
        except OSError:
            LOG.exception("Failed to write status file")

    # ── shutdown ─────────────────────────────────────────────────────

    def _request_shutdown(self) -> None:
        LOG.info("Shutdown requested")
        self._shutdown = True

    async def _close_all_positions(self, reason: str) -> None:
        """Close every open position."""
        for sym in list(self.tracker._positions.keys()):
            bar = self.ws.latest_bar(sym)
            price = bar["close"] if bar else 0.0
            record = self.tracker.close_position(sym, price, reason)
            if record:
                self._journal_write(record)
                self._today_trades += 1

    async def _shutdown_sequence(self) -> None:
        """Graceful shutdown: close positions, stop WS, final status."""
        LOG.info("Shutdown sequence: closing all positions")
        await self._close_all_positions("shutdown")
        self._write_status()
        self.monitor.close()
        await self.ws.stop()
        LOG.info("Shutdown complete")


# ── entry point ──────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    project_root = Path(__file__).resolve().parent.parent
    LOG.info("Paper trader starting. Root: %s", project_root)

    trader = PaperTrader(project_root)
    asyncio.run(trader.run())


if __name__ == "__main__":
    main()
