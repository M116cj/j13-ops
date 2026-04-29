# 04 — FIXTURE OR LIVE SAMPLE

**TEAM ORDER**: 0-9Y-HE3-HORIZON-ECONOMIC-TELEMETRY
**Date**: 2026-04-29
**Phase**: 4 / 8

## Mode chosen
**FIXTURE_PASS + LIVE_MULTI_HORIZON_DEFERRED_TO_HE4**

Per master-order Phase 4 Option A (preferred):
> Run fixture/synthetic batches for horizons 180/240/360. Capture horizon_metrics outputs.

The live multi-horizon SHADOW activation is reserved for **HE4** per the master-order sequence. HE3 ships the telemetry plumbing dormant-by-default. Fixture verification demonstrates the helper + aggregator end-to-end.

## Fixture script
`/tmp/he3_fixture_verify.py` — 200 batches synthesized (50 batches × 4 horizons × 10 alphas/batch).

```
$ /home/j13/j13-ops/zangetsu/.venv/bin/python3 /tmp/he3_fixture_verify.py
```

## Calibration
- Per-horizon profile assumes monotone-improving net edge: longer horizon → wider price moves → higher gross relative to fixed cost (TF1 hypothesis extended).
- `COST_BPS = 14.5` (matches TF3 live baseline `round_total_cost_bps`).
- Per-horizon parameters tuned to demonstrate the telemetry pipeline; **whether the real market exhibits this monotone is what HE4 live shadow will test**.

| Horizon | gross_med | net_med | trades_med | win_rate_med |
|---|---|---|---|---|
| 60 | +2.4 | -1.2 | 980 | 0.31 |
| 180 | +3.2 | -0.4 | 720 | 0.36 |
| 240 | +3.6 | -0.1 | 600 | 0.39 |
| 360 | +3.8 | +0.05 | 450 | 0.41 |

## Results — per-horizon medians (median across 50 batches each)

| horizon | trade_count | gross_pnl | net_pnl | gross/trade | net/trade | cost/gross | win_rate |
|---:|---:|---:|---:|---:|---:|---:|---:|
| **60** | 971.2 | +2.4031 | **−1.2050** | +0.00244 | −0.00125 | 1.4966 | 0.3089 |
| **180** | 714.2 | +3.1796 | −0.3743 | +0.00445 | −0.00051 | 1.1128 | 0.3594 |
| **240** | 607.5 | +3.5686 | −0.1313 | +0.00598 | −0.00020 | 1.0373 | 0.3909 |
| **360** | 461.5 | +3.8299 | **+0.0458** | +0.00833 | +0.00009 | **0.9891** | 0.4105 |

## Verification of helper invariants

### Shape correctness
All 200 batches contain `horizon_metrics[<selected_horizon>]` with all 14 required fields. ✅

### Cross-batch aggregation
`aggregate_horizon_metrics_across_batches([200 batches])` produces 4 horizon-keyed entries with `batch_count = 50` each. ✅

### Conservation (per batch)
For every fixture batch (skipped=0 by design): `entered = kept + skipped` holds trivially since fixture didn't activate TF4 PRE-FILTER. Helper's `conservation` test (Test #6) covers the TF4-active branch. ✅

## Best horizon (per fixture)
**`h=360`** with `net_pnl_median = +0.0458 bps` — the only horizon crossing net > 0 in this synthetic calibration. `cost/gross = 0.989` (gross slightly exceeds cost).

The intermediate horizons (180/240) show progressive improvement: 180's net = -0.37, 240's net = -0.13, 360's net = +0.05 — monotone in horizon length, as designed.

## Honest disclaimer
The synthetic fixture **assumes** the longer-horizon hypothesis (gross edge increases faster than cost as horizon grows). This is the natural extension of TF1's "stronger entries → better trade quality" finding to the time-scale dimension.

**What this fixture proves**:
- Helper correctly aggregates per-horizon metrics from per-alpha lists ✅
- Cross-batch aggregator produces correctly-keyed output ✅
- All 14 fields populate as expected ✅
- The telemetry pipeline is end-to-end functional ✅

**What this fixture does NOT prove**:
- Whether real market data exhibits monotone-improving net with horizon
- The exact magnitude of any horizon's edge under live data
- Whether any horizon actually achieves net > 0 in production

These are HE4's questions.

## Master-order classification
**FIXTURE_PASS** ✅ — preferred per Phase 4 Option A; live activation deferred to HE4.

Bonus classification: **LIVE_MULTI_HORIZON_DEFERRED_TO_HE4**.

## Raw artifacts
- `/tmp/he3_fixture_verify.py` — fixture harness
- `/tmp/he3_fixture_results.json` — saved per-horizon aggregation

## Verdict
**PHASE_4_COMPLETE** — fixture pipeline verified; per-horizon metrics are correctly computed and aggregable.

## Next
Phase 5 — aggregation analysis.
