# 09 — Truthfulness and Empty-State Report

**ORDER**: 0-9AF — Phase 6

## Truthfulness Rules Enforced

| Rule | Where enforced | How verified |
|---|---|---|
| No fake zero | `overview.py` returns None (not 0) when run_summary missing; pages render `'NO DATA'` for None | `tests/dashboard/test_no_fake_zero.py::test_no_data_distinct_from_zero` |
| NOT_EVALUATED separate from REJECTED | `arenas.py` builds `n_not_evaluated` from `status == 'NOT_EVALUATED'` and `n_rejected` from `status == 'REJECTED'` independently | `test_no_fake_zero.py::test_not_evaluated_separate_from_rejected_in_a2` |
| Survivor strictly distinct from near-survivor | `survivors.py` uses two distinct artifacts (survivor_report.csv vs near_survivor_report.csv); page renders two separated tables | `test_view_models.py::test_survivors_distinct_from_near` |
| NOT_EVALUATED never marked survivor / near-survivor | `survivor_bank.is_survivor` requires `status == 'PASSED'`; `is_near_survivor` requires `status == 'REJECTED'` AND -5 ≤ net ≤ 0 | `test_no_fake_zero.py::test_not_evaluated_not_in_survivors` |
| A3 NOT_AVAILABLE explicit | `arenas.build_a3` always returns `state='NOT_AVAILABLE'` because shadow orders never run A3 | `test_view_models.py::test_build_a1_a2_a3` |
| MISSING freshness explicit | `runtime_health.freshness_for` returns `state='MISSING'` for non-existent files (never `age=0`) | `test_freshness_logic.py::test_missing_file` |
| ERROR freshness explicit | parse / stat exceptions surface as `state='ERROR'` with `note` | `parsers.parse_jsonl`, `runtime_health.freshness_for` |
| feedback weights honest | `rejection_feedback.feedback_weights_from_summary` returns `status='EMPTY_WITH_REASON'` if no rejections; never fakes | `test_core_factory_rejection_feedback.py::test_no_rejections_yields_empty_with_reason` |
| Survivor != Deployable | All pages explicitly note `zangetsu_status.deployable_count` is unaffected by survivor count | landing page + survivors page captions; verified live: VIEW returns 0 |

## Empty-State Coverage Per Page

| Page | Empty/missing render |
|---|---|
| Overview | `'NO DATA'` for absent KPIs; warning banner if state != OK |
| Core Factory | warning banner if manifest missing; charts with no-data title if value mix is empty |
| A1 / A2 | warning if shadow_batch_results missing; per-symbol table empty if no symbol field |
| A3 | NOT_AVAILABLE banner; never renders 0/0 |
| Candidates | warning if results missing; filter row count visible |
| Survivors | info banner per table when empty |
| Rejects | info banner if no rejected rows |
| Feedback | warning if both feedback_weights and next_batch_weights missing; renders 'NO DATA' status if blocked |
| System Health | per-source table always renders; summary banner conditional |

## Test Coverage Summary

`pytest zangetsu/tests/dashboard/` → 22 / 22 PASSED in 0.29 s.

Tests cover: parser states, freshness states, view-model contract, no-fake-zero rule, NOT_EVALUATED separation, survivor separation, contract checks (no arena_pipeline import, no shadow_batch_runner import).
