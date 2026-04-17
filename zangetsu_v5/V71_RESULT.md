# V7.1 Deployment Result — Semantic Continuous Signals

## Status: DEPLOYED ✓
**Deployed**: 2026-04-16 07:57 UTC
**Engine Hash**: zv5_v71

## Changes Applied (6 steps)

### Step 1+2: signal_utils.py — Core Rewrite
- INDICATOR_SIGNALS: binary {+1,0,-1} → continuous [-1,+1] float64
- Overbought/Oversold (RSI, Stochastic, MFI, StochRSI): `clip((threshold-v)/threshold, 0.1, 1.0)`
- Zero-crossing (MACD, ROC, PPO, CMO, TSI, TRIX, OBV): `tanh(v/MAD)` normalization
- Mean-reversion (zscore, vwap): `clip((-thr-v)/thr, 0.1, 1.0)`
- _trend_vote: continuous `tanh(delta/avg_delta)` output
- _threshold_signals_numba: float64 vote_matrix, |v|>0.05 nonzero threshold
- NEW return: `(signals, sizes, agreements)` — sizes = mean(|vote_values|) for nonzero
- generate_threshold_signals: now returns 3-tuple (drop-in replacement for composite)

### Step 3: backtester.py — Size Scaling
- `_vectorized_backtest()`: new `sizes` parameter (float64 array)
- PnL scaled by position size: `(raw_return - cost) * size`
- `Backtester.run()`: new optional `sizes` parameter (defaults to ones)

### Step 4: Arena Orchestrators — Reverted to Threshold Signals
- arena_pipeline.py (A1): 4 call sites → generate_threshold_signals
- arena23_orchestrator.py (A23): 5 call sites → _gen_threshold
- arena45_orchestrator.py (A45): 2 call sites → generate_threshold_signals
- All use entry_threshold=0.55, exit_threshold=0.30 (same as v6)

### Step 5: Engine Hash
- `"zv5_v7"` → `"zv5_v71"` in arena_pipeline.py DB insert

### Step 6: Cleanup
- composite_score.py → .deleted (no longer imported anywhere)
- __pycache__ cleared for clean Numba recompilation

## Post-Deploy Verification
- All 6 services running (4×A1, A23, A45)
- Smoke test: sizes range [0.000, 0.999] — continuous confirmed
- Engine logs: A1 producing champions, A2/A3 processing normally
- No import errors or crashes after 20s

## Files Modified
1. `engine/components/signal_utils.py` — full rewrite (backup: .bak)
2. `engine/components/backtester.py` — sizes parameter added (backup: .bak)
3. `services/arena_pipeline.py` — import + 4 call sites + hash (backup: .bak)
4. `services/arena23_orchestrator.py` — import + 5 call sites (backup: .bak)
5. `services/arena45_orchestrator.py` — import + 2 call sites (backup: .bak)
6. `engine/components/composite_score.py` — deleted (.deleted)

## Rollback
All original files preserved as `.bak`. To rollback:
```bash
for f in signal_utils backtester; do
  cp ~/j13-ops/zangetsu_v5/engine/components/${f}.py.bak ~/j13-ops/zangetsu_v5/engine/components/${f}.py
done
for f in arena_pipeline arena23_orchestrator arena45_orchestrator; do
  cp ~/j13-ops/zangetsu_v5/services/${f}.py.bak ~/j13-ops/zangetsu_v5/services/${f}.py
done
mv ~/j13-ops/zangetsu_v5/engine/components/composite_score.py.deleted ~/j13-ops/zangetsu_v5/engine/components/composite_score.py
bash ~/j13-ops/zangetsu_v5/zangetsu_ctl.sh restart
```
