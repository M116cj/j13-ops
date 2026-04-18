"""V10 Regime-Conditional Alpha Discovery.

Instead of searching alphas that work globally, find alphas that excel in specific regimes.

Pipeline:
1. Load symbol's historical OHLCV
2. Segment bars by regime (using existing regime_labeler or proxy)
3. For each regime with >= MIN_REGIME_BARS bars, run GP evolution on that regime's subset
4. Discovered alphas tagged with regime affinity
5. Store to factor_zoo with regime field populated
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, '/home/j13/j13-ops')

import numpy as np
import polars as pl

from zangetsu.engine.components.alpha_engine import AlphaEngine
from zangetsu.engine.components.indicator_bridge import build_indicator_cache
from zangetsu.services.factor_zoo import FactorZoo

log = logging.getLogger(__name__)

DATA_DIR = Path('/home/j13/j13-ops/zangetsu/data/ohlcv')
SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT']
MIN_REGIME_BARS = 10000
REGIMES = [
    'BULL_TREND', 'BEAR_TREND', 'CONSOLIDATION', 'BULL_PULLBACK',
    'BEAR_RALLY', 'ACCUMULATION', 'DISTRIBUTION', 'SQUEEZE',
    'CHOPPY_VOLATILE', 'TOPPING', 'BOTTOMING', 'LIQUIDITY_CRISIS', 'PARABOLIC',
]
RECENT_BARS = 200_000


def _approximate_regime_labels(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    volume: np.ndarray,
) -> np.ndarray:
    """Simple regime proxy when full labeler unavailable.

    Classifies each bar into one of {BULL_TREND, BEAR_TREND, BULL_PULLBACK,
    BEAR_RALLY, CONSOLIDATION} by EMA20/EMA50 spread.
    """
    n = len(close)
    if n == 0:
        return np.array([], dtype=object)

    labels = np.full(n, 'CONSOLIDATION', dtype=object)

    # Use wider EMAs (240/720 ~= 4H/12H at 1m) so the proxy is meaningful on
    # minute-level bars. Combine with percentile thresholds so we don't assume
    # an absolute spread magnitude — this keeps the labeler scale/timeframe
    # agnostic for the V10 Phase-1 smoke run.
    alpha_fast = 2.0 / 241.0
    alpha_slow = 2.0 / 721.0
    ema_fast = np.zeros(n, dtype=np.float64)
    ema_slow = np.zeros(n, dtype=np.float64)
    ema_fast[0] = close[0]
    ema_slow[0] = close[0]
    for i in range(1, n):
        ema_fast[i] = alpha_fast * close[i] + (1 - alpha_fast) * ema_fast[i - 1]
        ema_slow[i] = alpha_slow * close[i] + (1 - alpha_slow) * ema_slow[i - 1]

    denom = np.maximum(np.abs(ema_slow), 1e-10)
    spread = (ema_fast - ema_slow) / denom

    # Percentile thresholds: top/bottom 25% = strong trend,
    # next 25% on each side = pullback/rally, middle 0% = consolidation core.
    # Fall back to absolute thresholds if distribution is degenerate.
    finite = spread[np.isfinite(spread)]
    if finite.size == 0:
        return labels

    hi_strong = float(np.quantile(finite, 0.75))
    hi_weak = float(np.quantile(finite, 0.55))
    lo_weak = float(np.quantile(finite, 0.45))
    lo_strong = float(np.quantile(finite, 0.25))

    # Guard against degenerate quantiles (all-equal spread).
    if hi_strong <= lo_strong:
        return labels

    labels[spread >= hi_strong] = 'BULL_TREND'
    labels[spread <= lo_strong] = 'BEAR_TREND'
    labels[(spread < hi_strong) & (spread >= hi_weak)] = 'BULL_PULLBACK'
    labels[(spread > lo_strong) & (spread <= lo_weak)] = 'BEAR_RALLY'
    # middle band (lo_weak, hi_weak) stays CONSOLIDATION

    return labels


async def discover_regime_alphas(
    symbol: str,
    regime: str,
    n_gen: int = 20,
    pop_size: int = 150,
    top_k: int = 10,
    min_ic: float = 0.02,
) -> List:
    """Run GP evolution on bars belonging to specified regime only.

    Returns list of AlphaResult with |IC| >= min_ic.
    """
    path = DATA_DIR / f"{symbol}.parquet"
    if not path.exists():
        log.warning("Data file missing for %s (%s)", symbol, path)
        return []

    try:
        df = pl.read_parquet(str(path))
    except Exception as exc:  # noqa: BLE001
        log.error("Failed reading parquet %s: %s", path, exc)
        return []

    if df.height == 0:
        log.warning("%s: empty OHLCV", symbol)
        return []

    df = df.tail(RECENT_BARS)

    try:
        close = df['close'].to_numpy().astype(np.float32)
        high = df['high'].to_numpy().astype(np.float32)
        low = df['low'].to_numpy().astype(np.float32)
        volume = df['volume'].to_numpy().astype(np.float32)
        open_arr = (
            df['open'].to_numpy().astype(np.float32)
            if 'open' in df.columns else close.copy()
        )
    except Exception as exc:  # noqa: BLE001
        log.error("Column extraction failed for %s: %s", symbol, exc)
        return []

    # Regime labeling — prefer full labeler if importable, else proxy.
    try:
        from zangetsu.engine.components.regime_labeler import label_4h_causal  # noqa: F401
        # Full labeler operates on 4H resampled data; integrating here requires
        # resampling + join-back. For Phase-1 V10 we use proxy to stay isolated.
        regime_labels = _approximate_regime_labels(close, high, low, volume)
    except Exception as exc:  # noqa: BLE001
        log.warning("Regime labeler unavailable (%s); using proxy", exc)
        regime_labels = _approximate_regime_labels(close, high, low, volume)

    mask = regime_labels == regime
    n_regime_bars = int(mask.sum())

    if n_regime_bars < MIN_REGIME_BARS:
        log.info(
            "%s/%s: only %d bars (need %d), skip",
            symbol, regime, n_regime_bars, MIN_REGIME_BARS,
        )
        return []

    c_r = np.ascontiguousarray(close[mask])
    h_r = np.ascontiguousarray(high[mask])
    l_r = np.ascontiguousarray(low[mask])
    v_r = np.ascontiguousarray(volume[mask])
    o_r = np.ascontiguousarray(open_arr[mask])

    # Build indicator cache on regime slice (Rust expects float64).
    try:
        cache = build_indicator_cache(
            c_r.astype(np.float64), h_r.astype(np.float64),
            l_r.astype(np.float64), v_r.astype(np.float64),
        )
    except Exception as exc:  # noqa: BLE001
        log.error("Cache build failed for %s/%s: %s", symbol, regime, exc)
        cache = {}

    engine = AlphaEngine(indicator_cache=cache) if cache else AlphaEngine()

    # NOTE: AlphaEngine.evolve signature is
    #   (close, high, low, open_arr, volume, n_gen, pop_size, top_k)
    # It computes forward_returns internally — do NOT pass a returns array.
    try:
        results = engine.evolve(
            c_r, h_r, l_r, o_r, v_r,
            n_gen=int(n_gen), pop_size=int(pop_size), top_k=int(top_k),
        )
    except Exception as exc:  # noqa: BLE001
        log.error("Evolve failed for %s/%s: %s", symbol, regime, exc)
        return []

    strong = [r for r in results if abs(getattr(r, 'ic', 0.0)) >= min_ic]
    log.info(
        "%s/%s: %d bars, evolved %d alphas, %d with |IC|>=%.3f",
        symbol, regime, n_regime_bars, len(results), len(strong), min_ic,
    )
    return strong


async def run_discovery_cycle(
    target_regimes: Optional[List[str]] = None,
    symbols: Optional[List[str]] = None,
    n_gen: int = 10,
    pop_size: int = 80,
    top_k: int = 5,
) -> int:
    """One cycle: for each symbol x target_regime, evolve alphas, store to zoo."""
    if target_regimes is None:
        target_regimes = [
            'BULL_TREND', 'BEAR_TREND', 'CONSOLIDATION',
            'BULL_PULLBACK', 'BEAR_RALLY',
        ]
    if symbols is None:
        symbols = SYMBOLS

    zoo = FactorZoo()
    total_stored = 0

    for sym in symbols:
        for regime in target_regimes:
            try:
                alphas = await discover_regime_alphas(
                    sym, regime,
                    n_gen=n_gen, pop_size=pop_size, top_k=top_k,
                )
            except Exception as exc:  # noqa: BLE001
                log.error("discover_regime_alphas crashed %s/%s: %s", sym, regime, exc)
                continue

            for alpha in alphas:
                try:
                    await zoo.store(alpha, sym, regime, arena1_metrics={'n_bars': -1})
                    total_stored += 1
                except Exception as exc:  # noqa: BLE001
                    log.warning("Store failed %s/%s: %s", sym, regime, exc)

    log.info("Discovery cycle complete: %d alphas stored", total_stored)
    return total_stored


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
    )

    async def _smoke() -> None:
        total = await run_discovery_cycle(
            target_regimes=['BULL_TREND', 'CONSOLIDATION'],
            symbols=['BTCUSDT', 'ETHUSDT'],
            n_gen=4, pop_size=40, top_k=3,
        )
        print(f"Test complete: {total} alphas discovered")

    asyncio.run(_smoke())
