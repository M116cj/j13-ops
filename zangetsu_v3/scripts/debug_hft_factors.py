#!/usr/bin/env python3
import sys; sys.path.insert(0, ".")
import numpy as np, polars as pl
from zangetsu_v3.factors.hft_factors import compute_hft_factors, FACTOR_NAMES
from zangetsu_v3.factors.normalizer import RobustNormalizer
from scripts.run_v31 import load_ohlcv
from zangetsu_v3.regime.rule_labeler import label_symbol, Regime

raw = load_ohlcv("BTCUSDT", 18)
labels_1m, _, _ = label_symbol(raw)
bull = labels_1m == Regime.BULL_TREND
diffs = np.diff(bull.astype(int))
starts = list(np.where(diffs == 1)[0] + 1)
ends = list(np.where(diffs == -1)[0] + 1)
if bull[0]: starts = [0] + starts
if bull[-1]: ends = ends + [len(labels_1m)]

for s, e in zip(starts, ends):
    if e - s > 5000:
        seg = raw.slice(s, e - s)
        fm = compute_hft_factors(seg)
        fm_np = fm.to_numpy()
        valid = ~np.any(np.isnan(fm_np), axis=1)
        fm_np = fm_np[valid]
        print(f"Segment: {e-s} bars, {fm_np.shape[0]} valid rows")
        print("\nRaw factor stds:")
        for i, name in enumerate(FACTOR_NAMES):
            print(f"  {name:20s} std={np.std(fm_np[:, i]):.6f}")

        norm = RobustNormalizer()
        fm_df = pl.DataFrame({n: fm_np[:, i] for i, n in enumerate(FACTOR_NAMES)})
        norm.fit(fm_df)
        fm_normed = norm.transform(fm_df).to_numpy()
        print("\nNormalized factor stds:")
        for i, name in enumerate(FACTOR_NAMES):
            print(f"  {name:20s} std={np.std(fm_normed[:, i]):.6f}")

        rng = np.random.default_rng(42)
        stds = []
        for _ in range(100):
            w = rng.standard_normal(15) * 0.5
            sig = fm_normed @ w
            stds.append(np.std(sig))
        print(f"\nSignal std (post-norm, single seg): median={np.median(stds):.4f}")
        break
