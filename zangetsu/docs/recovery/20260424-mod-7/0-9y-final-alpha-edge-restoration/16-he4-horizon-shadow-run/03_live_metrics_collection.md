# 03 — LIVE METRICS COLLECTION

**TEAM ORDER**: 0-9Y-HE4-HORIZON-SHADOW-RUN
**Date**: 2026-04-29
**Phase**: 3 / 8

## Collection window
| Field | Value |
|---|---|
| Activated | 2026-04-29T08:13:40Z (workers restarted with horizon env) |
| First post-restart batch | 2026-04-29T08:15:04Z |
| Stop / freeze | 2026-04-29T13:05:01Z |
| Duration | **~4h 50m** |

## Sample size
| Metric | Value |
|---|---|
| Total `arena_batch_metrics` events in window | **3266** |
| Batches with horizon ∈ {180, 240, 360} | **3266 / 3266** = 100% ✅ |
| Per-horizon distribution | h=180: **1088** \| h=240: **1089** \| h=360: **1089** |
| Master-order minimum (≥100 / horizon) | **exceeded by 10.9×** |
| Master-order preferred (150-200 / horizon) | **exceeded by 5.4-7.3×** |
| Total alpha entries (10/batch × 3266) | ~32 660 |

Allocation across horizons is virtually exactly equal: 1088 / 1089 / 1089 — confirming the deterministic SIMPLE_CYCLE rotation worked correctly over thousands of rounds.

## Conservation sanity
```
entered_count = 32660
sum(passed + rejected + skipped + in_flight + error) = 32660
residual = 0  ✅
```

## Per-horizon telemetry sanity
| Horizon | UNKNOWN_REJECT total | Conservation residual | with_horizon_metrics | symbols (top-1 share) |
|---|---|---|---|---|
| 180 | **0** ✅ | 0 ✅ | 1088 / 1088 ✅ | 14 unique, top-1 = DOTUSDT 13.1% |
| 240 | **0** ✅ | 0 ✅ | 1089 / 1089 ✅ | 14 unique, top-1 = LINKUSDT 12.8% |
| 360 | **0** ✅ | 0 ✅ | 1089 / 1089 ✅ | 14 unique, top-1 = LINKUSDT 13.5% |

No single-symbol artifact across any horizon (top-1 share ≤ 13.5% << 80% threshold).

## Reject reason distribution per horizon
| Horizon | Top-3 reasons |
|---|---|
| 180 | COST_NEGATIVE 10844, SIGNAL_TOO_SPARSE 34, LOW_BACKTEST_SCORE 2 |
| 240 | COST_NEGATIVE 10861, SIGNAL_TOO_SPARSE 29 |
| 360 | COST_NEGATIVE 10879, SIGNAL_TOO_SPARSE 11 |

`COST_NEGATIVE` continues to dominate at all horizons (>99.5% of rejects), matching pre-HE4 baseline behavior. Note: `SIGNAL_TOO_SPARSE` decreases with longer horizon (34→29→11), suggesting longer horizons capture slightly more wide-window signal — but the magnitude is small relative to total rejects.

## Frozen artifact
- `/tmp/0_9y_he4_shadow_collected.jsonl` (69609 lines)
- `/tmp/he4_analyze.py` (parser/analyzer)
- `/tmp/0_9y_he4_phase4_summary.json` (per-horizon summary)

## Verdict
**PHASE_3_COMPLETE** — sample exceeds preferred target by 5×; equal-allocation cycling confirmed; conservation + telemetry clean across all 3 horizons.

## Next
Phase 4 — per-horizon economic analysis.
