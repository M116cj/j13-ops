# 05 — Candidate Generation and Eligibility Audit

## 1. Are Candidates Being Generated In Memory?

YES — per /tmp/zangetsu_a1_w0..w3.log we see ENTRY lifecycle events emitted by `_emit_a1_lifecycle_safe` BEFORE any val gate checks:

```
{"alpha_id": "460b716d6fa08651", "arena_stage": "A1", "stage_event": "ENTRY", "status": "ENTERED", "source_pool": "XRPUSDT", ...}
{"alpha_id": "dbb507ef22bc99cc", ...}
{"alpha_id": "d5c9832849f769ae", ...}
... ~16 ENTRY events per cron cycle per worker ...
```

So A1 successfully constructs candidate objects in memory and emits the ENTRY signal. The `engine.compile_alpha` + `backtester.run` calls happen successfully (no compile-error exceptions logged).

## 2. Are Candidates Reaching the Val Gates?

This is the question the order asks. Empirical answer: **we cannot tell from the logs**, because the round-end stats summary at `arena_pipeline.py:1207` (`f"rejects: few_trades=... val_few=... val_neg_pnl=..."`) is **never reached** — the per-round batch metrics emit at line 1218 crashes BEFORE line 1207's stats line is logged… wait, actually line 1207 is BEFORE line 1218, so it should run. Let me re-check.

Looking at the code structure around lines 1207-1218:

```python
if round_number % 10 == 0:               # line 1206
    log.info(                             # line 1207
        f"R{round_number} | {sym}/{regime} | "
        f"champions={round_champions}/{len(alphas)} | {elapsed:.1f}s | "
        f"rejects: few_trades={stats['reject_few_trades']} ..."
    )

# P7-PR4-LITE: aggregate A1 batch pass-rate telemetry.
_emit_a1_batch_metrics_from_stats_safe(    # line 1218
    run_id=getattr(_pb, "run_id", "") or "",
    ...
)
```

The `if round_number % 10 == 0:` gate means the stats log only fires every 10 rounds. The batch-metrics emit at 1218 is **unconditional** (every round).

→ Even on rounds where `round_number % 10 != 0`, line 1218 still fires → `_pb` is still referenced → still crashes.

The first round that runs after the worker spawn is `round_number = 49451` (per the "Resumed from checkpoint: round=49450" log). 49451 % 10 = 1, so no stats line is logged on that first round. Then 1218 crashes.

→ **The crash happens on the FIRST round** after spawn, before any stats summary can ever appear in the log. That's why we never see `rejects: few_trades=N val_few=N` lines.

## 3. Hypotheses About What Filter All Candidates Hit

Without stats output, we can only infer. The most plausible cause based on indirect evidence:

| Filter | Likelihood | Evidence |
| --- | --- | --- |
| `bt.total_trades < 30` (train sparse) | HIGH | typical for cold-start regime classification with 4-symbol shards; 30-trade minimum on holdout split is strict |
| `bt_val.net_pnl <= 0` | MEDIUM | numpy overflow warnings in w2/w3 may corrupt val signals |
| `bt_val.sharpe_ratio < 0.3` | MEDIUM | strict 0.3 threshold (legitimate strategy gate) |
| `wilson_lower(val) < 0.52` | HIGH | very strict 52% threshold, hard to pass on small holdout sample |
| `bt_val.total_trades < 15` | HIGH | given 15-trade minimum on holdout (which is shorter than train) |

These filters are **strategy-design choices** (per v0.5.9 / Patch E comments in the source), not bugs. A separate `0-9X-VAL-FILTER-CALIBRATION` order could analyze whether they are too tight, but **that is out of scope**. The order's hard ban includes "Do NOT weaken Arena thresholds".

## 4. Phase 5 Classification

Per order §10:

| Verdict | Match? |
| --- | --- |
| CANDIDATES_GENERATED_FILTERED_ALL (generated but all fail eligibility before INSERT) | partial — likely true but unobservable due to crash blocking the stats output |
| CANDIDATES_NOT_GENERATED | NO (ENTRY events confirm generation) |
| CANDIDATES_DUPLICATE_SUPPRESSED | unlikely (Bloom filter only has 89 entries; not enough to dedup all) |
| CANDIDATES_INVALID_NUMERIC | possible (numpy overflow in w2/w3 — see 06) |
| CANDIDATES_INSUFFICIENT_DATA | unlikely (data caches build successfully with 14 symbols, 110 indicators each) |
| CANDIDATES_QUEUE_EMPTY | NO (`alphas` list is non-empty per ENTRY events) |
| CANDIDATES_SOURCE_DISABLED | NO |
| **CANDIDATES_UNKNOWN** | **YES — closest honest match** (we can confirm candidates ARE generated but cannot confirm where they get filtered, because the stats log is not reached due to the line-1218 crash) |

→ **Phase 5 verdict: CANDIDATES_UNKNOWN** (with leading hypothesis CANDIDATES_GENERATED_FILTERED_ALL — confirmable only after the line-1218 crash is fixed).
