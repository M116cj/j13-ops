# 03 — A1 Code Path Trace: COUNTER_INCONSISTENCY × UNKNOWN_REJECT

**Subagent:** `a1-codepath-auditor` · TEAM ORDER 0-9X-A1-REJECT-DISTRIBUTION-SHIFT-DIAGNOSIS Phase 3
**Repo:** `/Users/a13/dev/j13-ops` @ `b1615c67` (main, READ-ONLY)
**Date:** 2026-04-27
**Authoritative live signal:** `reject_reason_distribution = {COUNTER_INCONSISTENCY: 13350, UNKNOWN_REJECT: 13350}` (1:1)

---

## 1. Lifecycle Diagram (A1 candidate → telemetry emit)

```
┌─────────────────────────── per-round (sym, regime) ───────────────────────────┐
│                                                                                │
│   AlphaEngine.evolve() ─► alphas: list[AlphaResult]   (entered_count = len)   │
│            │                                                                   │
│            ▼                                                                   │
│   for alpha_result in alphas:                  ── arena_pipeline.py:918       │
│       stats["alphas_evaluated"] += 1                          :919            │
│       ├── compile/eval        FAIL → alpha_compile_errors          :929 (NOT in dist iter)
│       ├── std<1e-10           SKIP → no counter                    :933 (NOT counted)
│       ├── bloom hit           SKIP → bloom_hits                    :948 (NOT in dist iter)
│       ├── signal gen          FAIL → no counter                    :962 (NOT counted)
│       ├── train backtest      FAIL → no counter                    :971 (NOT counted)
│       │                                                                       │
│       ▼ pre-validation gates (TRAIN slice)                                    │
│       ├── total_trades < 30   ►  reject_few_trades        :975 (counted)      │
│       ├── PR#43: net_pnl<=0   ►  reject_train_neg_pnl     :988 (counted) NEW  │
│       │                                                                       │
│       ▼ validation gates (HOLDOUT slice)                                      │
│       ├── val_constant std    ►  reject_val_constant      :1020               │
│       ├── val backtest err    ►  reject_val_error         :1039               │
│       ├── val_trades < 15     ►  reject_val_few_trades    :1048               │
│       ├── val_net_pnl <= 0    ►  reject_val_neg_pnl       :1051               │
│       ├── val_sharpe < 0.3    ►  reject_val_low_sharpe    :1054               │
│       ├── val_wilson < 0.52   ►  reject_val_low_wr        :1058               │
│       ├── PR#43: combined<0.4 ►  reject_combined_sharpe_low :1066 NEW         │
│       │                                                                       │
│       ▼ champion path                                                         │
│       └── INSERT champion     ►  champions_inserted, regime_champion_counts   │
│                                                                                │
│   end-for                                                                     │
│                                                                                │
│   _emit_a1_batch_metrics_from_stats_safe(...)         :1255 (per round)       │
│   └─► reads stats[reject_*]  →  ArenaStageMetrics.reject_counter              │
│       └─► residual = entered - passed - rejected      :226                    │
│           if residual < 0:                                                    │
│               reject_counter.add("COUNTER_INCONSISTENCY", abs(residual))      │
│           build_arena_batch_metrics(acc) → reject_reason_distribution         │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Exact Function Citations

### 2a. COUNTER_INCONSISTENCY incrementer

**File:** `zangetsu/services/arena_pipeline.py`
**Function:** `_emit_a1_batch_metrics_from_stats_safe(...)` (lines 167–239)
**Critical lines:**

```python
# arena_pipeline.py:204-232
reject_total = 0
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
        canonical = reason.value
    except Exception:
        pass
    acc.reject_counter.add(canonical, n)
    reject_total += n
acc.rejected_count = reject_total
residual = acc.entered_count - acc.passed_count - acc.rejected_count
if residual > 0:
    acc.skipped_count = residual
elif residual < 0:
    acc.reject_counter.add("COUNTER_INCONSISTENCY", abs(residual))   # ◄ HERE :231
    acc.rejected_count += abs(residual)
```

### 2b. UNKNOWN_REJECT classification source

`UNKNOWN_REJECT` is **never explicitly added** by `arena_pipeline.py`. It enters the
distribution via the **`classify()` taxonomy fallback**:

**File:** `zangetsu/services/arena_rejection_taxonomy.py:285-328`

```python
# Falls back to UNKNOWN_REJECT only when raw_reason cannot be matched.
def classify(raw_reason: str, arena_stage: str = ""):
    ...
    # 3. Fallback: UNKNOWN_REJECT with whatever stage we could infer.
    meta = REJECTION_METADATA[RejectionReason.UNKNOWN_REJECT]
    return (RejectionReason.UNKNOWN_REJECT, meta.category, stage)        # :327
```

**Real classification vs fallback default** — In the pipeline path the value is
emitted via `acc.reject_counter.add(canonical, n)` at line 221 where `canonical =
reason.value`. If `classify()` returns `UNKNOWN_REJECT.value` for a key, the count
is added under "UNKNOWN_REJECT" — i.e. **the taxonomy file does not contain a
mapping** for one or more of the keys in the iteration tuple.

A second code path also produces `UNKNOWN_REJECT` defaults:

**File:** `zangetsu/services/arena_pass_rate_telemetry.py:175-180,194,333`

```python
# RejectReasonCounter.add()  :175-180
def add(self, reason: str, n: int = 1) -> None:
    if not isinstance(reason, str) or not reason:
        reason = "UNKNOWN_REJECT"        # ◄ empty-string default
    ...
# top_reason() :192-195 returns "UNKNOWN_REJECT" when counter empty
# on_rejected()  :333  defaults reason to "UNKNOWN_REJECT" when None
```

But the pipeline emit path goes through line 221, not line 333 — confirmed: the
pipeline calls `acc.reject_counter.add(canonical, n)`, not `on_rejected()`. So
the **only way `UNKNOWN_REJECT` enters the live distribution** in production A1
emit is the taxonomy classify fallback (i.e. one of the iterated `reject_*` keys
maps to `UNKNOWN_REJECT.value` because no taxonomy entry exists for it).

### 2c. arena_batch_metrics emitter

**File:** `zangetsu/services/arena_pipeline.py:1255-1266` (the call site)
**Builder:** `zangetsu/services/arena_pass_rate_telemetry.py:368-409`
**Wire-out:** `_safe_emit_arena_metrics()` writes JSON via `log.info`.

The `ArenaBatchMetrics.reject_reason_distribution` field (`arena_pass_rate_telemetry.py:236`,
`:404`) is the dict copy of `RejectReasonCounter._counts`.

---

## 3. Stage Classification of the Distribution

**Pre-validation vs validation:** the iterated tuple at `arena_pipeline.py:205-210`
includes BOTH:

- pre-val (TRAIN slice): `reject_few_trades`, `reject_neg_pnl`, `reject_train_neg_pnl`
- validation (HOLDOUT slice): `reject_val_constant`, `reject_val_error`,
  `reject_val_few_trades`, `reject_val_neg_pnl`, `reject_val_low_sharpe`,
  `reject_val_low_wr`, `reject_combined_sharpe_low`

A candidate is rejected at the **first failing gate** (each branch ends with
`continue`), so a candidate appears in **exactly one** bucket — never two.
Therefore `sum(stats[reject_*])` counts unique candidate failures and
**should equal** `entered − passed − [bloom_hits + alpha_compile_errors +
constant_skip + signal_fail + train_bt_fail]` (the uncounted skip/fail
branches above).

This is the seed of inconsistency: lines 929 (`alpha_compile_errors`), 933
(constant skip — uncounted), 948 (`bloom_hits`), 962 (signal-gen fail —
uncounted), 971 (train backtest fail — uncounted) **all `continue` without
incrementing any `reject_*`** key included in the iteration tuple. The
emit treats `entered − passed − rejected = residual` and forces residual<0
into `COUNTER_INCONSISTENCY` and residual>0 into `skipped_count`.

**Crucial:** `stats` is initialized once at worker startup (`:707`) and is
**NEVER reset between rounds**. Each per-round `_emit_a1_batch_metrics_from_stats_safe`
call passes `entered_count=len(alphas)` (this round only) but `stats[reject_*]`
(cumulative since worker startup). After round N, `rejected_count >> entered_count`
trivially, forcing residual to be massively negative every round → COUNTER_INCONSISTENCY
is incremented **every** emit.

---

## 4. Pairing Hypothesis (1:1 = 13350:13350)

**Verdict: (a) one event class, structurally double-counted in two buckets per emit.**

Mechanism (per round emit, after some warmup):

1. `acc.entered_count = len(alphas)` for this round (small, e.g. 100)
2. `acc.rejected_count = sum(stats[reject_*])` is the **cumulative-since-worker-start**
   sum across all rounds (huge, growing)
3. `residual = entered − passed − rejected` is therefore strongly negative
4. Line 231: `reject_counter.add("COUNTER_INCONSISTENCY", abs(residual))`
   adds a large bump
5. Simultaneously, **at least one** of the 10 iterated `stats[reject_*]` keys has
   no taxonomy mapping → `classify()` returns `UNKNOWN_REJECT.value` →
   `reject_counter.add("UNKNOWN_REJECT", n)` accumulates the same per-round
   over-count

Because both buckets accumulate from the same cumulative-stats over-count, and
because the live aggregator (`generation_profile_metrics.py:251`+ rolls the
per-emit dicts up additively across the run, the two counters track each other
and converge to `1:1`. The exact ratio is structural, not coincidental.

**Strongest evidence for (a) over (b):**

- `arena_rejection_taxonomy.py:54` — the only `UNKNOWN_REJECT.value` constant lives in the
  taxonomy enum. Combined with the classify fallback at `:285-328`, an unmapped
  `stats_key` → `UNKNOWN_REJECT.value`. Verify by inspecting `REJECTION_METADATA`
  for the 10 keys (Subagent A2/A3 task).
- The `stats` cumulative-vs-per-round mismatch is a structural defect that
  guarantees `residual < 0` once the worker has rejected anything.
- A 1:1 pairing across 13350 events is statistically untenable as coincidence.

---

## 5. PR #43 Impact

PR #43 (commit `c873857`) added two new gates to the GP loop:

- **`reject_train_neg_pnl`** (`arena_pipeline.py:984-994`) — TRAIN-slice early reject
  (NG2 from order 4-1, blocks train-val divergent artifacts).
- **`reject_combined_sharpe_low`** (`arena_pipeline.py:1061-1067`) — combined train+val
  Sharpe < 0.4 reject.

Both keys ARE listed in the iteration tuple at `arena_pipeline.py:206,209`. Their
inclusion **does not directly create COUNTER_INCONSISTENCY/UNKNOWN_REJECT** in
isolation — but:

1. They **further increase the cumulative `stats[reject_*]` rate** (more candidates
   get counted as rejected per round), which **accelerates the residual-going-negative
   defect** described in §4, raising COUNTER_INCONSISTENCY proportionally.
2. If `arena_rejection_taxonomy.REJECTION_METADATA` does not contain entries for
   `reject_train_neg_pnl` or `reject_combined_sharpe_low` (likely, since these
   were introduced in PR #43 alongside the gates — taxonomy update may have been
   missed), then those keys would map to `UNKNOWN_REJECT.value` via classify
   fallback, directly inflating the UNKNOWN_REJECT bucket.

**This is the smoking gun for the distribution shift observed at the live snapshot:**
the new keys very likely lack taxonomy mappings AND simultaneously raise the
cumulative reject rate, jointly explaining why COUNTER_INCONSISTENCY and
UNKNOWN_REJECT both appear at exactly the same magnitude.

---

## 6. Recommended next probes (handed to A2/A3)

- A2: dump `REJECTION_METADATA` keys in `arena_rejection_taxonomy.py:54+` and the
  `_RAW_TO_REASON` map (around `:228-280`) — confirm whether
  `reject_train_neg_pnl` and `reject_combined_sharpe_low` are present.
- A3: confirm by smoke test:
  `from zangetsu.services.arena_rejection_taxonomy import classify;
   print(classify("reject_train_neg_pnl", "A1"))` — should NOT return
  `UNKNOWN_REJECT`.
- Out of scope for this subagent: the cumulative-vs-per-round `stats` defect is
  a separate (and more severe) bug that produces COUNTER_INCONSISTENCY even
  for already-mapped keys; raise as a sibling finding.

---

## 7. File:line index (for grep recovery)

| Concern | File | Lines |
|---|---|---|
| `stats` init (per worker, never reset) | arena_pipeline.py | 707-723 |
| Per-candidate reject increments | arena_pipeline.py | 975, 988, 1020, 1039, 1048, 1051, 1054, 1058, 1066 |
| Emit call site (per round) | arena_pipeline.py | 1255-1266 |
| Emit-from-stats body | arena_pipeline.py | 167-239 |
| COUNTER_INCONSISTENCY add | arena_pipeline.py | 231 |
| classify() fallback to UNKNOWN_REJECT | arena_rejection_taxonomy.py | 285-328 |
| RejectReasonCounter empty-default | arena_pass_rate_telemetry.py | 175-180 |
| ArenaBatchMetrics builder | arena_pass_rate_telemetry.py | 368-409 |
| reject_reason_distribution field | arena_pass_rate_telemetry.py | 236, 404 |

— end of trace —
