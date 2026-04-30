"""0-9AC Round 2 cross-cutting invariants."""

import inspect
import pathlib
from zangetsu.core_factory import shadow_batch_runner as sbr
from zangetsu.core_factory import signal_processing as sp
from zangetsu.core_factory.constants import A2_MIN_TRADES
from zangetsu.services import arena_gates


def test_a2_min_trades_unchanged_round2():
    assert A2_MIN_TRADES == 25
    assert arena_gates.A2_MIN_TRADES == 25


def test_round2_does_not_import_arena_pipeline():
    src = inspect.getsource(sbr)
    assert 'arena_pipeline' not in src
    assert 'production' not in src.lower() or 'production runtime' in src


def test_clip_metadata_includes_required_keys():
    import numpy as np
    sig = np.array([1.0, 2.0, 3.0, 100.0, -50.0], dtype=np.float32)
    _, meta = sp.apply_p99_abs_clip(sig)
    md = meta.to_dict()
    for key in ('enabled', 'method', 'threshold', 'pre_clip_min', 'pre_clip_max',
                'post_clip_min', 'post_clip_max', 'pre_variance', 'post_variance'):
        assert key in md


def test_no_unknown_reject_silent_drop():
    # signal_processing must not silently drop; sign_flip with all zero signal
    # should produce zero trades, not a crash or fabricated count.
    import numpy as np
    sig = np.zeros(100, dtype=np.float32)
    close = np.linspace(100, 110, 100, dtype=np.float32)
    rets, nl, ns = sp.signal_to_trades_sign_flip(sig, close, 'BOTH')
    assert rets == [] and nl == 0 and ns == 0


def test_band_crossing_no_signal_no_trades():
    import numpy as np
    sig = np.zeros(100, dtype=np.float32)
    close = np.linspace(100, 110, 100, dtype=np.float32)
    rets, nl, ns = sp.signal_to_trades_band_crossing(
        sig, close, 'BOTH', band_k=1.0, rolling_sigma_window=20,
    )
    assert rets == [] and nl == 0 and ns == 0
