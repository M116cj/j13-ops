import numpy as np
from zangetsu.core_factory.signal_processing import (
    signal_to_trades_band_crossing, signal_to_trades_sign_flip,
)


def test_band_crossing_generates_trades():
    rng = np.random.default_rng(1)
    n = 500
    signal = rng.normal(0, 1, n).astype(np.float32)
    close = (100.0 + np.cumsum(rng.normal(0, 0.1, n))).astype(np.float32)
    returns_k1, nl1, ns1 = signal_to_trades_band_crossing(
        signal, close, 'BOTH', band_k=1.0, rolling_sigma_window=20,
    )
    assert nl1 + ns1 > 0


def test_band_crossing_supports_three_k_values():
    rng = np.random.default_rng(2)
    n = 600
    signal = rng.normal(0, 1, n).astype(np.float32)
    close = (100.0 + np.cumsum(rng.normal(0, 0.1, n))).astype(np.float32)
    counts = []
    for k in (0.5, 1.0, 1.5):
        rets, nl, ns = signal_to_trades_band_crossing(
            signal, close, 'LONG', band_k=k, rolling_sigma_window=20,
        )
        counts.append(nl + ns)
    # k=0.5 should produce more triggers than k=1.5 on a stationary signal.
    assert counts[0] >= counts[2]


def test_band_crossing_long_mode_excludes_shorts():
    rng = np.random.default_rng(3)
    n = 400
    signal = rng.normal(0, 1, n).astype(np.float32)
    close = (100.0 + np.cumsum(rng.normal(0, 0.1, n))).astype(np.float32)
    rets, nl, ns = signal_to_trades_band_crossing(
        signal, close, 'LONG', band_k=1.0, rolling_sigma_window=20,
    )
    assert ns == 0


def test_band_crossing_short_mode_excludes_longs():
    rng = np.random.default_rng(4)
    n = 400
    signal = rng.normal(0, 1, n).astype(np.float32)
    close = (100.0 + np.cumsum(rng.normal(0, 0.1, n))).astype(np.float32)
    rets, nl, ns = signal_to_trades_band_crossing(
        signal, close, 'SHORT', band_k=1.0, rolling_sigma_window=20,
    )
    assert nl == 0
