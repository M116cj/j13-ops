"""Live trading module — real-time execution layer for Zangetsu V5.

Components:
    ws_feed         — Binance Futures WebSocket bar feed
    regime_labeler  — Three-layer regime detection (L1/L2/L3)
    risk_manager    — Per-quant-class risk gates and kill switches
    journal         — Trade journal (async, PostgreSQL-backed)
    card_rotation   — Hot-swap deployed cards on ELO changes
    paper_trade     — Simulated execution engine
    main_loop       — Main live trading loop
"""

from .ws_feed import BinanceFuturesWS
from .regime_labeler import LiveRegimeLabeler
from .card_rotation import CardRotator
from .paper_trade import PaperTrader
from .main_loop import LiveLoop
from .journal import TradeJournal

__all__ = [
    "BinanceFuturesWS",
    "LiveRegimeLabeler",
    "CardRotator",
    "PaperTrader",
    "LiveLoop",
    "TradeJournal",
]
