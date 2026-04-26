# 03 — Runtime Safety Audit (post-CLEAN, at SHA 41796663)

## 1. Audit Context

| Field | Value |
| --- | --- |
| Audit timestamp (UTC) | `2026-04-26T08:25:20Z` |
| HEAD | `41796663ccc7cc6b7b66e5d92bc941de6c92c442` |
| Mode of audit | Static-grep against checked-out source. No runtime modification. |

## 2. Apply Path Inventory

```
$ grep -RIn "^def apply_" zangetsu/services
zangetsu/services/shared_utils.py:74:def apply_trailing_stop(...)
zangetsu/services/shared_utils.py:116:def apply_fixed_target(...)
zangetsu/services/shared_utils.py:141:def apply_tp_strategy(...)
```

Only the three pre-existing trading helpers (numpy signal-array manipulation). These match the PR #22 readiness check allow-list.

| Result | Value |
| --- | --- |
| `apply_*` budget / plan / consumer / allocator / canary / recommendation / weights / sampling / generation | **NONE** |
| Pre-existing trading helpers (apply_trailing_stop / apply_fixed_target / apply_tp_strategy) | UNCHANGED (allow-listed) |

## 3. APPLY Mode Flags

```
$ grep -RIn "mode=.*APPLY" zangetsu | grep -v test_ | grep -v results/
(none)
```

```
$ grep -RIn "applied=True" zangetsu/services
zangetsu/services/feedback_decision_record.py:10:The builder rejects any attempt to set ``applied=True``
zangetsu/services/feedback_decision_record.py:135:    Any attempt to pass ``applied=True`` or ``mode="APPLIED"`` via
zangetsu/services/feedback_budget_consumer.py:49: ... like applied=True input ...
zangetsu/services/feedback_budget_consumer.py:538: ... mode != DRY_RUN, applied=True, wrong consumer_version ...
```

All non-test occurrences are governance **rejection probes** (the builder rejects any caller attempting to set `applied=True`). They guard against APPLY rather than constituting an APPLY path.

| Result | Value |
| --- | --- |
| Hard-coded `mode == "APPLY"` literal in services | **NONE** |
| Runtime-switchable APPLY flag (env var / config flag) | **NONE** |
| `MODE_DRY_RUN` constant | present |
| `MODE_DRY_RUN_CANARY` constant (PR #25) | present |

## 4. Generation-Runtime Import Isolation

### 4.1 `arena_pipeline.py` (A1 generator)

```
$ grep -E "feedback_budget|sparse_canary_observer" zangetsu/services/arena_pipeline.py
(none)
```

→ Clean. A1 generation pipeline does NOT import any feedback / consumer / observer module.

### 4.2 `arena23_orchestrator.py` (A2/A3 orchestrator)

```
$ grep -E "feedback_budget|feedback_decision_record|sparse_canary" zangetsu/services/arena23_orchestrator.py
(none)
```

→ Clean.

### 4.3 `arena45_orchestrator.py` (A4/A5 orchestrator)

```
$ grep -E "feedback_budget|feedback_decision_record|sparse_canary" zangetsu/services/arena45_orchestrator.py
(none)
```

→ Clean.

### 4.4 What does import `feedback_budget_consumer` / `DryRunBudgetAllocation`?

```
$ grep -RIn "feedback_budget_consumer" zangetsu/services
zangetsu/services/sparse_canary_observer.py:57:from zangetsu.services.feedback_budget_consumer import (...)

$ grep -RIn "DryRunBudgetAllocation" zangetsu/services | grep -v feedback_budget
zangetsu/services/sparse_canary_observer.py:11:  - ``DryRunBudgetAllocation`` events (from 0-9O-B allocator)
zangetsu/services/sparse_canary_observer.py:64:    DryRunBudgetAllocation,
```

Only the **observer** (`sparse_canary_observer.py`) reads these symbols, and only as **read-only inputs**. The observer is not invoked by any of the three generation runtimes.

| Result | Value |
| --- | --- |
| `feedback_budget_consumer` imported by A1 / A2/A3 / A4/A5 runtime | **NO** |
| `feedback_budget_allocator` imported by A1 / A2/A3 / A4/A5 runtime | **NO** |
| Consumer output consumed by generation runtime | **NO** |
| Observer (`sparse_canary_observer`) — read-only / diagnostic only | YES (allowed; not in apply path) |

## 5. `A2_MIN_TRADES`

```
$ grep -RIn "bt.total_trades < 25" zangetsu/services/arena23_orchestrator.py
779:        if bt.total_trades < 25:
897:        if bt.total_trades < 25:
```

```
$ grep -RIn "A2_MIN_TRADES" zangetsu/services
zangetsu/services/arena_gates.py:48:A2_MIN_TRADES: int = 25
zangetsu/services/arena_gates.py:54:    if n < A2_MIN_TRADES:
zangetsu/services/feedback_decision_record.py:38:    "A2_MIN_TRADES_UNCHANGED",
```

```
$ grep -n ARENA2_MIN_TRADES zangetsu/config/settings.py
29:ARENA2_MIN_TRADES: int = 25
168:    arena2_min_trades: int = ARENA2_MIN_TRADES
```

| Result | Value |
| --- | --- |
| `A2_MIN_TRADES` source | `arena_gates.py:48 = 25` |
| `arena23_orchestrator.py` literal occurrences | 2 (both = 25) |
| `zangetsu/config/settings.py` `ARENA2_MIN_TRADES` | 25 |
| Threshold relaxation detected | **NO** |

## 6. Production / CANARY State

| Field | Value |
| --- | --- |
| Production rollout | **NOT STARTED** |
| Live trading enabled | UNCHANGED |
| CANARY activation | **NOT STARTED** (observer present but not running) |
| `MODE_DRY_RUN_CANARY` constant | present (PR #25) |

## 7. Conclusion

| Field | Value |
| --- | --- |
| Apply path | NONE |
| Runtime-switchable APPLY mode | NONE |
| Consumer connected to generation runtime | NO |
| Consumer output consumed by generation runtime | NO |
| Observer connected to generation runtime | NO (read-only diagnostic only) |
| `A2_MIN_TRADES` | 25 |
| Production rollout | NOT STARTED |
| CANARY | NOT STARTED |

→ **Phase C PASS.** No `BLOCKED_SAFETY_FAILURE`.
