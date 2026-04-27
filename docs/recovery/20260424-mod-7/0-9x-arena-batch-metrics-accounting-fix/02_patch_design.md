# 02 — Patch Design

Order: TEAM ORDER 0-9X-ARENA-BATCH-METRICS-ACCOUNTING-FIX
Phase: 2
Date (UTC): 2026-04-27
Author: Claude Lead

## Design goal

Convert the A1 emitter from cumulative-stats accounting to per-round delta accounting so that `reject_reason_distribution` sums equal the per-round `entered - passed` count, and `COUNTER_INCONSISTENCY` collapses to ≈ 0 for valid data.

## Constraints

- **No validator change** — the `stats[reject_*]` increment sites in `arena_pipeline.py` (lines 975, 988, 1020, 1039, 1048, 1051, 1054, 1058, 1066) MUST remain untouched. Validator continues to read raw integers; only the telemetry emitter's interpretation of those counters changes.
- **No taxonomy change** — `RAW_TO_REASON` and `classify()` are unchanged.
- **No new file** — surgical change confined to `arena_pipeline.py`.
- **Per-process state** — each Python worker has its own module instance; no cross-process synchronization needed.
- **Pure helper testable on Mac** — heavy `arena_pipeline.py` deps (pyarrow, Rust extensions, hard-coded chdir) make full-module import infeasible on the test runner. Helper must be importable without those deps.

## Architecture

### 1. Module-level constants

Add a stable iteration-order tuple of all reject stats keys walked by the emitter:
```python
_A1_REJECT_STATS_KEYS: tuple[str, ...] = (
    "reject_few_trades", "reject_neg_pnl", "reject_train_neg_pnl",
    "reject_val_constant", "reject_val_error", "reject_val_few_trades",
    "reject_val_neg_pnl", "reject_val_low_sharpe", "reject_val_low_wr",
    "reject_combined_sharpe_low",
)
```

### 2. Module-level snapshot dict (per-process state)

```python
_A1_PREV_REJECT_STATS_SNAPSHOT: dict[str, int] = {}
```

Single per-process dict. Keys are stats_key strings. Values are the cumulative count seen at the previous emit.

### 3. Pure helper

```python
def _compute_a1_reject_deltas(
    current_stats: dict,
    prev_snapshot: dict,
    stats_keys: tuple,
) -> tuple[dict, dict]:
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

Properties:
- **Pure** — no module-level read/write, no I/O
- **Returns a new snapshot dict** — caller assigns back; no in-place mutation
- **Always populates the new snapshot for ALL keys in `stats_keys`** — even keys with delta = 0 are written so the next emit's previous is correct
- **Skips emit-only when delta ≤ 0** — handles current==previous (no growth) and current<previous (rollback)
- **Importable in isolation** — only stdlib types

### 4. Emitter modification

Replace the cumulative loop:
```python
for stats_key in (...):
    n = int(stats.get(stats_key, 0) or 0)
    ...
    acc.reject_counter.add(canonical, n)
```

with:
```python
global _A1_PREV_REJECT_STATS_SNAPSHOT
deltas, _A1_PREV_REJECT_STATS_SNAPSHOT = _compute_a1_reject_deltas(
    stats, _A1_PREV_REJECT_STATS_SNAPSHOT, _A1_REJECT_STATS_KEYS,
)
for stats_key, delta in deltas.items():
    canonical = stats_key
    try:
        from zangetsu.services.arena_rejection_taxonomy import classify
        reason, _, _ = classify(raw_reason=stats_key, arena_stage="A1")
        canonical = reason.value
    except Exception:
        pass
    acc.reject_counter.add(canonical, delta)
    reject_total += delta
```

The `global` declaration is necessary because we rebind the module-level name (assignment, not in-place mutation).

### 5. Residual / COUNTER_INCONSISTENCY branch — UNCHANGED

```python
residual = acc.entered_count - acc.passed_count - acc.rejected_count
if residual > 0:
    acc.skipped_count = residual
elif residual < 0:
    acc.reject_counter.add("COUNTER_INCONSISTENCY", abs(residual))
    acc.rejected_count += abs(residual)
```

This is preserved as a defensive guard for any **real** residual-deficit case. Post-fix, the typical case has `residual >= 0` and the CI bucket is not exercised.

## Bootstrap behavior (first emit per worker)

On the very first call after a worker restart, `_A1_PREV_REJECT_STATS_SNAPSHOT` is empty. Therefore:
- `previous = new_snapshot.get(k, 0) = 0` for all keys
- `delta = current` (i.e. all stats accumulated since worker start enter the first emit's distribution)

If the first emit happens after a single round with `entered=10`, `current` totals are tiny (e.g. {few:5, neg:3}) and the delta logic correctly produces a per-round-equivalent distribution.

If the first emit is delayed by N rounds (atypical), the first emit absorbs all N rounds' rejects in one batch's distribution. Subsequent emits revert to true per-round deltas. This is acceptable bootstrap behavior — the cumulative-once-then-incremental pattern preserves total-reject conservation across the worker's lifetime when summed.

## Pairing with the previous taxonomy hotfix (PR #49)

PR #49 already added `reject_train_neg_pnl → COST_NEGATIVE` and `reject_combined_sharpe_low → LOW_BACKTEST_SCORE` to `RAW_TO_REASON`. Combined with this delta fix, the post-restart distribution should show:
- `COUNTER_INCONSISTENCY ≈ 0`
- `UNKNOWN_REJECT ≈ 0` (only genuinely-unknown future raw keys would surface)
- All canonical buckets (`COST_NEGATIVE`, `LOW_BACKTEST_SCORE`, `SIGNAL_TOO_SPARSE`, `INVALID_FORMULA`, etc.) populated with per-round delta values that sum to `entered - passed - skipped`

## Risk profile

LOW. Changes:
- 1 new pure helper function (no global state)
- 1 module-level tuple constant
- 1 module-level dict (per-process)
- 1 emitter function modified (replace cumulative loop with helper call)
- `global` declaration added inside emitter
- All other code paths untouched
- Validator decision logic untouched

The defensive `try / except: pass # never propagate` wrapper around the emitter remains intact, so even if the new code raises (it shouldn't), the worker is unaffected.
