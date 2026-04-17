"""OBSOLETE — V5-era tests, references removed modules (voter, data_weight).
Marked skip pending rewrite for V9 architecture. See TODO.
"""
import pytest
pytest.skip("V5-era tests — modules voter/data_weight deprecated in V9 unification", allow_module_level=True)

#!/usr/bin/env python3
"""Arena 1 single-round simulation — tests the full pipeline."""
import sys, os, time, importlib.util
sys.path.insert(0, "/home/j13/j13-ops/zangetsu_v5")
sys.path.insert(0, "/home/j13/j13-ops/zangetsu_v5/indicator_engine/target/release")

import numpy as np
import random

BASE = "/home/j13/j13-ops/zangetsu_v5/engine/components"

def _load_module(name, filepath):
    """Load a single .py file as a module, bypassing package __init__."""
    spec = importlib.util.spec_from_file_location(name, filepath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

# Pre-register parent packages as empty to avoid relative import issues
import types
for pkg in ["engine", "engine.components"]:
    if pkg not in sys.modules:
        sys.modules[pkg] = types.ModuleType(pkg)

# Load only the modules we need (order matters for cross-deps)
data_loader_mod = _load_module("engine.components.data_loader", f"{BASE}/data_loader.py")
signal_utils_mod = _load_module("engine.components.signal_utils", f"{BASE}/signal_utils.py")
voter_mod = _load_module("engine.components.voter", f"{BASE}/voter.py")
backtester_mod = _load_module("engine.components.backtester", f"{BASE}/backtester.py")
data_weight_mod = _load_module("engine.components.data_weight", f"{BASE}/data_weight.py")

generate_threshold_signals = signal_utils_mod.generate_threshold_signals
compute_signal_strength = signal_utils_mod.compute_signal_strength
grade_signal = signal_utils_mod.grade_signal
Voter = voter_mod.Voter
Backtester = backtester_mod.Backtester
compute_weights = data_weight_mod.compute_weights
weighted_pnl = data_weight_mod.weighted_pnl
weighted_score = data_weight_mod.weighted_score

# Step 1: Load data
print("=" * 60)
print("STEP 1: Load OHLCV data")
try:
    import polars as pl
    df = pl.read_parquet("/home/j13/j13-ops/zangetsu_v5/data/ohlcv/BTCUSDT.parquet")
    df = df.tail(50000)
    close = df['close'].to_numpy().astype(np.float64)
    high = df['high'].to_numpy().astype(np.float64)
    low = df['low'].to_numpy().astype(np.float64)
    volume = df['volume'].to_numpy().astype(np.float64)
    print(f"  OK: {len(close)} bars loaded for BTCUSDT (last 50k)")
except Exception as e:
    print(f"  FAIL: {e}")
    sys.exit(1)

# Step 2: Generate random indicator configs (like Arena 1)
print("\nSTEP 2: Generate random indicator configs")
INDICATOR_SPACE = [
    ("sma", {}), ("ema", {}), ("rsi", {}),
    ("macd", {}), ("atr", {}), ("adx", {}),
    ("bollinger_upper", {}), ("obv", {}),
    ("stochastic_k", {}), ("cci", {}),
    ("roc", {}), ("supertrend", {}), ("zscore", {}),
]
N_CONTESTANTS = 8
N_INDICATORS_PER = 3

contestants = []
for i in range(N_CONTESTANTS):
    selected = random.sample(INDICATOR_SPACE, min(N_INDICATORS_PER, len(INDICATOR_SPACE)))
    configs = []
    for name, _ in selected:
        period = random.choice([7, 14, 20, 30, 50])
        configs.append((name, {"period": period}))
    contestants.append(configs)
    print(f"  Contestant {i}: {[(n, p['period']) for n, p in configs]}")

# Step 3: Compute indicators (try Rust first, fallback Python)
print("\nSTEP 3: Compute indicators")
try:
    import zangetsu_indicators as zi
    USE_RUST = True
    print("  Using Rust engine")
except ImportError:
    USE_RUST = False
    print("  Rust not available, using Python fallback")

def compute_indicator(name, params):
    if USE_RUST:
        return zi.compute(name, params, close, high, low, volume)
    else:
        n = len(close)
        period = params.get("period", 14)
        if name in ("sma", "ema"):
            sma = np.convolve(close, np.ones(period)/period, mode='full')[:n]
            sma[:period-1] = sma[period-1]
            return sma
        elif name == "rsi":
            delta = np.diff(close, prepend=close[0])
            gain = np.where(delta > 0, delta, 0)
            loss = np.where(delta < 0, -delta, 0)
            avg_gain = np.convolve(gain, np.ones(period)/period, mode='full')[:n]
            avg_loss = np.convolve(loss, np.ones(period)/period, mode='full')[:n]
            rs = avg_gain / (avg_loss + 1e-12)
            return 100 - 100 / (1 + rs)
        else:
            return np.zeros(n)

test_val = compute_indicator("sma", {"period": 14})
print(f"  Test SMA(14): len={len(test_val)}, sample={test_val[-1]:.2f}")

# Step 4: For each contestant, compute normalized matrix and signals
print("\nSTEP 4: Compute signals via signal_utils")

results = []
for i, configs in enumerate(contestants):
    indicator_values = []
    for name, params in configs:
        try:
            values = compute_indicator(name, params)
            indicator_values.append(values)
        except Exception as e:
            print(f"  WARNING: {name} failed: {e}, using zeros")
            indicator_values.append(np.zeros(len(close)))

    matrix = np.column_stack(indicator_values)

    # Normalize: (x - median) / MAD, clip +/-5
    medians = np.median(matrix, axis=0)
    mads = np.median(np.abs(matrix - medians), axis=0) * 1.4826
    mads[mads == 0] = 1e-12
    normalized = np.clip((matrix - medians) / mads, -5, 5)

    signals, agreements = generate_threshold_signals(normalized, 0.80, 0.50)

    entries = np.where(np.diff(signals != 0) & (signals[1:] != 0))[0]
    n_trades = len(entries)

    strengths = compute_signal_strength(normalized, agreements, close, vol_window=60)
    avg_strength = np.mean(strengths[strengths > 0]) if np.any(strengths > 0) else 0.0

    print(f"  Contestant {i}: signals={np.sum(signals!=0)}, trades~={n_trades}, avg_strength={avg_strength:.3f}")
    results.append({
        "id": i,
        "configs": configs,
        "n_signals": int(np.sum(signals != 0)),
        "n_trades": n_trades,
        "avg_strength": avg_strength,
        "normalized": normalized,
        "signals": signals,
    })

# Step 5: Backtest top contestant
print("\nSTEP 5: Backtest")

class MockConfig:
    backtest_chunk_size = 10000
    backtest_gpu_enabled = False
    backtest_gpu_batch_size = 64

bt = Backtester(MockConfig())

candidates = [r for r in results if r["n_trades"] > 0]
if not candidates:
    best = max(results, key=lambda x: x["n_signals"])
    print(f"  WARNING: No trades found, using contestant {best['id']} with {best['n_signals']} signals")
else:
    best = max(candidates, key=lambda x: x["n_trades"])
    print(f"  Testing contestant {best['id']} with {best['n_trades']} estimated trades")

signals = best["signals"]

bt_result = bt.run(
    signals=signals,
    close=close,
    symbol="BTCUSDT",
    cost_bps=5.0,
    max_hold_bars=48,
    high=high,
    low=low,
)

print(f"  Trades: {bt_result.total_trades}")
print(f"  Win Rate: {bt_result.win_rate:.4f}")
print(f"  Net PnL: {bt_result.net_pnl:.6f}")
print(f"  Sharpe: {bt_result.sharpe_ratio:.4f}")
print(f"  Max DD: {bt_result.max_drawdown:.6f}")

# Step 6: Score
print("\nSTEP 6: Score")

if bt_result.total_trades > 0:
    timestamps = df['timestamp'].to_numpy().astype(np.float64)
    weights = compute_weights(timestamps)
    pnl_array = np.diff(bt_result.equity_curve, prepend=0.0)
    w_pnl = weighted_pnl(pnl_array, weights)
    score = weighted_score(bt_result.win_rate, max(w_pnl, 0))
    print(f"  Weighted PnL: {w_pnl:.6f}")
    print(f"  Score: {score:.6f}")
else:
    print(f"  No trades, score = 0")

# Step 7: Voter health check
print("\nSTEP 7: Component health checks")

class VoterConfig:
    voter_agreement_threshold = 0.80
    voter_short_circuit = True

v = Voter(VoterConfig())
norm_sample = best["normalized"]
for i in range(min(200, len(norm_sample))):
    v.vote_bar(norm_sample[i].tolist())

voter_health = v.health_check()
bt_health = bt.health_check()
print(f"  Voter: {voter_health}")
print(f"  Backtester: {bt_health}")

print("\n" + "=" * 60)
print("ARENA 1 SIMULATION COMPLETE")
print("=" * 60)
