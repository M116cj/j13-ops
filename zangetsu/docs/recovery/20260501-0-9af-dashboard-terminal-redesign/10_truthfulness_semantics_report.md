# 10 — Truthfulness Semantics Report

**ORDER**: 0-9AF-REDESIGN — Phase 6

## Rules Enforced

| Rule | Mechanism | Verified by |
|---|---|---|
| No fake zero | view_models return `None` (not 0) when source missing; theme distinguishes `'NO DATA'` / `'MISSING'` / `'NOT_REACHED'` from numeric 0 with gray badges | V1 test_no_fake_zero.py (still passing); arena_funnel A3/A4/A5 row hard-coded to NOT_REACHED |
| NOT_EVALUATED ≠ REJECTED | arenas.build_a2 builds `n_not_evaluated` and `n_rejected` from independent status filters; KPI strip and bottom Rejects tab render them in different cards / charts | V1 test_no_fake_zero.py::test_not_evaluated_separate_from_rejected_in_a2 |
| SURVIVOR ≠ NEAR_SURVIVOR | survivors tab renders TWO separate tables (PASSED above, REJECTED-with-net-in-band below) from two distinct artifacts | V1 test_view_models.py::test_survivors_distinct_from_near |
| NOT_EVALUATED never SURVIVOR | survivor_bank.is_survivor requires `status == 'PASSED'` | V1 test_no_fake_zero.py::test_not_evaluated_not_in_survivors |
| PASSED ≠ DEPLOYABLE | Top status bar shows zangetsu_status.deployable_count via System Health tab (currently 0, unchanged); drawer never claims a survivor is deployable | live VIEW query post-merge: `deployable_count = 0` |
| BLOCKED ≠ FAILED | Service freshness states (FRESH / STALE / OLD / MISSING / ERROR) are 5 distinct badges; no panel collapses them | top_status_bar uses badge color mapping |

## Per-Panel Empty-State Rendering

| Panel | When data missing | Rendered as |
|---|---|---|
| Top status bar | run_summary missing | 'NO DATA' / 'NO BATCH' / gray badges |
| KPI strip | candidates_total None | 'NO DATA' string + zt-na class |
| Arena funnel | shadow_batch_results missing | A3/A4/A5 row always shows NOT_REACHED |
| Reject depth | rs_summary empty | gray-mono 'NO DATA' line |
| Sidebar | no recovery folders | gray 'NO BATCH' caption |
| Drawer | no candidate selected | gray 'select candidate_id' caption |
| Candidates tab | results missing | 'NO DATA' line |
| Rejects tab | no rejected rows | 'NO REJECTED CANDIDATES' info |
| Survivors tab | survivor_report missing | per-table 'no survivors' / 'no near-survivors' |
| Feedback tab | no feedback artifacts | 'NO DATA' info |
| Health tab | always renders the per-source state table | (the table itself surfaces MISSING / ERROR per source) |

## A3 Treatment

A3 = `NOT_AVAILABLE` (V1) / `NOT_REACHED` (V2 wording in funnel). Hard-coded in arena_funnel.py because shadow orders never run `services.arena_gates.arena3_pass`. This is a product-correctness signal, not a data issue (Gemini V1 had flagged this; adjudicated as intended in 0-9AF V1 14_gemini_adversarial_review.md and again here).

## Gemini V2 UX Review

`PASS` (gemini-2.5-flash, env-loaded key, never echoed):
> "The dashboard described has real-time freshness indicators, interactive filtering, detailed operational metrics, and system health monitoring, all characteristic of an observability dashboard rather than a static report."

The first attempt returned a meta FAIL due to Gemini's codebase-investigation tool quota exhaustion (not a substantive UX FAIL). Retried with a self-contained prompt → PASS.
