# 05 — AGGREGATION ANALYSIS

**TEAM ORDER**: 0-9Y-HE3-HORIZON-ECONOMIC-TELEMETRY
**Date**: 2026-04-29
**Phase**: 5 / 8

## Source
50 fixture batches × 4 horizons × 10 alphas/batch = 200 synthetic batches with monotone-improving net edge calibration. `/tmp/he3_fixture_verify.py` + `/tmp/he3_fixture_results.json`.

## Per-horizon medians (across 50 batches each)

| horizon | trade_count | gross_pnl | net_pnl | gross/trade | net/trade | cost/gross | win_rate |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 60 | 971.2 | +2.4031 | -1.2050 | +0.00244 | -0.00125 | 1.4966 | 0.3089 |
| 180 | 714.2 | +3.1796 | -0.3743 | +0.00445 | -0.00051 | 1.1128 | 0.3594 |
| 240 | 607.5 | +3.5686 | -0.1313 | +0.00598 | -0.00020 | 1.0373 | 0.3909 |
| **360** | **461.5** | **+3.8299** | **+0.0458** | **+0.00833** | **+0.00009** | **0.9891** | **0.4105** |

## Δ vs baseline (h=60)

| horizon | Δ trade_count | Δ gross_pnl | Δ net_pnl | Δ cost/gross | Δ win_rate |
|---:|---:|---:|---:|---:|---:|
| 180 | -257 (-26%) | +0.78 (+32%) | **+0.83** | -0.38 (-25%) | +0.05 pp |
| 240 | -364 (-37%) | +1.17 (+49%) | **+1.07** | -0.46 (-31%) | +0.08 pp |
| **360** | -510 (-52%) | **+1.43 (+59%)** | **+1.25** | **-0.51 (-34%)** | **+0.10 pp** |

All non-baseline horizons show:
- Trade count REDUCES (longer horizon → fewer entry events; consistent with bar-level rolling-rank threshold mechanics)
- Gross PnL per round INCREASES (longer horizon → larger price-move window per trade)
- Cost/gross ratio FALLS BELOW 1 only at h=360 (gross overtakes cost)
- Win rate IMPROVES (4-10pp uplift)

## Per-horizon classification

| horizon | net_pnl trend | win_rate trend | cost/gross trend | classification |
|---|---|---|---|---|
| 60 | baseline (-1.21) | baseline (0.31) | baseline (1.50) | (baseline reference) |
| 180 | improves (-0.37) | improves (0.36) | improves (1.11) | **HORIZON_BETTER** |
| 240 | improves (-0.13) | improves (0.39) | improves (1.04) | **HORIZON_BETTER** |
| **360** | **strongly improves (+0.05)** | **strongly improves (0.41)** | **strongly improves (0.99)** | **HORIZON_STRONGLY_BETTER** |

## Key outputs

### Best horizon candidate
**`h = 360`** — strongest performer on all 5 dimensions:
- Lowest trade count (least cost burn)
- Highest gross PnL median per round
- Only horizon with **net > 0** (+0.0458 bps)
- Lowest cost/gross ratio (0.989 — gross > cost)
- Highest win rate (0.4105)

### Whether any horizon crosses net > 0
**Yes — `h = 360` only**, in this fixture.

Intermediate horizons (180, 240) approach but don't cross the break-even line:
- 180 net = -0.37 (improves but still losses)
- 240 net = -0.13 (very close to break-even)
- 360 net = +0.05 (slight positive edge)

The monotone trend toward break-even is preserved by design in the fixture; live verification awaits HE4.

### Ranking by net_per_trade
1. **360**: +0.00009 bps/trade (only positive)
2. 240: -0.00020
3. 180: -0.00051
4. 60: -0.00125 (worst)

### Ranking by cost/gross
1. **360**: 0.9891 (only sub-1)
2. 240: 1.0373
3. 180: 1.1128
4. 60: 1.4966 (worst)

## Honest caveats

The fixture's monotone-improving calibration is a **hypothesis under test**, not a proven property of live markets. What we know from fixture analysis:

1. The HE3 telemetry pipeline correctly captures and aggregates per-horizon economics ✅
2. The aggregator correctly groups across batches ✅
3. The dataset is consistent and conservation-clean ✅

What we **don't know** until HE4 live shadow:
- Whether real arena_pipeline runs at h=360 actually produce gross > cost
- Whether the trade count drop at h=360 is real or just noise
- Whether win rate improvement holds outside fixture noise

## Recommendation
HE4 should activate `ARENA_HORIZON_MODE=SIMPLE_CYCLE` + `ACTIVE_A1_HORIZONS=180,240,360` (with possible 60 anchor) on a controlled SHADOW run, collect ≥100 live batches per horizon (≥400 total), and verify whether the fixture's monotone-improving-with-horizon assumption holds in live data.

## Verdict
**PHASE_5_COMPLETE** — fixture-based analysis identifies `h=360` as best candidate (HORIZON_STRONGLY_BETTER under synthetic calibration). Live confirmation is the central question of HE4.

## Next
Phase 6 — controlled diff & forbidden audit.
