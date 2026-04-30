import numpy as np
from zangetsu.core_factory.signal_processing import apply_p99_abs_clip


def test_p99_clip_caps_blow_up():
    sig = np.array([0.0, 1.0, -1.0, 0.5, -0.5, 5000.0, -3000.0, 0.2, -0.1, 0.3], dtype=np.float32)
    clipped, meta = apply_p99_abs_clip(sig)
    assert meta.enabled is True
    assert meta.method == 'p99_abs'
    assert float(np.max(np.abs(clipped))) <= meta.threshold + 1e-3
    assert meta.threshold < 5000.0


def test_p99_clip_preserves_variance():
    rng = np.random.default_rng(42)
    sig = rng.normal(0, 1, size=1000).astype(np.float32)
    clipped, meta = apply_p99_abs_clip(sig)
    assert meta.post_variance > 0
    assert meta.post_variance >= 0.5 * meta.pre_variance


def test_p99_clip_metadata_records_min_max():
    sig = np.array([-100.0, 10.0, 0.0, 5.0, 200.0], dtype=np.float32)
    _, meta = apply_p99_abs_clip(sig)
    assert meta.pre_clip_min == -100.0
    assert meta.pre_clip_max == 200.0
    assert meta.post_clip_min >= -meta.threshold - 1e-3
    assert meta.post_clip_max <= meta.threshold + 1e-3


def test_p99_clip_handles_inf():
    sig = np.array([1.0, 2.0, -3.0, np.inf, -np.inf, 1.5], dtype=np.float32)
    clipped, meta = apply_p99_abs_clip(sig)
    # inf entries are preserved (not clipped); finite stats still computed.
    finite = clipped[np.isfinite(clipped)]
    assert finite.size > 0
