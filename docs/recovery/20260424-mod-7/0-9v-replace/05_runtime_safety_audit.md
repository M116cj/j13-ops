# 05 — Runtime Safety Audit

## 1. Audit context

Audit run against **Alaya pre-sync state** (`f5f62b2b` + dirty WIP). Diagnostic only.

## 2. Apply path inventory

```
$ grep -rn '^def apply_' zangetsu/services/
zangetsu/services/shared_utils.py:74:def apply_trailing_stop(...)
zangetsu/services/shared_utils.py:116:def apply_fixed_target(...)
zangetsu/services/shared_utils.py:141:def apply_tp_strategy(...)
```

Three pre-existing trading-helper functions (numpy signal-array
manipulation, NOT budget / sampling / generation apply paths). These
match the design pattern documented in PR #22's
`zangetsu/tools/sparse_canary_readiness_check.py::_grep_apply_def`
allow-list.

| Result | Value |
| --- | --- |
| `apply_*` budget / plan / consumer / allocator / canary / recommendation / weights / sampling / generation | **NONE** |
| Pre-existing trading helpers (apply_trailing_stop / apply_fixed_target / apply_tp_strategy) | UNCHANGED (documented exemption) |

## 3. APPLY mode flags

```
$ grep -rn 'mode=.*APPLY\|MODE_DRY_RUN' zangetsu/services/
zangetsu/services/generation_profile_metrics.py:40:MODE_DRY_RUN = "DRY_RUN"
zangetsu/services/feedback_decision_record.py:28:MODE_DRY_RUN = "DRY_RUN"
zangetsu/services/feedback_decision_record.py:80:    mode: str = MODE_DRY_RUN
zangetsu/services/feedback_decision_record.py:88:        self.mode = MODE_DRY_RUN
zangetsu/services/feedback_decision_record.py:110:    payload["mode"] = MODE_DRY_RUN
```

| Result | Value |
| --- | --- |
| Hard-coded `mode == "APPLY"` literal | **NONE** |
| Runtime-switchable APPLY flag (env var / config flag) | **NONE** |
| `MODE_DRY_RUN` constant | present (correct) |

Note: `MODE_DRY_RUN_CANARY` (introduced in PR #25) is NOT present on
Alaya yet, since `sparse_canary_observer.py` is missing. Once
fast-forward completes, `MODE_DRY_RUN_CANARY` will appear.

## 4. Consumer / allocator imports by runtime

```
$ grep -rn 'feedback_budget_consumer\|DryRunBudgetAllocation' zangetsu/services/
(empty)
```

`feedback_budget_consumer.py` and `feedback_budget_allocator.py` don't
exist on Alaya yet (shipped via PR #19 and PR #23). Once fast-forward
completes, the source-text isolation tests (PR #18 / PR #19 / PR #23 /
PR #25 suites) will verify they remain not-imported by runtime.

| Result | Value |
| --- | --- |
| Consumer imported by generation runtime | **NO** |
| Consumer output consumed by generation runtime | **NO** |
| Allocator imported by generation runtime | **NO** |

## 5. `A2_MIN_TRADES`

```
$ grep -rn 'bt.total_trades < 25' zangetsu/services/arena23_orchestrator.py
546: if bt.total_trades < 25:
664: if bt.total_trades < 25:
```

Both occurrences pinned at 25 (V10 path). Matches origin/main exactly
(verified by Mac-side `test_a2_min_trades_still_pinned` source-text
test).

| Result | Value |
| --- | --- |
| `A2_MIN_TRADES` literal occurrences | 2 (both = 25) |
| Threshold relaxation detected | **NO** |

## 6. Runtime mode (production)

| Field | Value |
| --- | --- |
| Production rollout | **NOT STARTED** |
| Live trading enabled | UNCHANGED (no broker / capital changes detected) |
| CANARY activation | **NOT STARTED** (consumer + observer not even on Alaya) |

## 7. Cross-PR safety inheritance

If/when fast-forward completes to `73b931d2`, the following safety
guarantees inherit from the merged PR chain:

- **PR #21 (0-9P)**: passport persistence is metadata-only; no apply
  path; `_safe_resolve_profile_identity` never raises.
- **PR #22 (0-9P-AUDIT)**: `profile_attribution_audit` is offline
  read-only; verdict thresholds (5%/1%/5% green; 20%/5%/20% yellow).
- **PR #23 (0-9R-IMPL-DRY)**: 3-layer dry-run invariant on
  `SparseCandidateDryRunPlan`; no apply method; gating chain blocks
  RED attribution.
- **PR #25 (0-9S-CANARY)**: 3-layer dry-run invariant on
  `SparseCanaryObservation`; gate chain CR1-CR15.
- **PR #27 (0-9S-CANARY-OBSERVE-COMPLETE)**: replay helper read-only;
  zero-round F-suppression honest behavior.

## 8. Conclusion

**Safety audit PASS** for the **pre-sync** state (Alaya runs old code with no apply path). Post-sync re-audit is required (and expected to PASS based on Mac validation).

| Field | Value |
| --- | --- |
| Apply path | NONE |
| Runtime-switchable APPLY mode | NONE |
| Consumer connected to generation runtime | NO |
| Consumer output consumed by generation runtime | NO |
| `A2_MIN_TRADES` | 25 |
| Production rollout | NOT STARTED |

**Phase E gate: PASS.**
