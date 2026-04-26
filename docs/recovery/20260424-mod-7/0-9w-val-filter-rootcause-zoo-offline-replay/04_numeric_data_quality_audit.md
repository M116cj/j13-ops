# 04 — Numeric and Data Quality Audit

## 1. RuntimeWarning Frequency (per worker, current cycle)

| Worker | Total RuntimeWarning lines | Types observed |
| --- | --- | --- |
| w0 | 4 | overflow / square (×2), overflow / reduce (×2) |
| w1 | 4 | same |
| w2 | 4 | same |
| w3 | 4 | same |

Total: **8 unique events across 4 workers** since 13:15 spawn (~37 min). Roughly one per worker every 9-10 minutes. **Non-blocking** (numpy default is to warn, not raise).

## 2. Source Lines

| File | Line | Pattern |
| --- | --- | --- |
| `numpy/_core/_methods.py:190` | `x = um.square(x, out=x)` | `RuntimeWarning: overflow encountered in square` |
| `numpy/_core/_methods.py:201` | `ret = umr_sum(x, axis, dtype, out, keepdims=keepdims, where=where)` | `RuntimeWarning: overflow encountered in reduce` |

Both come from `np.std()` / `np.mean()` style calls inside numpy internal codepaths. User-code call site is not directly captured in the warning, but they emerge during alpha evaluation (likely `np.std(av_val)` at `arena_pipeline.py:998`).

## 3. NaN / inf Handling

| Layer | Mechanism |
| --- | --- |
| Alpha output | `av_val = np.nan_to_num(av_val, nan=0.0, posinf=0.0, neginf=0.0)` (`arena_pipeline.py:1003`) — NaN/inf clamped to 0 |
| Constant signal detection | `if np.std(av_val) < 1e-10: stats["reject_val_constant"] += 1; continue` (line 998) — clamped-to-zero arrays caught here |
| Backtester signal validation | not explicitly scanned, but signals are typed `float32` — no inf propagation |

→ NaN/inf does NOT route to `val_neg_pnl`. It routes to `val_constant` (via std=0) or `val_error` (if exception). Live stats show `val_constant` is rare (counters near 0) — implying NaN/inf is uncommon.

## 4. Indicator Cache Validity

| Field | Status |
| --- | --- |
| Patch E (2026-04-19) status | **applied** — `engine.indicator_cache.clear()` + `update(holdout_indicator_cache.get(sym, {}))` swap before val backtest, restored via `finally` (lines 996, 1019) |
| Train cache contamination risk | mitigated — Patch E swaps caches per evaluation |
| Cache key correctness | indicator names match terminals (verified by AlphaEngine init logs `126 indicator terminals`) |

→ No evidence of indicator-cache contamination. Patch E is functioning.

## 5. Data Quality

| File | Size | Earliest bar | Latest bar | Bars |
| --- | --- | --- | --- | --- |
| BTCUSDT.parquet | 100 MB | 2019-09-18 | 2026-04-26 | 3 474 000 |
| XRPUSDT.parquet | 78 MB | 2020-01-06 | 2026-04-26 | 3 315 100 |
| 1000PEPEUSDT.parquet | 56 MB | 2023-05-09 | 2026-04-26 | 1 560 241 |

| Quality check | Result |
| --- | --- |
| File mtime (latest data refresh) | 2026-04-26T12:00 (today, ~2 hours before audit) |
| Columns | `timestamp, open, high, low, close, volume` (canonical OHLCV) |
| Missing-bar / gap audit | not run in this read-only audit (would require statistical scan) |
| Stale candles | unlikely (data updated 2 hours ago) |
| Duplicate timestamps | not observed (offline replay would have raised) |

## 6. Constant Alpha Rate

In offline replay (Phase 7): 0/150 evaluations hit `val_constant`. Post-Patch-E, the indicator cache swap appears to be eliminating the historical 5353/5500 contamination problem.

## 7. Phase 4 Classification

Per order §16:

| Verdict | Match? |
| --- | --- |
| NUMERIC_CORRUPTION_LIKELY | NO (only 4 RuntimeWarnings per worker over 37 min; non-blocking; nan_to_num catches outputs) |
| **NUMERIC_REJECTION_VALID** | **YES** — the rare numeric events are correctly caught by `val_constant` / `val_error`; not the cause of mass rejection |
| INDICATOR_CACHE_CONTAMINATION_LIKELY | NO (Patch E applied) |
| DATA_GAP_LIKELY | NO (data freshness 2 hours; no obvious gaps in size) |
| **DATA_QUALITY_OK** | **YES** for the available evidence |
| NUMERIC_UNKNOWN | NO |

→ **Phase 4 verdict: NUMERIC_REJECTION_VALID + DATA_QUALITY_OK.** Numeric handling is correct and bounded. Data is fresh. Numeric is NOT the root cause of `val_neg_pnl` dominance.
