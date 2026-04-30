# 11 — Controlled Diff Report

**ORDER**: 0-9AB — Workstream C
**Mode**: GOVERNANCE / SOURCE-AND-TESTS DIFF

## Source-Mutation Checks

| Area | Expected | Observed | Verdict |
|---|---|---|---|
| alpha generation | no change | no change in zangetsu/services/* | PASS |
| mutation / crossover / search policy | no change | no change | PASS |
| Arena thresholds | no change | no change in zangetsu/services/arena_gates.py | PASS |
| A2_MIN_TRADES | remains 25 | 25 (verified arena_gates.py:48 + settings.py:29 + tests) | PASS |
| Arena pass / fail logic | no change | no change | PASS |
| champion promotion | no change | no change | PASS |
| deployable_count semantics | no change | no change (live VIEW returned 0 at run start) | PASS |
| capital / risk engine | no change | no change | PASS |
| production execution path | no change | no change | PASS |
| production DB schema | no DDL | none | PASS |
| production DB data mutation | none | only read-only SELECT against pipeline_state and zangetsu_status | PASS |
| CANARY | not started | not started | PASS |
| production rollout | not started | not started | PASS |
| live trading | none | none — no exchange API key requested or used | PASS |
| Binance trading-key usage | none | none | PASS |
| arena_pipeline.py imports core_factory | NEVER | not present (verified by test_core_factory_not_imported_by_production_pipeline) | PASS |

## File Scope (NEW additions only — no modifications to existing source)

zangetsu/core_factory/__init__.py
zangetsu/core_factory/constants.py
zangetsu/core_factory/axis_registry.py
zangetsu/core_factory/primitive_inventory.py
zangetsu/core_factory/combination_grammar.py
zangetsu/core_factory/candidate_manifest.py
zangetsu/core_factory/economic_arena_adapter.py
zangetsu/core_factory/rejection_feedback.py
zangetsu/core_factory/survivor_bank.py
zangetsu/core_factory/long_short_summary.py
zangetsu/core_factory/axis_scoreboard.py
zangetsu/core_factory/io.py
zangetsu/core_factory/shadow_batch_runner.py

zangetsu/tests/test_core_factory_axis_registry.py
zangetsu/tests/test_core_factory_primitive_inventory.py
zangetsu/tests/test_core_factory_combination_grammar.py
zangetsu/tests/test_core_factory_candidate_manifest.py
zangetsu/tests/test_core_factory_shadow_batch_runner.py
zangetsu/tests/test_core_factory_economic_arena_adapter.py
zangetsu/tests/test_core_factory_rejection_feedback.py
zangetsu/tests/test_core_factory_survivor_bank.py
zangetsu/tests/test_core_factory_long_short_summary.py
zangetsu/tests/test_core_factory_axis_scoreboard.py
zangetsu/tests/test_core_factory_invariants.py
zangetsu/tests/test_core_factory_thresholds_unchanged.py

zangetsu/docs/recovery/20260430-0-9ab-core-factory-multi-axis-shadow-tournament/00_state_lock.md
zangetsu/docs/recovery/20260430-0-9ab-core-factory-multi-axis-shadow-tournament/01_system_reset_confirmation.md
zangetsu/docs/recovery/20260430-0-9ab-core-factory-multi-axis-shadow-tournament/02_axis_tournament_design.md
zangetsu/docs/recovery/20260430-0-9ab-core-factory-multi-axis-shadow-tournament/03_core_factory_contract.md
zangetsu/docs/recovery/20260430-0-9ab-core-factory-multi-axis-shadow-tournament/04_candidate_generation_report.md
zangetsu/docs/recovery/20260430-0-9ab-core-factory-multi-axis-shadow-tournament/05_economic_arena_evaluation_report.md
zangetsu/docs/recovery/20260430-0-9ab-core-factory-multi-axis-shadow-tournament/06_long_short_report.md
zangetsu/docs/recovery/20260430-0-9ab-core-factory-multi-axis-shadow-tournament/07_reject_reason_report.md
zangetsu/docs/recovery/20260430-0-9ab-core-factory-multi-axis-shadow-tournament/08_survivor_near_survivor_report.md
zangetsu/docs/recovery/20260430-0-9ab-core-factory-multi-axis-shadow-tournament/09_feedback_weights_report.md
zangetsu/docs/recovery/20260430-0-9ab-core-factory-multi-axis-shadow-tournament/10_axis_scoreboard.md
zangetsu/docs/recovery/20260430-0-9ab-core-factory-multi-axis-shadow-tournament/11_controlled_diff_report.md
zangetsu/docs/recovery/20260430-0-9ab-core-factory-multi-axis-shadow-tournament/12_gemini_adversarial_review.md
zangetsu/docs/recovery/20260430-0-9ab-core-factory-multi-axis-shadow-tournament/13_final_report.md

zangetsu/docs/recovery/20260430-0-9ab-core-factory-multi-axis-shadow-tournament/shadow_outputs/* (8 machine artifacts)

## Working-Tree Byproducts NOT Included

The following dirty files exist in working tree from long-running services and are NOT staged for this PR:
- calcifer/maintenance.log
- calcifer/maintenance_last.json
- calcifer/report_state.json
- zangetsu/logs/engine.jsonl.1

## Tests Pass

`pytest zangetsu/tests/test_core_factory_*.py` → 32 passed in 45.31s.

## Verdict

CONTROLLED_DIFF = SOURCE_AND_TESTS_AND_EVIDENCE_AND_OUTPUTS_ONLY
FORBIDDEN_DIFF = 0
**CONTROLLED_DIFF_PASS**

## Acceptance Mapping

- AC21 PASS no production DB mutation
- AC33 PASS A2_MIN_TRADES = 25 unchanged
- AC34 PASS Arena thresholds unchanged
- AC35 PASS champion promotion unchanged
- AC36 PASS deployable_count semantics unchanged
- AC37 PASS execution / capital / risk unchanged
- AC38 PASS no live trading
- AC39 PASS no CANARY
- AC40 PASS no production rollout
- AC41 PASS controlled diff reports 0 forbidden mutation
- AC42 PASS tests pass (32 / 32)
