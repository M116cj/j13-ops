# 01 — FULL PIPELINE TRACE

**TEAM ORDER**: 0-9Y-HE5-DEPLOYABLE-FLOW-RECHECK
**Date**: 2026-04-29
**Phase**: 1 / 8

## Pipeline architecture
```
A1 (arena_pipeline.py / GP search)
  ↓ pass: arena1_score / win_rate / pnl / n_trades
champion_pipeline_staging (status=ARENA1_COMPLETE)
  ↓
A23 orchestrator (arena23_orchestrator.py)
  ↓ A2: bt.total_trades >= 25 (A2_MIN_TRADES locked)
  ↓ A3: bt_a3.total_trades >= 25 + sharpe / OOS gates
champion_pipeline_fresh / champion_pipeline (status=ARENA2_REJECTED | ARENA2_COMPLETE | ARENA3_REJECTED | ARENA3_COMPLETE)
  ↓
A45 orchestrator (arena45_orchestrator.py)
  ↓ A4 hell-window + A5 ELO promotion
deployable champions (with `deployable=true` flag in champion_pipeline)
```

## Stage-by-stage observed counts (live state, 2026-04-29T13:36Z)

| Stage | Counter | Source | Notes |
|---|---:|---|---|
| A1 ENTERED (live, current engine.jsonl rotation) | 540 | lifecycle trace | GP-discovered alphas entering A1 |
| A1 REJECTED (live) | 536 | lifecycle trace | ~99.3% reject rate; dominant reason `COST_NEGATIVE` |
| A1 ENTRIES across all HE4 horizons (3266 batches × 10 alphas) | 32 660 | aggregate_metrics | Conservation: residual=0 |
| A1 PASSED → ARENA1_COMPLETE | **184** (in staging) | DB | All 184 are **manual_seed** (v0.7.2 cold-start), 0 GP-discovered |
| A2 ATTEMPTED (= ARENA2_REJECTED + ARENA2_COMPLETE) | **89** | DB | All in `ARENA2_REJECTED`; all `manual_seed` source |
| A2 PASSED → ARENA2_COMPLETE | **0** | DB | none |
| A3 ATTEMPTED | 0 | DB | (cannot reach A3 without A2 pass) |
| A45 deployable_count | **0** | DB | (cannot reach A45 without A3 pass) |

**Pipeline reach summary**:
- 32 660 GP-discovered alpha entries: ~99.3% rejected at A1 (COST_NEGATIVE)
- ≤4 GP-discovered alphas may have passed A1 in the most recent ~50 minutes; none yet reflected in `champion_pipeline_staging` (which is 100% manual_seed)
- All 89 manual_seed alphas reached A2 but were rejected there
- 0 alphas have ever passed A2 in this codebase generation

## A1 reject reason distribution (HE4 live window, 3266 batches × 3 horizons)
| Horizon | COST_NEGATIVE | SIGNAL_TOO_SPARSE | LOW_BACKTEST_SCORE |
|---|---:|---:|---:|
| 180 | 10 844 | 34 | 2 |
| 240 | 10 861 | 29 | 0 |
| 360 | 10 879 | 11 | 0 |
| **Total (3 horizons)** | **32 584 / 32 660** = **99.77%** | 74 | 2 |

`COST_NEGATIVE` dominates the rejector at all horizons. **Cost is the gate, not edge or signal density.**

## A2 reject mechanism (per code review)
`zangetsu/services/arena23_orchestrator.py:779`:
```python
if bt.total_trades < 25:
    log.info(f"A2 REJECTED id={champion_id} ...: trades={bt.total_trades} < 25")
    ... → ARENA2_REJECTED
```

A2's reject criterion is `bt.total_trades < 25` — a re-evaluation of the candidate signal under A2's own backtest. Note:
- A1's bt = train backtest under V10 alpha-expression (cost-included). Manual seeds had `arena1_n_trades = 1076` here.
- A2's bt = different evaluation (different cost / signal reconstruction). The 89 manual seeds produced **<25 trades** at A2 → rejection.

The A2 rejection is **not** about edge or cost directly — it's because A2's own signal-reconstruction phase failed to produce sufficient trade signals from the alpha formula. Possible causes:
- V9-vs-V10 signal-generation mismatch (the seeds may have been computed for V9 then re-evaluated under V10)
- Different evaluation window
- Different threshold parameters in A2's `generate_threshold_signals` flow

## Per-question analysis (master-order Phase 1)

### Is there any alpha that ever approached deployable (even once)?
**No.** All 89 manual_seed alphas reached A2 but were rejected at A2's `<25 trades` gate. 0 alphas have ever entered A3, A4, or A5. **deployable_count = 0 across the entire history of this codebase generation.**

### Where is the flow blocked?
**Two simultaneous bottlenecks**:
1. **For GP-discovered alphas**: `FLOW_BLOCKED_AT_A1` — 99.77% rejected by `COST_NEGATIVE` (gross < cost in train). Cost-burn is the dominant edge-killer.
2. **For manual_seed alphas (the only ones that did pass A1)**: `FLOW_REACHES_A2` — but A2 rejects all 89 due to insufficient trades (<25) in A2's reconstruction. This is a stage-mismatch between A1 (alpha-expression backtest) and A2 (signal-reconstruction backtest).

## Classification
**FLOW_REACHES_A2** (for manual_seed alphas) + **FLOW_BLOCKED_AT_A1** (for GP-discovered alphas).

**Neither cohort approaches NEAR_DEPLOYABLE.** No alpha is "one tweak away" from passing A3/A4/A5.

## Implication for HE5
The pipeline has **two simultaneous, decoupled blockages**:
1. GP cost-burn gate at A1
2. Signal-reconstruction trade-gap at A2

Both must be resolved for deployable_count > 0. Neither is solvable by horizon (HE4 falsified) or aggregation (TF3 improved economy at A1 but didn't cross break-even, and didn't help A2's reconstruction issue at all).

## Verdict
**PHASE_1_COMPLETE** — pipeline trace shows two decoupled bottlenecks; no alpha approaches deployable in current architecture.

## Next
Phase 2 — closest-to-deployable analysis (the 89 manual-seed alphas in fresh table).
