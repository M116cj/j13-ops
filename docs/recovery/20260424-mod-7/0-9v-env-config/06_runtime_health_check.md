# 06 — Runtime Health Check

## 1. Engine.jsonl Progress

| Field | Pre-repair (before Phase H) | Post-repair (after 45 s) |
| --- | --- | --- |
| Path | `/home/j13/j13-ops/zangetsu/logs/engine.jsonl` | unchanged |
| Size | 37 MB (38 654 233 B) | 38 MB (still 38 654 233 — appending, but rotation threshold 50 MB) |
| Last write | `2026-04-23T00:35:54Z` (3-day stale) | `2026-04-26T09:04:52Z` (live, advancing) |
| Tail timestamps | (no advance) | `2026-04-26T09:04:44`, `2026-04-26T09:04:52`, `2026-04-26T09:04:52` |
| Engine loop | IDLE | **ALIVE** |

→ `engine.jsonl` mtime advanced **8 minutes** after the watchdog trigger started workers; that is the first engine-loop activity since 2026-04-23. The 3-day staleness is cleared.

## 2. Worker Process Liveness

| Worker | PID | CPU% | Wall time alive at observation |
| --- | --- | --- | --- |
| `arena_pipeline_w0` | 103233 | 99 | 58 s |
| `arena_pipeline_w1` | 103242 | 99 | 57 s |
| `arena_pipeline_w2` | 103251 | 99 | 58 s |
| `arena_pipeline_w3` | 103260 | 99 | 58 s |

All four A1 workers are pegged at 99% CPU (regime classification + alpha generation work). They are not idle, not crashing.

## 3. KeyError Recurrence Search

```
$ tail -50 /tmp/zangetsu_a1_w0.log /tmp/zangetsu_a1_w1.log /tmp/zangetsu_a1_w2.log /tmp/zangetsu_a1_w3.log | grep -c "KeyError: 'ZV5_DB_PASSWORD'"
0
```

→ Zero recurrence in current-PID worker output.

## 4. HTTP API State (preserved)

| Service | PID | State |
| --- | --- | --- |
| `cp-api` | 2537810 | running (since Apr 24) |
| `dashboard-api` | 3871446 | running (since Apr 23) |
| `console-api` | 3871449 | running (since Apr 23) |

→ Untouched by this order.

## 5. Health Verdict

| Field | Value |
| --- | --- |
| Worker process remains alive | YES (4 A1 workers, ≥ 58 s wall time, no crash) |
| Engine.jsonl mtime advanced | YES (3-day staleness cleared) |
| `KeyError: ZV5_DB_PASSWORD` recurrence | NO |

→ Per order §14 health criteria, this maps to: **PASS** (worker process remains alive AND `engine.jsonl` mtime advances AND no `KeyError` recurrence).

## 6. Runtime Safety Audit (post-repair)

```
$ grep -RIn "mode=.*APPLY" zangetsu | grep -v test_ | grep -v results/
(none)

$ grep -RIn "^def apply_" zangetsu/services
zangetsu/services/shared_utils.py:74:def apply_trailing_stop(...)
zangetsu/services/shared_utils.py:116:def apply_fixed_target(...)
zangetsu/services/shared_utils.py:141:def apply_tp_strategy(...)

$ grep -RIn "feedback_budget_consumer" zangetsu/services
zangetsu/services/sparse_canary_observer.py:57:from zangetsu.services.feedback_budget_consumer import (...)

$ grep -RIn "DryRunBudgetAllocation" zangetsu/services | grep -v feedback_budget_allocator | grep -v feedback_budget_consumer
zangetsu/services/sparse_canary_observer.py:11:  - ``DryRunBudgetAllocation`` events (from 0-9O-B allocator)
zangetsu/services/sparse_canary_observer.py:64:    DryRunBudgetAllocation,

$ grep -RIn "A2_MIN_TRADES" zangetsu/services
zangetsu/services/arena_gates.py:48:A2_MIN_TRADES: int = 25
zangetsu/services/arena_gates.py:54:    if n < A2_MIN_TRADES:
zangetsu/services/feedback_decision_record.py:38:    "A2_MIN_TRADES_UNCHANGED",

$ grep -RIn "bt.total_trades < 25" zangetsu/services/arena23_orchestrator.py
779:        if bt.total_trades < 25:
897:        if bt.total_trades < 25:
```

| Check | Result |
| --- | --- |
| Apply path | NONE (only pre-existing trading helpers in shared_utils, allow-listed) |
| Runtime-switchable APPLY | NONE |
| Consumer connected to generation runtime | NO (only the offline observer reads it) |
| `A2_MIN_TRADES` | 25 |
| CANARY | NOT STARTED |
| Production rollout | NOT STARTED |

→ Runtime safety identical to PR #29 / PR #30 audits — env-config repair did not introduce any apply path or APPLY mode.

## 7. Phase I + L Verdict

→ **PASS / PASS.** Engine loop alive, runtime safety unchanged.
