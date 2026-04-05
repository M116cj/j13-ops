#!/usr/bin/env python3
"""Generate full regime data report for V3.1 planning."""
import sys; sys.path.insert(0, '.')
import numpy as np
from scripts.run_production import load_ohlcv
from zangetsu_v3.regime.rule_labeler import (
    label_symbol, regime_report, REGIME_NAMES, Regime, SEARCH_REGIMES
)

SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT']

# Build search regime mapping
search_map = {}
for search_name, fine_list in SEARCH_REGIMES.items():
    for r in fine_list:
        search_map[int(r)] = search_name
search_map.setdefault(int(Regime.CHOPPY_VOLATILE), "OTHER")
search_map.setdefault(int(Regime.LIQUIDITY_CRISIS), "OTHER")
search_map.setdefault(int(Regime.PARABOLIC), "OTHER")

# Collect data
all_data = {}
all_13_bars = {r.name: 0 for r in Regime}
all_13_segs = {r.name: 0 for r in Regime}
search_segs = {k: [] for k in list(SEARCH_REGIMES.keys()) + ["OTHER"]}

for sym in SYMBOLS:
    raw = load_ohlcv(sym, 18)
    labels_1m, labels_4h, df_4h = label_symbol(raw)
    rpt_4h = regime_report(labels_4h, timeframe_minutes=240)

    # 1m bars per search regime
    sym_1m = {sr: 0 for sr in list(SEARCH_REGIMES.keys()) + ["OTHER"]}
    for lbl in labels_1m:
        sr = search_map.get(int(lbl), "OTHER")
        sym_1m[sr] += 1

    all_data[sym] = {"labels_1m": labels_1m, "rpt_4h": rpt_4h, "search_1m": sym_1m, "total_1m": len(labels_1m)}

    # Accumulate 13-state
    for name, info in rpt_4h['regimes'].items():
        all_13_bars[name] += info['bars']
        all_13_segs[name] += info['segments']

    # Extract segments >= 1 day per search regime
    for sr_name in list(SEARCH_REGIMES.keys()) + ["OTHER"]:
        sr_mask = np.array([search_map.get(int(l), "OTHER") == sr_name for l in labels_1m])
        diffs = np.diff(sr_mask.astype(int))
        starts = list(np.where(diffs == 1)[0] + 1)
        ends = list(np.where(diffs == -1)[0] + 1)
        if sr_mask[0]:
            starts = [0] + starts
        if sr_mask[-1]:
            ends = ends + [len(labels_1m)]
        for s, e in zip(starts, ends):
            seg_len = e - s
            if seg_len >= 1440:
                search_segs[sr_name].append({"symbol": sym, "start": s, "end": e, "bars": seg_len, "days": seg_len / 1440})


# ── Print Report ──

print("=" * 95)
print("ZANGETSU V3.1 — REGIME DATA REPORT")
print("=" * 95)
print()

# Table 1: Per-symbol 1m bars by search regime
print("TABLE 1: Per-Symbol 1m Bars by Search Regime")
print("-" * 95)
print(f"{'SYMBOL':12s} {'BULL':>12s} {'BEAR':>12s} {'CONSOL':>12s} {'SQUEEZE':>12s} {'OTHER':>10s} {'TOTAL':>12s}")
print("-" * 95)
totals = {sr: 0 for sr in list(SEARCH_REGIMES.keys()) + ["OTHER"]}
for sym in SYMBOLS:
    d = all_data[sym]
    s = d["search_1m"]
    for k in totals:
        totals[k] += s.get(k, 0)
    print(f"{sym:12s} {s['BULL_TREND']:>11d}  {s['BEAR_TREND']:>11d}  {s['CONSOLIDATION']:>11d}  {s['SQUEEZE']:>11d}  {s.get('OTHER',0):>9d}  {d['total_1m']:>11d}")
grand = sum(totals.values())
print("-" * 95)
print(f"{'TOTAL':12s} {totals['BULL_TREND']:>11d}  {totals['BEAR_TREND']:>11d}  {totals['CONSOLIDATION']:>11d}  {totals['SQUEEZE']:>11d}  {totals.get('OTHER',0):>9d}  {grand:>11d}")
for sr in list(SEARCH_REGIMES.keys()) + ["OTHER"]:
    pct = totals[sr] / grand * 100
    print(f"  {sr:20s} = {pct:.1f}%")
print()

# Table 2: Training segments per search regime (>= 1 day, cross-symbol)
print("TABLE 2: Training Segments per Search Regime (>= 1 day)")
print("-" * 95)
print(f"{'REGIME':20s} {'SEGS':>6s} {'TOTAL DAYS':>12s} {'AVG':>8s} {'MIN':>8s} {'MEDIAN':>8s} {'MAX':>8s} {'SYMBOLS':>10s}")
print("-" * 95)
for sr_name in list(SEARCH_REGIMES.keys()) + ["OTHER"]:
    segs = search_segs[sr_name]
    if not segs:
        print(f"{sr_name:20s} {'0':>6s}")
        continue
    days = [s["days"] for s in segs]
    syms = set(s["symbol"] for s in segs)
    print(f"{sr_name:20s} {len(segs):>6d} {sum(days):>11.1f}d {np.mean(days):>7.1f}d {np.min(days):>7.1f}d {np.median(days):>7.1f}d {np.max(days):>7.1f}d {len(syms):>5d}/6")
print()

# Table 3: 13-state distribution (cross-symbol aggregate)
print("TABLE 3: 13-State Distribution (all symbols, 4h bars)")
print("-" * 70)
total_4h = sum(all_13_bars.values())
print(f"{'STATE':25s} {'4H BARS':>8s} {'%':>6s} {'SEGS':>6s} {'AVG SEG':>9s}")
print("-" * 70)
for name in sorted(all_13_bars.keys(), key=lambda x: -all_13_bars[x]):
    bars = all_13_bars[name]
    segs = all_13_segs.get(name, 0)
    if bars > 0:
        pct = bars / total_4h * 100
        avg_h = (bars / max(segs, 1)) * 4
        print(f"  {name:23s} {bars:>8d} {pct:>5.1f}% {segs:>6d}   {avg_h:>6.1f}h")

# Table 4: TRAIN/HOLDOUT split preview (70/30 by time)
print()
print("TABLE 4: TRAIN/HOLDOUT Split Preview (70/30 by segment time order)")
print("-" * 70)
for sr_name in SEARCH_REGIMES:
    segs = search_segs[sr_name]
    if not segs:
        continue
    n = len(segs)
    n_train = int(n * 0.7)
    n_holdout = n - n_train
    train_days = sum(s["days"] for s in segs[:n_train])
    holdout_days = sum(s["days"] for s in segs[n_train:])
    print(f"  {sr_name:20s} TRAIN: {n_train:>3d} segs ({train_days:>7.1f}d)  HOLDOUT: {n_holdout:>3d} segs ({holdout_days:>7.1f}d)")
