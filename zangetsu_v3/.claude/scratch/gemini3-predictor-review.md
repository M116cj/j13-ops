# Online Predictor Review — 2026-04-06

## 1. Lookahead Bias — PASS
**Severity: OK**
- `_compute_online_features()` uses only past data: EMA, ATR, rolling percentile, slope lookback, BB width — all causal.
- `predict_fine()` takes close/high/low/volume arrays and predicts on the LAST bar only.
- Training labels come from `rule_labeler.label_symbol()` which DOES use lookahead (by design — it's the ground truth). The model learns to approximate these labels using past-only features. This is the correct approach.

## 2. Train/Test Split — PASS with caveat
**Severity: LOW**
- `train_predictor.py` line 182: `split = int(len(X) * 0.8)` — time-based 80/20 split. Correct.
- **Caveat**: Multiple symbols are stacked sequentially (all_X.append), so the "last 20%" includes the tail of the last symbol loaded. If symbols have different time ranges, the test set is disproportionately the last symbol. Not ideal but acceptable since all symbols cover similar date ranges.

## 3. Overfit Risk — MEDIUM
**Severity: MEDIUM**
- LightGBM with 300 trees, max_depth=6, class_weight="balanced" — reasonable.
- No cross-validation. Single train/test split means accuracy estimate has high variance.
- Regime distribution may shift over time (e.g., 2024 was mostly BULL_TREND). Model trained on 2024 data may underperform in 2025 bear market.
- **Recommendation**: Add purged k-fold CV, or at minimum report per-quarter accuracy.

## 4. 13-State Coverage — PASS
**Severity: OK**
- `Regime` IntEnum has 13 values (0-12). `predict_fine()` clamps output to [0, 12] (line 197).
- `step()` debounce works on any integer — no filter on 13-state range.
- COARSE_MAP maps 11→7, 12→0 for search compatibility but fine prediction returns raw 0-12.

## 5. Debounce Logic — PASS
**Severity: OK**
- `predict_fine()` calls `step()` at the end, which applies debounce (5 consecutive bars required).
- Operates on 4h bar arrays, not 1m — correct level.
- `switch_confidence` ramps from 0.3 → 1.0 over 30 bars via `_confidence()`. Correct.

## 6. Feature Parity — HIGH (train/serve skew risk)
**Severity: HIGH**
- `train_predictor.compute_features()` and `predictor._compute_online_features()` are INDEPENDENTLY implemented with the same logic. Any future change to one without the other = silent train/serve skew.
- Both produce the same 12 features in the same order (verified by code comparison).
- `np.convolve(..., mode="same")` for BB mean and vol_ma — this uses future data at array boundaries (mode="same" pads symmetrically). Both training and serving use it, so no skew currently, but it's technically a minor lookahead at edges.
- **Recommendation**: Extract shared function. Or at minimum add a test that verifies both produce identical output on the same input.

## 7. Switch Confidence Ramp — PASS
**Severity: OK**
- `_confidence(bars)` = min(1.0, 0.3 + 0.7 * (bars / 30.0))
- At switch: bars=1 → confidence=0.323
- After 30 bars: confidence=1.0
- Monotonically increasing, bounded [0.3, 1.0]. Correct.

## Summary

| # | Finding | Severity |
|---|---------|----------|
| 1 | No lookahead in features | OK |
| 2 | Time-based split correct | LOW |
| 3 | No cross-validation | MEDIUM |
| 4 | Full 13-state coverage | OK |
| 5 | Debounce at 4h level | OK |
| 6 | **Duplicated feature code — skew risk** | HIGH |
| 7 | Confidence ramp correct | OK |

**One HIGH item: feature computation is duplicated between train and serve. Must be refactored to shared function before production.**
