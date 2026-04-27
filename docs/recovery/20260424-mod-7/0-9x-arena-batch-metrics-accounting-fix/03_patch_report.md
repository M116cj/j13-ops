# 03 — Patch Report

Order: TEAM ORDER 0-9X-ARENA-BATCH-METRICS-ACCOUNTING-FIX
Phase: 3
Date (UTC): 2026-04-27
Author: Claude Lead

## Files changed (single-file patch + new test file)

| File | LOC delta | Type |
|---|---|---|
| `zangetsu/services/arena_pipeline.py` | +56 / -16 | 1 new tuple constant + 1 new module dict + 1 new pure helper + emitter refactor |
| `zangetsu/tests/test_arena_batch_metrics_accounting.py` | +186 / 0 (new file) | 6 regression tests |

No other files modified. `validator` / `arena_gates.py` / `config/settings.py` / `arena_rejection_taxonomy.py` untouched.

## Patch shape (`zangetsu/services/arena_pipeline.py`)

### Added — module-level constants/state

```python
# Reject-stats keys walked by the A1 batch-metrics emitter. Stable order;
# adding a new key here MUST be paired with an entry in
# arena_rejection_taxonomy.RAW_TO_REASON or the new key falls through to
# UNKNOWN_REJECT (see TEAM ORDER 0-9X-A1-REJECT-TAXONOMY-HOTFIX for the
# regression-test contract).
_A1_REJECT_STATS_KEYS: tuple[str, ...] = (
    "reject_few_trades", "reject_neg_pnl", "reject_train_neg_pnl",
    "reject_val_constant", "reject_val_error", "reject_val_few_trades",
    "reject_val_neg_pnl", "reject_val_low_sharpe", "reject_val_low_wr",
    "reject_combined_sharpe_low",
)

_A1_PREV_REJECT_STATS_SNAPSHOT: dict[str, int] = {}
```

### Added — pure helper

```python
def _compute_a1_reject_deltas(
    current_stats: dict,
    prev_snapshot: dict,
    stats_keys: tuple,
) -> tuple[dict, dict]:
    """Pure helper: compute per-round reject deltas given the cumulative
    `current_stats` and a `prev_snapshot` from the last emit.
    ...
    """
    new_snapshot = dict(prev_snapshot)
    deltas: dict = {}
    for k in stats_keys:
        current = int(current_stats.get(k, 0) or 0)
        previous = int(new_snapshot.get(k, 0))
        new_snapshot[k] = current
        delta = current - previous
        if delta > 0:
            deltas[k] = delta
    return deltas, new_snapshot
```

### Modified — `_emit_a1_batch_metrics_from_stats_safe()`

Before:
```python
reject_total = 0
for stats_key in (
    "reject_few_trades", ...
):
    n = int(stats.get(stats_key, 0) or 0)   # CUMULATIVE
    if n <= 0: continue
    canonical = stats_key
    try:
        from zangetsu.services.arena_rejection_taxonomy import classify
        reason, _cat, _stage = classify(raw_reason=stats_key, arena_stage="A1")
        canonical = reason.value
    except Exception: pass
    acc.reject_counter.add(canonical, n)
    reject_total += n
```

After:
```python
global _A1_PREV_REJECT_STATS_SNAPSHOT
...
deltas, _A1_PREV_REJECT_STATS_SNAPSHOT = _compute_a1_reject_deltas(
    stats, _A1_PREV_REJECT_STATS_SNAPSHOT, _A1_REJECT_STATS_KEYS,
)
reject_total = 0
for stats_key, delta in deltas.items():
    canonical = stats_key
    try:
        from zangetsu.services.arena_rejection_taxonomy import classify
        reason, _cat, _stage = classify(raw_reason=stats_key, arena_stage="A1")
        canonical = reason.value
    except Exception: pass
    acc.reject_counter.add(canonical, delta)
    reject_total += delta
```

### Unchanged

- `acc.rejected_count = reject_total`
- `residual = acc.entered_count - acc.passed_count - acc.rejected_count`
- `if residual > 0: skipped_count = residual`
- `elif residual < 0: reject_counter.add("COUNTER_INCONSISTENCY", abs(residual)); rejected_count += abs(residual)` ← preserved as defensive guard for genuine residual deficits
- `acc.mark_closed(); _build_batch_metrics; _safe_emit_arena_metrics`
- Validator increment sites at lines 975, 988, 1020, 1039, 1048, 1051, 1054, 1058, 1066

## bash -n equivalent — Python syntax check

```
python3 -m py_compile zangetsu/services/arena_pipeline.py
COMPILE_OK
```

## Local helper logic verification (AST extract + exec)

Round-by-round simulation of the helper against synthetic cumulative growth:

```
Round 1 (empty prev): current = {few_trades: 5, neg_pnl: 3, train_neg_pnl: 0}
  → deltas = {reject_few_trades: 5, reject_neg_pnl: 3}
  → snapshot = {reject_few_trades: 5, reject_neg_pnl: 3, reject_train_neg_pnl: 0}

Round 2 (cumulative grows): current = {few_trades: 7, neg_pnl: 6, train_neg_pnl: 4}
  → deltas = {reject_few_trades: 2, reject_neg_pnl: 3, reject_train_neg_pnl: 4}  ← per-round increments
  → snapshot = {reject_few_trades: 7, reject_neg_pnl: 6, reject_train_neg_pnl: 4}

Round 3 (no changes): current == previous
  → deltas = {}  ← no event added
  → snapshot unchanged
```

Helper produces correct per-round deltas. No false positives in steady-state.

## Bootstrap semantics confirmed

First-call behavior verified by `test_first_batch_initialization`:
- empty prev → current values become deltas (one-shot capture of all warmup rejects)
- snapshot populated with ALL keys in `_A1_REJECT_STATS_KEYS` (including zeros)
- subsequent same-cumul call → empty deltas (no false-positive)

## Q1 5-dimension self-check (per-task)

| Dimension | Result |
|---|---|
| Input boundary | PASS — empty stats, zero current, current==prev, current<prev all handled (delta ≤ 0 → continue; snapshot still updates) |
| Silent failure propagation | PASS — emitter wrapper still catches all exceptions; helper has no I/O so no failure mode beyond TypeError on bad input (which the wrapper absorbs) |
| External dependency failure | PASS — pure helper has zero external deps; emitter still tolerates `classify()` ImportError via existing fallback |
| Concurrency / race | PASS — module-level dict is per-Python-process; each worker has its own; no cross-worker contention; no GIL-held mutation |
| Scope creep | PASS — only `arena_pipeline.py` (helper + state + emitter rewrite) + new test file; arena_gates / arena_rejection_taxonomy / config / validator increments untouched |

## Regression test pass

See `04_regression_test_report.md` — 6/6 PASS on Mac (Python 3.14.3, pytest 9.0.2).
