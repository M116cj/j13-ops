# 04 — UNKNOWN_REJECT Root Cause

Order: TEAM ORDER 0-9X-A1-REJECT-DISTRIBUTION-SHIFT-DIAGNOSIS
Phase: 4
Date (UTC): 2026-04-27
Author: Claude Lead

## Verdict

**UNKNOWN_REJECT_TAXONOMY_MAPPING_BUG**

UNKNOWN_REJECT is **not** a real classification. It is the fallback bucket emitted by `arena_rejection_taxonomy.classify()` whenever the supplied raw_reason key has no entry in the `RAW_TO_REASON` dict. PR #43 (commit `c873857`) introduced two new stats keys — `reject_train_neg_pnl` and `reject_combined_sharpe_low` — and added them to the emitter's iteration tuple in `arena_pipeline.py` lines 206-209, but did **not** add corresponding entries to `RAW_TO_REASON`. Every rejection that increments those two stats keys is therefore mapped to UNKNOWN_REJECT in `arena_batch_metrics.reject_reason_distribution`.

## Evidence (live-verified)

### 1. Direct import of taxonomy module on Mac at HEAD `b1615c6`

```python
from zangetsu.services.arena_rejection_taxonomy import RAW_TO_REASON
RAW_TO_REASON.get("reject_train_neg_pnl")     # → <<NOT IN MAP>>
RAW_TO_REASON.get("reject_combined_sharpe_low") # → <<NOT IN MAP>>
RAW_TO_REASON.get("reject_neg_pnl")            # → <RejectionReason.COST_NEGATIVE>
RAW_TO_REASON.get("reject_few_trades")         # → <RejectionReason.SIGNAL_TOO_SPARSE>
```

22 keys are present in `RAW_TO_REASON`. The two PR #43 keys are absent.

### 2. Pipeline iteration walks the missing keys

`zangetsu/services/arena_pipeline.py:205-209`:
```python
for stats_key in (
    "reject_few_trades", "reject_neg_pnl", "reject_train_neg_pnl",
    "reject_val_constant", "reject_val_error", "reject_val_few_trades",
    "reject_val_neg_pnl", "reject_val_low_sharpe", "reject_val_low_wr",
    "reject_combined_sharpe_low",
):
    n = int(stats.get(stats_key, 0) or 0)
    if n <= 0: continue
    canonical = stats_key
    try:
        from zangetsu.services.arena_rejection_taxonomy import classify
        reason, _cat, _stage = classify(raw_reason=stats_key, arena_stage="A1")
        canonical = reason.value          # ← UNKNOWN_REJECT for missing entries
    except Exception:
        pass
    acc.reject_counter.add(canonical, n)
```

### 3. Increment sites for the missing keys

- `reject_train_neg_pnl` incremented at `arena_pipeline.py:988` after train-window evaluation rejects with negative PnL.
- `reject_combined_sharpe_low` incremented at `arena_pipeline.py:1066` after the combined train+val Sharpe gate fails.
- Both are initialized to `0` at worker start (`:713`, `:720`) and counted forward.

### 4. Live distribution corroborates

3-hour live snapshot (Phase 1, `01_live_distribution_snapshot.md`):
- `UNKNOWN_REJECT = 7,641,019` (49.97 % of all rejects)
- Per-batch `UNKNOWN_REJECT` is 2 less than `COUNTER_INCONSISTENCY` consistently — the +2 delta is the COUNTER_INCONSISTENCY-specific contribution; the rest is the PR #43 keys flowing through fallback.
- `val_neg_pnl=N` still appears in the legacy text-format INFO line (`arena_pipeline.py:1240`) but the corresponding stats key `reject_val_neg_pnl` IS in `RAW_TO_REASON` (mapped to COST_NEGATIVE), so it does not contribute to UNKNOWN_REJECT.

## Q1 5-dimension self-check

| Dimension | Outcome |
|---|---|
| Input boundary | PASS — verified absent keys via direct module import + ran `RAW_TO_REASON.get(missing, "<<NOT IN MAP>>")` to disambiguate "absent" vs "mapped to None" |
| Silent failure | PASS — fallback path is silent in production but caught by classify() returning UNKNOWN_REJECT; this report surfaces it |
| External dependency | PASS — taxonomy module import succeeded; the bug is local data, not import failure |
| Concurrency | PASS — RAW_TO_REASON is a module-level constant dict, read-only across workers |
| Scope creep | PASS — diagnosis only, no patch in this phase |

## Recommended remediation (not implemented in this order)

A small, surgical taxonomy patch:
```python
# zangetsu/services/arena_rejection_taxonomy.py — RAW_TO_REASON additions
"reject_train_neg_pnl":     RejectionReason.COST_NEGATIVE,        # train-window negative PnL = real cost-negative outcome
"reject_combined_sharpe_low": RejectionReason.LOW_BACKTEST_SCORE, # Sharpe-gate failure
```

Plus a contract test:
```python
# tests/test_arena_pipeline_taxonomy_contract.py
def test_emitter_stats_keys_subset_of_raw_to_reason():
    """Every reject_* stats key walked by _emit_a1_batch_metrics_from_stats_safe
    must have a RAW_TO_REASON entry, otherwise UNKNOWN_REJECT silently absorbs."""
```

These belong to a separate hot-fix order (`TEAM ORDER 0-9X-A1-REJECT-TAXONOMY-HOTFIX`) per the parent order's recommendation table.

## Forbidden-ops audit for Phase 4

- No source patch applied.
- No alpha / Arena / threshold / execution / risk / capital / DB / runtime change.
- Read-only: `python3 -c` import + `grep` + `Read` on existing files.
