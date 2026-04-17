# Decision Record — Arena 13: Keep DISABLED

**Date:** 2026-04-14
**Status:** DECIDED — Arena 13 remains disabled
**Author:** Claude (Lead Architect)

## What Was Decided

Arena 13 (evolutionary search / mutation engine) stays **DISABLED** with a
defined interface contract. No implementation work until reactivation criteria
are met.

## Why

1. **A4 conversion is 0%.** The A1→A5 pipeline currently produces 42 champions,
   5 candidates, and 0 deployable strategies. Until at least one strategy passes
   A4 (forward walk) and A5 (paper trading), we have no proof the pipeline works
   end-to-end. Adding evolution on top of a pipeline that cannot yet produce
   deployable output is premature optimization.

2. **Active bugs distort signal quality.** The TP/ATR trailing-stop mismatch
   between A3 and A4 (now being fixed) means A4 rejection data is unreliable.
   Evolution that learns from unreliable fitness signals will amplify errors,
   not fix them.

3. **221 orphaned EVOLVED records exist in DB** from a prior Arena 13 version.
   These are invalid and must not be used for ranking or as evolution seeds.
   The stub's docstring correctly flags them as orphans.

4. **Complexity budget.** The V6 upgrade already includes: shared bloom dedup,
   family_id tracking, feature store, dashboard unification, and process
   supervision. Adding evolution would exceed the safe change boundary.

## When to Revisit

Reactivation gate (ALL must be true):
- [ ] At least 3 strategies reach DEPLOYABLE status through A1→A5
- [ ] A4 forward-walk pass rate > 10% (proves signal quality is real)
- [ ] Family-based population tracking is live and validated
- [ ] Shared bloom dedup is stable for > 1 week in production

When the gate opens, Arena 13 re-enters as a **Phase 2** feature with its own
/team sprint, not bolted onto an existing upgrade.

## Interface Contract

When Arena 13 is eventually implemented, it must conform to:

### Inputs (consumed from DB)
```
champion_pipeline WHERE status = 'DEPLOYABLE'
├── passport -> 'arena1' -> 'config'     # indicator config (parents)
├── passport -> 'arena1' -> 'config_hash' # dedup key
├── family_id                             # family grouping
├── regime                                # market regime
└── fitness metrics:
    ├── arena3_sharpe, arena3_sortino     # backtest quality
    ├── arena4_forward_sharpe             # out-of-sample quality
    └── arena5_paper_pnl                  # live performance
```

### Outputs (produced)
```
champion_pipeline INSERT with:
├── status = 'A1_CHAMPION'               # re-enters at A1, does NOT skip stages
├── passport -> 'arena13' = {
│     "parent_ids": [uuid, ...],         # full lineage
│     "generation": int,                  # monotonic counter
│     "mutation_type": str,              # "period_shift" | "threshold_adjust" | "crossover"
│     "mutation_params": {...}           # what changed
│   }
├── family_id = parent's family_id       # preserves family identity
└── config_hash = new hash               # must pass bloom dedup
```

### Hard Constraints (from stub docstring)
1. Mutation must preserve family identity (indicator names stable, only periods change)
2. `param_tune` must not produce equivalent-signal families
3. Evolved champions must re-enter at A1 (not skip stages)
4. Parent lineage must be fully traceable
5. Generation counter must be monotonic
6. Must pass Q1 adversarial review before reactivation

## What Was Rejected

### Option A: Build Arena 13 now with limited mutation
**Rejected because:** Even "limited" evolution adds complexity we cannot
validate when A4 conversion is 0%. We would be tuning a search algorithm
without a fitness signal. The 221 orphaned records prove this already failed
once.

### Option B: Use Arena 13 as a parameter tuner (no real evolution)
**Rejected because:** This overlaps with A2's pre-screen role. A2 already
rejects configs with poor quick-backtest performance. A parameter tuner that
feeds into A1 would create a confusing dual-entry path and complicate family
tracking.

### Option C: Delete Arena 13 entirely
**Rejected because:** The concept is sound — evolution over proven strategies
is a natural extension of the pipeline. The problem is timing, not design.
Keeping the stub with a clear interface contract preserves the design intent
at zero runtime cost.

## Adversarial Review (Q1)

- **Input boundary:** N/A — Arena 13 produces no code, no runtime behavior.
  PASS.
- **Failure propagation:** The disabled stub calls `sys.exit(0)`. If
  accidentally invoked, it exits cleanly with a stderr message. No silent
  failure. PASS.
- **External dependency:** None — it's a stub. PASS.
- **Concurrency:** No shared state. PASS.
- **Scope creep:** Decision explicitly defers implementation. The interface
  contract is descriptive, not prescriptive code. PASS.

## Consequences

- A1→A5 pipeline runs without evolutionary complexity overhead
- 221 EVOLVED orphan records remain in DB (harmless, excluded by status filter)
- When reactivation gate opens, the interface contract reduces design time
- Risk: if A4 conversion fixes work well, we may want Arena 13 sooner than
  expected — the contract ensures we can move fast when ready
