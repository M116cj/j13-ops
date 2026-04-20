"""V10 Signal Reconstructor — rebuild signal arrays from passport.

Handles both V9 (indicator combos) and V10 (alpha expressions).

Dispatches based on passport content:
  - passport['arena1']['alpha_expression']  -> V10 alpha path
  - passport['arena1']['configs']           -> V9 indicator path (fallback)

Returns (signals, sizes, agreements) — identical tuple shape to
signal_utils.generate_threshold_signals, so downstream A2/A3/A4/A5 gate
logic is unchanged.
"""
import logging
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)


def reconstruct_signal_from_passport(
    passport: dict,
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    open_arr: np.ndarray,
    volume: np.ndarray,
    indicator_cache: Optional[dict] = None,
    entry_threshold: float = 0.80,
    exit_threshold: float = 0.50,
    min_hold: int = 60,
    cooldown: int = 60,
    regime: str = "UNKNOWN",
) -> tuple:
    """Returns (signals, sizes, agreements) tuple.

    Dispatches based on passport content:
    - passport.arena1.alpha_expression -> V10 alpha path (GP formula)
    - passport.arena1.configs          -> V9 indicator path (legacy voting)

    The gate logic in A2/A3/A4/A5 is unchanged: it only consumes the returned
    (signals, sizes, agreements) tuple.
    """
    arena1 = passport.get('arena1', {}) if isinstance(passport, dict) else {}

    if 'alpha_expression' in arena1 and arena1['alpha_expression']:
        return _reconstruct_from_alpha(
            arena1['alpha_expression'],
            close, high, low, open_arr, volume, indicator_cache,
            entry_threshold, exit_threshold, min_hold, cooldown,
        )
    if 'configs' in arena1 and arena1['configs']:
        return _reconstruct_from_indicators(
            arena1['configs'],
            close, high, low, open_arr, volume,
            entry_threshold, exit_threshold, min_hold, cooldown, regime,
        )

    # Empty / malformed passport — return zero signal
    n = len(close)
    log.warning("reconstruct_signal_from_passport: passport missing both alpha_expression and configs; returning zero signal")
    return (
        np.zeros(n, dtype=np.int8),
        np.zeros(n, dtype=np.float64),
        np.zeros(n, dtype=np.float32),
    )


def _zero_signal(n: int) -> tuple:
    return (
        np.zeros(n, dtype=np.int8),
        np.zeros(n, dtype=np.float64),
        np.zeros(n, dtype=np.float32),
    )


def _reconstruct_from_alpha(
    alpha_expr, close, high, low, open_arr, volume,
    indicator_cache, entry_thr, exit_thr, min_hold, cooldown,
):
    """V10 path: compile alpha formula and evaluate to produce signals.

    The AlphaEngine GP terminals are (close, high, low, volume, returns).
    'open_arr' is accepted for interface parity but not consumed by the
    current primitive set; returns is derived from close.
    """
    n = len(close)
    try:
        from deap import gp
        from zangetsu.engine.components.alpha_engine import AlphaEngine
        from zangetsu.engine.components.alpha_signal import generate_alpha_signals
    except Exception as e:
        log.warning(f"Alpha modules unavailable: {e}; returning zero signal")
        return _zero_signal(n)

    formula = alpha_expr.get('formula', '') if isinstance(alpha_expr, dict) else ''
    if not formula:
        log.warning("alpha_expression has no 'formula'; returning zero signal")
        return _zero_signal(n)

    # Cast inputs to float32 (GP terminals were trained on float32 arrays)
    close32 = np.ascontiguousarray(close, dtype=np.float32)
    high32 = np.ascontiguousarray(high, dtype=np.float32)
    low32 = np.ascontiguousarray(low, dtype=np.float32)
    vol32 = np.ascontiguousarray(volume, dtype=np.float32)

    # Returns: simple pct-change of close, zero-prefixed (matches alpha_discovery)
    returns32 = np.zeros_like(close32)
    returns32[1:] = (close32[1:] - close32[:-1]) / np.maximum(close32[:-1], 1e-10)

    # end-to-end-upgrade fix 2026-04-19: if caller did not pre-compute
    # indicator_cache, build one from the OHLCV we already have. Without this,
    # AlphaEngine falls back to zeros for all 126 indicator terminals and the
    # reconstructed formula evaluates differently from how A1 evolved it.
    if not indicator_cache:
        try:
            from zangetsu.engine.components.indicator_bridge import build_indicator_cache
            indicator_cache = build_indicator_cache(
                np.ascontiguousarray(close, dtype=np.float64),
                np.ascontiguousarray(high, dtype=np.float64),
                np.ascontiguousarray(low, dtype=np.float64),
                np.ascontiguousarray(volume, dtype=np.float64),
            )
        except Exception as e:  # noqa: BLE001
            log.warning(f"Inline indicator_cache build failed: {e}; terminals will be zeros")
            indicator_cache = {}

    try:
        engine = AlphaEngine(indicator_cache=indicator_cache or {})
        tree = gp.PrimitiveTree.from_string(formula, engine.pset)
        func = engine.toolbox.compile(expr=tree)
        alpha_values = func(close32, high32, low32, close32, vol32)
        # Ephemeral scalar constants may be returned as len-1 np.full broadcast;
        # coerce to length-n array
        alpha_values = np.asarray(alpha_values, dtype=np.float32)
        if alpha_values.ndim == 0 or alpha_values.size == 1:
            alpha_values = np.full(n, float(alpha_values), dtype=np.float32)
        elif len(alpha_values) != n:
            log.warning(f"Alpha eval returned len={len(alpha_values)}, expected {n}; zero signal")
            return _zero_signal(n)
        alpha_values = np.nan_to_num(alpha_values, nan=0.0, posinf=0.0, neginf=0.0)
    except Exception as e:
        log.warning(f"Alpha reconstruction failed: {e}; returning zero signal")
        return _zero_signal(n)

    try:
        signals, sizes, agreements = generate_alpha_signals(
            alpha_values,
            entry_threshold=entry_thr,
            exit_threshold=exit_thr,
            min_hold=min_hold,
            cooldown=cooldown,
        )
    except Exception as e:
        log.warning(f"generate_alpha_signals failed: {e}; returning zero signal")
        return _zero_signal(n)

    return signals, sizes, agreements


def _reconstruct_from_indicators(
    configs, close, high, low, open_arr, volume,
    entry_thr, exit_thr, min_hold, cooldown, regime,
):
    """V9 path: compute raw indicators and use legacy threshold voting."""
    n = len(close)
    try:
        import zangetsu_indicators as zi
        from zangetsu.engine.components.signal_utils import generate_threshold_signals
    except Exception as e:
        log.warning(f"V9 indicator modules unavailable: {e}; returning zero signal")
        return _zero_signal(n)

    close64 = np.ascontiguousarray(close, dtype=np.float64)
    high64 = np.ascontiguousarray(high, dtype=np.float64)
    low64 = np.ascontiguousarray(low, dtype=np.float64)
    vol64 = np.ascontiguousarray(volume, dtype=np.float64)

    names, arrs = [], []
    for cfg in configs:
        try:
            name = cfg['name']
            period = cfg.get('period', 14)
            vals = zi.compute(name, {'period': period}, close64, high64, low64, vol64)
            names.append(name)
            arrs.append(np.asarray(vals, dtype=np.float64))
        except Exception as e:
            log.debug(f"Indicator {cfg} failed: {e}")
            continue

    if len(names) < 1:
        return _zero_signal(n)

    try:
        return generate_threshold_signals(
            names, arrs,
            entry_threshold=entry_thr, exit_threshold=exit_thr,
            min_hold=min_hold, cooldown=cooldown, regime=regime,
        )
    except Exception as e:
        log.warning(f"generate_threshold_signals failed: {e}; returning zero signal")
        return _zero_signal(n)
