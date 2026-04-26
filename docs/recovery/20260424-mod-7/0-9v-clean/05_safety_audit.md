# 05 — Runtime Safety Audit (post-cleanup, post-sync)

## 1. Audit Context

Audit run on Alaya at SHA `5ab95bfecadc41d61c5293fe5fe17e6d874b4176` (post-cleanup, post-fast-forward to latest origin/main). Diagnostic only. No runtime modification.

## 2. Apply Path Inventory

```
$ grep -RIn "^def apply_" zangetsu/services
zangetsu/services/shared_utils.py:74:def apply_trailing_stop(signals, close, trail_pct)
zangetsu/services/shared_utils.py:116:def apply_fixed_target(signals, close, target_pct)
zangetsu/services/shared_utils.py:141:def apply_tp_strategy(signals, close, tp_type, tp_param)
```

Three pre-existing trading-helper functions (numpy signal-array manipulation, NOT budget / sampling / generation apply paths). These match the design pattern documented in PR #22 `zangetsu/tools/sparse_canary_readiness_check.py::_grep_apply_def` allow-list.

| Result | Value |
| --- | --- |
| `apply_*` budget / plan / consumer / allocator / canary / recommendation / weights / sampling / generation | **NONE** |
| Pre-existing trading helpers (apply_trailing_stop / apply_fixed_target / apply_tp_strategy) | UNCHANGED (documented exemption) |

## 3. APPLY Mode Flags

```
$ grep -RIn "mode=.*APPLY" zangetsu
(none)
```

```
$ grep -RIn "applied=True" zangetsu | grep -v test_ | grep -v results/
zangetsu/services/feedback_decision_record.py:10:The builder rejects any attempt to set ``applied=True``
zangetsu/services/feedback_decision_record.py:135:    Any attempt to pass ``applied=True`` or ``mode="APPLIED"`` via
zangetsu/services/feedback_budget_consumer.py:49: ... like applied=True input ...
zangetsu/services/feedback_budget_consumer.py:538: ... mode != DRY_RUN, applied=True, wrong consumer_version ...
```

All non-test occurrences are **governance rejection probes** (the builder rejects any caller attempting to set `applied=True`). They are guards against apply, not apply paths themselves.

| Result | Value |
| --- | --- |
| Hard-coded `mode == "APPLY"` literal in services | **NONE** |
| Runtime-switchable APPLY flag (env var / config flag) | **NONE** |
| `MODE_DRY_RUN` constant | present (correct) |
| `MODE_DRY_RUN_CANARY` constant (PR #25) | present (correct) |

## 4. Consumer / Allocator Imports by Runtime

```
$ grep -RIn "feedback_budget_consumer" zangetsu/services
zangetsu/services/sparse_canary_observer.py:57:from zangetsu.services.feedback_budget_consumer import (...)
```

Only `sparse_canary_observer.py` imports `feedback_budget_consumer`. The observer is a **read-only diagnostic reader** of feedback events; it is NOT imported by `arena_pipeline`, `arena23_orchestrator`, or `arena45_orchestrator`. The observer's output is not consumed by the generation runtime.

```
$ grep -RIn "DryRunBudgetAllocation" zangetsu/services | grep -v feedback_budget_allocator | grep -v feedback_budget_consumer
zangetsu/services/sparse_canary_observer.py:11:  - ``DryRunBudgetAllocation`` events (from 0-9O-B allocator)
zangetsu/services/sparse_canary_observer.py:64:    DryRunBudgetAllocation,
```

Same: only the observer references `DryRunBudgetAllocation`, and only as an observation input — never as a runtime feedback signal.

| Result | Value |
| --- | --- |
| `feedback_budget_consumer` imported by generation runtime | **NO** |
| `feedback_budget_allocator` imported by generation runtime | **NO** |
| Consumer output consumed by generation runtime | **NO** |
| Observer (`sparse_canary_observer`) — read-only / diagnostic | **YES** (allowed; not in apply path) |

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
29:ARENA2_MIN_TRADES: int = 25  # Patch H1 2026-04-20: aligned from 30→25
```

| Result | Value |
| --- | --- |
| `A2_MIN_TRADES` source | `zangetsu/services/arena_gates.py:48 = 25` |
| `arena23_orchestrator.py` literal occurrences | 2 (both = 25) at lines 779 + 897 |
| `zangetsu/config/settings.py` `ARENA2_MIN_TRADES` | 25 |
| `feedback_decision_record.py` invariance marker | `"A2_MIN_TRADES_UNCHANGED"` constant present |
| Threshold relaxation detected | **NO** |

## 6. Runtime Mode (Production)

| Field | Value |
| --- | --- |
| Production rollout | **NOT STARTED** |
| Live trading enabled | UNCHANGED (no broker / capital changes detected) |
| CANARY activation | **NOT STARTED** (observer present but not running) |

## 7. Cross-PR Safety Inheritance (now landed on Alaya)

The fast-forward range carries the following safety guarantees:

- **PR #18 (P7-PR4B)**: `arena_batch_metrics` is trace-only — no apply path, decision-loop never reads emitter output.
- **PR #19 (0-9O-B)**: `feedback_budget_allocator` produces dry-run plans only; no apply method.
- **PR #21 (0-9P)**: passport persistence is metadata-only; `_safe_resolve_profile_identity` never raises.
- **PR #22 (0-9P-AUDIT)**: `profile_attribution_audit` is offline read-only.
- **PR #23 (0-9R-IMPL-DRY)**: 3-layer dry-run invariant on `SparseCandidateDryRunPlan`; gating chain blocks RED attribution.
- **PR #25 (0-9S-CANARY)**: 3-layer dry-run invariant on `SparseCanaryObservation`; gate chain CR1-CR15.
- **PR #27 (0-9S-CANARY-OBSERVE-COMPLETE)**: replay helper read-only; zero-round F-suppression honest behavior.
- **PR #28 (0-9V-REPLACE)**: BLOCKED_DIRTY_STATE evidence (this order resolves it).

## 8. Conclusion

| Field | Value |
| --- | --- |
| Apply path | NONE |
| Runtime-switchable APPLY mode | NONE |
| Consumer connected to generation runtime | NO |
| Consumer output consumed by generation runtime | NO |
| `A2_MIN_TRADES` | 25 |
| Production rollout | NOT STARTED |
| CANARY | NOT STARTED |

→ **Phase G PASS.** No `BLOCKED_SAFETY_FAILURE`.
