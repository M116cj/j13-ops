# 04 — LIVE SHADOW METRICS

**TEAM ORDER**: 0-9Y-TF3-SIGNAL-AGGREGATION-SHADOW-ACTIVATION
**Date**: 2026-04-28
**Phase**: 4 / 8

## Activation window
| Field | Value |
|---|---|
| Stop baseline workers | 2026-04-28T12:02:56Z |
| Restart with `ARENA_TF3_SHADOW=1` | 2026-04-28T12:03:xx (PIDs 2181934/71/2049/2149) |
| Stop shadow collection | 2026-04-28T12:37:50Z |
| Frozen dataset | `/tmp/0_9y_tf3_shadow_collected.jsonl` (7646 lines) |
| Restored to baseline (`ARENA_TF3_SHADOW` unset) | 2026-04-28T12:38:00Z (PIDs 2220816/39/931/55) |

Worker env confirmed pre-collection:
```
$ cat /proc/<pid>/environ | tr '\0' '\n' | grep ARENA_TF3
ARENA_TF3_SHADOW=1
```

Worker env confirmed post-restoration:
```
$ cat /proc/<pid>/environ | grep ARENA_TF3 → no_TF3_env (OK)
```

## Sample size
| Metric | Value |
|---|---|
| `arena_batch_metrics` events | **352** |
| Batches with `shadow_profiles` payload | **352 / 352** = 100% ✅ |
| Master-order minimum (≥100) | exceeded by **3.5×** |
| Master-order preferred (200-300) | exceeded |
| Total alpha entries observed (across all profiles) | **2 265 423** |

## Conservation sanity (baseline schema)
```
entered_count = 3520
sum(passed + rejected + skipped + in_flight + error) = 3520
residual = 0  ✅
UNKNOWN_REJECT total = 0   ✅
COUNTER_INCONSISTENCY total = 0   ✅
```

## Per-profile metrics (median of per-batch medians)

| Profile | Label | Trade Count | Gross PnL (bps) | Net PnL (bps) | Win Rate | Gross/Trade | Net/Trade | Cost/Gross |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **baseline** | (existing path) | **983** | **+2.4554** | **−1.1768** | **0.3125** | — | — | **1.4964** |
| **strength** | STRENGTH_q0.95 | 64.5 | +0.2111 | −0.0634 | **0.3576** | +0.003102 | **−0.000971** | **1.2970** |
| **top_k** | TOPK_K=50 | 89.2 | +0.2893 | −0.0955 | **0.3601** | +0.003176 | −0.001099 | 1.3340 |
| **hybrid** | HYBRID_q0.90_K=50 | 89.2 | +0.2809 | −0.0919 | 0.3585 | +0.003182 | −0.001098 | 1.3384 |

**Note**: `gross_pnl` and `net_pnl` here are **per-alpha medians**, not whole-batch totals. The shadow profiles run ~12-15× fewer trades, so absolute pnl is smaller but `cost / gross` ratio and `net / trade` are the apples-to-apples comparisons.

## Per-profile skip / kept totals
| Profile | Entered | Kept | Skipped | Skip Rate | Errors |
|---|---:|---:|---:|---:|---:|
| strength (q=0.95) | 2 265 423 | 148 528 | 2 116 895 | **0.9344** | 0 |
| top_k (K=50) | 2 265 423 | 173 377 | 2 092 046 | **0.9235** | 0 |
| hybrid (q=0.90, K=50) | 2 265 423 | 165 436 | 2 099 987 | **0.9270** | 0 |

**Errors = 0** across all profiles → shadow harness ran without runtime exceptions.

## Per-profile per-batch conservation
For every batch and every profile, `entered_count_total == kept_count_total + skipped_count_total`:
| Profile | Batches with residual ≠ 0 |
|---|---|
| strength | 0 / 352 ✅ |
| top_k | 0 / 352 ✅ |
| hybrid | 0 / 352 ✅ |

## Symbol concentration (sanity check for artifacts)
14 unique symbols across 352 shadow batches (no single-symbol dominance).

| Symbol | Batches | Share |
|---|---:|---:|
| BNBUSDT | 42 | 11.9% |
| 1000PEPEUSDT | 34 | 9.7% |
| AAVEUSDT | 33 | 9.4% |
| SOLUSDT | 32 | 9.1% |
| FILUSDT | 31 | 8.8% |
| LINKUSDT | 28 | 8.0% |
| DOGEUSDT | 24 | 6.8% |
| 1000SHIBUSDT | 23 | 6.5% |
| AVAXUSDT | 23 | 6.5% |
| XRPUSDT | 22 | 6.3% |
| (other 4) | 60 | 17.0% |

Top-1 = 11.9% — far from artifact threshold (typically ≥80%). **No symbol concentration artifact.**

## Cost/gross ratio comparison (per-batch median)
- **baseline**: 1.4964
- **strength**: 1.2970 (**−13.3%** vs baseline)
- **top_k**: 1.3340 (−10.9%)
- **hybrid**: 1.3384 (−10.6%)

All 3 profiles cost less per gross-bps than baseline. Strength is the leader.

## Telemetry sanity
- `UNKNOWN_REJECT`: **0** in all 352 batches ✅
- `COUNTER_INCONSISTENCY`: **0** ✅
- Conservation residual (per batch): **0** ✅
- No new error categories introduced by shadow path

## Live observations vs TF2 fixture
| Metric | TF2 fixture (synthetic) | TF3 live |
|---|---|---|
| Best profile | HYBRID_q0.90_K=50 | **STRENGTH_q0.95** |
| Win-rate uplift | +16.5 pp (HYBRID) | +4.6 pp (top_k) |
| Skip rate (best) | 0.95 (HYBRID) | 0.93 (strength) |
| Net-per-trade improvement | +0.0119 bps (HYBRID) | net still slightly negative; magnitude smaller than fixture predicted |
| Cost-per-gross reduction | n/a (fixture used per-trade cost) | **−13.3% (strength)** |

The fixture was directionally correct (filtering improves quality) but **overstated** the magnitude. Live strength→quality monotonicity is **shallower** than the assumed Beta(2,5) + linear-gross model — strong filtering still improves net but does not push it positive at current cost levels.

## Raw artifacts
- `/tmp/0_9y_tf3_shadow_collected.jsonl` — frozen dataset, 7646 lines (commit-ineligible, not staged)
- `/tmp/0_9y_tf3_phase4_summary.json` — per-profile aggregates (commit-ineligible)
- `/tmp/0_9y_tf3_phase4_parse.py` — parser (commit-ineligible)

## Verdict (this phase)
**PHASE_4_COMPLETE — 352 batches collected with full shadow_profiles emission; conservation holds across all profiles; no artifacts; telemetry clean.**

## Next
Phase 5 — comparative analysis with explicit Δ vs baseline + classification per profile.
