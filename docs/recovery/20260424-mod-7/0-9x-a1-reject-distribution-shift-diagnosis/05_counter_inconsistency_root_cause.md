# 05 — COUNTER_INCONSISTENCY Root Cause

Order: TEAM ORDER 0-9X-A1-REJECT-DISTRIBUTION-SHIFT-DIAGNOSIS
Phase: 5
Date (UTC): 2026-04-27
Author: Claude Lead

## Verdict

**COUNTER_INCONSISTENCY_TELEMETRY_BUG**

COUNTER_INCONSISTENCY is **not** a real strategy or signal failure. It is a per-emit residual delta between cumulative-since-worker-start rejection counters and per-round `entered_count`. The accounting bug is structural: `stats` is initialized once at worker startup and accumulates across all rounds, while `entered_count = len(alphas)` passed into `_emit_a1_batch_metrics_from_stats_safe()` is per-round only. After warmup, cumulative `rejected_count` strictly exceeds per-round `entered_count`, and the conservation check at `arena_pipeline.py:226-232` always trips into the negative-residual branch, adding `abs(residual)` to a `COUNTER_INCONSISTENCY` bucket every emit.

## Evidence (live-verified)

### 1. `stats` is worker-lifetime cumulative

`zangetsu/services/arena_pipeline.py:707-723` — initialized at worker startup:
```python
stats = {
    "bloom_hits": 0,
    "evolutions_run": 0,
    "alphas_evaluated": 0,
    "reject_few_trades": 0,
    "reject_neg_pnl": 0,
    "reject_train_neg_pnl": 0,
    "reject_val_constant": 0,
    "reject_val_error": 0,
    "reject_val_few_trades": 0,
    "reject_val_neg_pnl": 0,
    "reject_val_low_sharpe": 0,
    "reject_val_low_wr": 0,
    "reject_combined_sharpe_low": 0,
    "champions_inserted": 0,
    "alpha_compile_errors": 0,
}
```

No reset is performed between rounds. The same dict reference is passed into every `_emit_a1_batch_metrics_from_stats_safe(..., stats=stats, ...)` call.

### 2. Increment sites add to cumulative counters

- Line 975: `stats["reject_few_trades"] += 1`
- Line 988: `stats["reject_train_neg_pnl"] += 1`
- Line 1020: `stats["reject_val_constant"] += 1`
- Line 1039: `stats["reject_val_error"] += 1`
- Line 1048: `stats["reject_val_few_trades"] += 1`
- Line 1051: `stats["reject_val_neg_pnl"] += 1`
- Line 1054: `stats["reject_val_low_sharpe"] += 1`
- Line 1058: `stats["reject_val_low_wr"] += 1`
- Line 1066: `stats["reject_combined_sharpe_low"] += 1`

All `+= 1` against the worker-lifetime cumulative dict.

### 3. The emitter conservation check

`arena_pipeline.py:198-232`:
```python
# Record entered/passed directly (aggregate view, no per-candidate hook).
acc.entered_count = int(entered_count)        # per-round  — len(alphas)
acc.passed_count = int(passed_count)          # per-round
...
reject_total = 0
for stats_key in (... iteration tuple ...):
    n = int(stats.get(stats_key, 0) or 0)     # CUMULATIVE-since-start value
    if n <= 0: continue
    ...
    acc.reject_counter.add(canonical, n)
    reject_total += n
acc.rejected_count = reject_total
residual = acc.entered_count - acc.passed_count - acc.rejected_count
if residual > 0:
    acc.skipped_count = residual
elif residual < 0:
    # counters inconsistent — record as note; do not propagate a bad event
    acc.reject_counter.add("COUNTER_INCONSISTENCY", abs(residual))
    acc.rejected_count += abs(residual)
```

### 4. Numerical confirmation from live log (Phase 1)

3-hour snapshot, 726 batches:
- Aggregate `COUNTER_INCONSISTENCY = 7,648,410` (50.02 % of all reject buckets)
- Per-batch `COUNTER_INCONSISTENCY` consistently exceeds per-batch `UNKNOWN_REJECT` by ~+2 (e.g. 6910 vs 6908, 6920 vs 6918, 6930 vs 6928).
- 0 / 726 batches have CI exactly equal to UR (refutes the "CI = UR alias" hypothesis); 726 / 726 have CI > UR by a small constant. This is consistent with cumulative-stats producing a residual that grows monotonically per round.

## 1:1 pairing explained

The near-identity between COUNTER_INCONSISTENCY and UNKNOWN_REJECT arises because both buckets are populated by the same set of cumulative rejects from `reject_train_neg_pnl` and `reject_combined_sharpe_low`:

1. Each round adds N new `reject_train_neg_pnl` increments (where N is the train-rejection count for that round).
2. The emitter walks `stats[reject_train_neg_pnl]` (cumulative) → no `RAW_TO_REASON` entry → mapped to `UNKNOWN_REJECT` → adds the cumulative value to `UNKNOWN_REJECT` bucket every emit.
3. The same cumulative value also enters `rejected_count`, which makes `entered_count - passed_count - rejected_count` go strongly negative, so `abs(residual)` ≈ `cumulative_rejects_so_far - per_round_entered` is added to `COUNTER_INCONSISTENCY`.
4. The two values diverge by a small amount equal to the per-round delta absorbed (or by the +2 pattern observed in the snapshot).

This is **same root event double-booked into two buckets** — option (a) of the order's pairing hypothesis.

## Classification

Per the order's required-classification options, this maps to:

**COUNTER_INCONSISTENCY_TELEMETRY_BUG**

Not strategy failure; not duplicate accounting at the strategy level; not schema mismatch; not signal-cost interaction. It is the telemetry layer using cumulative-since-start counters against a per-round entered count.

## Q1 5-dimension self-check

| Dimension | Outcome |
|---|---|
| Input boundary | PASS — verified `stats` dict initialization at line 707-723 and absence of reset by reading entire `arena_pipeline.py` window 700-1300 |
| Silent failure | PASS — bug is non-silent (residual is recorded as COUNTER_INCONSISTENCY); but the meaning of that bucket has not been documented as a telemetry artifact, leading to operator confusion |
| External dependency | PASS — bug is purely in-memory counter arithmetic; no DB, network, or third-party dependency |
| Concurrency | PASS — each worker has its own `stats` dict (worker-local), no cross-worker contention |
| Scope creep | PASS — diagnosis only, no patch in this phase |

## Recommended remediation (not implemented in this order)

Two surgical options for a hotfix order (`TEAM ORDER 0-9X-ARENA-BATCH-METRICS-ACCOUNTING-FIX`):

**Option A — Per-round delta semantics**: snapshot stats before each round, pass the delta into `_emit_a1_batch_metrics_from_stats_safe`. Preserves cumulative stats for end-of-run summaries.

**Option B — Per-emit reset**: reset the `reject_*` keys after each emit. Simpler but loses cumulative info.

A regression test should assert:
```python
def test_arena_batch_metrics_residual_zero_after_first_full_round():
    """A single-round emit with no skip should produce residual == 0
    and zero COUNTER_INCONSISTENCY in reject_reason_distribution."""
```

Recommended next order per parent spec: `TEAM ORDER 0-9X-ARENA-BATCH-METRICS-ACCOUNTING-FIX`.

## Forbidden-ops audit for Phase 5

- No source patch applied.
- No alpha / Arena / threshold / execution / risk / capital / DB / runtime change.
- Read-only: `Read` tool on `arena_pipeline.py` + `grep`.
